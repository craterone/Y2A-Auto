#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Bilibili 合集（Season）管理模块
提供读取用户已创建合集列表，以及将稿件添加到合集小节的功能。
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from .bilibili_auth import load_cookie_dict

logger = logging.getLogger("bilibili_season")

# 内存缓存配置
_CACHE_LOCK = threading.Lock()
_SEASONS_CACHE: Dict[str, Any] = {
    "timestamp": 0,
    "data": [],
}
CACHE_TTL_SECONDS = 300  # 5 分钟缓存


def _get_default_cookie_file() -> str:
    from .utils import get_app_subdir
    cookie_dir = get_app_subdir("cookies")
    p1 = os.path.join(cookie_dir, "bili_cookies.json")
    if os.path.exists(p1):
        return p1
    p2 = os.path.join(cookie_dir, "bilibili_cookies.json")
    if os.path.exists(p2):
        return p2
    return p1


def _resolve_cookie_file(cookie_file: Optional[str] = None) -> str:
    if cookie_file:
        return cookie_file
    default_path = _get_default_cookie_file()
    return default_path


def get_user_seasons(
    cookie_file: Optional[str] = None,
    force_refresh: bool = False
) -> List[Dict[str, Any]]:
    """
    读取当前登录 UP 主已创建的合集列表。
    优先读取创作中心官方接口，并提供内存缓存支持。

    Args:
        cookie_file: 可选的 cookie 文件路径
        force_refresh: 是否强制跳过缓存刷新

    Returns:
        合集列表，每项包含 season_id, title, desc, cover, ep_num, sections 等
    """
    global _SEASONS_CACHE

    now = time.time()
    with _CACHE_LOCK:
        if not force_refresh and (now - _SEASONS_CACHE["timestamp"] < CACHE_TTL_SECONDS):
            return _SEASONS_CACHE["data"]

    resolved_path = _resolve_cookie_file(cookie_file)
    cookies = load_cookie_dict(resolved_path)
    if not cookies or not cookies.get("SESSDATA"):
        raise ValueError("Bilibili Cookie 无效或缺少 SESSDATA，请先登录 Bilibili")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Referer": "https://member.bilibili.com/platform/upload-manager/season",
        "Origin": "https://member.bilibili.com",
        "Accept": "application/json, text/plain, */*",
    }

    # 1. 尝试从创作中心接口读取
    url = "https://member.bilibili.com/x2/creative/web/seasons"
    params = {
        "pn": 1,
        "ps": 100,
    }

    seasons_result: List[Dict[str, Any]] = []

    try:
        resp = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0 and isinstance(data.get("data"), dict):
                raw_seasons = data["data"].get("seasons") or []
                for item in raw_seasons:
                    if not isinstance(item, dict):
                        continue
                    s_info = item.get("season") or {}
                    s_id = s_info.get("id")
                    if not s_id:
                        continue

                    # 解析小节列表
                    sections_data = item.get("sections") or {}
                    raw_sections = sections_data.get("sections") if isinstance(sections_data, dict) else []
                    parsed_sections = []
                    if isinstance(raw_sections, list):
                        for sec in raw_sections:
                            if not isinstance(sec, dict):
                                continue
                            sec_id = sec.get("id")
                            if sec_id:
                                parsed_sections.append({
                                    "section_id": sec_id,
                                    "title": sec.get("title") or "默认小节",
                                    "order": sec.get("order", 1),
                                    "ep_count": sec.get("epCount", 0),
                                })

                    ep_num = s_info.get("ep_num")
                    if ep_num is None:
                        ep_num = len(item.get("part_episodes") or [])

                    seasons_result.append({
                        "season_id": s_id,
                        "title": s_info.get("title") or f"合集_{s_id}",
                        "desc": s_info.get("desc") or "",
                        "cover": s_info.get("cover") or "",
                        "ep_num": ep_num,
                        "sections": parsed_sections,
                    })
    except Exception as e:
        logger.warning(f"从创作中心接口获取合集失败: {e}")

    # 2. 如果创作中心返回为空，且有 DedeUserID，尝试从用户空间接口补充
    mid = cookies.get("DedeUserID")
    if not seasons_result and mid:
        try:
            space_url = "https://api.bilibili.com/x/polymer/web-space/home/seasons_series"
            space_params = {
                "mid": mid,
                "page_num": 1,
                "page_size": 30,
            }
            space_headers = {
                "User-Agent": headers["User-Agent"],
                "Referer": f"https://space.bilibili.com/{mid}/channel/series",
            }
            s_resp = requests.get(space_url, params=space_params, headers=space_headers, cookies=cookies, timeout=15)
            if s_resp.status_code == 200:
                s_data = s_resp.json()
                if s_data.get("code") == 0 and isinstance(s_data.get("data"), dict):
                    items = s_data["data"].get("items_lists") or {}
                    series_list = items.get("series_list") or []
                    for s_item in series_list:
                        meta = s_item.get("meta") or {}
                        series_id = meta.get("series_id")
                        if series_id:
                            seasons_result.append({
                                "season_id": series_id,
                                "title": meta.get("name") or f"系列_{series_id}",
                                "desc": meta.get("description") or "",
                                "cover": meta.get("cover") or "",
                                "ep_num": meta.get("total", 0),
                                "sections": [],
                            })
        except Exception as e:
            logger.warning(f"从空间接口获取合集/系列失败: {e}")

    with _CACHE_LOCK:
        _SEASONS_CACHE = {
            "timestamp": time.time(),
            "data": seasons_result,
        }

    return seasons_result


