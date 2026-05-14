"""内联按钮回调处理"""

from telegram import Update
from telegram.ext import ContextTypes

from config import *
from packages.commands.basic import selfie_cmd, reset, memory_cmd, export_cmd
from packages.commands.skills import sticker_cmd, analyze_cmd, stats_cmd
from packages.commands.misc import anniversary_cmd, quota_cmd

# Lazy import for voice_cmd (defined in voice module to avoid circular imports)
def _get_voice_cmd():
    from packages.handlers.voice import voice_cmd
    return voice_cmd

# Lazy import for call_ai
def _get_call_ai():
    from bot import call_ai
    return call_ai

from characters.chat_history import get_history

__all__ = ["button_callback"]


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    data = query.data
    await query.answer()  # 确认按钮点击

    # v0.3: 处理对话选项回调
    if data.startswith("opt_"):
        parts = data.split("_")
        if len(parts) >= 3:
            opt_id = parts[1]
            # 解析选项效果
            # 这里简化处理：直接发送用户选择的选项作为新消息
            # 实际效果会在 handle_message 中处理
            await query.edit_message_reply_markup(reply_markup=None)  # 移除按钮
            # 模拟用户发送选项文本
            type('obj', (object,), {
                'effective_chat': type('obj', (object,), {'id': chat_id})(),
                'effective_user': type('obj', (object,), {'id': chat_id})(),
                'message': type('obj', (object,), {
                    'text': f"[选择选项 {opt_id}]",
                    'reply_text': lambda *args, **kwargs: None
                })()
            })()
            # 简单回复确认选择
            await query.message.reply_text(f"你选择了选项 {opt_id}...")
            # 然后触发 AI 回复
            history = get_history(chat_id)
            reply = await _get_call_ai()(f"用户选择了选项 {opt_id}", history)
            await query.message.reply_text(reply)
            return

    # 根据按钮触发对应命令
    if data == "cmd_selfie":
        await selfie_cmd(update, context)
    elif data == "cmd_sticker":
        await sticker_cmd(update, context)
    elif data == "cmd_memory":
        await memory_cmd(update, context)
    elif data == "cmd_stats":
        await stats_cmd(update, context)
    elif data == "cmd_analyze":
        await analyze_cmd(update, context)
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
