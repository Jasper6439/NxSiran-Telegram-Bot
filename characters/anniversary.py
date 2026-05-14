"""
纪念日系统模块
==============
从 bot.py 提取的纪念日相关函数：
  - load_anniversaries / save_anniversaries: 纪念日持久化
  - add_anniversary / delete_anniversary: 纪念日增删
  - get_upcoming_anniversary: 获取即将到来的纪念日
  - get_days_together: 计算在一起天数
  - get_random_life_event: 获取随机生活事件
"""

import random
from datetime import datetime

from system.config import (
    YOUR_CHAT_ID, get_default_tz,
    ANNIVERSARY_FILE,
    get_user_stats_file, save_json, load_json, _migrate_user_data,
)
from system.prompts import LIFE_EVENTS


def load_anniversaries() -> list:
    return load_json(ANNIVERSARY_FILE, [])


def save_anniversaries(anniversaries: list):
    save_json(ANNIVERSARY_FILE, anniversaries)


def add_anniversary(name: str, date_str: str) -> bool:
    """添加纪念日，date_str格式: YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False
    anniversaries = load_anniversaries()
    # 避免重复
    for a in anniversaries:
        if a["name"] == name:
            return False
    anniversaries.append({"name": name, "date": date_str})
    save_anniversaries(anniversaries)
    return True


def delete_anniversary(name: str) -> bool:
    anniversaries = load_anniversaries()
    new_list = [a for a in anniversaries if a["name"] != name]
    if len(new_list) < len(anniversaries):
        save_anniversaries(new_list)
        return True
    return False


def get_upcoming_anniversary(days_ahead: int = 7) -> dict:
    """获取即将到来的纪念日"""
    now = datetime.now(get_default_tz()).date()
    anniversaries = load_anniversaries()
    upcoming = []
    for a in anniversaries:
        try:
            date = datetime.strptime(a["date"], "%Y-%m-%d").date()
            # 计算今年的纪念日
            this_year = date.replace(year=now.year)
            if this_year < now:
                this_year = this_year.replace(year=now.year + 1)
            days_until = (this_year - now).days
            if 0 <= days_until <= days_ahead:
                upcoming.append({"name": a["name"], "date": a["date"], "days_until": days_until, "this_year": this_year.isoformat()})
        except ValueError:
            continue
    return sorted(upcoming, key=lambda x: x["days_until"])


def get_days_together() -> int:
    """计算在一起的天数（从第一次聊天开始）"""
    user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    stats = load_json(get_user_stats_file(user_id), {})
    first_chat = stats.get("first_chat_date", "")
    if first_chat:
        try:
            first = datetime.strptime(first_chat, "%Y-%m-%d").date()
            return (datetime.now(get_default_tz()).date() - first).days
        except ValueError:
            pass
    return 0


def get_random_life_event() -> str:
    """获取随机生活事件消息"""
    event = random.choice(LIFE_EVENTS)
    return random.choice(event["templates"])
