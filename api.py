"""
RESTful API 模块
包含登录认证、任务管理等 RESTful API 端点
"""
import logging
import time
from functools import wraps
from flask import Blueprint, request, jsonify, session

logger = logging.getLogger(__name__)

# 创建 API 蓝图，统一前缀为 /api
api_bp = Blueprint('api', __name__, url_prefix='/api')


def _get_app_module():
    import app as web_app
    return web_app


def api_login_required(f):
    """API 专用的登录验证装饰器，委托给主应用的 login_required"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        web_app = _get_app_module()
        return web_app.login_required(f)(*args, **kwargs)
    return decorated_function


# ==========================================
# 认证相关 API
# ==========================================

@api_bp.route('/login', methods=['POST'])
@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """
    RESTful API: 用户登录
    支持 JSON 格式: {"password": "xxx"} 或表单格式
    """
    web_app = _get_app_module()
    config = web_app.load_config()

    # 如果密码保护未启用，直接返回登录成功
    if not config.get('password_protection_enabled'):
        session['logged_in'] = True
        session.permanent = True
        return jsonify({
            'success': True,
            'message': '系统未启用密码保护，登录成功',
            'logged_in': True,
            'password_protection_enabled': False
        }), 200

    sec = web_app._load_security_state()
    now_ts = time.time()

    # 检查是否处于锁定期
    if sec.get('locked_until', 0) and now_ts < sec['locked_until']:
        remaining = int(sec['locked_until'] - now_ts)
        minutes = remaining // 60
        seconds = remaining % 60
        return jsonify({
            'success': False,
            'message': f'登录已被临时锁定，请 {minutes} 分 {seconds} 秒后重试。',
            'locked': True,
            'remaining_seconds': remaining
        }), 423

    # 解析密码字段
    data = request.get_json(silent=True) or {}
    password = None
    if isinstance(data, dict):
        password = data.get('password')
    if not password and request.form:
        password = request.form.get('password')

    stored_password = config.get('password')
    if not stored_password:
        return jsonify({
            'success': False,
            'message': '系统尚未设置密码，无法登录。请在系统设置中设置密码。'
        }), 400

    if not password:
        return jsonify({
            'success': False,
            'message': '密码不能为空'
        }), 400

    if password == stored_password:
        session['logged_in'] = True
        session.permanent = True
        sec.update({'failed_attempts': 0, 'locked_until': 0, 'last_attempt': now_ts})
        web_app._save_security_state(sec)
        web_app._emit_login_event(
            web_app.EVENT_LOGIN_SUCCESS,
            {
                'ip_address': web_app._get_request_ip_address(),
            }
        )
        return jsonify({
            'success': True,
            'message': '登录成功',
            'logged_in': True
        }), 200
    else:
        max_attempts = int(config.get('LOGIN_MAX_FAILED_ATTEMPTS', 5) or 5)
        lock_minutes = int(config.get('LOGIN_LOCKOUT_MINUTES', 15) or 15)
        failed = int(sec.get('failed_attempts', 0) or 0) + 1
        sec['failed_attempts'] = failed
        sec['last_attempt'] = now_ts
        if failed >= max_attempts:
            sec['locked_until'] = now_ts + lock_minutes * 60
            web_app._save_security_state(sec)
            web_app._emit_login_event(
                web_app.EVENT_LOGIN_LOCKED,
                {
                    'ip_address': web_app._get_request_ip_address(),
                    'failed_attempts': failed,
                    'max_attempts': max_attempts,
                    'lock_minutes': lock_minutes,
                }
            )
            return jsonify({
                'success': False,
                'message': f'密码错误次数过多（{failed}/{max_attempts}），已锁定 {lock_minutes} 分钟。',
                'locked': True,
                'remaining_seconds': lock_minutes * 60,
                'remaining_attempts': 0
            }), 423
        else:
            web_app._save_security_state(sec)
            remain = max_attempts - failed
            return jsonify({
                'success': False,
                'message': f'密码错误。还可尝试 {remain} 次后将被锁定。',
                'locked': False,
                'remaining_attempts': remain
            }), 401


@api_bp.route('/logout', methods=['POST'])
@api_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """RESTful API: 用户注销"""
    session.clear()
    return jsonify({
        'success': True,
        'message': '您已成功退出登录'
    }), 200


@api_bp.route('/auth/status', methods=['GET'])
@api_bp.route('/login/status', methods=['GET'])
def api_auth_status():
    """RESTful API: 查询当前认证状态"""
    web_app = _get_app_module()
    config = web_app.load_config()
    protection_enabled = bool(config.get('password_protection_enabled', False))
    is_logged = ('logged_in' in session) if protection_enabled else True
    return jsonify({
        'success': True,
        'logged_in': is_logged,
        'password_protection_enabled': protection_enabled
    }), 200


# ==========================================
# 任务相关 API
# ==========================================

@api_bp.route('/tasks', methods=['POST'])
@api_bp.route('/tasks/add', methods=['POST'])
@api_login_required
def api_add_task():
    """
    RESTful API: 添加新任务
    支持 JSON 格式:
    {
        "youtube_url": "https://www.youtube.com/watch?v=...",
        "upload_target": "acfun" | "bilibili" | "both",   # 可选，默认使用配置
        "auto_start": true | false                         # 可选，是否添加后立即处理
    }
    同时也兼容 form 提交
    """
    web_app = _get_app_module()
    try:
        data = request.get_json(silent=True) or {}
        if not data and request.form:
            data = request.form.to_dict()

        youtube_url = str(data.get('youtube_url') or '').strip()
        upload_target = data.get('upload_target')
        auto_start = data.get('auto_start')

        if not youtube_url:
            return jsonify({'success': False, 'message': 'YouTube URL不能为空'}), 400

        config = web_app.load_config()
        if not upload_target:
            upload_target = config.get('UPLOAD_TARGET_DEFAULT', 'acfun')
        else:
            upload_target = str(upload_target).strip().lower()

        if upload_target not in ('acfun', 'bilibili', 'both'):
            return jsonify({'success': False, 'message': '无效的投稿平台参数，支持: acfun, bilibili, both'}), 400

        # 判断是否立即启动
        if auto_start is not None:
            if isinstance(auto_start, str):
                should_start = auto_start.lower() in ('true', '1', 'yes')
            else:
                should_start = bool(auto_start)
        else:
            should_start = bool(config.get('AUTO_MODE_ENABLED', False))

        bilibili_season_id = data.get('bilibili_season_id')
        bilibili_section_id = data.get('bilibili_section_id')
        bilibili_season_title = data.get('bilibili_season_title')

        # 判断是否为播放列表URL
        if 'youtube.com/playlist' in youtube_url or 'youtu.be/playlist' in youtube_url:
            cookies_path = web_app.resolve_cookie_file_path(config.get('YOUTUBE_COOKIES_PATH'), 'youtube')
            video_urls = web_app.extract_video_urls_from_playlist(youtube_url, cookies_path)
            if not video_urls:
                return jsonify({'success': False, 'message': '未能提取到播放列表中的视频'}), 400

            added_count = 0
            task_ids = []
            for url in video_urls:
                task_id = web_app.add_task(
                    url,
                    upload_target=upload_target,
                    bilibili_season_id=bilibili_season_id,
                    bilibili_section_id=bilibili_section_id,
                    bilibili_season_title=bilibili_season_title,
                )
                if task_id:
                    added_count += 1
                    task_ids.append(task_id)
                    if should_start:
                        web_app.start_task(task_id, config)

            return jsonify({
                'success': True,
                'message': f'已批量添加 {added_count} 个视频任务（来自播放列表）',
                'is_playlist': True,
                'count': added_count,
                'task_ids': task_ids,
                'started': should_start,
                'upload_target': upload_target
            }), 201

        # 单个视频
        task_id = web_app.add_task(
            youtube_url,
            upload_target=upload_target,
            bilibili_season_id=bilibili_season_id,
            bilibili_section_id=bilibili_section_id,
            bilibili_season_title=bilibili_season_title,
        )
        if task_id:
            if should_start:
                logger.info(f"API添加任务并立即启动处理: {task_id}")
                web_app.start_task(task_id, config)
                return jsonify({
                    'success': True,
                    'message': '任务已添加并开始处理',
                    'is_playlist': False,
                    'task_id': task_id,
                    'started': True,
                    'upload_target': upload_target
                }), 201
            else:
                return jsonify({
                    'success': True,
                    'message': '任务已添加',
                    'is_playlist': False,
                    'task_id': task_id,
                    'started': False,
                    'upload_target': upload_target
                }), 201
        else:
            return jsonify({'success': False, 'message': '添加任务失败'}), 500

    except Exception as e:
        logger.error(f"API添加任务异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'服务器内部错误: {str(e)}'}), 500


def _enrich_task_display(task, web_app):
    if not task or not isinstance(task, dict):
        return task
    if hasattr(web_app, 'get_partition_name'):
        try:
            bili_pid = (
                task.get('selected_partition_id_bilibili') or
                task.get('recommended_partition_id_bilibili') or
                task.get('selected_partition_id') or
                task.get('recommended_partition_id')
            )
            if bili_pid:
                name = web_app.get_partition_name(bili_pid, 'bilibili')
                if name:
                    task['partition_name_bilibili'] = name

            ac_pid = (
                task.get('selected_partition_id_acfun') or
                task.get('recommended_partition_id_acfun') or
                task.get('selected_partition_id') or
                task.get('recommended_partition_id')
            )
            if ac_pid:
                name = web_app.get_partition_name(ac_pid, 'acfun')
                if name:
                    task['partition_name_acfun'] = name
        except Exception as e:
            logger.debug(f"解析分区名称异常: {str(e)}")
    return task


@api_bp.route('/tasks', methods=['GET'])
@api_login_required
def api_get_tasks():
    """
    RESTful API: 获取任务列表（支持分页）
    参数: page (int), per_page (int)
    """
    web_app = _get_app_module()
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = max(1, min(per_page, 100))  # 限制每页1-100条
        pagination_data = web_app.get_tasks_paginated(page=page, per_page=per_page)
        tasks = pagination_data.get('tasks', [])
        for task in tasks:
            _enrich_task_display(task, web_app)
        return jsonify({
            'success': True,
            'tasks': tasks,
            'total': pagination_data.get('total', 0),
            'page': pagination_data.get('page', page),
            'per_page': pagination_data.get('per_page', per_page),
            'total_pages': pagination_data.get('total_pages', 0)
        }), 200
    except Exception as e:
        logger.error(f"API获取任务列表异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'}), 500


@api_bp.route('/tasks/<task_id>', methods=['GET'])
@api_login_required
def api_get_task(task_id):
    """
    RESTful API: 获取单个任务详情
    """
    web_app = _get_app_module()
    try:
        task = web_app.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'}), 404
        _enrich_task_display(task, web_app)
        return jsonify({
            'success': True,
            'task': task
        }), 200
    except Exception as e:
        logger.error(f"API获取任务详情异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取任务详情失败: {str(e)}'}), 500


@api_bp.route('/tasks/<task_id>', methods=['DELETE'])
@api_login_required
def api_delete_task(task_id):
    """
    RESTful API: 删除指定任务
    参数: delete_files (bool, 默认 true)
    """
    web_app = _get_app_module()
    try:
        task = web_app.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'}), 404

        delete_files = True
        if request.is_json and request.get_json(silent=True) is not None:
            delete_files = bool(request.get_json().get('delete_files', True))
        elif 'delete_files' in request.args:
            delete_files = request.args.get('delete_files', 'true').lower() in ('true', 'yes', '1', 'on')

        success = web_app.delete_task(task_id, delete_files=delete_files)
        if success:
            return jsonify({
                'success': True,
                'message': '任务已成功删除'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '删除任务失败'
            }), 500
    except Exception as e:
        logger.error(f"API删除任务异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'删除任务失败: {str(e)}'}), 500


@api_bp.route('/tasks/<task_id>/start', methods=['POST'])
@api_login_required
def api_start_task(task_id):
    """
    RESTful API: 手动启动/重新开始任务（失败任务重启不受风控间隔限制）
    """
    web_app = _get_app_module()
    try:
        task = web_app.get_task(task_id)
        if not task:
            return jsonify({'success': False, 'message': '任务不存在'}), 404

        allowed = ('pending', 'failed')
        if task['status'] not in allowed:
            return jsonify({
                'success': False,
                'message': f'当前任务状态为 {task["status"]}，只有排队中或失败的任务可以手动启动'
            }), 400

        from modules.config_manager import load_config
        config = load_config()
        success = web_app.start_task(task_id, config, ignore_interval=True)

        if success:
            return jsonify({
                'success': True,
                'message': '任务已重新启动'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '启动任务失败，可能已达并发上限，请稍后再试'
            }), 500
    except Exception as e:
        logger.error(f"API启动任务异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'启动任务失败: {str(e)}'}), 500


@api_bp.route('/tasks', methods=['DELETE'])
@api_bp.route('/tasks/clear', methods=['POST', 'DELETE'])
@api_login_required
def api_clear_all_tasks():
    """
    RESTful API: 清空所有任务
    参数: delete_files (bool, 默认 true)
    """
    web_app = _get_app_module()
    try:
        delete_files = True
        if request.is_json and request.get_json(silent=True) is not None:
            delete_files = bool(request.get_json().get('delete_files', True))
        elif 'delete_files' in request.args:
            delete_files = request.args.get('delete_files', 'true').lower() in ('true', 'yes', '1', 'on')

        success = web_app.clear_all_tasks(delete_files=delete_files)
        if success:
            return jsonify({
                'success': True,
                'message': '所有任务已成功清空'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': '清空任务失败'
            }), 500
    except Exception as e:
        logger.error(f"API清空所有任务异常: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'清空任务失败: {str(e)}'}), 500




# ==========================================
# YouTube Playlist 监控 RESTful API
# ==========================================

@api_bp.route('/playlist-monitors', methods=['POST'])
@api_login_required
def api_create_playlist_monitor():
    """
    RESTful API: 创建新的 YouTube Playlist 监控
    Body (JSON):
    {
        "playlist_id": "PL...",                # 必填，播放列表ID或包含list=的URL
        "check_interval_minutes": 30,         # 可选，检测时间间隔（分钟），默认30
        "max_concurrency": 1,                 # 可选，最大并发运行任务数，默认1
        "auto_upload": true,                  # 可选，是否自动投稿，默认true
        "custom_description": "统一简介",      # 可选，所有视频投稿时统一使用的简介
        "enabled": true,                      # 可选，是否启用监控，默认true
        "custom_title": "我的播放列表"         # 可选，自定义名称
    }
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        data = request.get_json(silent=True) or {}
        if not data and request.form:
            data = request.form.to_dict()

        playlist_id_input = data.get('playlist_id') or data.get('url') or ''
        if not playlist_id_input:
            return jsonify({'success': False, 'message': '播放列表ID或URL不能为空'}), 400

        check_interval = data.get('check_interval_minutes', 30)
        max_concurrency = data.get('max_concurrency', 1)
        upload_target = 'bilibili'  # 默认固定为 bilibili
        enabled = data.get('enabled', True)
        custom_title = data.get('custom_title') or data.get('title')
        auto_upload = data.get('auto_upload', True)
        custom_description = data.get('custom_description', '')
        bilibili_season_id = data.get('bilibili_season_id')
        bilibili_section_id = data.get('bilibili_section_id')
        bilibili_season_title = data.get('bilibili_season_title')
        task_interval_minutes = data.get('task_interval_minutes', 15)
        max_import_per_check = data.get('max_import_per_check', 10)
        import_order = data.get('import_order', 'asc')
        title_pattern = data.get('title_pattern', '')
        title_template = data.get('title_template', '')
        custom_tags = data.get('custom_tags') if 'custom_tags' in data else data.get('tags')
        raw_translate_title = data.get('translate_title', False)
        if isinstance(raw_translate_title, str):
            translate_title = raw_translate_title.lower() in ('1', 'true', 'yes')
        else:
            translate_title = bool(raw_translate_title) if raw_translate_title is not None else False

        monitor = playlist_monitor_manager.create_monitor(
            playlist_id_input=playlist_id_input,
            check_interval_minutes=check_interval,
            max_concurrency=max_concurrency,
            upload_target=upload_target,
            enabled=enabled,
            custom_title=custom_title,
            auto_upload=bool(auto_upload),
            custom_description=str(custom_description or '').strip(),
            bilibili_season_id=bilibili_season_id,
            bilibili_section_id=bilibili_section_id,
            bilibili_season_title=bilibili_season_title,
            task_interval_minutes=task_interval_minutes,
            max_import_per_check=max_import_per_check,
            import_order=import_order,
            title_pattern=str(title_pattern or '').strip(),
            title_template=str(title_template or '').strip(),
            translate_title=translate_title,
            custom_tags=custom_tags,
        )

        return jsonify({
            'success': True,
            'message': f"成功添加播放列表监控：{monitor.get('title', '')}",
            'monitor': monitor
        }), 201

    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"创建 Playlist 监控失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'创建监控失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors', methods=['GET'])
