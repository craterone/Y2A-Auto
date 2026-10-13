#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
YouTube Playlist 监控模块
支持配置检测周期（默认30分钟）、最大并发任务数控制，
利用 YouTube Data API v3 轮询播放列表并自动创建投稿任务。
"""

import os
import re
import sqlite3
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from modules.task_manager import add_task, get_db_connection, DB_PATH
from modules.config_manager import load_config
from modules.youtube_monitor import youtube_monitor

logger = logging.getLogger('Y2A-Auto.PlaylistMonitor')
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - Playlist监控 - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)


def extract_playlist_id(url_or_id: str) -> Optional[str]:
    """
    从用户输入的字符串中提取 YouTube Playlist ID。
    支持完整 URL（如 https://www.youtube.com/playlist?list=PL...）或纯 ID。
    """
    if not url_or_id:
        return None
    val = str(url_or_id).strip()
    match = re.search(r'[?&]list=([a-zA-Z0-9_-]+)', val)
    if match:
        return match.group(1)
    
    # 匹配纯 ID (通常为 PL/UU/LL/FL 开头或包含英文字母数字下划线)
    if re.match(r'^[a-zA-Z0-9_-]{8,64}$', val):
        return val
    return None


class PlaylistMonitorManager:
    """Playlist 监控管理器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(daemon=True)
        self._scheduler_running = False
        self._check_lock = threading.Lock()
        self._active_check_monitors = set()
        self._init_db()

    def _init_db(self):
        """初始化播放列表监控相关表"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # 监控配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlist_monitors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id TEXT NOT NULL UNIQUE,
                    title TEXT,
                    description TEXT,
                    channel_title TEXT,
                    thumbnail_url TEXT,
                    check_interval_minutes INTEGER DEFAULT 30,
                    max_concurrency INTEGER DEFAULT 1,
                    upload_target TEXT DEFAULT 'bilibili',
                    auto_upload BOOLEAN DEFAULT 1,
                    custom_description TEXT,
                    bilibili_season_id INTEGER,
                    bilibili_section_id INTEGER,
                    bilibili_season_title TEXT,
                    task_interval_minutes INTEGER DEFAULT 30,
                    max_import_per_check INTEGER DEFAULT 10,
                    import_order TEXT DEFAULT 'asc',
                    last_task_completed_at TIMESTAMP,
                    enabled BOOLEAN DEFAULT 1,
                    last_checked_at TIMESTAMP,
                    last_check_status TEXT,
                    last_check_message TEXT,
                    total_videos_found INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 监控历史表（去重防重复入库）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS playlist_monitor_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    monitor_id INTEGER NOT NULL,
                    video_id TEXT NOT NULL,
                    video_title TEXT,
                    published_at TEXT,
                    task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(monitor_id, video_id),
                    FOREIGN KEY(monitor_id) REFERENCES playlist_monitors(id) ON DELETE CASCADE
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pmh_monitor_video ON playlist_monitor_history(monitor_id, video_id)')

            # 表结构平滑升级检查
            cursor.execute("PRAGMA table_info(playlist_monitors)")
            existing_columns = {row[1] for row in cursor.fetchall()}
            if 'auto_upload' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN auto_upload BOOLEAN DEFAULT 1")
                logger.info("数据库升级：playlist_monitors 添加 auto_upload 字段")
            if 'custom_description' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN custom_description TEXT")
                logger.info("数据库升级：playlist_monitors 添加 custom_description 字段")
            if 'bilibili_season_id' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN bilibili_season_id INTEGER")
                logger.info("数据库升级：playlist_monitors 添加 bilibili_season_id 字段")
            if 'bilibili_section_id' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN bilibili_section_id INTEGER")
                logger.info("数据库升级：playlist_monitors 添加 bilibili_section_id 字段")
            if 'bilibili_season_title' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN bilibili_season_title TEXT")
                logger.info("数据库升级：playlist_monitors 添加 bilibili_season_title 字段")
            if 'task_interval_minutes' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN task_interval_minutes INTEGER DEFAULT 30")
                logger.info("数据库升级：playlist_monitors 添加 task_interval_minutes 字段")
            if 'max_import_per_check' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN max_import_per_check INTEGER DEFAULT 10")
                logger.info("数据库升级：playlist_monitors 添加 max_import_per_check 字段")
            if 'import_order' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN import_order TEXT DEFAULT 'asc'")
                logger.info("数据库升级：playlist_monitors 添加 import_order 字段")
            if 'last_task_completed_at' not in existing_columns:
                cursor.execute("ALTER TABLE playlist_monitors ADD COLUMN last_task_completed_at TIMESTAMP")
                logger.info("数据库升级：playlist_monitors 添加 last_task_completed_at 字段")
            cursor.execute("UPDATE playlist_monitors SET upload_target = 'bilibili' WHERE upload_target = 'acfun' OR upload_target IS NULL")

            conn.commit()
            logger.info("Playlist 监控表结构初始化完成")
        except Exception as e:
            logger.error(f"初始化 Playlist 监控数据表失败: {str(e)}")
        finally:
            conn.close()

    def _get_youtube_client(self):
        """获取已初始化的 YouTube API Client"""
        if youtube_monitor.youtube:
            return youtube_monitor.youtube
        cfg = load_config()
        ok, _ = youtube_monitor.reload_api_client(cfg)
        if ok and youtube_monitor.youtube:
            return youtube_monitor.youtube
        return None

    def fetch_playlist_details(self, playlist_id: str) -> Dict[str, Any]:
        """
        通过 YouTube Data API v3 查询播放列表信息
        """
        client = self._get_youtube_client()
        if not client:
            raise RuntimeError("YouTube API 客户端未就绪，请在设置中配置有效 API Key 及代理")

        req = client.playlists().list(
            part='snippet,contentDetails',
            id=playlist_id,
            maxResults=1
        )
        resp = youtube_monitor._execute_with_retry(req, f'playlists.list ({playlist_id})')
        items = resp.get('items', [])
        if not items:
            raise ValueError(f"未能找到播放列表: {playlist_id}，请检查 ID 是否有效或是否设为私享")

        item = items[0]
        snippet = item.get('snippet', {})
        content_details = item.get('contentDetails', {})
        thumbnails = snippet.get('thumbnails', {})
        thumb_url = (
            thumbnails.get('maxres', {}).get('url') or
            thumbnails.get('high', {}).get('url') or
            thumbnails.get('medium', {}).get('url') or
            thumbnails.get('default', {}).get('url') or ''
        )

        return {
            'playlist_id': playlist_id,
            'title': snippet.get('title', '未知播放列表'),
            'description': snippet.get('description', ''),
            'channel_title': snippet.get('channelTitle', ''),
            'thumbnail_url': thumb_url,
            'item_count': content_details.get('itemCount', 0),
        }

    def create_monitor(
        self,
        playlist_id_input: str,
        check_interval_minutes: int = 30,
        max_concurrency: int = 1,
        upload_target: str = 'bilibili',
        enabled: bool = True,
        custom_title: Optional[str] = None,
        auto_upload: bool = True,
        custom_description: Optional[str] = None,
        bilibili_season_id: Optional[int] = None,
        bilibili_section_id: Optional[int] = None,
        bilibili_season_title: Optional[str] = None,
        task_interval_minutes: int = 30,
        max_import_per_check: int = 10,
        import_order: str = 'asc'
    ) -> Dict[str, Any]:
        """
        创建新的 Playlist 监控
        """
        clean_playlist_id = extract_playlist_id(playlist_id_input)
        if not clean_playlist_id:
            raise ValueError("无效的播放列表链接或 ID")

        # 检查是否已存在
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM playlist_monitors WHERE playlist_id = ?', (clean_playlist_id,))
            existing = cursor.fetchone()
            if existing:
                raise ValueError(f"播放列表 {clean_playlist_id} 已经在监控列表中，无需重复添加")
        finally:
            conn.close()

        # 尝试拉取 YouTube 元数据
        title = custom_title or f"播放列表 {clean_playlist_id}"
        description = ""
        channel_title = ""
        thumbnail_url = ""
        try:
            details = self.fetch_playlist_details(clean_playlist_id)
            title = custom_title or details.get('title') or title
            description = details.get('description', '')
            channel_title = details.get('channel_title', '')
            thumbnail_url = details.get('thumbnail_url', '')
        except Exception as e:
            logger.warning(f"获取播放列表元信息失败，将使用默认信息创建: {str(e)}")

        interval = max(5, int(check_interval_minutes or 30))
        concurrency = max(1, int(max_concurrency or 1))
        # 固定默认投稿平台为 bilibili
        target = 'bilibili'
        is_auto_upload = 1 if auto_upload else 0
        clean_custom_desc = (custom_description or '').strip()
        safe_season_id = int(bilibili_season_id) if bilibili_season_id else None
        safe_section_id = int(bilibili_section_id) if bilibili_section_id else None
        safe_season_title = str(bilibili_season_title).strip() if bilibili_season_title else None
        safe_task_interval = max(0, int(task_interval_minutes if task_interval_minutes is not None else 30))
        safe_max_import = max(0, int(max_import_per_check if max_import_per_check is not None else 10))
        safe_import_order = 'desc' if str(import_order or '').lower() == 'desc' else 'asc'

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO playlist_monitors (
                    playlist_id, title, description, channel_title, thumbnail_url,
                    check_interval_minutes, max_concurrency, upload_target, enabled,
                    auto_upload, custom_description, bilibili_season_id, bilibili_section_id,
                    bilibili_season_title, task_interval_minutes, max_import_per_check,
                    import_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (clean_playlist_id, title, description, channel_title, thumbnail_url,
                  interval, concurrency, target, 1 if enabled else 0,
                  is_auto_upload, clean_custom_desc, safe_season_id, safe_section_id,
                  safe_season_title, safe_task_interval, safe_max_import, safe_import_order))
            monitor_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

        # 注册定时调度
        if enabled:
            self._register_job(monitor_id, interval)

        # 异步立即执行一次检测
        threading.Thread(target=self._run_check_async, args=(monitor_id,), daemon=True).start()

        return self.get_monitor(monitor_id)

    def get_monitor(self, monitor_id: int) -> Optional[Dict[str, Any]]:
        """获取单个监控配置及统计"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM playlist_monitors WHERE id = ?', (monitor_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data['task_stats'] = self._get_monitor_task_stats(conn, monitor_id, data['playlist_id'])
            return data
        finally:
            conn.close()

    def get_monitors(self) -> List[Dict[str, Any]]:
        """获取所有监控配置列表及实时统计"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM playlist_monitors ORDER BY id DESC')
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item['task_stats'] = self._get_monitor_task_stats(conn, item['id'], item['playlist_id'])
                results.append(item)
            return results
        finally:
            conn.close()

    def _get_monitor_task_stats(self, conn, monitor_id: int, playlist_id: str) -> Dict[str, int]:
        """统计该监控下的任务状态"""
        cursor = conn.cursor()
        cursor.execute('''
            SELECT status, COUNT(*) 
            FROM tasks 
            WHERE playlist_monitor_id = ? OR playlist_id = ?
            GROUP BY status
        ''', (monitor_id, playlist_id))
        status_counts = dict(cursor.fetchall())
        
        pending_count = status_counts.get('pending', 0)
        completed_count = status_counts.get('completed', 0)
        failed_count = status_counts.get('failed', 0)
        cancelled_count = status_counts.get('cancelled', 0)
        
        total_count = sum(status_counts.values())
        running_count = total_count - pending_count - completed_count - failed_count - cancelled_count
        if running_count < 0:
            running_count = 0

        return {
            'total': total_count,
            'pending': pending_count,
            'running': running_count,
            'completed': completed_count,
            'failed': failed_count,
            'cancelled': cancelled_count,
        }

    def update_monitor(self, monitor_id: int, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """更新监控配置"""
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            raise ValueError(f"监控配置不存在: ID {monitor_id}")

        fields = []
        params = []
        if 'title' in update_data and update_data['title']:
            fields.append('title = ?')
            params.append(str(update_data['title']).strip())

        if 'check_interval_minutes' in update_data:
            interval = max(5, int(update_data['check_interval_minutes']))
            fields.append('check_interval_minutes = ?')
            params.append(interval)

        if 'max_concurrency' in update_data:
            concurrency = max(1, int(update_data['max_concurrency']))
            fields.append('max_concurrency = ?')
            params.append(concurrency)

        if 'auto_upload' in update_data:
            en_au = 1 if bool(update_data['auto_upload']) else 0
            fields.append('auto_upload = ?')
            params.append(en_au)

        if 'custom_description' in update_data:
            c_desc = str(update_data['custom_description'] or '').strip()
            fields.append('custom_description = ?')
            params.append(c_desc)

        if 'bilibili_season_id' in update_data:
            fields.append('bilibili_season_id = ?')
            val = update_data['bilibili_season_id']
            params.append(int(val) if val else None)

        if 'bilibili_section_id' in update_data:
            fields.append('bilibili_section_id = ?')
            val = update_data['bilibili_section_id']
            params.append(int(val) if val else None)

        if 'bilibili_season_title' in update_data:
            fields.append('bilibili_season_title = ?')
            val = str(update_data['bilibili_season_title'] or '').strip()
            params.append(val if val else None)

        if 'task_interval_minutes' in update_data:
            fields.append('task_interval_minutes = ?')
            val = update_data['task_interval_minutes']
            params.append(max(0, int(val)) if val is not None else 15)

        if 'max_import_per_check' in update_data:
            fields.append('max_import_per_check = ?')
            val = update_data['max_import_per_check']
            params.append(max(0, int(val)) if val is not None else 10)

        if 'import_order' in update_data:
            fields.append('import_order = ?')
            val = 'desc' if str(update_data['import_order'] or '').lower() == 'desc' else 'asc'
            params.append(val)

        # 投稿目标强制保持并默认固定为 bilibili
        fields.append('upload_target = ?')
        params.append('bilibili')

        if 'enabled' in update_data:
            en = 1 if bool(update_data['enabled']) else 0
            fields.append('enabled = ?')
            params.append(en)

        if not fields:
            return monitor

        fields.append('updated_at = CURRENT_TIMESTAMP')
        params.append(monitor_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE playlist_monitors SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
        finally:
            conn.close()

        updated = self.get_monitor(monitor_id)
        if updated['enabled']:
            self._register_job(monitor_id, updated['check_interval_minutes'])
        else:
            self._remove_job(monitor_id)

        return updated

    def delete_monitor(self, monitor_id: int, delete_tasks: bool = False) -> bool:
        """删除监控配置"""
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            return False

        self._remove_job(monitor_id)

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM playlist_monitors WHERE id = ?', (monitor_id,))
            cursor.execute('DELETE FROM playlist_monitor_history WHERE monitor_id = ?', (monitor_id,))
            if delete_tasks:
                cursor.execute('DELETE FROM tasks WHERE playlist_monitor_id = ? OR playlist_id = ?', 
                               (monitor_id, monitor['playlist_id']))
            else:
                cursor.execute('UPDATE tasks SET playlist_monitor_id = NULL WHERE playlist_monitor_id = ?', (monitor_id,))
            conn.commit()
        finally:
            conn.close()

        logger.info(f"已删除 Playlist 监控: ID {monitor_id}")
        return True

    def check_playlist(self, monitor_id: int, auto_add: bool = True) -> Dict[str, Any]:
        """
        执行一次检测：利用 YouTube Data API v3 读取播放列表并入库新任务
        （彻底解除连接事务嵌套，防止 SQLite database is locked）
        """
        with self._check_lock:
            if monitor_id in self._active_check_monitors:
                return {'success': False, 'message': '当前已有该播放列表的检测正在运行中，请勿重复操作', 'new_tasks_count': 0}
            self._active_check_monitors.add(monitor_id)

        try:
            monitor = self.get_monitor(monitor_id)
            if not monitor:
                raise ValueError(f"监控不存在: ID {monitor_id}")

            client = self._get_youtube_client()
            if not client:
                err_msg = "YouTube API 客户端未就绪，请先在系统设置中配置有效的 API Key 及代理"
                self._record_check_status(monitor_id, 'failed', err_msg)
                return {'success': False, 'message': err_msg, 'new_tasks_count': 0}

            playlist_id = monitor['playlist_id']
            upload_target = 'bilibili'  # 默认并固定投稿目标为 bilibili
            auto_upload = bool(monitor.get('auto_upload', 1) if monitor.get('auto_upload') is not None else 1)
            custom_description = monitor.get('custom_description', '')
            logger.info(f"开始检测 Playlist 监控 (ID: {monitor_id}, Playlist: {playlist_id}, 自动投稿: {auto_upload})...")

            # 1. 独立开启短连接读出该 monitor 历史上已添加的 video_id，读完立刻关闭连接释放锁
            conn = get_db_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('SELECT video_id FROM playlist_monitor_history WHERE monitor_id = ?', (monitor_id,))
                recorded_video_ids = {row[0] for row in cursor.fetchall()}
            finally:
                conn.close()

            # 2. 分页读取播放列表 items（纯网络 I/O，不占用数据库连接）
            all_items = []
            next_page_token = None
            max_pages = 20

            for _ in range(max_pages):
                params = {
                    'part': 'snippet,contentDetails',
                    'playlistId': playlist_id,
                    'maxResults': 50,
                }
                if next_page_token:
                    params['pageToken'] = next_page_token

                req = client.playlistItems().list(**params)
                resp = youtube_monitor._execute_with_retry(req, f'playlistItems.list ({playlist_id})')
                items = resp.get('items', [])
                all_items.extend(items)

                next_page_token = resp.get('nextPageToken')
                if not next_page_token or len(items) == 0:
                    break

            total_found = len(all_items)
            logger.info(f"Playlist {playlist_id} 共拉取到 {total_found} 个项目")

            # 3. 筛选新视频及更新已有视频的真实发布时间
            new_videos = []
            existing_videos_to_fix = []
            for item in all_items:
                snippet = item.get('snippet', {})
                content_details = item.get('contentDetails', {})
                v_id = content_details.get('videoId') or snippet.get('resourceId', {}).get('videoId')
                if not v_id:
                    continue
                v_title = snippet.get('title', '')
                if v_title in ('Private video', 'Deleted video'):
                    continue

                # 关键修复：contentDetails.videoPublishedAt 是 YouTube 视频真正的发布时间！
                # snippet.publishedAt 仅是视频加入播放列表的时间！
                real_published_at = content_details.get('videoPublishedAt') or snippet.get('publishedAt', '')

                if v_id not in recorded_video_ids:
                    new_videos.append({
                        'video_id': v_id,
                        'title': v_title,
                        'published_at': real_published_at,
                    })
                else:
                    if real_published_at:
                        existing_videos_to_fix.append((real_published_at, monitor_id, v_id))

            # 对历史上已录入但时间可能有误的视频，自动同步修正为真实发布时间
            if existing_videos_to_fix:
                u_conn = get_db_connection()
                try:
                    u_cursor = u_conn.cursor()
                    u_cursor.executemany('''
                        UPDATE playlist_monitor_history
                        SET published_at = ?
                        WHERE monitor_id = ? AND video_id = ?
                    ''', existing_videos_to_fix)
                    for r_pub, m_id, v_id in existing_videos_to_fix:
                        v_url = f"https://www.youtube.com/watch?v={v_id}"
                        u_cursor.execute('''
                            UPDATE tasks
                            SET video_published_at = ?
                            WHERE (playlist_monitor_id = ? OR playlist_id = ?) AND (youtube_url = ? OR youtube_url LIKE ?)
                        ''', (r_pub, m_id, playlist_id, v_url, f"%{v_id}%"))
                    u_conn.commit()
                except Exception as ex:
                    logger.warning(f"同步修复已有视频的实际发布时间出现异常: {ex}")
                finally:
                    u_conn.close()

            # 读取排序与单次导入上限配置
            max_import = int(monitor.get('max_import_per_check') if monitor.get('max_import_per_check') is not None else 10)
            import_order = str(monitor.get('import_order') or 'asc').lower().strip()

            # 按发布时间排序：'asc' 优先从最旧发布视频导入（适合连载/第一集优先）；'desc' 从最新发布视频导入
            def _get_pub_key(item):
                return item.get('published_at') or ''

            if import_order == 'desc':
                new_videos.sort(key=_get_pub_key, reverse=True)
            else:
                new_videos.sort(key=_get_pub_key, reverse=False)

            total_new_candidates = len(new_videos)
            logger.info(f"Playlist {playlist_id} 发现 {total_new_candidates} 个新视频待入库 (排序: {import_order}, 单次上限: {max_import})")

            # 若配置了单次导入上限（> 0），则截取前 N 个导入，其余留待后续检测周期继续平滑导入
            videos_to_import = new_videos
            remaining_pending_import = 0
            if max_import > 0 and len(new_videos) > max_import:
                videos_to_import = new_videos[:max_import]
                remaining_pending_import = len(new_videos) - max_import
                logger.info(f"Playlist {playlist_id} 超过单次导入限制 {max_import}，本次截取前 {len(videos_to_import)} 个入库，剩余 {remaining_pending_import} 个待下次导入")

            # 4. 入库新任务（注意：绝不持有未提交连接，各操作独立短事务完成）
            added_count = 0
            history_records = []
            if auto_add and videos_to_import:
                for v in videos_to_import:
                    video_url = f"https://www.youtube.com/watch?v={v['video_id']}"
                    task_id = add_task(
                        video_url,
                        upload_target='bilibili',
                        playlist_id=playlist_id,
                        playlist_monitor_id=monitor_id,
                        video_published_at=v['published_at'],
                        custom_description=custom_description,
                        auto_upload=auto_upload,
                        bilibili_season_id=monitor.get('bilibili_season_id'),
                        bilibili_section_id=monitor.get('bilibili_section_id'),
                        bilibili_season_title=monitor.get('bilibili_season_title'),
                    )
                    if task_id:
                        history_records.append((monitor_id, v['video_id'], v['title'], v['published_at'], task_id))
                        added_count += 1

                # 任务添加完成后，批量写入 history 表（仅记录本次实际导入的任务，未入库的保持待导入状态）
                if history_records:
                    h_conn = get_db_connection()
                    try:
                        h_conn.executemany('''
                            INSERT OR IGNORE INTO playlist_monitor_history 
                            (monitor_id, video_id, video_title, published_at, task_id)
                            VALUES (?, ?, ?, ?, ?)
                        ''', history_records)
                        h_conn.commit()
                    finally:
                        h_conn.close()

            # 5. 更新检测状态与视频总数
            if remaining_pending_import > 0:
                succ_msg = f"检测完成：播放列表共 {total_found} 个视频，发现 {total_new_candidates} 个新视频，本次导入前 {added_count} 个任务（剩余 {remaining_pending_import} 个将在后续周期自动导入）"
            else:
                succ_msg = f"检测完成：播放列表共 {total_found} 个视频，本次新增 {added_count} 个任务"
            self._record_check_status(monitor_id, 'success', succ_msg, total_videos_found=total_found)

            return {
                'success': True,
                'message': succ_msg,
                'new_tasks_count': added_count,
                'total_found': total_found,
                'remaining_to_import': remaining_pending_import,
            }

        except Exception as e:
            logger.error(f"检测 Playlist 出错: {str(e)}", exc_info=True)
            err_msg = f"检测失败: {str(e)}"
            self._record_check_status(monitor_id, 'failed', err_msg)
            return {'success': False, 'message': err_msg, 'new_tasks_count': 0}
        finally:
            with self._check_lock:
                self._active_check_monitors.discard(monitor_id)

    def _record_check_status(self, monitor_id: int, status: str, message: str, total_videos_found: Optional[int] = None):
        """记录检测结果"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if total_videos_found is not None:
                cursor.execute('''
                    UPDATE playlist_monitors
                    SET last_checked_at = CURRENT_TIMESTAMP,
                        last_check_status = ?,
                        last_check_message = ?,
                        total_videos_found = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, message, total_videos_found, monitor_id))
            else:
                cursor.execute('''
                    UPDATE playlist_monitors
                    SET last_checked_at = CURRENT_TIMESTAMP,
                        last_check_status = ?,
                        last_check_message = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (status, message, monitor_id))
            conn.commit()
        finally:
            conn.close()

    def _run_check_async(self, monitor_id: int):
        """异步执行检测任务"""
        try:
            self.check_playlist(monitor_id, auto_add=True)
        except Exception as e:
            logger.error(f"异步检测 Playlist (ID: {monitor_id}) 异常: {str(e)}")

    def get_playlist_tasks(
        self,
        monitor_id: int,
        order: str = 'desc',
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 20
    ) -> Dict[str, Any]:
        """
        获取该 Playlist 下的所有 Task 列表，按视频发布时间 (videoPublishedAt) 倒序或顺序排序。
        
        Args:
            monitor_id: 监控ID
            order: 'desc' (视频发布时间倒序，最新在前) 或 'asc' (视频发布时间正序，最早在前)
            status: 可选状态筛选
            page: 页码，从1开始
            per_page: 每页条数
        """
        monitor = self.get_monitor(monitor_id)
        if not monitor:
            raise ValueError(f"监控不存在: ID {monitor_id}")

        playlist_id = monitor['playlist_id']
        direction = 'ASC' if str(order).lower() == 'asc' else 'DESC'
        
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 20), 100))
        offset = (page - 1) * per_page

        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            # 构建查询条件
            where_clauses = ['(tasks.playlist_monitor_id = ? OR tasks.playlist_id = ?)']
            params: List[Any] = [monitor_id, playlist_id]

            if status and status.strip():
                where_clauses.append('tasks.status = ?')
                params.append(status.strip())

            where_sql = ' AND '.join(where_clauses)

            # 查询总数
            cursor.execute(f"SELECT COUNT(*) FROM tasks WHERE {where_sql}", params)
            total = cursor.fetchone()[0]

            # 分页查询：严格按 videoPublishedAt 排序
            query_sql = f"""
                SELECT tasks.*, 
                       COALESCE(tasks.video_published_at, h.published_at) AS video_published_at
                FROM tasks 
                LEFT JOIN playlist_monitor_history h 
                       ON tasks.id = h.task_id
                WHERE {where_sql} 
                ORDER BY COALESCE(tasks.video_published_at, h.published_at, tasks.created_at) {direction} 
                LIMIT ? OFFSET ?
            """
            cursor.execute(query_sql, params + [per_page, offset])
            rows = cursor.fetchall()
            tasks = []
            for r in rows:
                item = dict(r)
                item['videoPublishedAt'] = item.get('video_published_at')
                tasks.append(item)

            total_pages = (total + per_page - 1) // per_page if total > 0 else 0

            return {
                'tasks': tasks,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'order': 'asc' if direction == 'ASC' else 'desc',
                'status_filter': status,
                'monitor': {
                    'id': monitor['id'],
                    'title': monitor['title'],
                    'playlist_id': monitor['playlist_id'],
                    'max_concurrency': monitor['max_concurrency'],
                    'check_interval_minutes': monitor['check_interval_minutes'],
                    'task_interval_minutes': monitor.get('task_interval_minutes', 30),
                    'max_import_per_check': monitor.get('max_import_per_check', 10),
                    'import_order': monitor.get('import_order', 'asc'),
                    'last_task_completed_at': monitor.get('last_task_completed_at'),
                },
                'stats': monitor.get('task_stats', {}),
            }
        finally:
            conn.close()

    # ---------------- 调度器管理 ----------------
    def _register_job(self, monitor_id: int, interval_minutes: int):
        """向调度器注册或更新定时轮询作业"""
        job_id = f"playlist_monitor_{monitor_id}"
        interval = max(5, int(interval_minutes or 30))
        try:
            self.scheduler.add_job(
                func=self._run_check_async,
                args=[monitor_id],
                trigger=IntervalTrigger(minutes=interval),
                id=job_id,
                name=f"Playlist Monitor {monitor_id}",
                replace_existing=True
            )
            logger.info(f"已注册 Playlist 定时监控作业: ID {monitor_id}, 间隔: {interval} 分钟")
        except Exception as e:
            logger.error(f"注册 Playlist 定时作业失败: {str(e)}")

    def _remove_job(self, monitor_id: int):
        """移除指定监控作业"""
        job_id = f"playlist_monitor_{monitor_id}"
        try:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"已注销 Playlist 定时监控作业: ID {monitor_id}")
        except Exception as e:
            logger.debug(f"注销 Playlist 调度作业失败（可能未存在）: {str(e)}")

    def start(self):
        """启动后台调度器并载入所有已启用的监控配置"""
        if self._scheduler_running:
            return
        try:
            if not self.scheduler.running:
                self.scheduler.start()
            self._scheduler_running = True
            logger.info("Playlist 监控调度器已启动")

            monitors = self.get_monitors()
            for m in monitors:
                if m.get('enabled'):
                    self._register_job(m['id'], m['check_interval_minutes'])
        except Exception as e:
            logger.error(f"启动 Playlist 监控调度器失败: {str(e)}")

    def stop(self):
        """关闭调度器"""
        if self._scheduler_running:
            try:
                self.scheduler.shutdown(wait=False)
                self._scheduler_running = False
                logger.info("Playlist 监控调度器已关闭")
            except Exception as e:
                logger.error(f"关闭 Playlist 调度器异常: {str(e)}")


