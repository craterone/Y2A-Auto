#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单元测试：YouTube Playlist 监控与并发控制
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.task_manager import init_db, get_db_connection, add_task, get_tasks_by_status
from modules.playlist_monitor import (
    extract_playlist_id,
    playlist_monitor_manager,
    get_playlist_max_concurrency,
)
import app as flask_app_module


class TestPlaylistMonitor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_extract_playlist_id(self):
        """测试 Playlist ID 提取"""
        cases = [
            ("PLbpi6ZahtOH6Blw3RGY3973uEI836_QvB", "PLbpi6ZahtOH6Blw3RGY3973uEI836_QvB"),
            ("https://www.youtube.com/playlist?list=PLbpi6ZahtOH6Blw3RGY3973uEI836_QvB", "PLbpi6ZahtOH6Blw3RGY3973uEI836_QvB"),
            ("https://youtu.be/watch?v=12345&list=PLTest123456", "PLTest123456"),
            ("https://www.youtube.com/watch?v=abc&index=1&list=PLxyz_123-abc", "PLxyz_123-abc"),
            ("", None),
            ("invalid", None),
        ]
        for inp, expected in cases:
            self.assertEqual(extract_playlist_id(inp), expected, f"Failed on input: {inp}")

    def test_02_database_schema(self):
        """测试 tasks 表是否已成功升级 playlist 相关字段"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tasks)")
        cols = [r[1] for r in cursor.fetchall()]
        self.assertIn("playlist_id", cols)
        self.assertIn("playlist_monitor_id", cols)
        conn.close()

    def test_03_create_and_get_monitor(self):
        """测试创建与查询监控配置"""
        test_pid = "PL_Unit_Test_001"
        # 先清除可能存在的残留
        with get_db_connection() as conn:
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # 创建监控
        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=45,
            max_concurrency=2,
            upload_target='bilibili',
            enabled=True,
            custom_title="测试播放列表"
        )
        self.assertIsNotNone(mon)
        self.assertEqual(mon['playlist_id'], test_pid)
        self.assertEqual(mon['check_interval_minutes'], 45)
        self.assertEqual(mon['max_concurrency'], 2)
        self.assertEqual(mon['upload_target'], 'bilibili')
        self.assertEqual(mon['title'], "测试播放列表")

        # 查询单个
        fetched = playlist_monitor_manager.get_monitor(mon['id'])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched['id'], mon['id'])

        # 测试并发限制查询函数
        concurrency = get_playlist_max_concurrency(monitor_id=mon['id'])
        self.assertEqual(concurrency, 2)

    def test_04_add_task_with_playlist_and_query_tasks_ordering(self):
        """测试关联 Playlist 添加任务，以及严格按视频发布时间 (videoPublishedAt) 倒序/正序查看"""
        test_pid = "PL_Unit_Test_Order"
        # 清理
        with get_db_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE playlist_id = ?", (test_pid,))
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=30,
            max_concurrency=1,
            upload_target='acfun',
            custom_title="发布时间排序测试"
        )
        mon_id = mon['id']

        # 故意按照与发布时间不同的入库顺序添加任务：
        # t1 先入库，但视频发布时间是 2024-02-01 (较晚)
        # t2 后入库，但视频发布时间是 2024-01-01 (最早)
        # t3 最后入库，但视频发布时间是 2024-03-01 (最新)
        t1 = add_task(
            "https://www.youtube.com/watch?v=test_vid_mid", 
            upload_target="acfun", 
            playlist_id=test_pid, 
            playlist_monitor_id=mon_id,
            video_published_at="2024-02-01T12:00:00Z"
        )
        t2 = add_task(
            "https://www.youtube.com/watch?v=test_vid_old", 
            upload_target="acfun", 
            playlist_id=test_pid, 
            playlist_monitor_id=mon_id,
            video_published_at="2024-01-01T12:00:00Z"
        )
        t3 = add_task(
            "https://www.youtube.com/watch?v=test_vid_new", 
            upload_target="acfun", 
            playlist_id=test_pid, 
            playlist_monitor_id=mon_id,
            video_published_at="2024-03-01T12:00:00Z"
        )

        self.assertTrue(t1 and t2 and t3)

        # 1. 测试按视频发布时间倒序 (desc, 2024-03 -> 2024-02 -> 2024-01，即 t3 -> t1 -> t2)
        res_desc = playlist_monitor_manager.get_playlist_tasks(mon_id, order='desc')
        self.assertEqual(res_desc['total'], 3)
        self.assertEqual(res_desc['order'], 'desc')
        tasks_desc = res_desc['tasks']
        self.assertEqual(tasks_desc[0]['id'], t3)
        self.assertEqual(tasks_desc[1]['id'], t1)
        self.assertEqual(tasks_desc[2]['id'], t2)
        self.assertEqual(tasks_desc[0]['videoPublishedAt'], "2024-03-01T12:00:00Z")

        # 2. 测试按视频发布时间正序 (asc, 2024-01 -> 2024-02 -> 2024-03，即 t2 -> t1 -> t3)
        res_asc = playlist_monitor_manager.get_playlist_tasks(mon_id, order='asc')
        self.assertEqual(res_asc['total'], 3)
        self.assertEqual(res_asc['order'], 'asc')
        tasks_asc = res_asc['tasks']
        self.assertEqual(tasks_asc[0]['id'], t2)
        self.assertEqual(tasks_asc[1]['id'], t1)
        self.assertEqual(tasks_asc[2]['id'], t3)
        self.assertEqual(tasks_asc[0]['videoPublishedAt'], "2024-01-01T12:00:00Z")

    def test_05_restful_api_endpoints(self):
        """测试 RESTful API 端点交互"""
        app = flask_app_module.app
        app.config['TESTING'] = True
        client = app.test_client()

        with client.session_transaction() as sess:
            sess['logged_in'] = True

        test_pid = "PL_Api_Test_999"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # 1. POST /api/playlist-monitors
        create_resp = client.post('/api/playlist-monitors', json={
            'playlist_id': test_pid,
            'check_interval_minutes': 30,
            'max_concurrency': 2,
            'upload_target': 'acfun',
            'custom_title': 'API测试监控'
        })
        self.assertEqual(create_resp.status_code, 201)
        c_data = create_resp.get_json()
        self.assertTrue(c_data['success'])
        m_id = c_data['monitor']['id']

        # 2. GET /api/playlist-monitors
        list_resp = client.get('/api/playlist-monitors')
        self.assertEqual(list_resp.status_code, 200)
        l_data = list_resp.get_json()
        self.assertTrue(l_data['success'])
        ids = [m['id'] for m in l_data['monitors']]
        self.assertIn(m_id, ids)

        # 3. GET /api/playlist-monitors/<id>
        get_resp = client.get(f'/api/playlist-monitors/{m_id}')
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.get_json()['monitor']['id'], m_id)

        # 4. PUT /api/playlist-monitors/<id>
        put_resp = client.put(f'/api/playlist-monitors/{m_id}', json={
            'max_concurrency': 3,
            'check_interval_minutes': 60
        })
        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(put_resp.get_json()['monitor']['max_concurrency'], 3)
        self.assertEqual(put_resp.get_json()['monitor']['check_interval_minutes'], 60)

        # 5. GET /api/playlist-monitors/<id>/tasks (order=desc & order=asc)
        tasks_resp_desc = client.get(f'/api/playlist-monitors/{m_id}/tasks?order=desc')
        self.assertEqual(tasks_resp_desc.status_code, 200)
        self.assertEqual(tasks_resp_desc.get_json()['order'], 'desc')

        tasks_resp_asc = client.get(f'/api/playlist-monitors/{m_id}/tasks?order=asc')
        self.assertEqual(tasks_resp_asc.status_code, 200)
        self.assertEqual(tasks_resp_asc.get_json()['order'], 'asc')

        # 6. DELETE /api/playlist-monitors/<id>
        del_resp = client.delete(f'/api/playlist-monitors/{m_id}')
        self.assertEqual(del_resp.status_code, 200)

    def test_06_playlist_max_concurrency_restriction(self):
        """测试 Playlist 最大并发限制为 1 时，已有任务运行中则下一个任务无法调度启动"""
        test_pid = "PL_Concurrency_Limit_Test"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE playlist_id = ?", (test_pid,))
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # 创建最大并发为 1 的监控
        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=30,
            max_concurrency=1,
            upload_target='acfun',
            custom_title="并发限制测试"
        )
        mon_id = mon['id']

        # 添加两个属于该 playlist 的任务
        t1 = add_task("https://www.youtube.com/watch?v=vid_conc_1", playlist_id=test_pid, playlist_monitor_id=mon_id)
        t2 = add_task("https://www.youtube.com/watch?v=vid_conc_2", playlist_id=test_pid, playlist_monitor_id=mon_id)

        # 模拟 t1 已经进入运行中（如 fetching_info 状态）
        with get_db_connection() as conn:
            conn.execute("UPDATE tasks SET status = 'fetching_info' WHERE id = ?", (t1,))
            conn.commit()

        # 获取全局任务处理器并尝试调度 t2
        from modules.task_manager import get_global_task_processor
        processor = get_global_task_processor({})

        # 因为 t1 处于运行中，且该 playlist 最大并发是 1，调度 t2 必须被拦截返回 None
        scheduled_job_id = processor.schedule_task(t2)
        self.assertIsNone(scheduled_job_id, "当已有任务处于运行态且并发限制为1时，不应允许调度第二个任务！")

    def test_07_cooling_interval_restriction(self):
        """测试防风控任务执行间隔冷却限制与调度拦截"""
        from modules.playlist_monitor import (
            get_playlist_interval_cooling_info,
            update_playlist_last_task_completed
        )
        test_pid = "PL_Cooling_Interval_Test"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE playlist_id = ?", (test_pid,))
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # 创建任务间隔为 30 分钟的监控
        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=30,
            max_concurrency=2,
            task_interval_minutes=30,
            upload_target='bilibili',
            custom_title="冷却间隔测试"
        )
        mon_id = mon['id']

        # 初始未完成任何任务时，不应处于冷却
        is_cooling, rem = get_playlist_interval_cooling_info(monitor_id=mon_id)
        self.assertFalse(is_cooling)
        self.assertEqual(rem, 0)

        # 模拟刚才刚刚完成一个任务
        update_playlist_last_task_completed(monitor_id=mon_id)

        # 此时应处于冷却中，剩余秒数应在 1700~1800 之间 (30分钟 = 1800秒)
        is_cooling, rem = get_playlist_interval_cooling_info(monitor_id=mon_id)
        self.assertTrue(is_cooling)
        self.assertGreater(rem, 1750)
        self.assertLessEqual(rem, 1800)

        # 添加新任务并尝试自动调度，验证因冷却被拦截
        t = add_task("https://www.youtube.com/watch?v=cool_vid_1", playlist_id=test_pid, playlist_monitor_id=mon_id)
        from modules.task_manager import get_global_task_processor
        processor = get_global_task_processor({})

        job_id = processor.schedule_task(t, ignore_interval=False)
        self.assertIsNone(job_id, "处于冷却期且未忽略间隔时，不应允许调度执行！")

    @patch.object(playlist_monitor_manager, '_run_check_async')
    @patch.object(playlist_monitor_manager, 'fetch_playlist_details', return_value={'title': '分批导入测试', 'description': '', 'channel_title': '', 'thumbnail_url': ''})
    @patch.object(playlist_monitor_manager, '_get_youtube_client')
    def test_08_batch_import_and_order(self, mock_get_client, mock_fetch_details, mock_run_async):
        """测试单次导入上限截断与排序功能"""
        test_pid = "PL_Batch_Import_Test"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM tasks WHERE playlist_id = ?", (test_pid,))
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # Mock YouTube API 返回 4 个视频，发布时间从 2024-01 到 2024-04
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_items = [
            {
                'snippet': {'title': 'Video 4', 'publishedAt': '2024-04-01T00:00:00Z'},
                'contentDetails': {'videoId': 'vid_04', 'videoPublishedAt': '2024-04-01T00:00:00Z'}
            },
            {
                'snippet': {'title': 'Video 1', 'publishedAt': '2024-01-01T00:00:00Z'},
                'contentDetails': {'videoId': 'vid_01', 'videoPublishedAt': '2024-01-01T00:00:00Z'}
            },
            {
                'snippet': {'title': 'Video 3', 'publishedAt': '2024-03-01T00:00:00Z'},
                'contentDetails': {'videoId': 'vid_03', 'videoPublishedAt': '2024-03-01T00:00:00Z'}
            },
            {
                'snippet': {'title': 'Video 2', 'publishedAt': '2024-02-01T00:00:00Z'},
                'contentDetails': {'videoId': 'vid_02', 'videoPublishedAt': '2024-02-01T00:00:00Z'}
            },
        ]
        mock_resp = {'items': mock_items, 'nextPageToken': None}
        mock_req = MagicMock()
        mock_req.execute.return_value = mock_resp
        mock_client.playlistItems().list.return_value = mock_req

        # 创建监控：max_import_per_check=2, import_order='asc' (正序，旧视频优先)
        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=30,
            max_concurrency=1,
            max_import_per_check=2,
            import_order='asc',
            upload_target='bilibili',
            custom_title="分批导入测试"
        )
        mon_id = mon['id']

        # 执行首次检测
        result = playlist_monitor_manager.check_playlist(mon_id, auto_add=True)
        self.assertTrue(result['success'])
        self.assertEqual(result['new_tasks_count'], 2)
        self.assertEqual(result['remaining_to_import'], 2)

        # 检查入库的任务是按正序最旧的 vid_01 和 vid_02
        tasks_res = playlist_monitor_manager.get_playlist_tasks(mon_id, order='asc')
        self.assertEqual(tasks_res['total'], 2)
        task_urls = [t['youtube_url'] for t in tasks_res['tasks']]
        self.assertIn("https://www.youtube.com/watch?v=vid_01", task_urls)
        self.assertIn("https://www.youtube.com/watch?v=vid_02", task_urls)

        # 再次执行检测（模拟下一个轮询周期），应继续导入剩余的 vid_03 和 vid_04
        result2 = playlist_monitor_manager.check_playlist(mon_id, auto_add=True)
        self.assertTrue(result2['success'])
        self.assertEqual(result2['new_tasks_count'], 2)
        self.assertEqual(result2['remaining_to_import'], 0)

        tasks_res2 = playlist_monitor_manager.get_playlist_tasks(mon_id, order='asc')
        self.assertEqual(tasks_res2['total'], 4)


if __name__ == '__main__':
    unittest.main()
