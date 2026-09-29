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


if __name__ == '__main__':
    unittest.main()
