import os
import unittest
from unittest.mock import MagicMock, patch

from modules.task_manager import (
    TaskProcessor,
    TASK_STATES,
    get_task,
    add_task,
    delete_task,
    is_members_only_error,
)
from modules.notifications import (
    build_notification_message,
    NotificationEvent,
    EVENT_TASK_COMPLETED,
)
from modules.task_manager import _build_task_notification_payload


class MembersOnlyDetectionTests(unittest.TestCase):
    def test_members_only_indicators(self):
        cases = [
            "yt-dlp执行错误: ERROR: [youtube] od1fYxQqtM4: Join this channel to get access to members-only content like this video, and other exclusive perks.",
            "ERROR: [youtube] abc123xyz: Join this channel to get access to members-only content",
            "This video is available to this channel's members on level VIP",
            "members-only content",
            "members only",
            "join this channel to get access",
            "仅限会员观看",
            "会员专享内容",
            "这是会员专属视频",
        ]
        for msg in cases:
            with self.subTest(msg=msg):
                self.assertTrue(is_members_only_error(msg), f"应该被识别为 members-only: {msg}")

    def test_non_members_only_errors(self):
        cases = [
            "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable",
            "HTTP Error 404: Not Found",
            "timed out",
            "Sign in to confirm you're not a bot",
            "Requested format is not available",
            "ffmpeg not found",
            "",
            None,
            {},
        ]
        for msg in cases:
            with self.subTest(msg=msg):
                self.assertFalse(is_members_only_error(msg), f"不应该被误判为 members-only: {msg}")


class MembersOnlyTaskProcessingTests(unittest.TestCase):
    def setUp(self):
        self.processor = TaskProcessor(config={
            "YOUTUBE_COOKIES_PATH": "cookies/yt_cookies.txt",
            "MAX_CONCURRENT_TASKS": 1,
            "MAX_CONCURRENT_UPLOADS": 1,
        })
        self.mock_logger = MagicMock()
        self.created_task_ids = []

    def tearDown(self):
        if hasattr(self.processor, "scheduler") and self.processor.scheduler.running:
            self.processor.scheduler.shutdown(wait=False)
        for tid in self.created_task_ids:
            try:
                delete_task(tid, delete_files=False)
            except Exception:
                pass

    def test_mark_task_members_only_for_bilibili(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="bilibili")
        self.created_task_ids.append(task_id)

        self.processor._mark_task_members_only(task_id, self.mock_logger)
        task = get_task(task_id)

        self.assertEqual(task["status"], TASK_STATES["COMPLETED"])
        self.assertEqual(task["bilibili_upload_response"], "members-only")
        self.assertIsNone(task["error_message"])

    def test_mark_task_members_only_for_acfun(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="acfun")
        self.created_task_ids.append(task_id)

        self.processor._mark_task_members_only(task_id, self.mock_logger)
        task = get_task(task_id)

        self.assertEqual(task["status"], TASK_STATES["COMPLETED"])
        self.assertEqual(task["acfun_upload_response"], "members-only")
        self.assertIsNone(task["error_message"])

    def test_mark_task_members_only_for_both(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="both")
        self.created_task_ids.append(task_id)

        self.processor._mark_task_members_only(task_id, self.mock_logger)
        task = get_task(task_id)

        self.assertEqual(task["status"], TASK_STATES["COMPLETED"])
        self.assertEqual(task["bilibili_upload_response"], "members-only")
        self.assertEqual(task["acfun_upload_response"], "members-only")
        self.assertIsNone(task["error_message"])

    def test_download_video_file_skips_on_members_only(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="bilibili")
        self.created_task_ids.append(task_id)

        error_msg = "yt-dlp执行错误: ERROR: [youtube] od1fYxQqtM4: Join this channel to get access to members-only content like this video, and other exclusive perks."
        with patch.object(self.processor, "_download_video_data_with_cookie_fallback", return_value=(False, error_msg)):
            self.processor._download_video_file(task_id, "https://www.youtube.com/watch?v=od1fYxQqtM4", self.mock_logger)

        task = get_task(task_id)
        self.assertEqual(task["status"], TASK_STATES["COMPLETED"])
        self.assertEqual(task["bilibili_upload_response"], "members-only")
        self.assertIsNone(task["error_message"])
        self.assertIsNone(task["upload_progress"])

    def test_fetch_video_info_skips_on_members_only(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="bilibili")
        self.created_task_ids.append(task_id)

        error_msg = "yt-dlp执行错误: ERROR: [youtube] od1fYxQqtM4: Join this channel to get access to members-only content like this video, and other exclusive perks."
        with patch.object(self.processor, "_download_video_data_with_cookie_fallback", return_value=(False, error_msg)):
            self.processor._fetch_video_info(task_id, "https://www.youtube.com/watch?v=od1fYxQqtM4", self.mock_logger)

        task = get_task(task_id)
        self.assertEqual(task["status"], TASK_STATES["COMPLETED"])
        self.assertEqual(task["bilibili_upload_response"], "members-only")
        self.assertIsNone(task["error_message"])

    def test_cookie_fallback_no_cookie_returns_without_error_log(self):
        task_id = add_task("https://www.youtube.com/watch?v=od1fYxQqtM4", upload_target="bilibili")
        self.created_task_ids.append(task_id)

        error_msg = "yt-dlp执行错误: ERROR: [youtube] od1fYxQqtM4: Join this channel to get access to members-only content like this video, and other exclusive perks."
        with patch("modules.youtube_handler.download_video_data", return_value=(False, error_msg)), \
             patch.object(self.processor, "_get_valid_youtube_cookies_path", return_value=None):
            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=task_id,
                youtube_url="https://www.youtube.com/watch?v=od1fYxQqtM4",
                task_logger=self.mock_logger,
            )

        self.assertFalse(success)
        self.assertTrue(is_members_only_error(result))
        # 应该记录为 info 而不是 error
        self.mock_logger.error.assert_not_called()

    def test_notification_payload_and_render_members_only(self):
        task_dict = {
            "id": "task-test-members",
            "youtube_url": "https://www.youtube.com/watch?v=od1fYxQqtM4",
            "upload_target": "bilibili",
            "status": "completed",
            "video_title_original": "Members Only Video Title",
            "bilibili_upload_response": "members-only",
        }
        payload = _build_task_notification_payload(task_dict)
        self.assertTrue(payload["members_only"])
        self.assertFalse(payload["bilibili_uploaded"])

        event = NotificationEvent(event_type=EVENT_TASK_COMPLETED, payload=payload)
        msg = build_notification_message(event)
        self.assertIn("members-only", msg.summary)
        self.assertIn("members-only", msg.markdown)