# 全局单例
playlist_monitor_manager = PlaylistMonitorManager()


def get_playlist_max_concurrency(monitor_id: Optional[int] = None, playlist_id: Optional[str] = None) -> int:
    """
    供任务调度器查询指定 Playlist 的最大并发配置。
    若未找到，默认返回 1。
    """
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if monitor_id:
                cursor.execute('SELECT max_concurrency FROM playlist_monitors WHERE id = ?', (monitor_id,))
            elif playlist_id:
                cursor.execute('SELECT max_concurrency FROM playlist_monitors WHERE playlist_id = ?', (playlist_id,))
            else:
                return 1
            row = cursor.fetchone()
            if row and row[0] is not None:
                return max(1, int(row[0]))
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"查询 playlist 并发限制失败: {e}")
    return 1


def update_playlist_last_task_completed(monitor_id: Optional[int] = None, playlist_id: Optional[str] = None):
    """
    当属于该播放列表的任务完成时调用，记录任务完成时间（用于防风控任务执行间隔计算）
    """
    if not monitor_id and not playlist_id:
        return
    try:
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if monitor_id:
                cursor.execute('''
                    UPDATE playlist_monitors
                    SET last_task_completed_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (now_str, monitor_id))
            elif playlist_id:
                cursor.execute('''
                    UPDATE playlist_monitors
                    SET last_task_completed_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE playlist_id = ?
                ''', (now_str, playlist_id))
            conn.commit()
            logger.info(f"已更新播放列表 (monitor_id={monitor_id}, playlist_id={playlist_id}) 的最后任务完成时间为: {now_str}")
        finally:
            conn.close()
    except Exception as e:
        logger.warning(f"更新播放列表最后任务完成时间失败: {e}")


def get_playlist_interval_cooling_info(monitor_id: Optional[int] = None, playlist_id: Optional[str] = None) -> Tuple[bool, int]:
    """
    检查指定播放列表是否处于防风控任务执行间隔冷却中。
    返回 (is_cooling, remaining_seconds)。
    若处于冷却期，is_cooling 为 True，remaining_seconds 为剩余秒数。
    """
    if not monitor_id and not playlist_id:
        return False, 0

    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if monitor_id:
                cursor.execute('''
                    SELECT id, playlist_id, task_interval_minutes, last_task_completed_at 
                    FROM playlist_monitors WHERE id = ?
                ''', (monitor_id,))
            else:
                cursor.execute('''
                    SELECT id, playlist_id, task_interval_minutes, last_task_completed_at 
                    FROM playlist_monitors WHERE playlist_id = ?
                ''', (playlist_id,))
            row = cursor.fetchone()
            if not row:
                return False, 0

            m_id, p_id, interval_minutes, last_completed_str = row[0], row[1], row[2], row[3]
            interval_min = int(interval_minutes) if interval_minutes is not None else 30
            if interval_min <= 0:
                return False, 0

            # 若 last_task_completed_at 字段暂无记录，兜底查询该播放列表已完成任务的最大更新时间
            last_dt = None
            if last_completed_str:
                try:
                    last_clean = str(last_completed_str).replace('T', ' ').split('.')[0]
                    last_dt = datetime.strptime(last_clean, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass

            if not last_dt:
                cursor.execute('''
                    SELECT MAX(updated_at) FROM tasks 
                    WHERE (playlist_monitor_id = ? OR playlist_id = ?) AND status = 'completed'
                ''', (m_id, p_id))
                t_row = cursor.fetchone()
                if t_row and t_row[0]:
                    try:
                        t_clean = str(t_row[0]).replace('T', ' ').split('.')[0]
                        last_dt = datetime.strptime(t_clean, '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        pass

            if not last_dt:
                return False, 0

            now = datetime.now()
            elapsed_seconds = (now - last_dt).total_seconds()
            if elapsed_seconds < 0:
                elapsed_seconds = 0

            cooling_needed = interval_min * 60
            if elapsed_seconds < cooling_needed:
                remaining_seconds = int(cooling_needed - elapsed_seconds)
                return True, remaining_seconds

            return False, 0
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"查询播放列表任务间隔冷却信息失败: {e}")
        return False, 0
