__all__ = [
    "start",
    "reset",
    "selfie_cmd",
    "memory_cmd",
    "forget_cmd",
    "search_memory_cmd",
    "export_cmd",
    "import_cmd",
    "photo_count_cmd",
]

import io
import os
import random
import zipfile
from datetime import datetime

from telegram import Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from config import (
    YOUR_CHAT_ID, MEMORY_FILE, HISTORY_FILE, ANNIVERSARY_FILE,
    STATS_FILE, SEMANTIC_MEMORY_FILE, DATA_DIR, LOG_DIR,
)
from prompts import SELFIE_CAPTIONS
from memory_legacy import (
    load_json, save_json, get_user_memory_file,
    categorize_memory, delete_semantic_memory, search_semantic_memory,
)
from stats import load_stats
from anniversary import load_anniversaries, get_days_together
from emotion import detect_emotion
from image_gen import get_selfie_count, get_saved_selfies, send_selfie_to_chat
from chat_history import get_history, chat_histories, save_chat_history
from characters import get_current_character
from tts_engine import TTSEngine

tts = TTSEngine()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        await update.message.reply_text("...你是谁？")
        return
    count = get_selfie_count()
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))
    memory_count = stats.get("memories_count", 0)
    photo_info = f"\n📸 我有 {count} 张照片" if count > 0 else "\n📸 你可以给我发照片"
    memory_info = f"\n🧠 我记得 {memory_count} 件事关于明" if memory_count > 0 else ""
    days = get_days_together()
    days_info = f"\n💕 我们认识 {days} 天了" if days > 0 else ""
    
    # 设置菜单按钮
    from telegram import BotCommand
    commands = [
        BotCommand("selfie", "📸 发自拍"),
        BotCommand("sticker", "🎨 表情包"),
        BotCommand("memory", "🧠 我的记忆"),
        BotCommand("search", "🔍 搜索记忆"),
        BotCommand("forget", "🗑️ 删除记忆"),
        BotCommand("stats", "📊 数据统计"),
        BotCommand("analyze", "📈 对话分析"),
        BotCommand("anniversary", "🎉 纪念日"),
        BotCommand("summarize", "📝 摘要生成"),
        BotCommand("version", "📋 版本信息"),
        BotCommand("quota", "💰 免费额度"),
        BotCommand("voice", "🎤 语音消息"),
        BotCommand("export", "📦 导出数据"),
        BotCommand("reset", "🔄 重置对话"),
        BotCommand("learned", "📝 学到了什么"),
    ]
    await update.get_bot().set_my_commands(commands)
    
    # 自定义键盘按钮（像 BotFather 那样的底部按钮）
    
    keyboard = [
        [KeyboardButton("🎤 语音开关"), KeyboardButton("📷 自拍相册")],
        [KeyboardButton("🤖 Gemini AI"), KeyboardButton("📊 统计")],
        [KeyboardButton("🎨 表情包"), KeyboardButton("🧠 记忆")],
        [KeyboardButton("📅 纪念日"), KeyboardButton("📱 Mini App")],
        [KeyboardButton("❓ 帮助"), KeyboardButton("🔄 重置")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"...又是你。\n\n（低头，不看你）\n\n...好吧，既然你来了。\n\n"
        f"点下面的按钮就行。{photo_info}{memory_info}{days_info}",
        reply_markup=reply_markup
    )

@auto_delete_messages(delay=3)
async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    chat_histories[chat_id] = []
    save_chat_history(chat_id, [])
    await update.message.reply_text("...（沉默了一会儿）\n\n...好吧，重新开始。")

@auto_delete_messages(delay=3)
async def selfie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    # 支持可选角色参数
    char_id = None
    if context.args and len(context.args) > 0:
        char_id = context.args[0]
    if not char_id:
        char = get_current_character()
        char_id = char.config.id if char else None
    saved = get_saved_selfies(chat_id)
    if saved:
        caption = await call_ai("学长让我发一张自拍给他，用一句话害羞地回应，不超过15个字")
    else:
        caption = random.choice(SELFIE_CAPTIONS)
    await send_selfie_to_chat(update.get_bot(), chat_id, caption)

@auto_delete_messages(delay=3)
async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # [Skill: semantic-memory] 同时显示语义记忆
    semantic_memories = load_json(SEMANTIC_MEMORY_FILE, [])
    memories = load_json(get_user_memory_file(chat_id), [])
    
    has_semantic = len(semantic_memories) > 0
    has_regular = len(memories) > 0
    
    if not has_semantic and not has_regular:
        await update.message.reply_text("...我还什么都不记得。多跟我说说话吧。")
        return
    
    parts = []
    
    # 显示语义记忆（结构化）
    if has_semantic:
        categories = {}
        for m in semantic_memories:
            cat = m.get("category", "其他")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)
        
        parts.append("...关于学长的事，我记得这些：\n")
        for cat, items in categories.items():
            cat_items = "\n".join([f"  • {m['key']}: {m['value']}" for m in items[-8:]])
            parts.append(f"📌 [{cat}]：\n{cat_items}")
    
    # 显示常规记忆（分类）
    if has_regular:
        categorized = {}
        for m in memories:
            cat = categorize_memory(m)
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(m)
        
        if has_semantic:
            parts.append("\n\n💬 对话记忆：")
        else:
            parts.append("...关于学长的事，我记得这些：\n")
        
        for cat in ["偏好", "事件", "情感", "约定", "其他"]:
            if cat in categorized:
                items = "\n".join([f"  • {m}" for m in categorized[cat][-8:]])
                parts.append(f"📌 {cat}：\n{items}")
    
    await update.message.reply_text("\n\n".join(parts))

