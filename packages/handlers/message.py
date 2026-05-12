"""Message handlers for the Telegram bot."""

import asyncio
import base64
import io
import logging
import os
import random
import re
import zipfile
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import *
from prompts import AUTO_STICKER_TRIGGERS, detect_sticker_mood, detect_music_request
from memory_legacy import *
from stats import *
from emotion import *
import emotion  # needed for emotion._last_user_active_time
from chat_history import *
from image_gen import *
from tts_engine import TTSEngine

# Lazy import for bot.call_ai (the high-level AI function with character/memory/emotion integration)
def _get_call_ai():
    from bot import call_ai
    return call_ai
from characters import get_current_character
from music_skill import music_skill
from novel_knowledge import query_novel
from qdrant_memory import search_memories
from packages.commands.extra import _pending_analyze_img, _pending_ocr
from packages.commands.import_cmds import (
    pending_chat_imports,
    handle_chatlog_document,
)
from packages.commands.basic import selfie_cmd, reset, memory_cmd, export_cmd
from packages.commands.skills import sticker_cmd, analyze_cmd, stats_cmd
from packages.commands.misc import anniversary_cmd, quota_cmd

# Lazy import for summarize_and_save_memory (defined in bot.py, the entry point)
def _get_summarize_func():
    from bot import summarize_and_save_memory
    return summarize_and_save_memory

tts = TTSEngine()

__all__ = [
    "handle_photo",
    "handle_document",
    "button_callback",
    "handle_message",
    "send_active_message",
    "send_voice_message",
    "voice_cmd",
    "music_cmd",
    "novel_cmd",
    "qdrant_memory_cmd",
    "tts_voice_toggle",
    "tts_status_cmd",
    "send_smart_reply",
    "message_count",
]

# ============================================================
# 照片和文档处理
# ============================================================

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """智能处理收到的照片"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    photos = update.message.photo
    if not photos:
        return
    
    photo = photos[-1]
    
    # [Skill: vision-sandbox] [Skill: deepread-ocr] 检查是否有待处理的图片分析/OCR请求
    if chat_id in _pending_analyze_img:
        del _pending_analyze_img[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
                photo_bytes = await file.download_as_bytearray()
                image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                
                analysis_prompt = """请详细分析这张图片，包括：
1. 图片中有什么（主体内容）
2. 颜色、构图、风格
3. 如果有人物，描述其表情和动作
4. 图片的整体氛围和感受
5. 任何有趣的细节