class MembersOnlyTemplateRenderingTests(unittest.TestCase):
    def setUp(self):
        import app as web_app
        self.web_app = web_app
        self.web_app.app.config['TESTING'] = True
        self.app_context = self.web_app.app.test_request_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_task_row_renders_members_only_badge(self):
        from flask import render_template
        task = {
            "id": "test-task-row-members",
            "youtube_url": "https://www.youtube.com/watch?v=od1fYxQqtM4",
            "upload_target": "bilibili",
            "status": "completed",
            "video_title_original": "Members Only Video Title",
            "video_title_translated": "会员专属视频",
            "bilibili_upload_response": "members-only",
            "acfun_upload_response": None,
            "error_message": None,
            "upload_progress": None,
            "subtitle_qc_score": None,
            "subtitle_qc_reason": None,
            "tags_generated": None,
        }
        html = render_template('partials/task_row.html', task=task, config={})
        self.assertIn("members-only", html)
        self.assertIn("badge bg-warning text-dark", html)
        self.assertIn("已完成", html)

    def test_task_card_renders_members_only_badge(self):
        from flask import render_template
        task = {
            "id": "test-task-card-members",
            "youtube_url": "https://www.youtube.com/watch?v=od1fYxQqtM4",
            "upload_target": "bilibili",
            "status": "completed",
            "video_title_original": "Members Only Video Title",
            "video_title_translated": "会员专属视频",
            "bilibili_upload_response": "members-only",
            "acfun_upload_response": None,
            "error_message": None,
            "upload_progress": None,
            "subtitle_qc_score": None,
            "subtitle_qc_reason": None,
            "tags_generated": None,
        }
        html = render_template('partials/task_card.html', task=task, config={})
        self.assertIn("members-only", html)
        self.assertIn("badge bg-warning text-dark", html)
        self.assertIn("已完成", html)


if __name__ == "__main__":
    unittest.main()
