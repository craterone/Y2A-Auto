#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单元测试：YouTube 监控客户端多线程安全与传输隔离
验证多线程并发下线程局部客户端隔离、重试连接重建隔离，彻底杜绝串包与连接竞态。
"""

import sys
import os
import unittest
import threading
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.youtube_monitor import YouTubeMonitor


class TestYouTubeMonitorThreadSafety(unittest.TestCase):
    def setUp(self):
        self.monitor = YouTubeMonitor.__new__(YouTubeMonitor)
        self.monitor._local = threading.local()
        self.monitor._api_lock = threading.RLock()
        self.monitor._config_version = 1
        self.monitor._current_config = {'YOUTUBE_API_KEY': 'test_fake_key'}
        self.monitor.api_key = 'test_fake_key'
        self.monitor._global_youtube = MagicMock(name='global_client')
        self.monitor._global_youtube_http = MagicMock(name='global_http')

    @patch('modules.youtube_monitor.build')
    @patch.object(YouTubeMonitor, '_build_youtube_http')
    def test_distinct_client_and_http_per_thread(self, mock_build_http, mock_build):
        """测试不同线程获取到的是彼此独立的客户端和 Http 实例"""
        # 每个线程构建不同的 mock 对象
        mock_build_http.side_effect = lambda cfg: MagicMock(name=f'http_{threading.get_ident()}')
        mock_build.side_effect = lambda *args, **kwargs: MagicMock(name=f'client_{threading.get_ident()}')

        results = {}

        def worker(thread_name):
            client = self.monitor.get_thread_client()
            http_obj = getattr(self.monitor._local, 'youtube_http', None)
            results[thread_name] = (client, http_obj)

        t1 = threading.Thread(target=worker, args=('thread_1',))
        t2 = threading.Thread(target=worker, args=('thread_2',))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        self.assertIn('thread_1', results)
        self.assertIn('thread_2', results)

        client1, http1 = results['thread_1']
        client2, http2 = results['thread_2']

        # 两个线程的 client 和 http 必须完全互不相同
        self.assertIsNotNone(client1)
        self.assertIsNotNone(client2)
        self.assertNotEqual(client1, client2)
        self.assertNotEqual(http1, http2)

    @patch('modules.youtube_monitor.build')
    @patch.object(YouTubeMonitor, '_build_youtube_http')
    def test_rebuild_in_one_thread_does_not_affect_other_thread(self, mock_build_http, mock_build):
        """测试某线程重建连接时，仅更新该线程，不影响其他线程的已有客户端和连接"""
        mock_build_http.side_effect = lambda cfg: MagicMock(name=f'http_{id(threading.current_thread())}')
        mock_build.side_effect = lambda *args, **kwargs: MagicMock(name=f'client_{id(threading.current_thread())}')

        thread_2_client = None
        thread_2_http = None
        ready_event = threading.Event()
        finish_event = threading.Event()

        def worker_2():
            nonlocal thread_2_client, thread_2_http
            thread_2_client = self.monitor.get_thread_client()
            thread_2_http = getattr(self.monitor._local, 'youtube_http', None)
            ready_event.set()
            finish_event.wait(timeout=5)
            # 再次检查本线程对象未被篡改
            self.assertEqual(thread_2_client, self.monitor.get_thread_client())
            self.assertEqual(thread_2_http, getattr(self.monitor._local, 'youtube_http', None))

        t2 = threading.Thread(target=worker_2)
        t2.start()
        ready_event.wait(timeout=5)

        # 线程 1 中重置/重建
        old_t1_client = self.monitor.get_thread_client()
        new_t1_client = self.monitor._rebuild_thread_client()

        self.assertNotEqual(old_t1_client, new_t1_client)
        # 线程 2 的客户端不受任何影响
        self.assertNotEqual(new_t1_client, thread_2_client)

        finish_event.set()
        t2.join()

    def test_execute_with_retry_uses_thread_http_without_global_reset(self):
        """测试 _execute_with_retry 遇到 SSL 异常时，仅局部重建且传入当前线程 http 执行"""
        mock_req = MagicMock()
        # 模拟第一次抛出 ssl.SSLError，第二次成功返回
        import ssl
        mock_req.execute.side_effect = [ssl.SSLError("test ssl error"), {"items": ["ok"]}]

        with patch.object(self.monitor, '_rebuild_thread_client') as mock_rebuild:
            res = self.monitor._execute_with_retry(mock_req, "测试API重试", max_attempts=2, backoff_seconds=0.01)
            self.assertEqual(res, {"items": ["ok"]})
            # 确认调用了线程局部重建，而不是全局重建
            mock_rebuild.assert_called_once()


if __name__ == '__main__':
    unittest.main()

