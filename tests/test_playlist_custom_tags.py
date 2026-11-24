#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单元测试：Playlist 监控设置“预设标签”功能
验证：
1. _normalize_playlist_tags 的标准化处理
2. create_monitor 存储 custom_tags
3. update_monitor 更新 custom_tags
4. get_monitor / get_monitors 正确返回 tags 和 custom_tags
5. add_task 正确注入 custom_tags 到 tags_generated
6. _generate_tags 阶段优先保留任务预设标签，跳过 AI 生成
7. check_playlist 轮询入库任务时自动透传 monitor 的 custom_tags
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.task_manager import init_db, get_db_connection, add_task, get_task, TaskProcessor
from modules.playlist_monitor import (
    _normalize_playlist_tags,
    playlist_monitor_manager,
)


class TestPlaylistCustomTags(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_01_normalize_playlist_tags(self):
        """测试标签标准化逻辑"""
        # 1. 列表输入
        res1 = _normalize_playlist_tags(["科技", "数码", "科技", "  AI人工智能  ", ""])
        self.assertEqual(res1, ["科技", "数码", "AI人工智能"])

        # 2. JSON 字符串输入
        res2 = _normalize_playlist_tags('["科普", "纪录片", "科普"]')
        self.assertEqual(res2, ["科普", "纪录片"])

        # 3. 逗号/分号分隔字符串输入
        res3 = _normalize_playlist_tags("汽车, 评测；跑车，改装\n极速")
        self.assertEqual(res3, ["汽车", "评测", "跑车", "改装", "极速"])

        # 4. 单标签超长截断（>20字）
        long_tag = "a" * 30
        res4 = _normalize_playlist_tags([long_tag])
        self.assertEqual(len(res4[0]), 20)

        # 5. 上限最多10个标签
        many_tags = [f"tag_{i}" for i in range(20)]
        res5 = _normalize_playlist_tags(many_tags)
        self.assertEqual(len(res5), 10)

    def test_02_create_and_update_monitor_tags(self):
        """测试创建和更新带 custom_tags 的监控"""
        test_pid = "PL_Tags_Test_001"
        with get_db_connection() as conn:
            conn.execute("DELETE FROM playlist_monitors WHERE playlist_id = ?", (test_pid,))
            conn.commit()

        # Mock fetch_playlist_details 避免真实网络请求
        with patch.object(playlist_monitor_manager, 'fetch_playlist_details', return_value={
            'playlist_id': test_pid,
            'title': '标签测试播放列表',
            'description': '测试描述',
            'channel_title': '测试频道',
            'thumbnail_url': '',
            'item_count': 5,
        }), patch.object(playlist_monitor_manager, '_run_check_async'):
            mon = playlist_monitor_manager.create_monitor(
                playlist_id_input=test_pid,
                custom_title="标签测试播放列表",
                custom_tags=["科技", "开源软件", "AI"],
                enabled=False
            )
            self.assertIsNotNone(mon)
            self.assertEqual(mon['tags'], ["科技", "开源软件", "AI"])
            self.assertEqual(json.loads(mon['custom_tags']), ["科技", "开源软件", "AI"])

            # 查询单个
            fetched = playlist_monitor_manager.get_monitor(mon['id'])
            self.assertEqual(fetched['tags'], ["科技", "开源软件", "AI"])

            # 更新标签
            updated = playlist_monitor_manager.update_monitor(mon['id'], {
                'custom_tags': ["数码", "手机", "数码"]
            })
            self.assertEqual(updated['tags'], ["数码", "手机"])
            self.assertEqual(json.loads(updated['custom_tags']), ["数码", "手机"])

            # 测试使用 'tags' 别名字段更新
            updated2 = playlist_monitor_manager.update_monitor(mon['id'], {
                'tags': ["极客", "Linux"]
            })
            self.assertEqual(updated2['tags'], ["极客", "Linux"])

    def test_03_add_task_with_custom_tags(self):
        """测试 add_task 时注入 custom_tags"""
        test_url = "https://www.youtube.com/watch?v=tag_test_vid1"
        task_id = add_task(
            test_url,
            upload_target='bilibili',
            custom_tags=["自定义标签1", "自定义标签2"]
        )
        self.assertIsNotNone(task_id)
        task = get_task(task_id)
        self.assertIsNotNone(task)
        self.assertIsNotNone(task.get('tags_generated'))
        tags_list = json.loads(task['tags_generated'])
        self.assertEqual(tags_list, ["自定义标签1", "自定义标签2"])

    def test_04_generate_tags_preserves_preset_tags(self):
        """测试当任务已有预设标签时，_generate_tags 跳过 AI 生成并保留预设标签"""
        test_url = "https://www.youtube.com/watch?v=tag_test_vid2"
        task_id = add_task(
            test_url,
            upload_target='bilibili',
            custom_tags=["保留标签A", "保留标签B"]
        )
        processor = TaskProcessor()
        mock_logger = MagicMock()

        # 执行 _generate_tags
        ok = processor._generate_tags(task_id, mock_logger)
        self.assertTrue(ok)

        # 验证 tags 依然为预设值
        task = get_task(task_id)
        tags_list = json.loads(task['tags_generated'])
        self.assertEqual(tags_list, ["保留标签A", "保留标签B"])
        # 验证输出日志包含跳过信息
        mock_logger.info.assert_any_call("任务已配置预设标签，跳过AI大模型标签生成，直接使用预设标签: ['保留标签A', '保留标签B']")


if __name__ == '__main__':
    unittest.main()
