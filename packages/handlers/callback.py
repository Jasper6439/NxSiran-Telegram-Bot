"""内联按钮回调处理"""

from telegram import Update
from telegram.ext import ContextTypes

from system.config import *
from packages.commands.basic import selfie_cmd, reset, memory_cmd, export_cmd
from packages.commands.misc import anniversary_cmd, quota_cmd

# Lazy import for voice_cmd (defined in voice module to avoid circular imports)
def _get_voice_cmd():
    from packages.handlers.voice import voice_cmd
    return voice_cmd

__all__ = ["button_callback"]


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    data = query.data
    await query.answer()  # 确认按钮点击

    # 根据按钮触发对应命令
    if data == "cmd_selfie":
        await selfie_cmd(update, context)
    elif data == "cmd_memory":
        await memory_cmd(update, context)
    elif data == "cmd_anniversary":
        await anniversary_cmd(update, context)
    elif data == "cmd_quota":
        await quota_cmd(update, context)
    elif data == "cmd_voice":
        await _get_voice_cmd()(update, context)
    elif data == "cmd_export":
        await export_cmd(update, context)
    elif data == "cmd_reset":
        await reset(update, context)
