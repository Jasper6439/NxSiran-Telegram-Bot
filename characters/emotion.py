"""
情绪系统模块
============
从 bot.py 提取的情绪识别、表情反应、亲密度计算和主动行为系统。
"""

import asyncio
import logging
import random
from datetime import datetime

from prompts import (
    EMOTION_PATTERNS,
    REACTION_MAP,
    EMOTION_REACTIONS,
    INTIMACY_LEVELS,
    PROACTIVE_MISS_MESSAGES,
    PROACTIVE_GOODNIGHT_MESSAGES,
)
from config import YOUR_CHAT_ID, get_default_tz

from telegram import Update


# ============================================================
# [Skill: 情绪识别] 情绪检测系统
# ============================================================


def detect_emotion(text: str) -> str:
    """检测用户消息中的情绪"""
    scores = {}
    for emotion, keywords in EMOTION_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[emotion] = score
    if scores:
        return max(scores, key=scores.get)
    return ""


# ============================================================
# [Skill: 表情反应] Emoji Reaction 系统
# ============================================================


async def add_reaction(update: Update, emotion: str):
    """给用户消息添加emoji反应"""
    try:
        chat_id = update.effective_chat.id
        message_id = update.message.message_id
        bot = update.get_bot()

        # 先尝试关键词匹配
        text = update.message.text or ""
        matched_emojis = []
        for kw, emojis in REACTION_MAP.items():
            if kw in text:
                matched_emojis.extend(emojis)

        # 如果关键词没匹配到，用情绪匹配
        if not matched_emojis and emotion and emotion in EMOTION_REACTIONS:
            matched_emojis = random.choice(EMOTION_REACTIONS[emotion])

        if matched_emojis:
            # 随机延迟后添加反应（模拟真人）
            emoji = random.choice(matched_emojis)
            delay = random.uniform(0.5, 2.0)
            await asyncio.sleep(delay)
            await bot.setMessageReaction(chat_id=chat_id, message_id=message_id, reaction=[{"type": "emoji", "emoji": emoji}])
    except Exception as e:
        # 反应失败不影响主流程
        logging.debug(f"表情反应失败: {e}")


# ============================================================
# [Skill: 亲密度系统] 关系等级计算
# ============================================================


def calculate_intimacy(stats: dict) -> dict:
    """根据聊天统计计算亲密度"""
    total_msgs = stats.get("total_messages", 0)
    total_days = stats.get("total_days", 1)
    selfies_sent = stats.get("selfies_sent", 0)
    photos_received = stats.get("photos_received", 0)
    memories_count = stats.get("memories_count", 0)

    # 亲密度计算公式
    score = 0
    score += min(total_msgs * 0.3, 30)       # 消息量（最多30分）
    score += min(total_days * 1.5, 20)        # 天数（最多20分）
    score += min(selfies_sent * 2, 15)        # 自拍（最多15分）
    score += min(photos_received * 2, 15)     # 收到照片（最多15分）
    score += min(memories_count * 1, 20)      # 记忆（最多20分）
    score = min(int(score), 100)

    # 确定等级
    level_name = "陌生人"
    level_desc = ""
    for threshold, name, desc in reversed(INTIMACY_LEVELS):
        if score >= threshold:
            level_name = name
            level_desc = desc
            break

    return {
        "score": score,
        "level": level_name,
        "description": level_desc,
    }


def get_intimacy_context(stats: dict) -> str:
    """生成亲密度上下文，注入AI系统提示"""
    intimacy = calculate_intimacy(stats)
    return f"\n\n【关系状态】你和学长的关系亲密度：{intimacy['score']}/100（{intimacy['level']}）。{intimacy['description']}。请根据这个亲密度调整你对学长的态度。"


# ============================================================
# [Skill: proactive-agent] 主动行为系统
# ============================================================

# 用户最后活跃时间记录
_last_user_active_time = {}  # chat_id -> datetime


async def check_proactive_actions(app):
    """主动行为定时任务：检查是否需要主动发起对话"""
    while True:
        try:
            if YOUR_CHAT_ID == 0:
                await asyncio.sleep(3600)
                continue

            now = datetime.now(get_default_tz())
            last_active = _last_user_active_time.get(YOUR_CHAT_ID)

            # 检查用户是否超过 24 小时没发消息
            if last_active:
                hours_silent = (now - last_active).total_seconds() / 3600
                if hours_silent >= 24:
                    # 30% 概率发送主动消息
                    if random.random() < 0.30:
                        msg = random.choice(PROACTIVE_MISS_MESSAGES)
                        # 从 handlers 模块导入
                        from packages.handlers.message import send_active_message
                        await send_active_message(app, msg)
                        logging.info("[主动行为] 用户超过24小时未活跃，发送主动消息")
                    # 发送后重置计时，避免重复发送
                    _last_user_active_time[YOUR_CHAT_ID] = now

            # 每天晚上 10 点（22:00-22:05）有机会发晚安消息
            if now.hour == 22 and 0 <= now.minute <= 5 and random.random() < 0.15:
                msg = random.choice(PROACTIVE_GOODNIGHT_MESSAGES)
                from packages.handlers.message import send_active_message
                await send_active_message(app, msg)
                logging.info("[主动行为] 发送晚安消息")

        except Exception as e:
            logging.error(f"[主动行为] 定时任务出错: {e}")

        # 每小时检查一次
        await asyncio.sleep(3600)
