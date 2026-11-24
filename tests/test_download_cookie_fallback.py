import os
import unittest
from unittest.mock import MagicMock, patch

from modules.task_manager import (
    TaskProcessor,
    TaskCancelledError,
    is_cookie_required_error,
)


class CookieRequiredErrorDetectionTests(unittest.TestCase):
    def test_cookie_required_indicators(self):
        cases = [
            "ERROR: [youtube] dQw4w9WgXcQ: Sign in to confirm you’re not a bot. This helps protect our community.",
            "Sign in to confirm you're not a bot",
            "Sign in to view this video",
            "This video is private. Sign in if you've been granted access to this video",
            "Private video",
            "Sign in to confirm your age",
            "This video is only available to registered users",
            "Join this channel to get access to members-only content",
            "members-only content",
            "Use --cookies to provide authentication credentials",
            "--cookies-from-browser",
            "HTTP Error 403: Forbidden",
            "The page needs to be reloaded.",
            "Signature extraction failed",
            "需要登录后才能观看",
            "需要 Cookie",
            "人机验证",
            "视频不可用或无法访问: Sign in to confirm you’re not a bot",
        ]
        for msg in cases:
            with self.subTest(msg=msg):
                self.assertTrue(is_cookie_required_error(msg), f"应该被识别为需要 Cookie: {msg}")

    def test_non_cookie_errors(self):
        cases = [
            "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable",
            "HTTP Error 404: Not Found",
            "timed out",
            "Connection refused",
            "Network is unreachable",
            "Requested format is not available",
            "ffmpeg not found",
            "",
            None,
            {},
        ]
        for msg in cases:
            with self.subTest(msg=msg):
                self.assertFalse(is_cookie_required_error(msg), f"不应该被误判为需要 Cookie: {msg}")


