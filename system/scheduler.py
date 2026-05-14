"""
Background Scheduler - 后台定时任务
=====================================
从 bot.py 提取，降低多 SOLO 并行开发时的 Git 冲突。

包含：
  - scheduler: 定时任务调度器（纪念日提醒、早安/晚安、主动消息等）
"""

import asyncio
import logging
import random
from datetime import datetime

from config import get_default_tz, YOUR_CHAT_ID
from prompts import (
    MORNING_MESSAGES,
    NIGHT_MESSAGES,
    MISS_YOU_MESSAGES,
    RANDOM_CARE_MESSAGES,
    WEATHER_CARE_MESSAGES,
    SELFIE_CAPTIONS,
)
from anniversary import get_upcoming_anniversary, get_random_life_event
from weather import get_seoul_weather
from image_gen import send_selfie_to_chat
from packages.handlers.message import send_active_message


async def scheduler(app):
    while True:
        now = datetime.now(get_default_tz())

        # [Skill: 纪念日提醒] 每天早上8点检查
        if now.hour == 8 and 0 <= now.minute <= 5:
            upcoming = get_upcoming_anniversary(1)
            for u in upcoming:
                if u["days_until"] == 0:
                    await send_active_message(app, f"...明。今天是{u['name']}。\n\n（低头，声音很小）...我记得。")
                else:
                    await send_active_message(app, f"...明。{u['name']}还有{u['days_until']}天。\n\n...我只是随便说说。")
            await asyncio.sleep(3600)  # 每小时检查一次就够了

        # 早安消息（7:00-7:30）
        if now.hour == 7 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(MORNING_MESSAGES))

        # 晚安消息（23:00-23:30）
        if now.hour == 23 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(NIGHT_MESSAGES))

        # 想你消息（10:00-22:00 每小时）
        if 10 <= now.hour <= 22 and now.minute == 0 and random.random() < 0.05:
            await send_active_message(app, random.choice(MISS_YOU_MESSAGES))

        # 关心消息（12:00-21:00 每半小时）
        if 12 <= now.hour <= 21 and now.minute == 30 and random.random() < 0.03:
            await send_active_message(app, random.choice(RANDOM_CARE_MESSAGES))

        # [Skill: 生活事件] 随机生活事件（15:00-22:00）
        if 15 <= now.hour <= 22 and now.minute == 15 and random.random() < 0.02:
            event_msg = get_random_life_event()
            await send_active_message(app, event_msg)

        # [Skill: 天气关怀] 天气相关主动消息（7:30）
        if now.hour == 7 and 30 <= now.minute <= 35 and random.random() < 0.03:
            weather = await get_seoul_weather()
            if weather:
                desc = weather.get("desc", "").lower()
                temp = int(weather.get("temp_c", 20))
                if "rain" in desc or "drizzle" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("rain", ["...下雨了。"])))
                elif "snow" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("snow", ["...下雪了。"])))
                elif temp <= 5:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("cold", ["...好冷。"])))
                elif temp >= 30:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("hot", ["...好热。"])))

        # 主动发自拍（14:00-22:00）
        if 14 <= now.hour <= 22 and now.minute == 45 and random.random() < 0.02:
            caption = random.choice(SELFIE_CAPTIONS)
            await send_selfie_to_chat(app.bot, YOUR_CHAT_ID, caption)

        await asyncio.sleep(60)
