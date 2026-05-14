__all__ = [
    "sticker_cmd",
    "analyze_cmd",
    "stats_cmd",
]

from telegram import Update
from telegram.ext import ContextTypes

from config import YOUR_CHAT_ID, load_json
from prompts import STICKER_PROMPTS, detect_sticker_mood
from characters.image_gen import generate_sticker_url, get_selfie_count
from characters.ai_client import call_ai
from characters.memory_legacy import get_user_memory_file
from characters.chat_history import append_bot_message
from characters.stats import load_stats
from characters.anniversary import load_anniversaries, get_days_together
from characters.chat_history import get_history
from characters.emotion import calculate_intimacy
from prompts import analyze_dialogue_patterns, get_relationship_advice
from packages.commands.misc import auto_delete_messages


async def sticker_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示可用表情
        moods = list(STICKER_PROMPTS.keys())
        mood_list = "、".join(moods)
        await update.message.reply_text(
            f"...学长想要表情包吗。\n\n"
            f"可用表情：{mood_list}\n\n"
            f"用法：/sticker 表情类型\n"
            f"例如：/sticker 害羞\n\n"
            f"也可以直接说「发个害羞的表情」之类的。"
        )
        return
    
    mood = args[0]
    if mood not in STICKER_PROMPTS:
        # 模糊匹配
        matched = detect_sticker_mood(" ".join(args))
        if matched:
            mood = matched
        else:
            await update.message.reply_text(f"...没有'{mood}'这个表情。\n\n可用：{'、'.join(STICKER_PROMPTS.keys())}")
            return
    
    url = generate_sticker_url(mood)
    if url:
        # 用AI生成一句符合表情的台词
        caption = await call_ai(f"用一句话配合'{mood}'的表情，不超过10个字，用括号表示内心独白")
        await update.message.reply_photo(photo=url, caption=caption)
        # 保存到聊天记录
        append_bot_message(chat_id, f"[发送了一个{mood}的表情包] {caption}")
    else:
        await update.message.reply_text("...生成失败了。再试试。")

# ============================================================
# /analyze 对话分析命令
# ============================================================

@auto_delete_messages(delay=3)
async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    await update.message.chat.send_action("typing")
    
    analysis = analyze_dialogue_patterns(chat_id)
    
    if "error" in analysis:
        await update.message.reply_text(f"...{analysis['error']}")
        return
    
    # 格式化分析报告
    emotion_dist = analysis.get("用户情绪分布", {})
    emotion_str = ""
    if isinstance(emotion_dist, dict):
        emotion_str = "、".join([f"{k}:{v}次" for k, v in emotion_dist.items()])
    
    report = (
        f"...明要看分析报告吗。\n\n"
        f"📊 对话模式分析报告\n"
        f"━━━━━━━━━━━━━━\n"
        f"💬 总对话数：{analysis['总对话数']}\n"
        f"📏 学长的平均消息：{analysis['用户平均消息长度']}\n"
        f"📏 我的平均回复：{analysis['车如云平均回复长度']}\n"
        f"🎯 明主动发起：{analysis['用户主动发起比例']}\n"
        f"📊 日均消息：{analysis['日均消息数']}\n"
        f"💗 亲密度：{analysis['亲密度']}\n"
        f"━━━━━━━━━━━━━━\n"
        f"😊 学长的情绪分布：{emotion_str if emotion_str else '正常'}\n"
        f"💝 关心表达：{analysis['关心表达次数']}次\n"
        f"😤 吃醋次数：{analysis['吃醋次数']}次\n"
        f"🌙 温暖表达：{analysis['温暖表达次数']}次\n"
        f"━━━━━━━━━━━━━━\n"
        f"🤔 我的回复风格：\n"
        f"  · 使用省略号：{analysis['车如云使用省略号']}\n"
        f"  · 内心独白：{analysis['车如云内心独白']}\n"
        f"  · 短回复比例：{analysis['车如云短回复(<20字)']}\n"
        f"━━━━━━━━━━━━━━\n"
    )
    
    # 添加关系建议
    advice = get_relationship_advice(analysis)
    report += f"\n{advice}"
    
    await update.message.reply_text(report)

# ============================================================
# /stats 命令
# ============================================================

@auto_delete_messages(delay=3)
async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))
    stats["selfies_sent"] = stats.get("selfies_sent", 0)
    stats["photos_received"] = stats.get("photos_received", 0)
    
    total_msgs = stats.get("total_messages", 0)
    total_days = stats.get("total_days", 0)
    today_count = stats.get("today_count", 0)
    first_date = stats.get("first_chat_date", "未知")
    days_together = get_days_together()
    
    # 亲密度
    intimacy = calculate_intimacy(stats)
    
    # 纪念日
    anniversaries = load_anniversaries()
    ann_count = len(anniversaries)
    
    # 对话条数
    history = get_history(chat_id)
    history_count = len(history)
    
    stats_text = (
        f"...明要看数据吗。\n\n"
        f"📊 我们的聊天数据\n"
        f"━━━━━━━━━━━━━━\n"
        f"💬 总消息数：{total_msgs}\n"
        f"📅 聊天天数：{total_days} 天\n"
        f"📝 当前对话：{history_count} 条\n"
        f"🕐 今天消息：{today_count} 条\n"
        f"💕 认识天数：{days_together} 天\n"
        f"🧠 记忆条数：{stats['memories_count']}\n"
        f"📸 我的照片：{get_selfie_count()} 张\n"
        f"📷 发过自拍：{stats['selfies_sent']} 次\n"
        f"🎁 收到照片：{stats['photos_received']} 张\n"
        f"🎉 纪念日：{ann_count} 个\n"
        f"━━━━━━━━━━━━━━\n"
        f"💗 亲密度：{intimacy['score']}/100（{intimacy['level']}）\n"
        f"📅 第一次聊天：{first_date}"
    )
    
    await update.message.reply_text(stats_text)
