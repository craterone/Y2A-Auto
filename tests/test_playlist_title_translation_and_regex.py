# -*- coding: utf-8 -*-
"""
单元测试：Playlist 标题同时开启翻译与正则替换
1. 翻译在正则前面执行
2. 正则表达式为空时为全匹配，翻译后的标题等于 {1}
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.playlist_monitor import apply_title_replacement
from modules.task_manager import TaskProcessor


class TestPlaylistTitleTranslationAndRegex(unittest.TestCase):
    def test_apply_title_replacement_empty_pattern_full_match(self):
        """测试正则表达式为空时为全匹配模式，{1} 等于完整标题"""
        # 1. 传入空字符串
        res1 = apply_title_replacement("动物庄园 精听课程", "", "【深度精读】{1}")
        self.assertEqual(res1, "【深度精读】动物庄园 精听课程")

        # 2. 传入 None
        res2 = apply_title_replacement("动物庄园 精听课程", None, "【深度精读】{1}")
        self.assertEqual(res2, "【深度精读】动物庄园 精听课程")

        # 3. 模板只有 {1}
        res3 = apply_title_replacement("动物庄园 精听课程", "", "{1}")
        self.assertEqual(res3, "动物庄园 精听课程")

        # 4. 支持 \\1 语法
        res4 = apply_title_replacement("Animal Farm Lesson 1", "", r"Prefix_\1_Suffix")
        self.assertEqual(res4, "Prefix_Animal Farm Lesson 1_Suffix")

        # 5. 待替换文本或模板为空
        self.assertIsNone(apply_title_replacement("", "", "模板"))
        self.assertIsNone(apply_title_replacement("标题", "", ""))
        self.assertIsNone(apply_title_replacement("标题", "", None))

    def test_apply_title_replacement_with_pattern(self):
        """测试提供具体正则表达式时的匹配与替换"""
        # 命中正则
        res = apply_title_replacement(
            "动物庄园 深度精读 第05集 完结",
            r"第(\d+)集",
            "EP{1}"
        )
        self.assertEqual(res, "EP05")

        # 未命中正则返回 None
        res_miss = apply_title_replacement(
            "动物庄园 深度精读 导读课",
            r"第(\d+)集",
            "EP{1}"
        )
        self.assertIsNone(res_miss)

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task")
    @patch("modules.playlist_monitor.playlist_monitor_manager.get_monitor")
    @patch("modules.ai_enhancer.translate_video_metadata")
    def test_simultaneous_translation_and_regex_empty_pattern(
        self, mock_translate, mock_get_monitor, mock_get_task, mock_update_task
    ):
        """
        测试同时开启翻译与正则替换（pattern 为空）：
        先执行翻译，再执行正则替换，翻译后标题作为 {1}
        """
        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": True, "TRANSLATE_DESCRIPTION": False}

        task = {
            "id": "task_full_match_test",
            "video_title_original": "Learn English with Animal Farm - Lesson 1",
            "video_title_translated": None,
            "description_original": "Sample description",
            "description_translated": None,
            "custom_description": None,
            "upload_target": "bilibili",
            "translate_title": 1,
            "playlist_monitor_id": 999,
        }
        mock_get_task.return_value = task
        mock_get_monitor.return_value = {
            "id": 999,
            "translate_title": 1,
            "title_pattern": "",  # 正则表达式留空 -> 全匹配
            "title_template": "【中英双字】{1} ｜ 英语精听",
        }
        mock_translate.return_value = {
            "success": True,
            "title": "跟着《动物庄园》学英语 - 第1课",
            "description": "",
            "requested_fields": ["title"],
        }

        logger_mock = MagicMock()
        ok = tp._translate_content("task_full_match_test", logger_mock)

        self.assertTrue(ok)
        # 检查翻译调用传入的是原始标题
        mock_translate.assert_called_once()
        self.assertEqual(mock_translate.call_args[0][0], "Learn English with Animal Farm - Lesson 1")

        # 检查最终写入的任务标题是经全匹配正则展开后的结果
        last_update_kwargs = mock_update_task.call_args_list[-1][1]
        self.assertEqual(last_update_kwargs["video_title_translated"], "【中英双字】跟着《动物庄园》学英语 - 第1课 ｜ 英语精听")

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task")
    @patch("modules.playlist_monitor.playlist_monitor_manager.get_monitor")
    @patch("modules.ai_enhancer.translate_video_metadata")
    def test_simultaneous_translation_and_regex_with_pattern_matched(
        self, mock_translate, mock_get_monitor, mock_get_task, mock_update_task
    ):
        """
        测试同时开启翻译与正则替换（pattern 具有具体正则）：
        翻译后针对翻译标题匹配正则并提取捕获组
        """
        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": True, "TRANSLATE_DESCRIPTION": False}

        task = {
            "id": "task_pattern_match_test",
            "video_title_original": "Lesson 08 Advanced Reading",
            "video_title_translated": None,
            "description_original": "",
            "description_translated": None,
            "custom_description": None,
            "upload_target": "bilibili",
            "translate_title": 1,
            "playlist_monitor_id": 888,
        }
        mock_get_task.return_value = task
        mock_get_monitor.return_value = {
            "id": 888,
            "translate_title": 1,
            "title_pattern": r"第\s*(\d+)\s*课",
            "title_template": "高级阅读专题｜第 {1} 讲",
        }
        mock_translate.return_value = {
            "success": True,
            "title": "第 08 课 高级阅读",
            "description": "",
            "requested_fields": ["title"],
        }

        logger_mock = MagicMock()
        ok = tp._translate_content("task_pattern_match_test", logger_mock)

        self.assertTrue(ok)
        last_update_kwargs = mock_update_task.call_args_list[-1][1]
        self.assertEqual(last_update_kwargs["video_title_translated"], "高级阅读专题｜第 08 讲")

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task")
    @patch("modules.playlist_monitor.playlist_monitor_manager.get_monitor")
    @patch("modules.ai_enhancer.translate_video_metadata")
    def test_simultaneous_translation_and_regex_pattern_unmatched_fallback(
        self, mock_translate, mock_get_monitor, mock_get_task, mock_update_task
    ):
        """
        测试同时开启翻译与正则替换时，正则未命中应回退保留翻译后的标题
        """
        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": True, "TRANSLATE_DESCRIPTION": False}

        task = {
            "id": "task_unmatched_fallback_test",
            "video_title_original": "Introduction to the Course",
            "video_title_translated": None,
            "description_original": "",
            "description_translated": None,
            "custom_description": None,
            "upload_target": "bilibili",
            "translate_title": 1,
            "playlist_monitor_id": 777,
        }
        mock_get_task.return_value = task
        mock_get_monitor.return_value = {
            "id": 777,
            "translate_title": 1,
            "title_pattern": r"第\s*(\d+)\s*课",
            "title_template": "高级阅读专题｜第 {1} 讲",
        }
        mock_translate.return_value = {
            "success": True,
            "title": "课程导论与前言",
            "description": "",
            "requested_fields": ["title"],
        }

        logger_mock = MagicMock()
        ok = tp._translate_content("task_unmatched_fallback_test", logger_mock)

        self.assertTrue(ok)
        last_update_kwargs = mock_update_task.call_args_list[-1][1]
        # 未命中 pattern，保留原翻译标题
        self.assertEqual(last_update_kwargs["video_title_translated"], "课程导论与前言")

    @patch("modules.task_manager.update_task")
    @patch("modules.playlist_monitor.playlist_monitor_manager.get_monitor")
    def test_apply_playlist_overrides_delays_regex_when_translation_enabled(
        self, mock_get_monitor, mock_update_task
    ):
        """
        测试在 _apply_playlist_overrides 阶段，若开启了标题翻译，应延后正则替换，不写入 video_title_translated
        """
        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": True}

        task = {
            "id": "task_delay_test",
            "video_title_original": "Original Title",
            "video_title_translated": None,
            "custom_description": None,
            "playlist_monitor_id": 666,
            "translate_title": 1,  # 开启了标题翻译
        }
        mock_get_monitor.return_value = {
            "id": 666,
            "title_pattern": "",
            "title_template": "【全匹配】{1}",
            "custom_description": "统一简介内容",
        }

        logger_mock = MagicMock()
        tp._apply_playlist_overrides("task_delay_test", task, logger_mock)

        # 验证 updates 只写入了 custom_description，未提前写入 video_title_translated
        mock_update_task.assert_called_once()
        updates = mock_update_task.call_args[1]
        self.assertEqual(updates.get("custom_description"), "统一简介内容")
        self.assertNotIn("video_title_translated", updates)

    @patch("modules.task_manager.update_task")
    @patch("modules.playlist_monitor.playlist_monitor_manager.get_monitor")
    def test_apply_playlist_overrides_applies_regex_when_translation_disabled(
        self, mock_get_monitor, mock_update_task
    ):
        """
        测试在 _apply_playlist_overrides 阶段，若未开启标题翻译，直接对原标题执行正则替换
        """
        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": False}

        task = {
            "id": "task_no_trans_test",
            "video_title_original": "Chapter 01 Introduction",
            "video_title_translated": None,
            "custom_description": None,
            "playlist_monitor_id": 555,
            "translate_title": 0,  # 未开启标题翻译
        }
        mock_get_monitor.return_value = {
            "id": 555,
            "title_pattern": "",  # 全匹配
            "title_template": "【第一季】{1}",
            "custom_description": None,
        }

        logger_mock = MagicMock()
        tp._apply_playlist_overrides("task_no_trans_test", task, logger_mock)

        # 验证 updates 直接对原标题全匹配替换
        mock_update_task.assert_called_once()
        updates = mock_update_task.call_args[1]
        self.assertEqual(updates.get("video_title_translated"), "【第一季】Chapter 01 Introduction")


if __name__ == "__main__":
    unittest.main()
