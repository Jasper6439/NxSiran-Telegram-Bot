"""文字消息处理（整合所有Skill）"""

import asyncio
import logging
import os
import random
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from system.config import load_config, PORT, YOUR_CHAT_ID, get_default_tz
from system.prompts import (
    AUTO_STICKER_TRIGGERS, detect_sticker_mood, detect_music_request,
    parse_dialogue_options,
)
from characters.memory_legacy import detect_correction, learn_from_correction, save_semantic_memory, parse_memory_tags
from characters.stats import record_request, update_stats_on_message
from characters.emotion import detect_emotion, add_reaction, update_user_active_time
from characters.chat_history import (
    get_history, save_chat_history, chat_histories, append_bot_message, human_typing_delay,
)
from characters.image_gen import (
    get_saved_selfies, SELFIE_CAPTIONS, send_selfie_to_chat,
    detect_scene, generate_scene_url, SCENE_PROMPTS, generate_sticker_url,
)
from packages.commands.basic import selfie_cmd, reset, memory_cmd
from packages.commands.skills import sticker_cmd, stats_cmd
from packages.commands.misc import anniversary_cmd

# [Services Integration] 导入服务模块
from services.tts_service import get_tts_service, send_voice_to_telegram
from services.image_service import get_image_service, send_image_to_telegram, detect_visual_intent, generate_prompt_from_context
from services.evolution_service import analyze_and_evolve, get_context_for_reply
from services.llm_service import get_llm_service

# Lazy import for bot.call_ai (the high-level AI function with character/memory/emotion integration)
from packages.commands.utils import _get_call_ai

# Lazy import for summarize_and_save_memory (defined in bot.py, the entry point)
def _get_summarize_func():
    from bot import summarize_and_save_memory
    return summarize_and_save_memory

# Lazy import for voice functions (defined in voice module to avoid circular imports)
def _get_tts_voice_toggle():
    from packages.handlers.voice import tts_voice_toggle
    return tts_voice_toggle

def _get_upload_voice_sample():
    from packages.handlers.voice import upload_voice_sample
    return upload_voice_sample

# Lazy import for _pending_voice_samples (defined in voice module)
def _get_pending_voice_samples():
    from packages.handlers.voice import _pending_voice_samples
    return _pending_voice_samples

__all__ = ["handle_message", "send_active_message", "send_smart_reply", "message_count"]

