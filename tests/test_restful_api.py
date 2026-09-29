"""
RESTful API 单元测试与回归测试
测试内容包括：
1. 原有模板页面在未登录时的重定向行为（确保原有 template 功能不受影响）
2. 登录 API (/api/login, /api/auth/login)
3. 注销 API (/api/logout)
4. 认证状态 API (/api/auth/status)
5. 添加任务 API (/api/tasks, /api/tasks/add)
6. 任务查询 API (/api/tasks, /api/tasks/<task_id>)
"""
import json
import unittest
from unittest.mock import patch, MagicMock

import app as web_app


class RestfulApiTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config['TESTING'] = True
        web_app.app.config['SECRET_KEY'] = 'test-secret-key'
        self.client = web_app.app.test_client()

    def test_original_template_redirect_when_not_logged_in(self):
        """测试原有模板路由在未登录时依然执行 302 重定向到登录页"""
        fake_config = {'password_protection_enabled': True, 'password': 'mypassword'}
        with patch.object(web_app, 'load_config', return_value=fake_config):
            response = self.client.get('/tasks', follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertIn('/login', response.headers.get('Location', ''))

    def test_api_unauthorized_returns_401_json(self):
        """测试 API 请求在未登录时返回 401 JSON，而非 302 重定向"""
        fake_config = {'password_protection_enabled': True, 'password': 'mypassword'}
        with patch.object(web_app, 'load_config', return_value=fake_config):
            # 访问 /api/tasks
            response = self.client.get('/api/tasks')
            self.assertEqual(response.status_code, 401)
            data = response.get_json()
            self.assertFalse(data['success'])
            self.assertIn('未登录', data['message'])

            # POST /api/tasks 未登录
            post_response = self.client.post('/api/tasks', json={'youtube_url': 'https://www.youtube.com/watch?v=abc'})
            self.assertEqual(post_response.status_code, 401)
            post_data = post_response.get_json()
            self.assertFalse(post_data['success'])

    def test_api_login_no_password_protection(self):
        """测试系统未启用密码保护时直接登录成功"""
        fake_config = {'password_protection_enabled': False}
        with patch.object(web_app, 'load_config', return_value=fake_config):
            response = self.client.post('/api/login', json={})
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertTrue(data['success'])
            self.assertTrue(data['logged_in'])

    def test_api_login_flow_with_password(self):
        """测试启用密码保护时的登录流程：密码错误、达到阈值锁定、成功登录"""
        fake_config = {
            'password_protection_enabled': True,
            'password': 'secret_password',
            'LOGIN_MAX_FAILED_ATTEMPTS': 3,
            'LOGIN_LOCKOUT_MINUTES': 10
        }
        sec_state = {'failed_attempts': 0, 'locked_until': 0, 'last_attempt': 0}

        def mock_load_sec():
            return dict(sec_state)

        def mock_save_sec(s):
            sec_state.update(s)
            return True

        with patch.object(web_app, 'load_config', return_value=fake_config), \
             patch.object(web_app, '_load_security_state', side_effect=mock_load_sec), \
             patch.object(web_app, '_save_security_state', side_effect=mock_save_sec), \
             patch.object(web_app, '_emit_login_event'):

            # 1. 缺少密码
            res = self.client.post('/api/login', json={'password': ''})
            self.assertEqual(res.status_code, 400)
            self.assertFalse(res.get_json()['success'])

            # 2. 密码错误 1 次
            res1 = self.client.post('/api/login', json={'password': 'wrong'})
            self.assertEqual(res1.status_code, 401)
            data1 = res1.get_json()
            self.assertFalse(data1['success'])
            self.assertEqual(data1['remaining_attempts'], 2)

            # 3. 密码错误 2 次
            res2 = self.client.post('/api/login', json={'password': 'wrong'})
            self.assertEqual(res2.status_code, 401)
            self.assertEqual(res2.get_json()['remaining_attempts'], 1)

            # 4. 密码错误第 3 次（达到锁定阈值）
            res3 = self.client.post('/api/login', json={'password': 'wrong'})
            self.assertEqual(res3.status_code, 423)
            data3 = res3.get_json()
            self.assertTrue(data3['locked'])

            # 5. 锁定状态下再次尝试登录
            res4 = self.client.post('/api/login', json={'password': 'secret_password'})
            self.assertEqual(res4.status_code, 423)
            self.assertTrue(res4.get_json()['locked'])

            # 解除锁定
            sec_state['locked_until'] = 0
            sec_state['failed_attempts'] = 0

            # 6. 正确密码成功登录
            res5 = self.client.post('/api/login', json={'password': 'secret_password'})
            self.assertEqual(res5.status_code, 200)
            data5 = res5.get_json()
            self.assertTrue(data5['success'])
            self.assertTrue(data5['logged_in'])

    def test_api_logout_and_auth_status(self):
        """测试注销与登录状态查询 API"""
        fake_config = {'password_protection_enabled': True, 'password': '123'}
        with patch.object(web_app, 'load_config', return_value=fake_config):
            with self.client.session_transaction() as sess:
                sess['logged_in'] = True

            # 查询状态：已登录
            status_res = self.client.get('/api/auth/status')
            self.assertEqual(status_res.status_code, 200)
            self.assertTrue(status_res.get_json()['logged_in'])

            # 注销
            logout_res = self.client.post('/api/logout')
            self.assertEqual(logout_res.status_code, 200)
            self.assertTrue(logout_res.get_json()['success'])

            # 再次查询状态：未登录
            status_res2 = self.client.get('/api/auth/status')
            self.assertEqual(status_res2.status_code, 200)
            self.assertFalse(status_res2.get_json()['logged_in'])

    def test_api_add_task_validation(self):
        """测试添加任务 API 的参数校验"""
        fake_config = {'password_protection_enabled': False, 'UPLOAD_TARGET_DEFAULT': 'acfun'}
        with patch.object(web_app, 'load_config', return_value=fake_config):
            with self.client.session_transaction() as sess:
                sess['logged_in'] = True

            # 1. 缺少 URL
            res1 = self.client.post('/api/tasks', json={'youtube_url': ''})
            self.assertEqual(res1.status_code, 400)
            self.assertIn('不能为空', res1.get_json()['message'])

            # 2. 无效的 upload_target
            res2 = self.client.post('/api/tasks', json={
                'youtube_url': 'https://www.youtube.com/watch?v=123',
                'upload_target': 'invalid_platform'
            })
            self.assertEqual(res2.status_code, 400)
            self.assertIn('无效的投稿平台参数', res2.get_json()['message'])

    def test_api_add_single_task_success(self):
        """测试添加单个视频任务成功"""
        fake_config = {
            'password_protection_enabled': False,
            'UPLOAD_TARGET_DEFAULT': 'acfun',
            'AUTO_MODE_ENABLED': False
        }
        with patch.object(web_app, 'load_config', return_value=fake_config), \
             patch.object(web_app, 'add_task', return_value='task-uuid-123') as mock_add, \
             patch.object(web_app, 'start_task') as mock_start:

            with self.client.session_transaction() as sess:
                sess['logged_in'] = True

            # 添加任务（不立即启动）
            res = self.client.post('/api/tasks', json={
                'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'upload_target': 'bilibili',
                'auto_start': False
            })
            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertEqual(data['task_id'], 'task-uuid-123')
            self.assertFalse(data['started'])
            mock_add.assert_called_once_with('https://www.youtube.com/watch?v=dQw4w9WgXcQ', upload_target='bilibili')
            mock_start.assert_not_called()

            # 添加任务（显式要求立即启动）
            res_start = self.client.post('/api/tasks/add', json={
                'youtube_url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
                'upload_target': 'both',
                'auto_start': True
            })
            self.assertEqual(res_start.status_code, 201)
            data_start = res_start.get_json()
            self.assertTrue(data_start['started'])
            mock_start.assert_called_once()

    def test_api_add_playlist_tasks_success(self):
        """测试添加播放列表任务成功"""
        fake_config = {
            'password_protection_enabled': False,
            'UPLOAD_TARGET_DEFAULT': 'acfun',
            'AUTO_MODE_ENABLED': False,
            'YOUTUBE_COOKIES_PATH': ''
        }
        playlist_videos = [
            'https://www.youtube.com/watch?v=vid1',
            'https://www.youtube.com/watch?v=vid2'
        ]
        with patch.object(web_app, 'load_config', return_value=fake_config), \
             patch.object(web_app, 'extract_video_urls_from_playlist', return_value=playlist_videos), \
             patch.object(web_app, 'add_task', side_effect=['task-1', 'task-2']), \
             patch.object(web_app, 'start_task') as mock_start:

            with self.client.session_transaction() as sess:
                sess['logged_in'] = True

            res = self.client.post('/api/tasks', json={
                'youtube_url': 'https://www.youtube.com/playlist?list=PL123456',
                'auto_start': True
            })
            self.assertEqual(res.status_code, 201)
            data = res.get_json()
            self.assertTrue(data['success'])
            self.assertTrue(data['is_playlist'])
            self.assertEqual(data['count'], 2)
            self.assertEqual(data['task_ids'], ['task-1', 'task-2'])
            self.assertEqual(mock_start.call_count, 2)

    def test_api_get_tasks_and_detail(self):
        """测试任务列表与详情查询 API"""
        fake_config = {'password_protection_enabled': False}
        fake_pagination = {
            'tasks': [{'id': 'task-1', 'youtube_url': 'https://...' }],
            'total': 1,
            'page': 1,
            'per_page': 20,
            'total_pages': 1
        }
        fake_single_task = {'id': 'task-1', 'status': 'completed'}

        with patch.object(web_app, 'load_config', return_value=fake_config), \
             patch.object(web_app, 'get_tasks_paginated', return_value=fake_pagination), \
             patch.object(web_app, 'get_task', side_effect=lambda tid: fake_single_task if tid == 'task-1' else None):

            with self.client.session_transaction() as sess:
                sess['logged_in'] = True

            # 获取列表
            res_list = self.client.get('/api/tasks?page=1&per_page=10')
            self.assertEqual(res_list.status_code, 200)
            self.assertEqual(len(res_list.get_json()['tasks']), 1)

            # 获取存在任务详情
            res_detail = self.client.get('/api/tasks/task-1')
            self.assertEqual(res_detail.status_code, 200)
            self.assertEqual(res_detail.get_json()['task']['id'], 'task-1')

            # 获取不存在任务详情
            res_not_found = self.client.get('/api/tasks/non-exist')
            self.assertEqual(res_not_found.status_code, 404)


if __name__ == '__main__':
    unittest.main()