用简洁的中文回答。"""
                
                result = await analyze_image_with_gemini(image_b64, analysis_prompt)
                if result:
                    if len(result) > 4000:
                        result = result[:4000] + "\n\n...太多了，就这些。"
                    await update.message.reply_text(result)
                else:
                    await update.message.reply_text("...分析失败了。再试试。")
                return
            except Exception as e:
                logging.error(f"[Skill: vision-sandbox] 图片分析失败: {e}")
                await update.message.reply_text("...出错了。")
                return
    
    if chat_id in _pending_ocr:
        del _pending_ocr[chat_id]
        if GEMINI_API_KEY:
            try:
                await update.message.chat.send_action("typing")
                file = await update.get_bot().get_file(photo.file_id)
                photo_bytes = await file.download_as_bytearray()
                image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                
                result = await ocr_document(image_b64)
                if result:
                    if len(result) > 4000:
                        for i in range(0, len(result), 4000):
                            await update.message.reply_text(result[i:i+4000])
                    else:
                        await update.message.reply_text(result)
                else:
                    await update.message.reply_text("...没识别出文字。")
                return
            except Exception as e:
                logging.error(f"[Skill: deepread-ocr] OCR失败: {e}")
                await update.message.reply_text("...出错了。")
                return
    
    try:
        # 先发送分析中的提示
        await update.message.chat.send_action("typing")
        
        # 获取照片文件
        file = await update.get_bot().get_file(photo.file_id)
        
        # 下载到临时位置进行分析
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = os.path.splitext(file.file_path)[1] or ".jpg"
        
        # 使用AI分析照片（通过文件URL）
        photo_url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file.file_path}"
        analysis = await analyze_photo_with_ai(photo_url)
        
        photo_type = analysis.get("type", "other")
        description = analysis.get("description", "")
        is_selfie = analysis.get("is_selfie", False)
        is_chayewoon = analysis.get("is_chayewoon", False)
        
        # 如果AI识别为车如云，强制设为自拍
        if is_chayewoon:
            is_selfie = True
            photo_type = "portrait"
        
        # 根据类型决定保存位置和回复
        if is_selfie or photo_type == "portrait" or is_chayewoon:
            # 保存为车如云的自拍
            filename = f"selfie_{timestamp}{ext}"
            char = get_current_character()
            char_id = char.config.id if char else None
            filepath = os.path.join(get_user_selfie_dir(chat_id, char_id), filename)
            await file.download_to_drive(filepath)
            count = get_selfie_count()
            
            # 更新统计
            stats = load_stats()
            stats["photos_received"] = stats.get("photos_received", 0) + 1
            save_stats(stats)
            
            responses = [
                f"...你给我发照片干什么。（已保存，现在共{count}张）",
                f"（看了一眼）...哦。（已保存，现在共{count}张）",
                f"...我保存了。现在共{count}张了。",
                f"（皱鼻子）...干嘛发这个。（已保存，现在共{count}张）",
                f"...收到了。现在共{count}张。",
            ]
            await update.message.reply_text(random.choice(responses))
        else:
            # 保存为用户照片（不统计在自拍里）
            filename = f"user_{timestamp}{ext}"
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
            await file.download_to_drive(filepath)
            
            # 根据类型生成回复
            reply = get_photo_response_by_type(photo_type, description)
            await update.message.reply_text(reply)
            
            # 记录到记忆中
            if photo_type == "food":
                save_memory_entry(f"明喜欢吃{description}")
            elif photo_type == "scenery":
                save_memory_entry(f"明去过{description}")
            
            # [Skill: vision-sandbox] 使用Gemini对图片进行深度分析并保存描述到记忆
            if GEMINI_API_KEY:
                try:
                    photo_bytes = await file.download_as_bytearray()
                    image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
                    detail_prompt = "请用一句简短的中文描述这张图片的内容（不超过30字）："
                    detail_desc = await analyze_image_with_gemini(image_b64, detail_prompt)
                    if detail_desc and len(detail_desc) > 5:
                        save_memory_entry(f"明发了一张图片：{detail_desc.strip()}")
                except Exception as e:
                    logging.debug(f"[Skill: vision-sandbox] 深度分析跳过: {e}")
            
    except Exception as e:
        logging.error(f"处理照片失败: {e}")
        await update.message.reply_text("...（照片处理失败了，再发一次试试）")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    doc = update.message.document
    if not doc:
        return
    
    # 检查是否在等待导入聊天记录
    if chat_id in pending_chat_imports and doc.file_name.lower().endswith('.txt'):
        await handle_chatlog_document(update, context)
        return
    
    if not doc.file_name.endswith('.zip'):
        return
    
    try:
        await update.message.chat.send_action("upload_document")
        
        file = await update.get_bot().get_file(doc.file_id)
        tmp_path = f"/tmp/import_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"
        await file.download_to_drive(tmp_path)
        
        imported_memories = 0
        imported_photos = 0
        imported_history = False
        imported_anniversaries = False
        imported_stats = False
        
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            for name in zf.namelist():
                if name == "long_term_memory.json":
                    zf.extract(name, get_user_dir(chat_id))
                    imported_memories = len(load_json(get_user_memory_file(chat_id), []))
                elif name == "chat_history.json":
                    zf.extract(name, DATA_DIR)
                    imported_history = True
                elif name == "anniversaries.json":
                    zf.extract(name, DATA_DIR)
                    imported_anniversaries = True
                elif name == "chat_stats.json":
                    zf.extract(name, DATA_DIR)
                    imported_stats = True
                elif name.startswith("selfies/"):
                    user_selfie_dir = get_user_selfie_dir(chat_id)
                    zf.extract(name, os.path.dirname(user_selfie_dir))
                    imported_photos += 1
        
        os.remove(tmp_path)
        
        if imported_history:
            chat_histories[chat_id] = load_chat_history(chat_id)
        
        parts = ["...收到了。\n\n"]
        parts.append(f"🧠 {imported_memories} 条记忆")
        parts.append(f"📸 {imported_photos} 张照片")
        if imported_history:
            parts.append("💬 对话历史")
        if imported_anniversaries:
            parts.append("🎉 纪念日")
        if imported_stats:
            parts.append("📊 聊天统计")
        parts.append("\n\n...都回来了。")
        
        await update.message.reply_text("\n".join(parts))
        logging.info(f"数据导入完成: {imported_memories}条记忆, {imported_photos}张照片")
    except Exception as e:
        logging.error(f"导入数据失败: {e}")
        await update.message.reply_text("...（导入失败了，再发一次试试）")

# ============================================================
# 内联按钮回调处理
# ============================================================

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
        await voice_cmd(update, context)
    elif data == "cmd_export":
        await export_cmd(update, context)
    elif data == "cmd_reset":
        await reset(update, context)

# ============================================================
# 文字消息处理（整合所有Skill）
# ============================================================

message_count = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text
    if not user_text:
        return
    
    # 处理键盘按钮文字，转发到对应命令
    button_commands = {
        "🎤 语音开关": "tts",
        "📷 自拍相册": "selfie",
        "🤖 Gemini AI": "gemini_help",
        "📊 统计": "stats",
        "🎨 表情包": "sticker",
        "🧠 记忆": "memory",
        "📅 纪念日": "anniversary",
        "❓ 帮助": "help",
        "🔄 重置": "reset",
    }
    if user_text in button_commands:
        cmd_name = button_commands[user_text]
        if cmd_name == "tts":
            await tts_voice_toggle(update, context)
            return
        elif cmd_name == "selfie":
            await selfie_cmd(update, context)
            return
        elif cmd_name == "gemini_help":
            await update.message.reply_text("使用: /gemini <你的问题>\n例如: /gemini 今天天气怎么样")
            return
        elif cmd_name == "stats":
            await stats_cmd(update, context)
            return
        elif cmd_name == "sticker":
            await sticker_cmd(update, context)
            return
        elif cmd_name == "memory":
            await memory_cmd(update, context)
            return
        elif cmd_name == "anniversary":
            await anniversary_cmd(update, context)
            return
        elif cmd_name == "help":
            await update.message.reply_text(
                "...学长需要帮助吗。\n\n"
                "可用命令：\n"
                "/start - 开始对话\n"
                "/reset - 重置对话\n"
                "/selfie - 查看自拍\n"
                "/stats - 统计数据\n"
                "/memory - 记忆管理\n"
                "/gemini - Gemini AI\n"
                "/analyze_img - 分析图片\n"
                "/ocr - 文档识别\n"
                "/research - 深度研究\n"
                "/sticker - 表情包\n"
                "/tts - 语音模式\n"
                "/anniversary - 纪念日\n"
                "/export - 导出数据\n"
                "/import - 导入数据"
            )
            return
        elif cmd_name == "reset":
            await reset(update, context)
            return
    elif user_text == "📱 Mini App":
        # 发送 Mini App 链接
        miniapp_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}/miniapp" if os.environ.get('RENDER_EXTERNAL_HOSTNAME') else f"http://localhost:{PORT}/miniapp"
        await update.message.reply_text(f"📱 点击打开 Mini App\n\n{miniapp_url}")
        return
    
    # [Skill: 免费额度监控] 检查额度
    quota_status = record_request()
    if quota_status == 'shutdown':
        await update.message.reply_text(
            "...（沉默）\n\n"
            "🚫 本月免费额度已用完，Bot已自动断开。\n"
            "下月1号自动恢复，或使用 /quota_reset 重置。\n"
            "使用 /quota 查看详细用量。"
        )
        return
    elif quota_status == 'critical':
        await update.message.reply_text(
            "...明。\n\n"
            "🟠 ⚠️ 免费额度即将用完（超过95%）！\n"
            "建议减少使用频率，或使用 /quota 查看详情。"
        )
    elif quota_status == 'warning':
        # 只在第一次警告时提醒
        pass  # 静默记录，不干扰对话
    
    # [Skill: 情绪识别] 检测用户情绪
    emotion = detect_emotion(user_text)
    
    # [Skill: self-improving] 更新用户最后活跃时间（用于主动行为）
    emotion._last_user_active_time[chat_id] = datetime.now(get_default_tz())
    
    # [Skill: self-improving] 检测用户纠正，从上一条 bot 回复中学习
    history = get_history(chat_id)
    if detect_correction(user_text) and history:
        # 找到最近一条 bot 回复
        last_bot_msg = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_bot_msg = msg.get("content", "")
                break
        if last_bot_msg:
            learn_from_correction(user_text, last_bot_msg)
            # [Skill: self-improving v1.4.7] 添加学习反馈提示
            correction_responses = [
                "...（记下了）",
                "...知道了。",
                "...我会记住的。",
                "...（低头）...明白了。",
            ]
            # 30% 概率回复，避免太频繁
            if random.random() < 0.3:
                asyncio.create_task(
                    send_active_message(context.bot, chat_id, random.choice(correction_responses))
                )
    
    # [Skill: 表情反应] 后台添加emoji反应
    asyncio.create_task(add_reaction(update, emotion))
    
    # 检测特殊请求
    want_selfie = any(kw in user_text for kw in ["自拍", "照片", "看看你", "发张照", "想看你", "你的照片", "看看你长什么样"])
    scene = detect_scene(user_text)
    want_scene = bool(scene) and not want_selfie
    want_show = any(kw in user_text for kw in ["给我看", "拍给我", "发给我看", "看看", "拍一张"]) and not want_selfie and not want_scene
    want_sticker = any(kw in user_text for kw in ["表情包", "表情", "贴图", "sticker", "发个.*表情"]) and not want_selfie
    sticker_mood = detect_sticker_mood(user_text) if want_sticker else ""
    
    # [Skill: Music] 检测音乐搜索请求
    want_music, song_name = detect_music_request(user_text)
    
    # [Skill: 打字模拟] 人类打字延迟
    await human_typing_delay(chat_id, update.get_bot(), len(user_text))
    
    # [Skill: 更新统计]
    update_stats_on_message(chat_id)
    
    # AI回复（带情绪上下文）
    reply = await _get_call_ai()(user_text, history, emotion=emotion)
    
    # v0.3: 解析对话选项
    parsed = parse_dialogue_options(reply)
    reply_text = parsed['text']
    has_options = parsed['has_options']
    options = parsed['options']
    
    # v0.3: 检测是否应该自动发送表情包
    auto_sticker_mood = None
    for mood, triggers in AUTO_STICKER_TRIGGERS.items():
        for trigger in triggers:
            if trigger in reply_text:
                auto_sticker_mood = mood
                break
        if auto_sticker_mood:
            break
    
    # [Skill: semantic-memory] 解析 AI 回复中的 [MEMORY:...] 标记并保存
    memory_tags = parse_memory_tags(reply)
    if memory_tags:
        for key, value in memory_tags:
            key = key.strip()
            value = value.strip()
            if key and value:
                # 自动分类
                if any(kw in key for kw in ["生日", "年龄", "星座"]):
                    category = "personal"
                elif any(kw in key for kw in ["喜欢", "爱好", "讨厌", "偏好"]):
                    category = "preference"
                elif any(kw in key for kw in ["家人", "妈妈", "爸爸", "朋友"]):
                    category = "family"
                elif any(kw in key for kw in ["工作", "公司", "学校"]):
                    category = "work"
                elif any(kw in key for kw in ["约定", "答应", "说好"]):
                    category = "promise"
                else:
                    category = "personal"
                save_semantic_memory(key, value, category)
        # 从回复中移除 [MEMORY:...] 标记，不让用户看到
        reply_text = re.sub(r'\[MEMORY:[^\]]+\]', '', reply_text).strip()
    
    # 保存消息（带时间戳，用于Web端同步）
    timestamp = datetime.now(get_default_tz()).isoformat()
    history.append({"role": "user", "content": user_text, "timestamp": timestamp})
    history.append({"role": "assistant", "content": reply_text, "timestamp": timestamp})
    
    if len(history) > 100:
        chat_histories[chat_id] = history[-100:]
    
    save_chat_history(chat_id, history)
    
    # 记忆提取
    count = message_count.get(chat_id, 0) + 1
    message_count[chat_id] = count
    if count >= 10:
        message_count[chat_id] = 0
        asyncio.create_task(_get_summarize_func()(chat_id))
    
    # 发送回复 + 附加内容
    if want_selfie:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        saved = get_saved_selfies()
        if saved:
            selfie_caption = await _get_call_ai()("学长看到了我的自拍，用一句话害羞地回应，不超过10个字")
        else:
            selfie_caption = random.choice(SELFIE_CAPTIONS)
        await send_selfie_to_chat(update.get_bot(), chat_id, selfie_caption)
    elif want_scene:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        scene_url = generate_scene_url(scene)
        if scene_url:
            caption = await _get_call_ai()(f"学长让我给他看{scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{scene}的照片] {caption}")
    elif want_show:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        random_scene = random.choice(list(SCENE_PROMPTS.keys()))
        scene_url = generate_scene_url(random_scene)
        if scene_url:
            caption = await _get_call_ai()(f"学长让我给他看{random_scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{random_scene}的照片] {caption}")
    elif want_sticker and sticker_mood:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        sticker_url = generate_sticker_url(sticker_mood)
        if sticker_url:
            caption = await _get_call_ai()(f"用一句话配合'{sticker_mood}'的表情，不超过10个字")
            await update.message.reply_photo(photo=sticker_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一个{sticker_mood}的表情包] {caption}")
    elif want_music and song_name:
        # [Skill: Music] 自然语言触发音乐搜索
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        await update.message.chat.send_action("typing")
        try:
            result = await music_skill.process_music_request(song_name)
            if result:
                song = result['song']
                style = result['style']
                review = result['review']
                music_reply = f"🎵 {song['title']}\n👤 {song['artist']}\n⏱️ {style['duration_formatted']}\n\n{review}\n\n▶️ {song['url']}"
                if song.get('thumbnail'):
                    try:
                        await update.message.reply_photo(photo=song['thumbnail'], caption=music_reply)
                    except Exception:
                        await update.message.reply_text(music_reply)
                else:
                    await update.message.reply_text(music_reply)
                append_bot_message(chat_id, f"[搜索了歌曲: {song['title']}] {review}")
            else:
                await update.message.reply_text("...没找到这首歌。（歌名对吗？）")
        except Exception as e:
            logging.error(f"[Music] 自然语言触发失败: {e}")
            await update.message.reply_text("...（搜索失败）网络问题。")
    else:
        # v0.3: 如果有选项，渲染 InlineKeyboard
        if has_options and options:
            keyboard = []
            for opt in options:
                effect_text = ""
                if opt.get('effects'):
                    parts = []
                    if opt['effects'].get('affection'):
                        parts.append(f"❤️{'+' if opt['effects']['affection'] > 0 else ''}{opt['effects']['affection']}")
                    if opt['effects'].get('happiness'):
                        parts.append(f"😊{'+' if opt['effects']['happiness'] > 0 else ''}{opt['effects']['happiness']}")
                    if opt['effects'].get('awakening'):
                        parts.append(f"🔮{'+' if opt['effects']['awakening'] > 0 else ''}{opt['effects']['awakening']}")
                    if parts:
                        effect_text = f" ({' '.join(parts)})"
                
                callback_data = f"opt_{opt['id']}_{chat_id}"
                keyboard.append([InlineKeyboardButton(
                    f"{opt['id']}. {opt['text']}{effect_text}",
                    callback_data=callback_data
                )])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(reply_text, reply_markup=reply_markup)
        else:
            # [Skill: TTS] 使用智能回复（支持语音模式）
            await send_smart_reply(update, reply_text)
        
        # v0.3: 自动发送表情包
        if auto_sticker_mood and random.random() < 0.3:  # 30% 概率自动发
            await asyncio.sleep(2)
            sticker_url = generate_sticker_url(auto_sticker_mood)
            if sticker_url:
                await update.message.reply_photo(photo=sticker_url, caption="...")

# ============================================================
# 主动消息（[Skill: 个性化主动] 增强）
# ============================================================

async def send_active_message(app, msg):
    if YOUR_CHAT_ID == 0:
        return
    try:
        await app.bot.send_message(chat_id=YOUR_CHAT_ID, text=msg)
    except Exception as e:
        logging.error(f"发送主动消息失败: {e}")

async def send_voice_message(app, chat_id: int, text: str):
    """使用TTS生成语音消息发送给用户"""
    try:
        import httpx
        # 使用免费的TTS API
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 使用 Google Translate TTS（免费）
            tts_url = "http://translate.google.com/translate_tts"
            params = {
                "ie": "UTF-8",
                "q": text[:200],  # 限制长度
                "tl": "ko",  # 韩语
                "client": "tw-ob",
            }
            resp = await client.get(tts_url, params=params,
                                     headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200 and len(resp.content) > 1000:
                voice_buf = io.BytesIO(resp.content)
                voice_buf.name = "voice.ogg"
                await app.bot.send_voice(chat_id=chat_id, voice=voice_buf)
                return True
    except Exception as e:
        logging.error(f"TTS语音生成失败: {e}")
    return False

# ============================================================
# 消息自动删除装饰器
# ============================================================

def auto_delete_messages(delay: int = 5):
    """装饰器：命令完成后自动删除用户命令和Bot回复，减少非真人聊天感"""
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_msg_id = update.message.message_id if update.message else None
            chat_id = update.effective_chat.id
            
            try:
                result = await func(update, context)
                
                # 延迟删除消息
                if user_msg_id and chat_id:
                    try:
                        await asyncio.sleep(delay)
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass  # 消息可能已被删除或权限不足
                
                return result
            except Exception as e:
                # 出错时也尝试删除用户消息
                if user_msg_id and chat_id:
                    try:
                        await asyncio.sleep(delay)
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass
                raise
        return wrapper
    return decorator


# Global state
user_voice_enabled = {}  # {user_id: bool}

@auto_delete_messages(delay=3)
async def voice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """让车如云发语音消息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 生成一句简短的韩语语音
    voice_texts = [
        "...안녕.",  # ...你好
        "...보고 싶어.",  # ...想你
        "...잘 자.",  # ...晚安
        "...밥 먹었어?",  # ...吃饭了吗
        "...어디야.",  # ...在哪
        "...미안해.",  # ...对不起
        "...고마워.",  # ...谢谢
        "...기다려.",  # ...等我
    ]
    
    text = random.choice(voice_texts)
    await update.message.chat.send_action("record_voice")
    
    success = await send_voice_message(context.bot, chat_id, text)
    if success:
        # 同时发送文字翻译
        translations = {
            "...안녕.": "...你好。",
            "...보고 싶어.": "...想你。",
            "...잘 자.": "...晚安。",
            "...밥 먹었어?": "...吃饭了吗？",
            "...어디야.": "...在哪。",
            "...미안해.": "...对不起。",
            "...고마워.": "...谢谢。",
            "...기다려.": "...等我。",
        }
        await update.message.reply_text(translations.get(text, text))
    else:
        await update.message.reply_text("...（沉默）语音发不出去。")


