import hashlib
import logging
import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from config import (
    BOT_VERSION,
    VERSION_FILE,
    YOUR_CHAT_ID,
    get_default_tz,
    load_json,
    save_json,
)
from packages.commands.utils import auto_delete_messages


# ============================================================
# 自动更新检查系统
# ============================================================

def calculate_bot_hash() -> str:
    """计算 bot.py 的 MD5 hash"""
    try:
        bot_path = os.path.abspath(__file__)
        with open(bot_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logging.error(f"[自动更新] 计算 hash 失败: {e}")
        return ""

def check_for_updates() -> dict:
    """检查 bot.py 是否有更新，返回更新信息"""
    current_hash = calculate_bot_hash()
    if not current_hash:
        return {"updated": False, "reason": "hash计算失败"}

    version_data = load_json(VERSION_FILE, {})

    if not version_data:
        # 首次运行，记录当前 hash
        version_data = {
            "version": BOT_VERSION,
            "last_check": datetime.now(get_default_tz()).strftime("%Y-%m-%d"),
            "bot_hash": current_hash,
        }
        save_json(VERSION_FILE, version_data)
        return {"updated": False, "reason": "首次运行，已记录版本信息"}

    saved_hash = version_data.get("bot_hash", "")
    saved_version = version_data.get("version", "未知")

    # 更新检查时间
    version_data["last_check"] = datetime.now(get_default_tz()).strftime("%Y-%m-%d")
    version_data["bot_hash"] = current_hash
    version_data["version"] = BOT_VERSION
    save_json(VERSION_FILE, version_data)

    if saved_hash and saved_hash != current_hash:
        return {
            "updated": True,
            "old_version": saved_version,
            "new_version": BOT_VERSION,
            "reason": "代码已变更",
        }

    return {"updated": False, "old_version": saved_version, "new_version": BOT_VERSION}

@auto_delete_messages(delay=3)
async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前版本信息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    version_data = load_json(VERSION_FILE, {})
    last_check = version_data.get("last_check", "未知")
    saved_version = version_data.get("version", "未知")
    current_hash = calculate_bot_hash()

    await update.message.reply_text(
        f"...版本信息。\n\n"
        f"📋 当前版本：{BOT_VERSION}\n"
        f"📦 记录版本：{saved_version}\n"
        f"🔍 代码Hash：{current_hash[:12]}...\n"
        f"📅 上次检查：{last_check}\n\n"
        f"使用 /check_update 手动检查更新。"
    )

@auto_delete_messages(delay=3)
async def check_update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动检查更新"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    await update.message.chat.send_action("typing")
    result = check_for_updates()

    if result["updated"]:
        await update.message.reply_text(
            f"...明。\n\n"
            f"🔄 Bot 代码已更新！\n"
            f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
            f"...好像变强了一点点。"
        )
    else:
        await update.message.reply_text(
            f"...没有更新。\n\n"
            f"📋 当前版本：{BOT_VERSION}\n"
            f"📅 上次检查：{result.get('last_check', datetime.now(get_default_tz()).strftime('%Y-%m-%d'))}\n\n"
            f"...一切正常。"
        )
