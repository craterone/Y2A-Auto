#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单元测试：Bilibili 合集读取、选择与配置功能测试
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.task_manager import init_db, get_db_connection, add_task, get_task, update_task
from modules.playlist_monitor import playlist_monitor_manager
from modules.bilibili_season import get_user_seasons, add_video_to_season, _SEASONS_CACHE
import app as flask_app_module


class TestBilibiliSeason(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        flask_app_module.app.config['TESTING'] = True
        cls.client = flask_app_module.app.test_client()

    def setUp(self):
        # 登录 session mock
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True

    def test_01_database_columns_tasks(self):
        """测试 tasks 表是否已正确新增合集相关字段"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tasks)")
        cols = {r[1] for r in cursor.fetchall()}
        conn.close()

        self.assertIn("bilibili_season_id", cols)
        self.assertIn("bilibili_section_id", cols)
        self.assertIn("bilibili_season_title", cols)

    def test_02_database_columns_playlist_monitors(self):
        """测试 playlist_monitors 表是否已正确新增合集相关字段"""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(playlist_monitors)")
        cols = {r[1] for r in cursor.fetchall()}
        conn.close()

        self.assertIn("bilibili_season_id", cols)
        self.assertIn("bilibili_section_id", cols)
        self.assertIn("bilibili_season_title", cols)

    def test_03_add_task_with_season(self):
        """测试创建任务时保存合集字段并在获取时正确返回"""
        task_id = add_task(
            youtube_url="https://www.youtube.com/watch?v=test_season_123",
            upload_target="bilibili",
            bilibili_season_id=98765,
            bilibili_section_id=54321,
            bilibili_season_title="我的测试合集",
        )
        self.assertIsNotNone(task_id)

        task = get_task(task_id)
        self.assertEqual(task["bilibili_season_id"], 98765)
        self.assertEqual(task["bilibili_section_id"], 54321)
        self.assertEqual(task["bilibili_season_title"], "我的测试合集")

        # 测试 update_task 更新合集
        update_task(task_id, bilibili_season_title="已更名合集")
        updated_task = get_task(task_id)
        self.assertEqual(updated_task["bilibili_season_title"], "已更名合集")

    def test_04_playlist_monitor_with_season(self):
        """测试创建与更新 Playlist 监控时保存合集字段"""
        test_pid = "PL_Test_Season_Monitor_001"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        mon = playlist_monitor_manager.create_monitor(
            playlist_id_input=test_pid,
            check_interval_minutes=30,
            max_concurrency=1,
            upload_target='bilibili',
            enabled=True,
            custom_title="合集监控测试",
            bilibili_season_id=112233,
            bilibili_section_id=445566,
            bilibili_season_title="自动入库合集",
        )
        self.assertEqual(mon["bilibili_season_id"], 112233)
        self.assertEqual(mon["bilibili_section_id"], 445566)
        self.assertEqual(mon["bilibili_season_title"], "自动入库合集")

        # 更新合集信息
        mon_updated = playlist_monitor_manager.update_monitor(mon["id"], {
            "bilibili_season_id": 998877,
            "bilibili_season_title": "更新后的合集"
        })
        self.assertEqual(mon_updated["bilibili_season_id"], 998877)
        self.assertEqual(mon_updated["bilibili_season_title"], "更新后的合集")

    @patch("modules.bilibili_season.load_cookie_dict")
    @patch("modules.bilibili_season.requests.get")
    def test_05_get_user_seasons_parsing(self, mock_get, mock_cookies):
        """测试从创作中心接口读取合集列表的结构化解析"""
        mock_cookies.return_value = {
            "SESSDATA": "mock_sessdata",
            "bili_jct": "mock_jct",
            "DedeUserID": "12345678"
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "data": {
                "seasons": [
                    {
                        "season": {
                            "id": 88888,
                            "title": "计算机系统导论",
                            "desc": "深入理解计算机系统",
                            "cover": "https://i0.hdslb.com/cover.jpg",
                            "ep_num": 10,
                        },
                        "sections": {
                            "sections": [
                                {
                                    "id": 99999,
                                    "title": "正片",
                                    "order": 1,
                                    "epCount": 10
                                }
                            ]
                        }
                    }
                ],
                "total": 1
            }
        }
        mock_get.return_value = mock_resp

        # 强制跳过缓存刷新
        seasons = get_user_seasons(cookie_file="/mock/cookie.json", force_refresh=True)
        self.assertEqual(len(seasons), 1)
        self.assertEqual(seasons[0]["season_id"], 88888)
        self.assertEqual(seasons[0]["title"], "计算机系统导论")
        self.assertEqual(seasons[0]["ep_num"], 10)
        self.assertEqual(len(seasons[0]["sections"]), 1)
        self.assertEqual(seasons[0]["sections"][0]["section_id"], 99999)

    @patch("modules.bilibili_season.load_cookie_dict")
    @patch("modules.bilibili_season.requests.post")
    def test_06_add_video_to_season(self, mock_post, mock_cookies):
        """测试调用接口将视频加入合集小节"""
        mock_cookies.return_value = {
            "SESSDATA": "mock_sessdata",
            "bili_jct": "mock_jct",
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": 0,
            "message": "0"
        }
        mock_post.return_value = mock_resp

        ok, msg = add_video_to_season(
            season_id=88888,
            section_id=99999,
            aid=1234567,
            bvid="BV1mocktest",
            title="测试视频",
            cookie_file="/mock/cookie.json"
        )
        self.assertTrue(ok)
        self.assertIn("成功", msg)

        # 验证 post 请求参数
        called_args, called_kwargs = mock_post.call_args
        self.assertEqual(called_kwargs["json"]["section_id"], 99999)
        self.assertEqual(called_kwargs["json"]["episodes"][0]["bvid"], "BV1mocktest")
        self.assertEqual(called_kwargs["params"]["csrf"], "mock_jct")

    @patch("modules.bilibili_season.get_user_seasons")
    def test_07_restful_api_get_seasons(self, mock_get_seasons):
        """测试 RESTful API: GET /api/bilibili/seasons"""
        mock_get_seasons.return_value = [
            {
                "season_id": 1001,
                "title": "API测试合集",
                "desc": "测试描述",
                "ep_num": 5,
                "sections": [{"section_id": 2001, "title": "第一章", "ep_count": 5}]
            }
        ]

        resp = self.client.get("/api/bilibili/seasons")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["seasons"][0]["title"], "API测试合集")

    def test_08_restful_api_create_task_with_season(self):
        """测试 RESTful API: POST /api/tasks 携带合集信息"""
        resp = self.client.post("/api/tasks", json={
            "youtube_url": "https://www.youtube.com/watch?v=api_season_test",
            "upload_target": "bilibili",
            "auto_start": False,
            "bilibili_season_id": 5566,
            "bilibili_section_id": 7788,
            "bilibili_season_title": "通过API创建的任务合集"
        })
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertTrue(data["success"])
        task_id = data["task_id"]

        task = get_task(task_id)
        self.assertEqual(task["bilibili_season_id"], 5566)
        self.assertEqual(task["bilibili_section_id"], 7788)
        self.assertEqual(task["bilibili_season_title"], "通过API创建的任务合集")


if __name__ == '__main__':
    unittest.main()
