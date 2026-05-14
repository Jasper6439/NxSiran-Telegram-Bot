from telegram import Update
from telegram.ext import ContextTypes

from system.config import YOUR_CHAT_ID, load_json
from characters.memory_legacy import CORRECTIONS_FILE
from characters.stats import format_quota_report, load_quota_usage, save_quota_usage
from characters import stats
from packages.commands.utils import auto_delete_messages


async def quota_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看免费额度使用情况"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    report = format_quota_report()
    await update.message.reply_text(report)

@auto_delete_messages(delay=3)
async def quota_reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """重置额度告警和断开状态"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    stats._quota_shutdown = False

    usage = load_quota_usage()
    usage['warnings_sent'] = []
    usage['shutdown_triggered'] = False
    save_quota_usage(usage)

    await update.message.reply_text(
        "...额度监控已重置。\n\n"
        "🟢 告警已清除，自动断开已解除。\n"
        "⚠️ 注意：这只是重置了Bot内部的监控状态，\n"
        "Google Cloud 的实际额度不会重置。"
    )

# ============================================================
# /learned 命令 - 查看学到了什么
# ============================================================

@auto_delete_messages(delay=3)
async def learned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 Bot 从纠正中学到了什么"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    corrections = load_json(CORRECTIONS_FILE, [])

    if not corrections:
        await update.message.reply_text(
            "...我还没学到什么。\n\n"
            "（小声）...明纠正我的时候，我会记住的。"
        )
        return

    # 显示最近 10 条纠正记录
    recent = corrections[-10:]
    parts = [f"...明要看我学到了什么吗。\n\n📊 最近 {len(recent)} 条纠正记录：\n━━━━━━━━━━━━━━"]

    for i, c in enumerate(recent, 1):
        user_said = c.get("user_said", "")[:40]
        bot_said = c.get("bot_said", "")[:30]
        timestamp = c.get("timestamp", "")[:16]
        parts.append(f"\n{i}. [{timestamp}]")
        parts.append(f"   学长说：{user_said}")
        parts.append(f"   我说：{bot_said}...")

    parts.append("\n━━━━━━━━━━━━━━")
    parts.append(f"...一共记住了 {len(corrections)} 条。")
    parts.append("（低头）...我会努力改的。")

    await update.message.reply_text("\n".join(parts))