# [Skill: semantic-memory] /forget 命令 - 删除特定记忆
@auto_delete_messages(delay=3)
async def forget_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "...学长想让我忘记什么？\n\n"
            "用法：/forget <关键词>\n"
            "例如：/forget 生日\n\n"
            "会删除所有包含该关键词的记忆。"
        )
        return
    
    keyword = " ".join(args)
    deleted = delete_semantic_memory(keyword)
    
    if deleted > 0:
        await update.message.reply_text(f"...删掉了 {deleted} 条关于「{keyword}」的记忆。\n\n（低头，不说话）")
    else:
        await update.message.reply_text(f"...没有找到关于「{keyword}」的记忆。")

# [Skill: semantic-memory] /search 命令 - 搜索记忆
@auto_delete_messages(delay=3)
async def search_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "...学长想找什么记忆？\n\n"
            "用法：/search <关键词>\n"
            "例如：/search 生日"
        )
        return
    
    query = " ".join(args)
    results = search_semantic_memory(query, topk=5)
    
    if not results:
        await update.message.reply_text(f"...没有找到和「{query}」相关的记忆。")
        return
    
    parts = [f"...找到了 {len(results)} 条相关记忆：\n"]
    for i, m in enumerate(results, 1):
        timestamp = m.get("timestamp", "")[:10]
        parts.append(f"{i}. [{m.get('category', '?')}] {m['key']}: {m['value']}（{timestamp}）")
    
    await update.message.reply_text("\n".join(parts))

async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    await update.message.chat.send_action("upload_document")
    
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(MEMORY_FILE):
            zf.write(MEMORY_FILE, "long_term_memory.json")
        if os.path.exists(HISTORY_FILE):
            zf.write(HISTORY_FILE, "chat_history.json")
        if os.path.exists(ANNIVERSARY_FILE):
            zf.write(ANNIVERSARY_FILE, "anniversaries.json")
        if os.path.exists(STATS_FILE):
            zf.write(STATS_FILE, "chat_stats.json")
        selfies = get_saved_selfies(chat_id)
        for s in selfies:
            selfie_dir = get_user_selfie_dir(chat_id)
            filepath = os.path.join(selfie_dir, s)
            if os.path.exists(filepath):
                zf.write(filepath, f"selfies/{s}")
    
    buf.seek(0)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    await update.message.reply_document(
        document=buf,
        filename=f"车如云数据_{timestamp}.zip",
        caption=f"...都给你了。{len(get_saved_selfies(chat_id))}张照片 + {len(load_json(get_user_memory_file(chat_id), []))}条记忆。"
    )

async def import_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    await update.message.reply_text("...把zip文件发给我就行。")

async def photo_count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    count = get_selfie_count()
    if count > 0:
        await update.message.reply_text(f"...我有 {count} 张照片了。都是明给我的。")
    else:
        await update.message.reply_text("...一张都没有。明要给我发照片吗？")