# [Skill: Music] 音乐搜索与评价
async def music_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索歌曲并给出车如云的评价"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取歌名（去掉 /music 命令）
    query = update.message.text.replace('/music', '').strip()
    if not query:
        await update.message.reply_text("...什么歌？（把歌名发给我）")
        return
    
    # 发送"正在搜索"状态
    await update.message.chat.send_action("typing")
    
    try:
        # 搜索歌曲
        result = await music_skill.process_music_request(query)
        
        if not result:
            await update.message.reply_text("...没找到这首歌。（歌名对吗？）")
            return
        
        song = result['song']
        style = result['style']
        review = result['review']
        
        # 构建回复
        reply = f"🎵 {song['title']}\n"
        reply += f"👤 {song['artist']}\n"
        reply += f"⏱️ {style['duration_formatted']}\n\n"
        reply += f"{review}\n\n"
        reply += f"▶️ {song['url']}"
        
        # 如果有封面，发送封面+文字
        if song.get('thumbnail'):
            try:
                await update.message.reply_photo(
                    photo=song['thumbnail'],
                    caption=reply
                )
            except Exception:
                # 封面发送失败，只发文字
                await update.message.reply_text(reply)
        else:
            await update.message.reply_text(reply)
        
        # 保存到聊天记录
        history = load_chat_history(chat_id)
        history.append({"role": "user", "content": f"/music {query}"})
        history.append({"role": "assistant", "content": review})
        save_chat_history(chat_id, history)
        
    except Exception as e:
        logging.error(f"[Music] 错误: {e}")
        await update.message.reply_text("...（搜索失败）网络问题。")

