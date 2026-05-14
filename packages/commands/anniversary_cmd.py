from telegram import Update
from telegram.ext import ContextTypes

from system.config import YOUR_CHAT_ID
from characters.anniversary import load_anniversaries, get_upcoming_anniversary, add_anniversary, delete_anniversary
from packages.commands.utils import auto_delete_messages


# ============================================================
# /anniversary 命令
# ============================================================

@auto_delete_messages(delay=3)
async def anniversary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    args = context.args or []

    if not args:
        # 显示所有纪念日
        anniversaries = load_anniversaries()
        if not anniversaries:
            await update.message.reply_text(
                "...还没有纪念日。\n\n"
                "添加方法：\n"
                "/anniversary 添加 名称 YYYY-MM-DD\n"
                "/anniversary 删除 名称\n\n"
                "例如：/anniversary 添加 第一次见面 2025-01-15"
            )
            return

        # 显示列表 + 即将到来
        upcoming = get_upcoming_anniversary(30)
        parts = ["...学长想看纪念日吗。\n\n📌 我们的纪念日："]
        for a in anniversaries:
            parts.append(f"  • {a['name']}（{a['date']}）")

        if upcoming:
            parts.append("\n⏰ 即将到来：")
            for u in upcoming:
                if u["days_until"] == 0:
                    parts.append(f"  🎂 {u['name']} — 今天！！")
                else:
                    parts.append(f"  📅 {u['name']} — 还有 {u['days_until']} 天")

        parts.append("\n\n/anniversary 添加 名称 YYYY-MM-DD")
        parts.append("/anniversary 删除 名称")
        await update.message.reply_text("\n".join(parts))
        return

    action = args[0]

    if action == "添加" and len(args) >= 3:
        name = args[1]
        date_str = args[2]
        if add_anniversary(name, date_str):
            await update.message.reply_text(f"...记住了。{name} — {date_str}。\n\n（偷偷在心里数着日子）")
        else:
            await update.message.reply_text("...日期格式不对，或者这个名字已经有了。\n\n格式：YYYY-MM-DD（例如 2025-01-15）")

    elif action == "删除" and len(args) >= 2:
        name = " ".join(args[1:])
        if delete_anniversary(name):
            await update.message.reply_text(f"...删掉了{name}。\n\n（低头，不说话）")
        else:
            await update.message.reply_text(f"...没有叫'{name}'的纪念日。")

    else:
        await update.message.reply_text(
            "...用法不对。\n\n"
            "/anniversary → 查看所有纪念日\n"
            "/anniversary 添加 名称 YYYY-MM-DD\n"
            "/anniversary 删除 名称"
        )
