import asyncio
import os
import tempfile
import unittest
import logging
from unittest.mock import AsyncMock, Mock, patch

from modules.bili_sdk.exceptions.NetworkException import NetworkException
from modules.bili_sdk.utils.AsyncEvent import AsyncEvent
from modules.bili_sdk.video_uploader import (
    Lines,
    VideoUploader,
    VideoUploaderEvents,
    VideoUploaderPage,
    _choose_line,
    _probe,
)
from modules.bilibili_uploader import BilibiliUploader, _BilibiliChunkProgress


class _FakeResponse:
    def __init__(self, code=200, text="MULTIPART_PUT_SUCCESS", json_data=None):
        self.code = code
        self._text = text
        self._json_data = json_data

    def utf8_text(self):
        return self._text

    def json(self):
        if self._json_data is not None:
            return self._json_data
        return {}


class BilibiliSdkChunkRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.video_path = os.path.join(self.temp_dir.name, "video.mp4")
        with open(self.video_path, "wb") as stream:
            stream.write(b"abcdefgh")
        self.page = VideoUploaderPage(self.video_path, "test")
        self.uploader = object.__new__(VideoUploader)
        AsyncEvent.__init__(self.uploader)
        self.uploader.line = None
        self.preupload = {
            "endpoint": "//upload.example.com",
            "upos_uri": "upos://bucket/video.mp4",
            "upload_id": "upload-id",
            "chunk_size": 8,
            "auth": "auth",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_chunk_retries_transient_failures_then_succeeds(self):
        client = Mock()
        client.request = AsyncMock(
            side_effect=[
                _FakeResponse(503),
                _FakeResponse(503),
                _FakeResponse(200),
            ]
        )
        failures = []
        successes = []
        self.uploader.add_event_listener(
            VideoUploaderEvents.CHUNK_FAILED.value, failures.append
        )
        self.uploader.add_event_listener(
            VideoUploaderEvents.AFTER_CHUNK.value, successes.append
        )

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=client
        ), patch(
            "modules.bili_sdk.video_uploader.asyncio.sleep", new=AsyncMock()
        ) as sleep_mock:
            result = asyncio.run(
                self.uploader._upload_chunk(
                    self.page, 0, 0, 1, dict(self.preupload)
                )
            )

        self.assertTrue(result["ok"])
        self.assertEqual(client.request.await_count, 3)
        self.assertEqual([item["attempt"] for item in failures], [1, 2])
        self.assertEqual([item["retrying"] for item in failures], [True, True])
        self.assertEqual([item["retry_delay_seconds"] for item in failures], [1, 2])
        self.assertEqual(len(successes), 1)
        self.assertEqual(sleep_mock.await_count, 2)

    def test_chunk_stops_after_three_transient_failures(self):
        client = Mock()
        client.request = AsyncMock(return_value=_FakeResponse(503))
        failures = []
        self.uploader.add_event_listener(
            VideoUploaderEvents.CHUNK_FAILED.value, failures.append
        )

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=client
        ), patch(
            "modules.bili_sdk.video_uploader.asyncio.sleep", new=AsyncMock()
        ):
            with self.assertRaises(NetworkException):
                asyncio.run(
                    self.uploader._upload_chunk(
                        self.page, 0, 0, 1, dict(self.preupload)
                    )
                )

        self.assertEqual(client.request.await_count, 3)
        self.assertEqual(len(failures), 3)
        self.assertFalse(failures[-1]["retrying"])
        self.assertEqual(failures[-1]["attempt"], 3)
        self.assertEqual(failures[-1]["status_code"], 503)

    def test_chunk_does_not_retry_client_error(self):
        client = Mock()
        client.request = AsyncMock(return_value=_FakeResponse(403))
        failures = []
        self.uploader.add_event_listener(
            VideoUploaderEvents.CHUNK_FAILED.value, failures.append
        )

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=client
        ):
            with self.assertRaises(NetworkException):
                asyncio.run(
                    self.uploader._upload_chunk(
                        self.page, 0, 0, 1, dict(self.preupload)
                    )
                )

        self.assertEqual(client.request.await_count, 1)
        self.assertEqual(len(failures), 1)
        self.assertFalse(failures[0]["retrying"])

    def test_upload_page_uses_one_thread_when_preupload_returns_zero(self):
        preupload = {
            **self.preupload,
            "chunk_size": 4,
            "threads": 0,
            "biz_id": 123,
        }
        self.uploader._preupload = AsyncMock(return_value=preupload)
        self.uploader._upload_chunk = AsyncMock(return_value={"ok": True})
        self.uploader._complete_page = AsyncMock(
            return_value={"filename": "video", "cid": 123}
        )

        result = asyncio.run(self.uploader._upload_page(self.page))

        self.assertEqual(result, {"filename": "video", "cid": 123})
        self.assertEqual(self.uploader._upload_chunk.await_count, 2)
        self.uploader._complete_page.assert_awaited_once()


