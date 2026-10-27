import json
import unittest
from unittest.mock import MagicMock, patch

from modules.ai_enhancer import (
    _build_metadata_translation_payload,
    _build_metadata_translation_system_prompt,
    translate_video_metadata,
)
from modules.prompt_manager import get_metadata_translate_prompt


class TitleOnlyTranslationTests(unittest.TestCase):
    def test_prompt_manager_default_excludes_description(self):
        # 默认标题翻译 Prompt 绝不能带 description
        prompt = get_metadata_translate_prompt(target_language="zh")
        self.assertIn("视频标题翻译器", prompt)
        self.assertIn('只返回 JSON：{"title":""}。', prompt)
        self.assertNotIn("description", prompt)
        self.assertNotIn("自然简介", prompt)

    def test_build_metadata_translation_system_prompt_title_only(self):
        prompt = _build_metadata_translation_system_prompt("zh-CN", retry=False, include_description=False)
        self.assertIn("视频标题翻译器", prompt)
        self.assertIn('{"title":""}', prompt)
        self.assertNotIn("description", prompt)

    def test_build_metadata_translation_payload_title_only(self):
        payload = _build_metadata_translation_payload(
            title="My Video Title",
            description="Long video description with promo links",
            target_language="zh-CN",
            translate_title=True,
            translate_description=False,
        )
        self.assertEqual(payload, {
            "target_language": "zh-CN",
            "title": "My Video Title",
        })
        self.assertNotIn("description", payload)

    @patch("modules.ai_enhancer.get_openai_client")
    @patch("modules.ai_enhancer.openai_chat_create_with_thinking_control")
    def test_translate_video_metadata_title_only_calls_llm_without_description(
        self, mock_create, mock_get_client
    ):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # 模拟 LLM 仅返回标题 JSON
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message = MagicMock()
        mock_choice.message.content = json.dumps({"title": "我的视频标题"}, ensure_ascii=False)
        mock_response.choices = [mock_choice]
        mock_create.return_value = mock_response

        openai_config = {
            "OPENAI_API_KEY": "fake-key",
            "OPENAI_MODEL_NAME": "gpt-3.5-turbo",
        }

        result = translate_video_metadata(
            title="My Video Title",
            description="This is a description that should not be translated",
            target_language="zh-CN",
            openai_config=openai_config,
            task_id="test_task_title_only",
            translate_title=True,
            translate_description=False,
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["title"], "我的视频标题")
        self.assertEqual(result["description"], "")
        self.assertEqual(result["requested_fields"], ["title"])

        # 检查传入大模型的参数
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]["create_kwargs"]
        messages = call_kwargs["messages"]

        # system prompt 检查
        system_content = messages[0]["content"]
        self.assertIn("视频标题翻译器", system_content)
        self.assertNotIn("description", system_content)
        self.assertIn('{"title":""}', system_content)

        # user payload 检查
        user_content = json.loads(messages[1]["content"])
        self.assertIn("title", user_content)
        self.assertNotIn("description", user_content)

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task")
    @patch("modules.ai_enhancer.translate_video_metadata")
    def test_task_manager_translate_content_passes_empty_description_when_title_only(
        self, mock_translate, mock_get_task, mock_update_task
    ):
        from modules.task_manager import TaskProcessor

        tp = TaskProcessor.__new__(TaskProcessor)
        tp.config = {"TRANSLATE_TITLE": True, "TRANSLATE_DESCRIPTION": False}

        task = {
            "id": "task_123",
            "video_title_original": "Original Title",
            "video_title_translated": None,
            "description_original": "Should be ignored description",
            "description_translated": None,
            "custom_description": None,
            "upload_target": "bilibili",
            "translate_title": 1,
        }
        mock_get_task.return_value = task
        mock_translate.return_value = {
            "success": True,
            "title": "翻译后的标题",
            "description": "",
            "requested_fields": ["title"],
        }

        logger_mock = MagicMock()
        ok = tp._translate_content("task_123", logger_mock)

        self.assertTrue(ok)
        mock_translate.assert_called_once()
        # 验证调用 translate_video_metadata 时：第二个参数（描述）为空字符串，且 translate_description=False
        args, kwargs = mock_translate.call_args
        self.assertEqual(args[0], "Original Title")
        self.assertEqual(args[1], "")  # 描述被清空移除
        self.assertTrue(kwargs["translate_title"])
        self.assertFalse(kwargs["translate_description"])


if __name__ == "__main__":
    unittest.main()

