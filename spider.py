#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
淘宝生意参谋 (sycm.taobao.com) 市场排行商品离线数据爬虫

使用说明：
1. 请先登录 https://sycm.taobao.com/mc/free/market_rank 并抓取最新的 Cookie 和 token。
2. 通过环境变量传入：COOKIE、TOKEN、WEBHOOK_URL（可选）。
3. 运行脚本：python spider.py
4. 结果会保存到 output/ 目录下的 CSV 文件中，支持 append 断点续传。

Docker / 定时任务：
- 设置环境变量 AUTO_LAST_WEEK=1 可自动抓取前一周数据（无需传日期参数）。
- 每周三自动执行，抓取上周（周一→周日）的数据。
"""

import csv
import json
import os
import random
import sys
import time
import urllib.parse
from datetime import date as dt_date, datetime, timedelta
from typing import Any

import requests

# ========================== 环境变量配置 ==========================
COOKIE = os.getenv("COOKIE", "")
TOKEN = os.getenv("TOKEN", "")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
NOTIFY_URL = os.getenv("NOTIFY_URL", WEBHOOK_URL)
AUTO_LAST_WEEK = os.getenv("AUTO_LAST_WEEK", "0") == "1"

# 日期配置：从 START_DATE 开始，按自然周（周一→周日）递增
START_DATE = "2026-01-19"      # 必须是周一
END_DATE = None
DATE_TYPE = os.getenv("DATE_TYPE", "week")

# 每个组合最多爬取页数（None 表示全部）
MAX_PAGES = None

# 请求间隔（秒）
MIN_SLEEP = 6.0
MAX_SLEEP = 15.0

# 是否只抓取第一页用于测试
DEBUG_MODE = False
# ========================== 配置区域结束 ==========================


CATEGORIES = {
    1101: "笔记本电脑",
    1205: "影音电器>头戴耳机>游戏电竞头戴耳机",
    110808: "网络设备/网络相关>路由器>普通路由器",
    121616: "影音电器>音箱/音响>桌面音响/音箱>组合音响",
    121703: "影音电器>Hifi音箱/功放/器材>Hifi音箱",
    350122: "影音电器>无线耳机>AI音频眼镜",
    50001810: "影音电器>音箱/音响>电脑多媒体音箱",
    50001813: "影音电器>音箱/音响>家庭影院",
    50003327: "3C数码配件>数码周边>数据线",
    50003850: "电脑硬件/显示器/电脑周边>电脑视听配件>电脑耳机/耳麦",
    50005050: "影音电器>无线耳机>蓝牙耳机",
    50005266: "影音电器>手机耳机",
    50005267: "影音电器>音箱/音响>桌面音响/音箱>插卡音箱/唱戏机",
    50009211: "3C数码配件>便携电源>移动电源",
    50012143: "影音电器>Hifi音箱/功放/器材>低音炮",
    50012146: "影音电器>Hifi音箱/功放/器材>Hifi套装",
    50012584: "3C数码配件>手机配件>手机充电器",
    50012586: "3C数码配件>数码相机配件>数码相机充电器",
    50012934: "影音电器>音箱/音响>拉杆广场音箱/户外音响",
    50017469: "乐器/吉他/钢琴/配件>MIDI乐器/电脑音乐>耳机放大器",
    50017523: "乐器/吉他/钢琴/配件>乐器音箱>监听音箱",
    50017524: "乐器/吉他/钢琴/配件>乐器音箱>监听耳机",
    50017526: "乐器/吉他/钢琴/配件>乐器音箱>多功能音箱",
    50017529: "乐器/吉他/钢琴/配件>乐器音箱>吉他音箱",
    50018094: "电玩/配件/游戏/攻略>PSP专用配件>专用耳机",
    50018602: "3C数码配件>车载手机配件>车载充电器",
    50018614: "影音电器>音箱/音响>桌面音响/音箱>苹果专用音箱",
    50019322: "网络设备/网络相关>路由器>中继器/扩展器",
    50019355: "网络设备/网络相关>网络存储设备>NAS网络储存",
    50019780: "平板电脑/MID",
    50020184: "3C数码配件>电子书配件>电纸书充电器",
    50020262: "网络设备/网络相关>路由器>电力猫",
    50022650: "网络设备/网络相关>路由器>移动路由器",
    50023280: "影音电器>MP3/MP4耳机",
    50023706: "电脑硬件/显示器/电脑周边>电脑周边>耳麦",
    50024114: "3C数码配件>直播/摄影配件>单反/单电专用电池电源>单反/单电充电器",
    50024118: "3C数码配件>平板电脑配件>平板电脑充电器",
    50024944: "影音电器>耳机(麦)",
    50025714: "电玩/配件/游戏/攻略>PSV专用配件>PSV专用耳机",
    50050366: "3C数码配件>手机配件>手机数据线",
    50228001: "影音电器>音箱/音响>无线/蓝牙音箱",
    120878006: "智能设备>智能手环",
    121988001: "影音电器>音箱/音响>回音壁音响",
    124086006: "智能设备>智能手表",
    124138007: "智能设备>智能眼镜/VR头盔",
    124250003: "网络设备/网络相关>路由器>智能路由器",
    124252004: "电脑硬件/显示器/电脑周边>虚拟现实设备",
    126412033: "影音电器>音箱/音响>智能音箱",
    200836002: "摩托车/装备/配件>摩托车骑士装备>头盔耳机",
    201128601: "网络设备/网络相关>路由器>全屋覆盖路由器",
    201159808: "智能设备>智能儿童手表",
    201182903: "智能设备>XR设备>MR设备",
    201184201: "智能设备>XR设备>AR设备",
    201301101: "影音电器>音箱/音响>移动便携音箱",
    201302401: "影音电器>无线耳机>睡眠耳机",
    201304301: "3C数码配件>便携电源>背夹电源",
    201306323: "影音电器>无线耳机>辅听耳机",
    201307704: "网络设备/网络相关>路由器>网桥",
    201315702: "影音电器>无线耳机>真无线降噪耳机",
    201325901: "影音电器>无线耳机>无线运动耳机",
    201326002: "影音电器>无线耳机>无线游戏耳机",
    201326101: "影音电器>有线耳机>有线HIFI耳机",
    201326301: "影音电器>有线耳机>有线游戏耳机",
    201326401: "影音电器>无线耳机>无线降噪耳机",
    201334602: "影音电器>无线耳机>智能耳机",
    201336602: "影音电器>无线耳机>普通真无线耳机",
    201337601: "影音电器>有线耳机>普通有线耳机",
    201800203: "影音电器>无线耳机>骨传导耳机",
    201835102: "影音电器>音箱/音响>吸顶音箱",
    201835801: "影音电器>头戴耳机>普通头戴耳机",
    201835901: "影音电器>头戴耳机>降噪头戴耳机",
    201899812: "智能设备>智能穿戴>智能指环",
    202109501: "网络设备/网络相关>路由器>插卡路由器",
    202154414: "智能设备>XR设备>智能眼镜",
    202157705: "3C数码配件>数码周边>桌面充电站",
}

RANK_TYPES = ["gmv", "growth", "newitm_ipv"]
PRICE_SEGS = [1, 2, 3, 4, 5, 6]
SELLER_TYPES = [0, 1]

BASE_URL = "https://sycm.taobao.com/mc/mq/mkt/item/offline/rank.json"

HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "bx-v": "2.5.36",
    "onetrace-card-id": "%2Fmc%2Ffree%2Fmarket_rank%7C%E5%B8%82%E5%9C%BA%E6%8E%92%E8%A1%8C-%E5%95%86%E5%93%81-%E5%95%86%E5%93%81%E6%8E%92%E8%A1%8C",
    "priority": "u=1, i",
    "referer": "https://sycm.taobao.com/mc/free/market_rank?activeKey=item&dateRange=2026-04-06%7C2026-04-12&dateType=week&parentCateId=50008090&cateId=201590602&cateFlag=2",
    "sec-ch-ua": '"Microsoft Edge";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "sycm-referer": "/mc/free/market_rank",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0",
}


def generate_week_ranges(start_date_str: str, end_date_str: str | None = None) -> list[str]:
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    if start.weekday() != 0:
        raise ValueError(f"START_DATE {start_date_str} 不是周一，请修正")

    if end_date_str:
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        today = dt_date.today()
        days_since_sunday = (today.weekday() + 1) % 7
        end = today - timedelta(days=days_since_sunday)

    ranges = []
    current = start
    delta = timedelta(days=7)
    while current + timedelta(days=6) <= end:
        week_end = current + timedelta(days=6)
        ranges.append(f"{current.isoformat()}|{week_end.isoformat()}")
        current += delta
    return ranges


def generate_day_ranges(start_date_str: str, end_date_str: str | None = None) -> list[str]:
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    if end_date_str:
        end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    else:
        end = dt_date.today() - timedelta(days=1)

    ranges = []
    current = start
    while current <= end:
        d = current.isoformat()
        ranges.append(f"{d}|{d}")
        current += timedelta(days=1)
    return ranges


def cookie_to_dict(cookie_str: str) -> dict:
    cookies = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def send_webhook(message: str, status: str = "error"):
    url = NOTIFY_URL or WEBHOOK_URL
    if not url:
        return
    content = f"【SYCM爬虫】{status.upper()}\n{message}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        print(f"[WEBHOOK] 已发送通知: {message}")
    except Exception as e:
        print(f"[WEBHOOK] 发送失败: {e}")


def get_last_date_range(date_type: str = "week") -> str:
    today = dt_date.today()
    if date_type == "day":
        yesterday = today - timedelta(days=1)
        return f"{yesterday.isoformat()}|{yesterday.isoformat()}"
    days_since_sunday = (today.weekday() + 1) % 7
    last_sunday = today - timedelta(days=days_since_sunday)
    last_monday = last_sunday - timedelta(days=6)
    return f"{last_monday.isoformat()}|{last_sunday.isoformat()}"


def parse_response(resp_json: Any) -> list[dict]:
    if isinstance(resp_json, list):
        # 若顶层直接是列表，尝试过滤出字典元素
        return [x for x in resp_json if isinstance(x, dict)]
    if not isinstance(resp_json, dict):
        return []
    candidates = [
        resp_json.get("data", {}).get("data", []) if isinstance(resp_json.get("data"), dict) else [],
        resp_json.get("data", {}).get("list", []) if isinstance(resp_json.get("data"), dict) else [],
        resp_json.get("data", []) if isinstance(resp_json.get("data"), list) else [],
        resp_json.get("result", {}).get("data", []) if isinstance(resp_json.get("result"), dict) else [],
        resp_json.get("result", {}).get("list", []) if isinstance(resp_json.get("result"), dict) else [],
    ]
    for data in candidates:
        if isinstance(data, list) and len(data) > 0:
            return data
    return []


class CookieExpiredError(RuntimeError):
    pass


def _is_auth_error(text: str) -> bool:
    keywords = ["登录", "token", "权限", "鉴权", "未登录", "超时", "过期", "重新登录"]
    text_lo = text.lower()
    return any(k in text or k in text_lo for k in keywords)


def fetch_one_page(
    session: requests.Session,
    date_range: str,
    cate_id: int,
    rank_type: str,
    price_seg: int,
    seller_type: int,
    page: int,
    date_type: str = "week",
) -> tuple[list[dict], int | None]:
    params = {
        "dateRange": date_range,
        "dateType": date_type,
        "pageSize": 20,
        "page": page,
        "cateId": cate_id,
        "rankType": rank_type,
        "minPrice": "",
        "maxPrice": "",
        "priceSeg": price_seg,
        "sellerType": seller_type,
        "keyWord": "",
        "cateFlag": 2,
        "indexCode": "uv,payByrCnt,cartByrCnt",
        "marketVersion": "free",
        "_": int(datetime.now().timestamp() * 1000),
        "token": TOKEN,
    }

    resp = session.get(BASE_URL, headers=HEADERS, params=params, timeout=30)

    if resp.status_code in (401, 403):
        raise CookieExpiredError(f"HTTP {resp.status_code}，Cookie/Token 可能已失效。")

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" in content_type:
        snippet = resp.text[:200].replace("\n", " ")
        raise CookieExpiredError(f"返回 HTML 页面，疑似登录失效。内容片段: {snippet}")

    resp.raise_for_status()

    try:
        data = resp.json()
    except Exception as e:
        raise CookieExpiredError(f"响应无法解析为 JSON，Cookie 可能已失效。{e}")

    if DEBUG_MODE and page == 1:
        debug_path = f"output/debug_{date_range.replace('|', '_')}_{cate_id}_{rank_type}_{price_seg}_{seller_type}.json"
        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 原始响应已保存到 {debug_path}")

    if isinstance(data, dict):
        msg = str(data.get("message", ""))
        code = data.get("code", 0)
        if _is_auth_error(msg):
            raise CookieExpiredError(f"接口返回登录/权限异常: {msg} (code={code})")
        if code != 0 and _is_auth_error(msg):
            raise CookieExpiredError(f"接口异常: {msg} (code={code})")

    records = parse_response(data)

    total_page = None
    if isinstance(data, dict):
        d = data.get("data", {})
        if isinstance(d, dict):
            total_page = d.get("totalPage") or d.get("totalPages") or d.get("maxPage")
        elif isinstance(d, list) and len(records) < 20:
            total_page = page
    return records, total_page


def flatten_record(record: dict, meta: dict) -> dict:
    flat: dict[str, Any] = {}
    for key, val in record.items():
        if isinstance(val, dict):
            for sub_key, sub_val in val.items():
                flat[f"{key}_{sub_key}"] = sub_val
        else:
            flat[key] = val

    flat["_query_date_range"] = meta["date_range"]
    flat["_query_date_type"] = "recent7"
    flat["_query_cate_id"] = meta["cate_id"]
    flat["_query_cate_name"] = meta["cate_name"]
    flat["_query_rank_type"] = meta["rank_type"]
    flat["_query_price_seg"] = meta["price_seg"]
    flat["_query_seller_type"] = meta["seller_type"]
    flat["_query_page"] = meta["page"]
    return flat


def safe_filename(name: str) -> str:
    invalid_chars = r'\/:*?"<>| '
    for ch in invalid_chars:
        name = name.replace(ch, "_")
    return name


def normalize_date_str(raw: str) -> str:
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def parse_category_ids(raw: list[str]) -> list[int]:
    if not raw or any(v.lower() == "all" for v in raw):
        return list(CATEGORIES.keys())
    ids = []
    for v in raw:
        try:
            ids.append(int(v))
        except ValueError:
            print(f"[WARN] 忽略非法的品类 ID: {v}")
    return ids


def _progress_key(date_range: str, cate_id: int, rank_type: str, price_seg: int, seller_type: int) -> str:
    return f"{date_range}#{cate_id}#{rank_type}#{price_seg}#{seller_type}"


def _progress_path(date_range: str, cate_id: int) -> str:
    dr = date_range.replace("|", "_")
    return f"output/.progress_{cate_id}_{dr}.json"


def _csv_path(date_range: str, cate_id: int, cate_name: str) -> str:
    safe_name = safe_filename(cate_name)
    d_start, d_end = date_range.split("|")
    return f"output/{cate_id}_{safe_name}_{d_start}_{d_end}.csv"


def _load_progress(date_range: str, cate_id: int) -> set[str]:
    path = _progress_path(date_range, cate_id)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("done", []))
    except Exception:
        return set()


def _save_progress(date_range: str, cate_id: int, done: set[str]):
    path = _progress_path(date_range, cate_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done": sorted(done)}, f, ensure_ascii=False, indent=2)


def _append_csv(csv_path: str, records: list[dict]):
    if not records:
        return

    # 计算新记录中所有可能的字段
    new_keys = set()
    for r in records:
        new_keys.update(r.keys())

    file_exists = os.path.exists(csv_path) and os.path.getsize(csv_path) > 0

    if not file_exists:
        fieldnames = sorted(new_keys)
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        return

    # 文件已存在：读取现有表头
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        existing_rows = list(reader)
        existing_fieldnames = list(reader.fieldnames or [])

    # 合并表头
    combined_keys = set(existing_fieldnames) | new_keys
    if combined_keys == set(existing_fieldnames):
        # 字段无变化，直接追加
        with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=existing_fieldnames)
            writer.writerows(records)
    else:
        # 字段有扩展，需要重写整个文件（保留旧数据 + 新字段）
        fieldnames = sorted(combined_keys)
        all_rows = existing_rows + records
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"  -> CSV 表头已扩展并重写: {csv_path}")


def run(
    start_date: str | None = None,
    end_date: str | None = None,
    date_type: str | None = None,
    category_ids: list[int] | str | None = None,
):
    if not COOKIE or not TOKEN:
        msg = "[ERROR] COOKIE 或 TOKEN 未配置，请先设置环境变量。"
        print(msg)
        send_webhook(msg)
        return

    session = requests.Session()
    session.cookies.update(cookie_to_dict(COOKIE))

    dt = (date_type or DATE_TYPE or "week").lower()

    # 自动前一周/前一天模式
    if AUTO_LAST_WEEK and not start_date and not end_date:
        date_ranges = [get_last_date_range(dt)]
        label = "前一天" if dt == "day" else "前一周"
        print(f"[AUTO] 自动抓取{label}数据: {date_ranges[0]}\n")
    else:
        start = normalize_date_str(start_date) if start_date and str(start_date).lower() != "all" else START_DATE
        end = normalize_date_str(end_date) if end_date and str(end_date).lower() != "all" else END_DATE
        if dt == "day":
            date_ranges = generate_day_ranges(start, end)
        else:
            date_ranges = generate_week_ranges(start, end)
        if not date_ranges:
            msg = f"根据 START_DATE ({start}) 和 END_DATE ({end}) 未生成任何日期区间，请检查配置。"
            print(msg)
            send_webhook(msg)
            return
        print(f"本次将抓取以下 {len(date_ranges)} 个日期区间: {date_ranges}\n")

    if category_ids is None or (isinstance(category_ids, str) and category_ids.lower() == "all"):
        selected_categories = dict(CATEGORIES)
    else:
        selected_categories = {
            cid: name for cid, name in CATEGORIES.items() if cid in category_ids
        }
        if not selected_categories:
            msg = "未匹配到任何有效的品类 ID，请检查输入。"
            print(msg)
            send_webhook(msg)
            return

    os.makedirs("output", exist_ok=True)
    total_written = 0
    total_files = 0
    cookie_invalid_notified = False

    total_tasks = len(date_ranges) * len(selected_categories) * len(RANK_TYPES) * len(PRICE_SEGS) * len(SELLER_TYPES)
    current_task = 0

    for date_range in date_ranges:
        for cate_id, cate_name in selected_categories.items():
            csv_path = _csv_path(date_range, cate_id, cate_name)
            done_set = _load_progress(date_range, cate_id)
            cate_records: list[dict] = []
            combo_done = 0

            for rank_type in RANK_TYPES:
                for price_seg in PRICE_SEGS:
                    for seller_type in SELLER_TYPES:
                        current_task += 1
                        pkey = _progress_key(date_range, cate_id, rank_type, price_seg, seller_type)
                        if pkey in done_set:
                            print(f"[{current_task}/{total_tasks}] 已跳过（已抓取）: {pkey}")
                            continue

                        meta = {
                            "date_range": date_range,
                            "cate_id": cate_id,
                            "cate_name": cate_name,
                            "rank_type": rank_type,
                            "price_seg": price_seg,
                            "seller_type": seller_type,
                        }
                        print(
                            f"[{current_task}/{total_tasks}] 开始抓取: "
                            f"date={date_range}, cate={cate_id}({cate_name}), rank={rank_type}, "
                            f"priceSeg={price_seg}, sellerType={seller_type}"
                        )

                        page = 1
                        combo_records = 0
                        combo_error = None
                        while True:
                            try:
                                records, total_page = fetch_one_page(
                                    session, date_range, cate_id, rank_type, price_seg, seller_type, page, dt
                                )
                            except CookieExpiredError as e:
                                combo_error = str(e)
                                print(f"  [ERROR] 抓取失败 page={page}: {e}")
                                if not cookie_invalid_notified:
                                    cookie_invalid_notified = True
                                    send_webhook(f"Cookie/Token 已失效，请尽快更新。详情: {combo_error}")
                                # 保存已抓数据后抛出异常，供上层服务捕获
                                if cate_records:
                                    _append_csv(csv_path, cate_records)
                                msg = f"因 Cookie/Token 失效，爬虫已中断。已处理 {total_files} 个文件，{total_written} 条记录。"
                                print(f"\n{msg}")
                                raise CookieExpiredError(combo_error) from e
                            except Exception as e:
                                combo_error = str(e)
                                print(f"  [ERROR] 抓取失败 page={page}: {e}")
                                break

                            if not records:
                                print(f"  本组合 page={page} 无数据，结束。")
                                break

                            for r in records:
                                flat = flatten_record(r, {**meta, "page": page})
                                cate_records.append(flat)
                                combo_records += 1

                            print(f"  page={page} 获取 {len(records)} 条，累计 {combo_records} 条")

                            if DEBUG_MODE:
                                break

                            if total_page is not None and page >= int(total_page):
                                break

                            if MAX_PAGES is not None and page >= MAX_PAGES:
                                print(f"  已达最大页数限制 {MAX_PAGES}，停止。")
                                break

                            page += 1
                            time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))

                        if combo_error is None:
                            done_set.add(pkey)
                            _save_progress(date_range, cate_id, done_set)
                            combo_done += 1

                        time.sleep(random.uniform(MIN_SLEEP, MAX_SLEEP))

            if cate_records:
                _append_csv(csv_path, cate_records)
                total_written += len(cate_records)
                total_files += 1
                print(f"  -> 已追加 {len(cate_records)} 条到 {csv_path}")

    if total_written == 0:
        msg = "未获取到任何数据，请检查 Cookie / token 是否有效，或接口是否返回异常。"
        print(msg)
        send_webhook(msg)
        return

    success_msg = f"全部完成！共写入 {total_files} 个文件，{total_written} 条记录。"
    print(f"\n{success_msg}")
    send_webhook(success_msg, status="success")


if __name__ == "__main__":
    argv = sys.argv[1:]
    known_dt = {"day", "week"}

    start_arg = argv[0] if len(argv) >= 1 else None
    end_arg = argv[1] if len(argv) >= 2 else None
    cate_args = argv[2:] if len(argv) >= 3 else []
    date_type_arg = None

    if start_arg and start_arg.lower() in known_dt:
        date_type_arg = start_arg
        start_arg = end_arg
        end_arg = cate_args[0] if cate_args else None
        cate_args = cate_args[1:]
    elif end_arg and end_arg.lower() in known_dt:
        date_type_arg = end_arg
        end_arg = cate_args[0] if cate_args else None
        cate_args = cate_args[1:]
    elif cate_args and cate_args[0].lower() in known_dt:
        date_type_arg = cate_args[0]
        cate_args = cate_args[1:]

    try:
        run(
            start_date=start_arg,
            end_date=end_arg,
            date_type=date_type_arg,
            category_ids=parse_category_ids(cate_args),
        )
    except CookieExpiredError as e:
        print(f"\n程序因 Cookie 失效退出: {e}")
        sys.exit(1)