class BilibiliProgressTests(unittest.TestCase):
    def test_progress_counts_unique_chunks_in_completion_order(self):
        tracker = _BilibiliChunkProgress()
        page = object()

        first = tracker.record(
            {"page": page, "chunk_number": 0, "total_chunk_count": 23}
        )
        duplicate = tracker.record(
            {"page": page, "chunk_number": 0, "total_chunk_count": 23}
        )
        out_of_order = tracker.record(
            {"page": page, "chunk_number": 22, "total_chunk_count": 23}
        )

        self.assertAlmostEqual(first, 95 / 23)
        self.assertEqual(duplicate, first)
        self.assertAlmostEqual(out_of_order, 2 * 95 / 23)

        final = out_of_order
        for chunk_number in range(1, 22):
            final = tracker.record(
                {
                    "page": page,
                    "chunk_number": chunk_number,
                    "total_chunk_count": 23,
                }
            )
        self.assertEqual(final, 95.0)

    def test_upload_video_emits_stage_progress_and_retry_log(self):
        progress = []
        logger = Mock()

        class FakePage:
            def __init__(self, path, title):
                self.path = path
                self.title = title

        class FakeUploader(AsyncEvent):
            def __init__(self, pages, meta, credential, cover):
                super().__init__()
                self.pages = pages

            async def start(self):
                page = self.pages[0]
                self.dispatch(
                    VideoUploaderEvents.CHOOSE_LINE.value,
                    {"line": {"upcdn": "bda2"}},
                )
                self.dispatch(
                    VideoUploaderEvents.CHUNK_FAILED.value,
                    {
                        "page": page,
                        "chunk_number": 0,
                        "total_chunk_count": 3,
                        "attempt": 1,
                        "max_attempts": 3,
                        "retrying": True,
                        "retry_delay_seconds": 1,
                        "info": "Status 503",
                    },
                )
                for chunk_number in (0, 0, 2, 1):
                    self.dispatch(
                        VideoUploaderEvents.AFTER_CHUNK.value,
                        {
                            "page": page,
                            "chunk_number": chunk_number,
                            "total_chunk_count": 3,
                        },
                    )
                self.dispatch(
                    VideoUploaderEvents.PRE_PAGE_SUBMIT.value, {"page": page}
                )
                self.dispatch(
                    VideoUploaderEvents.AFTER_PAGE_SUBMIT.value, {"page": page}
                )
                self.dispatch(VideoUploaderEvents.PRE_COVER.value, None)
                self.dispatch(VideoUploaderEvents.AFTER_COVER.value, {"url": "cover"})
                self.dispatch(VideoUploaderEvents.PRE_SUBMIT.value, {})
                self.dispatch(
                    VideoUploaderEvents.AFTER_SUBMIT.value,
                    {"bvid": "BV1test", "aid": 1},
                )
                return {"bvid": "BV1test", "aid": 1}

        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = os.path.join(temp_dir, "video.mp4")
            cover_path = os.path.join(temp_dir, "cover.jpg")
            for path in (video_path, cover_path):
                with open(path, "wb") as stream:
                    stream.write(b"test")

            with patch(
                "modules.bilibili_uploader.setup_task_logger", return_value=logger
            ), patch(
                "modules.bilibili_uploader.configure_bilibili_runtime"
            ), patch(
                "modules.bilibili_uploader.load_credential_from_file",
                return_value=object(),
            ), patch(
                "modules.bilibili_uploader.validate_credential_remote",
                return_value=(True, "ok"),
            ), patch(
                "modules.bilibili_uploader.video_uploader.VideoMeta",
                return_value=object(),
            ), patch(
                "modules.bilibili_uploader.video_uploader.VideoUploaderPage",
                FakePage,
            ), patch(
                "modules.bilibili_uploader.video_uploader.VideoUploader",
                FakeUploader,
            ):
                success, result = BilibiliUploader("cookies.json").upload_video(
                    video_path,
                    cover_path,
                    "标题",
                    "简介",
                    ["标签"],
                    21,
                    youtube_url="https://www.youtube.com/watch?v=test",
                    task_id="test-task",
                    progress_callback=progress.append,
                )

        self.assertTrue(success)
        self.assertEqual(result["bvid"], "BV1test")
        self.assertEqual(
            progress,
            ["0.0%", "31.7%", "63.3%", "95.0%", "96.0%", "98.0%", "99.0%", "100.0%"],
        )
        log_messages = [call.args[0] for call in logger.info.call_args_list]
        self.assertTrue(any("选择上传线路: bda2" in item for item in log_messages))
        self.assertTrue(any("尝试 1/3，1 秒后重试" in item for item in log_messages))
        self.assertTrue(any("正在提交分P" in item for item in log_messages))
        self.assertTrue(any("正在提交Bilibili投稿" in item for item in log_messages))