# [Skill: LightRAG] 小说知识查询 - v1.4.7 修复：添加依赖检查和更好错误提示
from novel_knowledge import query_novel, init_novel_knowledge

async def novel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询小说知识库"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 获取查询内容（去掉 /novel 命令）
    query = update.message.text.replace('/novel', '').strip()
    if not query:
        await update.message.reply_text("...想问小说里的什么？（把问题发给我）")
        return

    await update.message.chat.send_action("typing")

    try:
        # v1.4.7: 尝试初始化知识库（如果还没初始化）
        await init_novel_knowledge()

        # 查询知识库
        result = await query_novel(query)

        # 车如云风格的回应
        if result and len(result) > 10:
            # 让 AI 用车如云的口吻转述
            prompt = f"用户问：{query}\n\n小说中的相关内容：\n{result}\n\n请用车如云的口吻（极简、省略号、外冷内热）简短回答，不超过50个字。"
            response = await _get_call_ai()(prompt)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...小说里好像没有这个。")

    except ImportError as e:
        logging.error(f"[Novel] 缺少依赖: {e}")
        await update.message.reply_text("...（知识库依赖未安装）需要安装 LightRAG。")
    except Exception as e:
        logging.error(f"[Novel] 查询失败: {e}")
        await update.message.reply_text("...（查询失败）知识库还没准备好。")

