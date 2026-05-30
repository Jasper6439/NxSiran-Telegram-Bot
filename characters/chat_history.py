"""
聊天历史管理
从 bot.py 提取的聊天历史保存、加载、获取等函数
"""

import asyncio
import random

from system.config import (
    get_user_history_file,
    save_json,
    load_json,
    _migrate_user_data,
)


# ============================================================
# 聊天历史持久化
# ============================================================

def save_chat_history(chat_id: int, history: list):
    _migrate_user_data(chat_id)
    all_histories = load_json(get_user_history_file(chat_id), {})
    all_histories[str(chat_id)] = history[-100:]
    save_json(get_user_history_file(chat_id), all_histories)

def load_chat_history(chat_id: int) -> list:
    _migrate_user_data(chat_id)
    all_histories = load_json(get_user_history_file(chat_id), {})
    return all_histories.get(str(chat_id), [])


# ============================================================
# 对话历史（内存缓存）
# ============================================================

chat_histories = {}

def get_history(chat_id: int) -> list:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = load_chat_history(chat_id)
    return chat_histories[chat_id]

def append_bot_message(chat_id: int, content: str):
    """保存Bot发送的消息到聊天历史"""
    history = get_history(chat_id)
    history.append({"role": "assistant", "content": content})
    # 限制历史长度
    if len(history) > 100:
        history = history[-100:]
    chat_histories[chat_id] = history
    save_chat_history(chat_id, history)

    # [Skill: 向量记忆] 保存到向量数据库
    try:
        from characters.memory import add_memory
        add_memory(chat_id, content, {"role": "assistant"})
    except Exception:
        pass  # 静默失败


# ============================================================
# [Skill: 打字模拟] 人类打字速度模拟
# ============================================================

async def human_typing_delay(chat_id: int, bot, text_length: int = 20):
    """模拟人类打字延迟"""
    # 基础延迟 + 按回复长度增加
    base_delay = random.uniform(1.0, 3.0)
    length_delay = min(text_length * 0.05, 2.0)
    total_delay = base_delay + length_delay

    # 先发送typing状态（权限不足时静默跳过）
    try:
        await bot.send_chat_action(chat_id=chat_id, action="typing")
    except Exception:
        pass
    # 等待一段时间（typing状态会自动持续）
    await asyncio.sleep(min(total_delay, 10.0))