class BilibiliLineSelectionTests(unittest.TestCase):
    def test_choose_line_with_specified_line(self):
        with patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(Lines.WS))
            self.assertEqual(result["upcdn"], "ws")
            mock_logger.info.assert_any_call("[VideoUploader] 选择上传线路: ws (指定线路)")

    def test_choose_line_with_probe(self):
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=_FakeResponse(200))

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ), patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(None))
            self.assertIsNotNone(result)
            self.assertIn("upcdn", result)

            logged_lines = [call.args[0] for call in mock_logger.info.call_args_list if call.args]
            self.assertTrue(any("开始测试所有线路速度" in text for text in logged_lines))
            self.assertTrue(any("测速耗时" in text for text in logged_lines))
            self.assertTrue(any("最快线路" in text for text in logged_lines))
            self.assertTrue(any(f"选择上传线路: {result['upcdn']}" in text for text in logged_lines))

    def test_choose_line_timeout_skips_line(self):
        mock_client = Mock()

        async def _request_side_effect(method, url, **kwargs):
            if "bda2" in url:
                raise asyncio.TimeoutError()
            return _FakeResponse(200)

        mock_client.request = AsyncMock(side_effect=_request_side_effect)

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ), patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(None))
            self.assertIsNotNone(result)
            self.assertNotEqual(result["upcdn"], "bda2")
            warn_logs = [call.args[0] for call in mock_logger.warning.call_args_list if call.args]
            self.assertTrue(any("未响应，跳过该线路" in text for text in warn_logs))

    def test_choose_line_abnormal_status_code_skips_line(self):
        mock_client = Mock()

        async def _request_side_effect(method, url, **kwargs):
            if "bda2" in url:
                return _FakeResponse(502)
            return _FakeResponse(200)

        mock_client.request = AsyncMock(side_effect=_request_side_effect)

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ), patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(None))
            self.assertIsNotNone(result)
            self.assertNotEqual(result["upcdn"], "bda2")
            warn_logs = [call.args[0] for call in mock_logger.warning.call_args_list if call.args]
            self.assertTrue(any("测速返回异常状态码 502" in text for text in warn_logs))

    def test_choose_line_dynamic_probe_with_get(self):
        mock_client = Mock()
        dynamic_payload = {
            "OK": 1,
            "lines": [
                {
                    "os": "upos",
                    "probe_url": "//upos-cs-dyn1.bilivideo.com/OK",
                    "query": "probe_version=20230101&upcdn=dyn1",
                    "upcdn": "dyn1",
                }
            ],
            "probe": {"get": 1},
        }

        async def _request_side_effect(method, url, **kwargs):
            if "r=probe" in url:
                return _FakeResponse(200, json_data=dynamic_payload)
            if "dyn1" in url:
                self.assertEqual(method, "GET")
                return _FakeResponse(200)
            return _FakeResponse(404)

        mock_client.request = AsyncMock(side_effect=_request_side_effect)

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ), patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(None))
            self.assertEqual(result["upcdn"], "dyn1")
            self.assertEqual(result["probe_version"], 20230101)

    def test_choose_line_all_failed_uses_fallback(self):
        mock_client = Mock()
        mock_client.request = AsyncMock(return_value=_FakeResponse(500))

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ), patch("modules.bili_sdk.video_uploader.logger") as mock_logger:
            result = asyncio.run(_choose_line(None))
            self.assertIsNotNone(result)
            warn_logs = [call.args[0] for call in mock_logger.warning.call_args_list if call.args]
            self.assertTrue(any("无可用线路，使用兜底线路" in text for text in warn_logs))

    def test_choose_line_dynamic_probe_query_parsing(self):
        mock_client = Mock()
        # 模拟真实 B 站 preupload?r=probe 响应结构（不包含顶层 upcdn 字段，参数均在 query 字符串中）
        real_bilibili_payload = {
            "OK": 1,
            "lines": [
                {
                    "os": "upos",
                    "query": "probe_version=20250923&upcdn=tx&zone=cs",
                    "probe_url": "//upos-cs-upcdntx.bilivideo.com/OK",
                }
            ],
            "probe": {"post": 1},
        }

        async def _request_side_effect(method, url, **kwargs):
            if "r=probe" in url:
                return _FakeResponse(200, json_data=real_bilibili_payload)
            if "upcdntx" in url:
                return _FakeResponse(200)
            return _FakeResponse(404)

        mock_client.request = AsyncMock(side_effect=_request_side_effect)

        with patch(
            "modules.bili_sdk.video_uploader.get_client", return_value=mock_client
        ):
            result = asyncio.run(_choose_line(None))
            self.assertEqual(result["upcdn"], "tx")
            self.assertEqual(result["probe_version"], 20250923)
            self.assertEqual(result["os"], "upos")

    def test_video_uploader_start_dispatches_choose_line_event(self):
        from modules.bili_sdk.video_uploader import VideoUploader, VideoUploaderEvents

        uploader = VideoUploader(pages=[], meta={}, credential=Mock())
        dispatched = []

        @uploader.on(VideoUploaderEvents.CHOOSE_LINE.value)
        def _on_choose_line(data):
            dispatched.append(data)

        with patch(
            "modules.bili_sdk.video_uploader._choose_line",
            new=AsyncMock(return_value={"upcdn": "bda2"}),
        ), patch.object(uploader, "_main", new=AsyncMock(return_value={"bvid": "BV1test"})):
            result = asyncio.run(uploader.start())
            self.assertEqual(result["bvid"], "BV1test")
            self.assertEqual(len(dispatched), 1)
            self.assertEqual(dispatched[0]["line"]["upcdn"], "bda2")

    def test_video_uploader_logger_level_is_info(self):
        from modules.bili_sdk.video_uploader import logger
        self.assertTrue(logger.isEnabledFor(logging.INFO))


if __name__ == "__main__":
    unittest.main()