message_count = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # [Skill: TTS v1.4.7.2] 处理语音语料上传
    _pending_voice_samples = _get_pending_voice_samples()
    if chat_id in _pending_voice_samples and update.message.voice:
        await update.message.chat.send_action("typing")
        try:
            # 下载语音文件
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)

            # 创建临时文件
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp_path = tmp.name

            await file.download_to_drive(tmp_path)

            # 上传语料
            upload_voice_sample = _get_upload_voice_sample()
            result = await upload_voice_sample(tmp_path, "chayewoon")

            # 清理临时文件
            os.unlink(tmp_path)

            if result.get('success'):
                await update.message.reply_text(f"...收到了。{result.get('message', '')}")
            else:
                await update.message.reply_text(f"...保存失败。{result.get('error', '')}")

        except Exception as e:
            logging.error(f"处理语音语料失败: {e}")
            await update.message.reply_text("...处理语音出错了。")

        # 清除等待状态
        _pending_voice_samples.pop(chat_id, None)
        return

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
            await _get_tts_voice_toggle()(update, context)
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
        # 发送 Mini App 链接 - v1.4.8: 优先使用 public_url 配置（支持 Cloudflare HTTPS）
        config = load_config()
        public_url = config.get('public_url', '').rstrip('/')
        if public_url:
            miniapp_url = f"{public_url}/miniapp"
        elif os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
            miniapp_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/miniapp"
        else:
            miniapp_url = f"http://localhost:{PORT}/miniapp"
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

    # [Skill: 情绪识别] 检测用户情绪
    emotion = detect_emotion(user_text)

    # [Skill: self-improving] 更新用户最后活跃时间（用于主动行为）
    update_user_active_time(chat_id)

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
                    send_active_message(context.bot, random.choice(correction_responses))
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

    # [Service: Image] 检测视觉意图（新的图像生成服务）
    image_service = get_image_service()
    has_visual_intent, scene_type = detect_visual_intent(user_text)

    # [Skill: 打字模拟] 人类打字延迟
    await human_typing_delay(chat_id, update.get_bot(), len(user_text))

    # [Skill: 更新统计]
    update_stats_on_message(chat_id)

    # [Service: Evolution] 获取用户专属上下文（记忆+角色状态）
    user_id = update.effective_user.id
    character_id = "chayewoon"  # 当前默认角色
    try:
        evolution_context = await get_context_for_reply(user_id, character_id)
        if evolution_context.get("memories"):
            logging.info(f"[Evolution] 加载 {len(evolution_context['memories'])} 条记忆用于回复")
    except Exception as e:
        logging.error(f"[Evolution] 获取上下文失败: {e}")
        evolution_context = {}

    # AI回复（带情绪上下文和进化记忆）
    # 将记忆添加到历史上下文中
    history_with_context = history.copy()
    if evolution_context.get("memories"):
        memory_prompt = "以下是你记住的关于学长的事：\n" + "\n".join([f"- {m}" for m in evolution_context["memories"][:3]])
        history_with_context.insert(0, {"role": "system", "content": memory_prompt})
    if evolution_context.get("system_prompt_additions"):
        history_with_context.insert(0, {"role": "system", "content": evolution_context["system_prompt_additions"]})

    reply = await _get_call_ai()(user_text, history_with_context, emotion=emotion)

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

    # [Service: Evolution] 对话结束后分析并保存记忆（后台异步执行）
    async def _evolve_after_conversation():
        try:
            # 准备对话历史
            chat_history_for_evolution = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history[-20:]  # 最近20条消息
            ]
            result = await analyze_and_evolve(user_id, character_id, chat_history_for_evolution)
            logging.info(f"[Evolution] 分析完成: 新增 {result.get('memories_added', 0)} 条记忆, "
                        f"获得 {result.get('evolution_points', 0)} 进化点, "
                        f"情绪状态: {result.get('emotion_state', 'neutral')}")
        except Exception as e:
            logging.error(f"[Evolution] 对话分析失败: {e}")

    # 每5条消息触发一次进化分析
    if count % 5 == 0:
        asyncio.create_task(_evolve_after_conversation())

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
            from characters.music_skill import music_skill
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
    elif has_visual_intent and not want_selfie and not want_scene:
        # [Service: Image] 检测到视觉意图，生成并发送图片
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        await update.message.chat.send_action("upload_photo")
        try:
            # 生成提示词
            chat_history_for_image = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in history[-10:]
            ]
            prompt = generate_prompt_from_context(chat_history_for_image, scene_type)
            # 生成图片
            image_path = await image_service.generate_image(prompt)
            if image_path:
                # 发送图片
                caption = await _get_call_ai()(f"学长让我发照片，用一句话害羞地回应，不超过10个字")
                success = await send_image_to_telegram(context.bot, chat_id, image_path, caption)
                if success:
                    append_bot_message(chat_id, f"[发送了一张照片] {caption}")
                else:
                    await update.message.reply_text("...（发送图片失败）")
            else:
                await update.message.reply_text("...（图片生成失败）")
        except Exception as e:
            logging.error(f"[Image] 生成/发送图片失败: {e}")
            await update.message.reply_text("...（图片生成失败）")
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

async def send_smart_reply(update: Update, text: str):
    """智能回复: 根据用户设置选择文字/语音（集成 services/tts_service）"""
    if not text:
        return
    from packages.handlers.voice import user_voice_enabled
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if user_voice_enabled.get(user_id, False):
        # [Service: TTS] 使用新的 TTS 服务生成语音
        try:
            tts_service = get_tts_service()
            voice_path = await tts_service.synthesize(text, character_id="chayewoon", emotion="neutral")
            if voice_path and os.path.exists(voice_path):
                try:
                    with open(voice_path, "rb") as f:
                        await update.message.reply_voice(f)
                    await update.message.reply_text(f"🎤 {text}")
                except Exception as e:
                    logging.error(f"[TTS] 发送语音失败: {e}")
                    await update.message.reply_text(text)
                return
            else:
                logging.warning("[TTS] 语音合成失败，回退到文字")
        except Exception as e:
            logging.error(f"[TTS] 语音合成异常: {e}")

    await update.message.reply_text(text)


# [Service: TTS] 便捷函数：发送语音消息到指定聊天
async def send_voice_reply(bot, chat_id: int, text: str, character_id: str = "chayewoon") -> bool:
    """使用 TTS 服务发送语音消息"""
    try:
        success = await send_voice_to_telegram(bot, chat_id, text, character_id)
        return success
    except Exception as e:
        logging.error(f"[TTS] 发送语音消息失败: {e}")
        return False