@api_login_required
def api_get_playlist_monitors():
    """
    RESTful API: 获取所有 Playlist 监控配置列表及实时任务统计
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        monitors = playlist_monitor_manager.get_monitors()
        return jsonify({
            'success': True,
            'monitors': monitors,
            'total': len(monitors)
        }), 200
    except Exception as e:
        logger.error(f"获取 Playlist 监控列表失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取监控列表失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/<int:monitor_id>', methods=['GET'])
@api_login_required
def api_get_playlist_monitor(monitor_id):
    """
    RESTful API: 获取单个 Playlist 监控配置详情
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        monitor = playlist_monitor_manager.get_monitor(monitor_id)
        if not monitor:
            return jsonify({'success': False, 'message': '监控配置不存在'}), 404
        return jsonify({
            'success': True,
            'monitor': monitor
        }), 200
    except Exception as e:
        logger.error(f"获取 Playlist 监控详情失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取详情失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/<int:monitor_id>', methods=['PUT', 'PATCH'])
@api_login_required
def api_update_playlist_monitor(monitor_id):
    """
    RESTful API: 修改 Playlist 监控配置（检测周期、最大并发、启用状态等）
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        data = request.get_json(silent=True) or {}
        if not data and request.form:
            data = request.form.to_dict()

        updated = playlist_monitor_manager.update_monitor(monitor_id, data)
        return jsonify({
            'success': True,
            'message': '监控配置已更新',
            'monitor': updated
        }), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"更新 Playlist 监控失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'更新监控配置失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/<int:monitor_id>', methods=['DELETE'])
@api_login_required
def api_delete_playlist_monitor(monitor_id):
    """
    RESTful API: 删除 Playlist 监控配置
    Query/Body: delete_tasks (bool, 可选，是否级联删除生成的任务)
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        delete_tasks = request.args.get('delete_tasks', '').lower() in ('1', 'true', 'yes')
        success = playlist_monitor_manager.delete_monitor(monitor_id, delete_tasks=delete_tasks)
        if not success:
            return jsonify({'success': False, 'message': '监控配置不存在或已删除'}), 404
        return jsonify({
            'success': True,
            'message': '监控已成功删除'
        }), 200
    except Exception as e:
        logger.error(f"删除 Playlist 监控失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'删除监控失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/<int:monitor_id>/check', methods=['POST'])
@api_login_required
def api_check_playlist_monitor_now(monitor_id):
    """
    RESTful API: 立即手动触发一次 YouTube Playlist 检测
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        res = playlist_monitor_manager.check_playlist(monitor_id, auto_add=True)
        return jsonify(res), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 400
    except Exception as e:
        logger.error(f"即时检测 Playlist 失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'即时检测失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/<int:monitor_id>/tasks', methods=['GET'])
@api_login_required
def api_get_playlist_monitor_tasks(monitor_id):
    """
    RESTful API: 查看该 Playlist 下的所有 Task
    Query 参数:
      - order: 'desc' (时间倒序，最新优先，默认) 或 'asc' (时间顺序，最早优先)
      - page: 页码 (默认1)
      - per_page: 每页数量 (默认20)
      - status: 可选，按任务状态筛选 (pending, downloading, completed, failed 等)
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager
        order = request.args.get('order', 'desc')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', type=str)

        result = playlist_monitor_manager.get_playlist_tasks(
            monitor_id=monitor_id,
            order=order,
            status=status,
            page=page,
            per_page=per_page
        )
        return jsonify({
            'success': True,
            **result
        }), 200
    except ValueError as ve:
        return jsonify({'success': False, 'message': str(ve)}), 404
    except Exception as e:
        logger.error(f"获取 Playlist 任务列表失败: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': f'获取任务列表失败: {str(e)}'}), 500


@api_bp.route('/playlist-monitors/preview', methods=['POST'])
@api_login_required
def api_preview_playlist():
    """
    RESTful API: 预览 YouTube Playlist 信息（校验 ID 并获取标题和封面）
    """
    try:
        from modules.playlist_monitor import playlist_monitor_manager, extract_playlist_id
        data = request.get_json(silent=True) or {}
        raw_input = data.get('playlist_id') or data.get('url') or ''
        clean_id = extract_playlist_id(raw_input)
        if not clean_id:
            return jsonify({'success': False, 'message': '无法解析出有效的 Playlist ID'}), 400

        details = playlist_monitor_manager.fetch_playlist_details(clean_id)
        return jsonify({
            'success': True,
            'preview': details
        }), 200
    except Exception as e:
        return jsonify({'success': False, 'message': f'解析失败: {str(e)}'}), 400


# ==========================================
# Bilibili 业务扩展 RESTful API
# ==========================================

@api_bp.route('/bilibili/seasons', methods=['GET'])
@api_login_required
def api_get_bilibili_seasons():
    """
    RESTful API: 获取当前登录 UP 主的 Bilibili 稿件合集列表
    Query 参数:
        refresh: 可选，'true' / '1' 强制跳过缓存刷新
    """
    try:
        from modules.bilibili_season import get_user_seasons
        web_app = _get_app_module()
        config = web_app.load_config()
        cookie_file = web_app.resolve_cookie_file_path(config.get('BILIBILI_COOKIES_PATH'), 'bilibili')

        refresh = request.args.get('refresh', '').lower() in ('true', '1', 'yes')
        seasons = get_user_seasons(cookie_file=cookie_file, force_refresh=refresh)
        return jsonify({
            'success': True,
            'seasons': seasons,
            'count': len(seasons)
        }), 200
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'message': '未找到 Bilibili Cookie 文件，请在系统设置中登录 Bilibili'
        }), 404
    except ValueError as ve:
        return jsonify({
            'success': False,
            'message': str(ve)
        }), 400
    except Exception as e:
        logger.error(f"获取 Bilibili 合集失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': f"获取合集失败: {str(e)}"
        }), 500


