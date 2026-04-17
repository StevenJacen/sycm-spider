#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SYCM 爬虫服务化入口

功能：
- 后台定时任务：按配置自动抓取前一周/前一天数据
- REST API：接收新 Cookie、手动触发、查看状态
- Cookie 失效时自动请求 NOTIFY_URL 通知用户
- 用户更新 Cookie 后自动恢复中断的爬取
"""

import os
import sys
import threading
from datetime import datetime

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, request

import spider

app = Flask(__name__)

NOTIFY_URL = os.getenv("NOTIFY_URL", "")
AUTO_LAST_WEEK = os.getenv("AUTO_LAST_WEEK", "1") == "1"
CRON_SCHEDULE = os.getenv("CRON_SCHEDULE", "0 3 * * 3")
DEFAULT_DATE_TYPE = os.getenv("DATE_TYPE", "week")

spider_lock = threading.Lock()
spider_state = {
    "status": "idle",  # idle | running | waiting_cookie | error
    "message": "",
    "last_notify": None,
    "date_range": None,
    "date_type": None,
}


def notify_user(message: str, status: str = "cookie_expired"):
    url = os.getenv("NOTIFY_URL", "") or os.getenv("WEBHOOK_URL", "")
    if not url:
        print(f"[NOTIFY] 未配置 NOTIFY_URL，跳过通知。消息: {message}")
        return
    content = f"【SYCM爬虫】{status.upper()}\n{message}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[NOTIFY] 已发送通知: {message}")
        spider_state["last_notify"] = {
            "type": status,
            "message": message,
            "time": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"[NOTIFY] 发送失败: {e}")


def do_spider_job(date_range: str | None = None, date_type: str | None = None):
    global spider_state
    dt = (date_type or DEFAULT_DATE_TYPE or "week").lower()
    label = "前一天" if dt == "day" else "前一周"
    with spider_lock:
        if spider_state["status"] == "running":
            print("[SPIDER] 已有任务在运行，跳过本次调度")
            return
        spider_state["status"] = "running"
        spider_state["message"] = f"开始爬取 {date_range or label + '数据'}"
        spider_state["date_range"] = date_range
        spider_state["date_type"] = dt

    try:
        if date_range:
            start, end = date_range.split("|")
            spider.run(start_date=start, end_date=end, date_type=dt)
        elif AUTO_LAST_WEEK:
            spider.run(date_type=dt)
        else:
            spider.run(date_type=dt)
    except spider.CookieExpiredError as e:
        spider_state["status"] = "waiting_cookie"
        spider_state["message"] = f"Cookie 失效: {e}"
        notify_user(f"Cookie/Token 已失效，请通过 POST /update-cookie 更新。详情: {e}")
    except Exception as e:
        spider_state["status"] = "error"
        spider_state["message"] = f"运行异常: {e}"
        notify_user(f"爬虫运行异常: {e}", status="error")
    else:
        spider_state["status"] = "idle"
        spider_state["message"] = "爬取完成"


@app.route("/health", methods=["GET"])
def health():
    return jsonify(spider_state)


@app.route("/update-cookie", methods=["POST"])
def update_cookie():
    data = request.get_json(force=True) or {}
    new_cookie = data.get("cookie", "")
    new_token = data.get("token", "")

    if not new_cookie or not new_token:
        return jsonify({"success": False, "message": "cookie 和 token 不能为空"}), 400

    # 更新 spider 模块和进程环境变量
    spider.COOKIE = new_cookie
    spider.TOKEN = new_token
    os.environ["COOKIE"] = new_cookie
    os.environ["TOKEN"] = new_token

    # 如果是 waiting_cookie 或 error 状态，自动恢复
    if spider_state["status"] in ("waiting_cookie", "error"):
        target_date_range = spider_state.get("date_range") or spider.get_last_date_range(
            spider_state.get("date_type") or DEFAULT_DATE_TYPE
        )
        target_date_type = spider_state.get("date_type") or DEFAULT_DATE_TYPE
        t = threading.Thread(target=do_spider_job, args=(target_date_range, target_date_type))
        t.start()
        return jsonify({
            "success": True,
            "message": "已更新 cookie，正在恢复爬取",
            "date_range": target_date_range,
            "date_type": target_date_type,
        })

    return jsonify({"success": True, "message": "已更新 cookie"})


@app.route("/trigger", methods=["POST"])
def trigger():
    """手动触发一次爬取任务"""
    if spider_state["status"] == "running":
        return jsonify({"success": False, "message": "已有任务在运行"}), 429

    data = request.get_json(silent=True) or {}
    date_range = data.get("date_range")
    date_type = data.get("date_type")

    t = threading.Thread(target=do_spider_job, args=(date_range, date_type))
    t.start()
    return jsonify({"success": True, "message": "已触发爬取任务"})


def scheduled_job():
    print(f"[SCHEDULER] 定时任务触发: {datetime.now().isoformat()}")
    do_spider_job()


if __name__ == "__main__":
    scheduler = BackgroundScheduler()
    parts = CRON_SCHEDULE.split()
    if len(parts) != 5:
        print(f"[ERROR] CRON_SCHEDULE 格式错误: {CRON_SCHEDULE}")
        sys.exit(1)
    minute, hour, day, month, day_of_week = parts
    scheduler.add_job(
        scheduled_job,
        "cron",
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
    )
    scheduler.start()
    print(f"[INIT] 定时任务已启动: {CRON_SCHEDULE}")

    if os.getenv("RUN_ONCE") == "1":
        print("[INIT] RUN_ONCE=1，启动时立即执行一次")
        t = threading.Thread(target=do_spider_job)
        t.start()

    app.run(host="0.0.0.0", port=5000)