# [Skill: ChromaDB] 记忆搜索 - v1.4.7 修复：改为 /semantic 命令避免冲突
from qdrant_memory import search_memories

async def qdrant_memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Qdrant语义记忆 - 使用 /semantic 命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    # 获取查询内容（支持 /semantic 或 /语义）
    query = update.message.text.replace('/semantic', '').replace('/语义', '').strip()
    if not query:
        await update.message.reply_text("...想找什么记忆？（比如：/semantic 我们聊过跑步吗）")
        return
    
    try:
        # 搜索记忆
        memories = search_memories(query, chat_id, n_results=3)
        
        if memories:
            # 找到相关记忆
            response = "...找到了。\n\n"
            for i, mem in enumerate(memories[:3]):
                content = mem.get('content', '')[:100]
                response += f"• {content}...\n"
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...不记得有这个。")
            
    except Exception as e:
        logging.error(f"[Memory] 搜索失败: {e}")
        await update.message.reply_text("...（搜索失败）记忆系统出问题了。")

# [Skill: TTS] 语音模式切换
async def tts_voice_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换语音回复模式"""
    user_id = update.effective_user.id
    user_voice_enabled[user_id] = not user_voice_enabled.get(user_id, False)
    if user_voice_enabled[user_id]:
        await update.message.reply_text(f"🎤 语音模式已开启\n当前引擎: {tts.current_backend}\n发送消息将自动语音回复")
    else:
        await update.message.reply_text("🔇 语音模式已关闭")

async def tts_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看 TTS 状态"""
    backends = []
    if await TTSEngine._backends["edge"].is_available():
        backends.append("Edge TTS ✅")
    if TTSEngine._backends["sovits"].is_available():
        backends.append("GPT-SoVITS ✅")
    if TTSEngine._backends["fish"].is_available():
        backends.append("Fish Speech ✅")
    status = "\n".join(backends) if backends else "无可用引擎 ❌"
    await update.message.reply_text(f"🔊 TTS 状态\n当前引擎: {tts.current_backend}\n可用引擎:\n{status}")

async def send_smart_reply(update: Update, text: str):
    """智能回复: 根据用户设置选择文字/语音"""
    if not text:
        return
    user_id = update.effective_user.id
    if user_voice_enabled.get(user_id, False):
        voice_path = await tts.synthesize(text)
        if voice_path:
            try:
                with open(voice_path, "rb") as f:
                    await update.message.reply_voice(f)
                await update.message.reply_text(f"🎤 {text}")
            except Exception as e:
                logging.error(f"发送语音失败: {e}")
                await update.message.reply_text(text)
            finally:
                TTSEngine._safe_delete(voice_path)
            return
    await update.message.reply_text(text)