def get_video_cid(
    bvid: Optional[str] = None,
    aid: Optional[int] = None,
    cookie_file: Optional[str] = None,
) -> Optional[int]:
    """
    获取视频首个分 P 的 cid。
    优先通过 pagelist 接口获取；若不可用则通过 view 接口获取。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com",
    }
    cookies = {}
    try:
        resolved_path = _resolve_cookie_file(cookie_file)
        if os.path.exists(resolved_path):
            cookies = load_cookie_dict(resolved_path)
    except Exception:
        pass

    # 1. 尝试 pagelist 接口
    try:
        params: Dict[str, Any] = {}
        if bvid:
            params["bvid"] = str(bvid)
        elif aid:
            params["aid"] = int(aid)
        if params:
            url = "https://api.bilibili.com/x/player/pagelist"
            resp = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0 and isinstance(data.get("data"), list) and data["data"]:
                    first_page = data["data"][0]
                    cid = first_page.get("cid")
                    if cid:
                        logger.debug(f"[debug] 通过 pagelist 接口获取到 cid: {cid} (bvid={bvid}, aid={aid})")
                        return int(cid)
    except Exception as e:
        logger.debug(f"[debug] 通过 pagelist 获取 cid 失败: {e}")

    # 2. 尝试 view 接口
    try:
        params = {}
        if bvid:
            params["bvid"] = str(bvid)
        elif aid:
            params["aid"] = int(aid)
        if params:
            url = "https://api.bilibili.com/x/web-interface/view"
            resp = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0 and isinstance(data.get("data"), dict):
                    v_data = data["data"]
                    cid = v_data.get("cid")
                    if cid:
                        logger.debug(f"[debug] 通过 view 接口获取到 cid: {cid} (bvid={bvid}, aid={aid})")
                        return int(cid)
                    pages = v_data.get("pages") or []
                    if pages and pages[0].get("cid"):
                        cid = pages[0]["cid"]
                        logger.debug(f"[debug] 通过 view 接口 pages 获取到 cid: {cid}")
                        return int(cid)
    except Exception as e:
        logger.debug(f"[debug] 通过 view 接口获取 cid 失败: {e}")

    return None


def add_video_to_season(
    season_id: int,
    aid: Optional[int] = None,
    bvid: Optional[str] = None,
    cid: Optional[int] = None,
    title: str = "",
    charging_pay: int = 0,
    section_id: Optional[int] = None,
    cookie_file: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    将视频添加到指定合集小节（遵循 Bilibili 官方合集 API 规范）。

    Args:
        season_id: 合集 ID
        aid: 视频 aid (avid)
        bvid: 视频 bvid
        cid: 视频首个分 P 的 cid（若为空则自动通过 API 查询）
        title: 视频标题
        charging_pay: 付费标记，0 = 免费，其他为付费
        section_id: 可选的小节 ID，若为空则自动获取该合集的第一个小节
        cookie_file: 可选的 cookie 文件路径

    Returns:
        (success, message)
    """
    logger.debug(
        f"[debug] 调用 add_video_to_season: season_id={season_id}, aid={aid}, bvid={bvid}, "
        f"cid={cid}, title={title!r}, charging_pay={charging_pay}, section_id={section_id}"
    )

    if not season_id:
        return False, "合集 ID 为空"
    if not aid and not bvid:
        return False, "缺少视频 aid 或 bvid"

    resolved_path = _resolve_cookie_file(cookie_file)
    cookies = load_cookie_dict(resolved_path)
    bili_jct = cookies.get("bili_jct")
    if not bili_jct:
        logger.warning(f"Cookie 文件 ({resolved_path}) 中缺少 bili_jct (CSRF token)")
        return False, "缺少 bili_jct (CSRF token)"

    # 1. 解析小节 ID (sectionId)
    effective_section_id = section_id
    if not effective_section_id:
        try:
            seasons = get_user_seasons(cookie_file=resolved_path)
            for s in seasons:
                if s.get("season_id") == season_id:
                    sections = s.get("sections") or []
                    if sections:
                        effective_section_id = sections[0].get("section_id")
                    break
        except Exception as e:
            logger.warning(f"获取合集 {season_id} 小节失败: {e}")

    if not effective_section_id:
        effective_section_id = season_id

    # 2. 如果缺少 cid，自动获取
    effective_cid = cid
    if not effective_cid:
        logger.debug(f"[debug] 未传入 cid，尝试自动获取 (bvid={bvid}, aid={aid})")
        effective_cid = get_video_cid(bvid=bvid, aid=aid, cookie_file=resolved_path)

    # 3. 如果缺少 aid，尝试从 bvid 换取
    effective_aid = aid
    if not effective_aid and bvid:
        try:
            from .bilibili_auth import bvid_to_aid
            effective_aid = bvid_to_aid(bvid)
        except Exception as e:
            logger.debug(f"[debug] bvid 换取 aid 失败: {e}")

    logger.debug(
        f"[debug] 准备发起合集添加请求: sectionId={effective_section_id}, "
        f"aid={effective_aid}, cid={effective_cid}, title={title!r}"
    )

    if not effective_aid:
        return False, f"缺少有效的视频 aid (bvid: {bvid})"
    if not effective_cid:
        logger.warning(
            f"[debug] 无法获取到视频的 cid (bvid={bvid}, aid={aid})，"
            f"缺少 cid 会导致 B 站接口返回 -404 错误"
        )
        return False, f"无法获取视频分P的 cid (bvid: {bvid}, aid: {aid})"

    add_url = f"https://member.bilibili.com/x2/creative/web/season/section/episodes/add?csrf={bili_jct}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
        "Referer": "https://member.bilibili.com/platform/upload-manager/season",
        "Origin": "https://member.bilibili.com",
        "Content-Type": "application/json; charset=UTF-8",
        "Accept": "application/json, text/plain, */*",
    }

    payload = {
        "sectionId": int(effective_section_id),
        "episodes": [
            {
                "aid": int(effective_aid),
                "cid": int(effective_cid),
                "title": title or "",
                "charging_pay": int(charging_pay),
            }
        ],
        "csrf": bili_jct,
    }

    # 日志输出（对 csrf 进行脱敏）
    debug_payload = {
        "sectionId": payload["sectionId"],
        "episodes": payload["episodes"],
        "csrf": f"{bili_jct[:4]}***{bili_jct[-4:]}" if len(bili_jct) > 8 else "***",
    }
    logger.debug(f"[debug] 发送 POST 请求到 {add_url.split('?')[0]}?csrf=***: payload={debug_payload}")

    try:
        start_time = time.time()
        resp = requests.post(
            add_url,
            json=payload,
            headers=headers,
            cookies=cookies,
            timeout=10,
        )
        elapsed = time.time() - start_time
        logger.debug(f"[debug] B站合集添加响应 (耗时 {elapsed:.2f}s): HTTP {resp.status_code}, 内容: {resp.text}")

        data = resp.json()
        code = data.get("code")
        msg = data.get("message") or data.get("msg") or "未知状态"
        if code == 0:
            logger.info(
                f"成功将视频 (aid={effective_aid}, cid={effective_cid}, bvid={bvid}) "
                f"加入合集 {season_id} (小节: {effective_section_id})"
            )
            return True, f"成功加入合集: {season_id}"
        elif code == 20080:
            logger.info(
                f"视频 (aid={effective_aid}, bvid={bvid}) 已存在于合集 {season_id} 中，无需重复添加"
            )
            return True, f"视频已存在于合集中: {season_id}"
        else:
            logger.warning(
                f"将视频加入合集失败: code={code}, msg={msg}, "
                f"season_id={season_id}, section_id={effective_section_id}, "
                f"aid={effective_aid}, cid={effective_cid}"
            )
            return False, f"B站接口返回: {msg} (code={code})"
    except Exception as exc:
        err_msg = f"调用加入合集接口异常: {str(exc)}"
        logger.error(err_msg, exc_info=True)
        return False, err_msg
