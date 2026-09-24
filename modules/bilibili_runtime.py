#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from typing import Optional

logger = logging.getLogger("bilibili_runtime")

_INITIALIZED = False
_LAST_ERROR: Optional[str] = None


def configure_bilibili_runtime() -> bool:
    """Configure the internal Bilibili SDK network runtime once per process."""
    global _INITIALIZED, _LAST_ERROR
    if _INITIALIZED:
        return True

    try:
        from .bili_sdk import request_settings

        # 禁用浏览器指纹模拟
        request_settings.set("impersonate", None)

        # 请求超时：120 秒
        request_settings.set_timeout(120)

        # 关闭 SSL 证书验证
        request_settings.set_verify_ssl(False)

        _INITIALIZED = True
        _LAST_ERROR = None

        logger.info(
            "Bilibili network runtime configured: "
            "impersonate=disabled, timeout=120s, verify_ssl=false"
        )

        return True

    except Exception as exc:
        _LAST_ERROR = str(exc)
        logger.warning("配置 bilibili-api 网络运行时失败: %s", exc)
        return False


def get_bilibili_runtime_error() -> Optional[str]:
    return _LAST_ERROR