class DownloadCookieFallbackTests(unittest.TestCase):
    def setUp(self):
        self.processor = TaskProcessor(config={
            "YOUTUBE_COOKIES_PATH": "cookies/yt_cookies.txt",
            "MAX_CONCURRENT_TASKS": 1,
            "MAX_CONCURRENT_UPLOADS": 1,
        })
        self.mock_logger = MagicMock()
        self.task_id = "test-task-123"
        self.youtube_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def tearDown(self):
        if hasattr(self.processor, "scheduler") and self.processor.scheduler.running:
            self.processor.scheduler.shutdown(wait=False)

    @patch("modules.task_manager.get_task_cancel_event", return_value=MagicMock(is_set=lambda: False))
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_normal_download_does_not_use_cookies_when_successful(
        self, mock_raise, mock_cancelled, mock_cancel_event
    ):
        """普通下载成功时不带 Cookie，且不触发 Cookie 重试"""
        with patch("modules.youtube_handler.download_video_data") as mock_download, \
             patch.object(self.processor, "_get_valid_youtube_cookies_path") as mock_get_cookies:
            mock_download.return_value = (True, {"video_path": "/tmp/video.mp4"})

            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                only_video=True,
            )

            self.assertTrue(success)
            self.assertEqual(result, {"video_path": "/tmp/video.mp4"})
            # 必须只调用一次，并且 cookies_file_path 必须为 None
            self.assertEqual(mock_download.call_count, 1)
            first_call_cookies = mock_download.call_args[1].get("cookies_file_path")
            self.assertIsNone(first_call_cookies)
            # 未报错时不应查询或验证 Cookie 文件
            mock_get_cookies.assert_not_called()

    @patch("modules.task_manager.get_task_cancel_event", return_value=MagicMock(is_set=lambda: False))
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_non_cookie_failure_does_not_retry_with_cookies(
        self, mock_raise, mock_cancelled, mock_cancel_event
    ):
        """普通下载报错不需要 Cookie 时，不进行带 Cookie 重试"""
        with patch("modules.youtube_handler.download_video_data") as mock_download, \
             patch.object(self.processor, "_get_valid_youtube_cookies_path") as mock_get_cookies:
            mock_download.return_value = (False, "HTTP Error 404: Not Found")

            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                only_video=True,
            )

            self.assertFalse(success)
            self.assertEqual(result, "HTTP Error 404: Not Found")
            # 只调用一次
            self.assertEqual(mock_download.call_count, 1)
            mock_get_cookies.assert_not_called()

    @patch("modules.task_manager.get_task_cancel_event", return_value=MagicMock(is_set=lambda: False))
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_retries_with_cookies_when_error_requires_cookies_and_cookie_exists(
        self, mock_raise, mock_cancelled, mock_cancel_event
    ):
        """普通下载报错提示需要 Cookie 时，若本地有有效 Cookie，则带上 Cookie 重试并成功"""
        with patch("modules.youtube_handler.download_video_data") as mock_download, \
             patch.object(self.processor, "_get_valid_youtube_cookies_path") as mock_get_cookies:
            mock_get_cookies.return_value = "/path/to/valid_cookies.txt"

            # 第一次失败（需要Cookie），第二次成功
            mock_download.side_effect = [
                (False, "Sign in to confirm you’re not a bot"),
                (True, {"video_path": "/tmp/video.mp4"}),
            ]

            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                only_video=True,
            )

            self.assertTrue(success)
            self.assertEqual(result, {"video_path": "/tmp/video.mp4"})
            self.assertEqual(mock_download.call_count, 2)
            # 第一次调用无 Cookie
            first_cookies = mock_download.call_args_list[0][1].get("cookies_file_path")
            self.assertIsNone(first_cookies)
            # 第二次调用带上有效 Cookie
            second_cookies = mock_download.call_args_list[1][1].get("cookies_file_path")
            self.assertEqual(second_cookies, "/path/to/valid_cookies.txt")

    @patch("modules.task_manager.get_task_cancel_event", return_value=MagicMock(is_set=lambda: False))
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_fails_gracefully_when_error_requires_cookies_but_no_valid_cookie(
        self, mock_raise, mock_cancelled, mock_cancel_event
    ):
        """报错需要 Cookie 但本地没有有效 Cookie 时，记录错误并返回明确提示，不盲目重试"""
        with patch("modules.youtube_handler.download_video_data") as mock_download, \
             patch.object(self.processor, "_get_valid_youtube_cookies_path") as mock_get_cookies:
            mock_get_cookies.return_value = None
            mock_download.return_value = (False, "Sign in to confirm you’re not a bot")

            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                only_video=True,
            )

            self.assertFalse(success)
            self.assertIn("未配置有效凭证", result)
            self.assertEqual(mock_download.call_count, 1)

    @patch("modules.task_manager.get_task_cancel_event", return_value=MagicMock(is_set=lambda: False))
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_exception_with_cookie_requirement_triggers_cookie_retry(
        self, mock_raise, mock_cancelled, mock_cancel_event
    ):
        """首次下载抛出异常且异常信息提示需要 Cookie 时，触发带 Cookie 重试"""
        with patch("modules.youtube_handler.download_video_data") as mock_download, \
             patch.object(self.processor, "_get_valid_youtube_cookies_path") as mock_get_cookies:
            mock_get_cookies.return_value = "/path/to/valid_cookies.txt"

            mock_download.side_effect = [
                RuntimeError("yt-dlp failed: Sign in to confirm your age"),
                (True, {"video_path": "/tmp/video.mp4"}),
            ]

            success, result = self.processor._download_video_data_with_cookie_fallback(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                only_video=True,
            )

            self.assertTrue(success)
            self.assertEqual(mock_download.call_count, 2)
            self.assertEqual(mock_download.call_args_list[1][1].get("cookies_file_path"), "/path/to/valid_cookies.txt")

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task", return_value={"id": "test-task-123"})
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_fetch_video_info_end_to_end_fallback(
        self, mock_raise, mock_cancelled, mock_get_task, mock_update_task
    ):
        """_fetch_video_info 在需要 Cookie 时能自动触发带 Cookie 重试并保存元数据"""
        with patch.object(self.processor, "_download_video_data_with_cookie_fallback") as mock_fallback:
            mock_fallback.return_value = (True, {
                "cover_path": "/tmp/cover.jpg",
                "metadata_path": "/tmp/non_existent_metadata.json",
            })

            self.processor._fetch_video_info(self.task_id, self.youtube_url, self.mock_logger)

            mock_fallback.assert_called_once_with(
                task_id=self.task_id,
                youtube_url=self.youtube_url,
                task_logger=self.mock_logger,
                skip_download=True,
            )
            # 状态更新为 info_fetched
            calls = [c[1] for c in mock_update_task.call_args_list]
            self.assertTrue(any(c.get("status") == "info_fetched" for c in calls))

    @patch("modules.task_manager.update_task")
    @patch("modules.task_manager.get_task", return_value={"id": "test-task-123"})
    @patch("modules.task_manager.is_task_cancelled", return_value=False)
    @patch("modules.task_manager._raise_if_cancelled")
    def test_download_video_file_end_to_end_fallback(
        self, mock_raise, mock_cancelled, mock_get_task, mock_update_task
    ):
        """_download_video_file 在需要 Cookie 时能自动触发带 Cookie 重试并更新下载状态"""
        with patch.object(self.processor, "_download_video_data_with_cookie_fallback") as mock_fallback:
            mock_fallback.return_value = (True, {
                "video_path": "/tmp/video.mp4",
            })

            self.processor._download_video_file(self.task_id, self.youtube_url, self.mock_logger)

            self.assertTrue(mock_fallback.called)
            kwargs = mock_fallback.call_args[1]
            self.assertEqual(kwargs.get("task_id"), self.task_id)
            self.assertEqual(kwargs.get("youtube_url"), self.youtube_url)
            self.assertTrue(kwargs.get("only_video"))
            # 状态更新为 downloaded
            calls = [c[1] for c in mock_update_task.call_args_list]
            self.assertTrue(any(c.get("status") == "downloaded" for c in calls))


if __name__ == "__main__":
    unittest.main()
