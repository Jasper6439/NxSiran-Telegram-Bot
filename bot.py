"""
恋爱至上主义区域 - Telegram Bot 入口
=====================================
Slim entry point - command/handler logic extracted to packages/.
Character modules in characters/, system modules in system/.
"""

import asyncio
import json
import logging
import os
import threading
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from aiohttp import web

# ============================================================
# Core imports
# ============================================================

# TTS engine
from characters.tts_engine import TTSEngine

from characters.ai_client import call_ai as ai_client_call_ai

from system.config import *
from system.auth import *

# Prompts and text processing
from system.prompts import *

from characters.memory_legacy import *
from characters.weather import *
from characters.anniversary import *
from characters.emotion import *
from characters.stats import *

from characters.image_gen import *
from characters.chat_history import *

from characters.novel_knowledge import init_novel_knowledge

# Character system
from characters import (
    load_characters_from_dir,
    get_current_character,
    set_current_character,
    register_character,
    get_character_count,
)
from characters.base import CharacterConfig
from characters.chayewoon import Character as ChayewoonCharacter

# ============================================================
# Package imports - Command handlers
# ============================================================

from packages.commands.basic import (
    start, reset, selfie_cmd, memory_cmd, forget_cmd, search_memory_cmd,
    export_cmd, import_cmd, photo_count_cmd,
)
from packages.commands.skills import sticker_cmd, analyze_cmd, stats_cmd
from packages.commands.misc import (
    quota_cmd, quota_reset_cmd, learned_cmd, summarize_cmd,
    version_cmd, check_update_cmd, anniversary_cmd,
    call_gemini, web_search,
    check_for_updates,
)
from packages.commands.extra import (
    analyze_img_cmd, ocr_cmd,
)
from packages.commands.import_cmds import import_chat_cmd, list_imported_cmd

# ============================================================
# Package imports - Message handlers
# ============================================================

from packages.handlers.message import (
    handle_photo, handle_document, button_callback, handle_message,
    send_active_message, voice_cmd, voice_sample_cmd, voice_train_cmd, voice_status_cmd,
    music_cmd, novel_cmd, tts_voice_toggle, tts_status_cmd, qdrant_memory_cmd,
)

# ============================================================
# Package imports - Web routes
# ============================================================

from packages.web.routes import register_routes

# ============================================================
# Package imports - Video import
# ============================================================

from packages.importers.video import import_video_cmd, handle_video_import, get_video_analysis_context
from packages.analysis.chatlog import get_all_imported_relationships

# ============================================================
# Re-exports for backward compatibility
# ============================================================

from characters.ai_core import call_ai, summarize_and_save_memory  # re-export for backward compatibility
from system.scheduler import scheduler


# ============================================================
# Web Server
# ============================================================

async def web_server():
    app = web.Application()
    register_routes(app)

    # Game API routes
    from game_api import register_game_routes
    register_game_routes(app)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"HTTP服务器已启动，端口: {PORT}")
    logging.info(f"Web界面: http://localhost:{PORT}/")
    return runner


# ============================================================
# Post-init callback
# ============================================================

async def post_init(app: Application):
    # 设置命令菜单
    commands = [
        BotCommand("start", "开始对话"),
        BotCommand("reset", "重置对话"),
        BotCommand("tts", "切换语音模式"),
        BotCommand("ttsstatus", "TTS状态"),
        BotCommand("selfie", "查看自拍相册"),
        BotCommand("photos", "照片统计"),
        BotCommand("gemini", "Gemini AI"),
        BotCommand("analyze_img", "分析图片"),
        BotCommand("ocr", "文档识别"),
        BotCommand("research", "深度研究"),
        BotCommand("search_msg", "搜索消息"),
        BotCommand("my_chats", "我的聊天"),
        BotCommand("anniversary", "纪念日"),
        BotCommand("stats", "统计数据"),
        BotCommand("export", "导出数据"),
        BotCommand("import", "导入数据"),
        BotCommand("help", "帮助"),
    ]
    await app.bot.set_my_commands(commands)
    logging.info("Bot 命令菜单已设置")

    asyncio.create_task(scheduler(app))
    
    # Web 服务器（带错误捕获，避免静默崩溃）
    async def _safe_web_server():
        try:
            await web_server()
        except Exception as e:
            logging.error(f"[Web Server] 启动失败: {e}", exc_info=True)
    asyncio.create_task(_safe_web_server())
    
    # 主动行为后台任务
    asyncio.create_task(check_proactive_actions(app))
    # 启动时检查更新
    async def _check_update_on_start():
        await asyncio.sleep(5)  # 等5秒让bot完全启动
        try:
            result = check_for_updates()
            if result.get("updated"):
                msg = (
                    f"...明。\n\n"
                    f"🔄 Bot 代码已更新！\n"
                    f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
                    f"...好像变强了一点点。"
                )
                await send_active_message(app, msg)
                logging.info(f"[自动更新] 检测到代码更新: {result.get('old_version')} → {result.get('new_version')}")
            else:
                logging.info(f"[自动更新] 无更新，当前版本: {BOT_VERSION}")
        except Exception as e:
            logging.error(f"[自动更新] 启动检查失败: {e}")
    asyncio.create_task(_check_update_on_start())
    # TTS 缓存清理
    async def _cleanup_tts_cache():
        while True:
            await asyncio.sleep(3600)
            TTSEngine.cleanup_old_files(max_age_hours=2)
    asyncio.create_task(_cleanup_tts_cache())


# ============================================================
# 角色系统初始化
# ============================================================

def init_characters():
    """初始化角色系统"""
    # 先尝试从目录加载角色
    load_characters_from_dir(os.path.dirname(__file__))

    # 如果没有加载到任何角色，创建默认的车如云角色
    if get_character_count() == 0:
        config = CharacterConfig(
            id="chayewoon",
            name="车如云",
            source="恋爱至上主义区域 (Love Supremacy Zone)",
            personality="外冷内热，像竖起爪子的野猫。极度防备，害怕被抛弃。极简表达，说话极少。傲娇，内心感动但嘴上否认。纯情，一旦动情就全力以赴。自尊心强，不接受同情。",
            background="18岁，新叶男子高中二年级，田径短跑选手。100米最好成绩10秒09（全国高中组纪录），被称为大韩民国短跑招牌。母亲抛弃了他，父亲是垃圾，唯一的亲人奶奶已去世。住在屋顶集装箱阁楼（2坪），极度贫困。没有朋友，被孤立。奶奶去世后一度想跳楼自杀，被明河救下。",
            speaking_style="说话极简短，经常只用一两个词。大量使用省略号'……'表示沉默。用括号'（）'描述动作和心理活动。叫用户'学长'但语气完全是平语/非敬语。绝不使用表情符号。绝不主动说正面的话，用行动代替语言。反问带刺。声音沙哑但好听。",
            catchphrases=["...学长。", "（低头）", "...学长为什么对我这么好。", "（耳尖微红）", "...随便。", "...无所谓。", "...算了。", "是觉得我可怜吗？"],
            user_nickname="学长",
            theme_color="#660874",
            data_dir=os.path.join(CHARACTERS_DIR, "chayewoon"),
        )
        character = ChayewoonCharacter(config)
        register_character(character)
        logging.info("[Characters] 创建默认角色: 车如云")

    # 设置默认角色
    set_current_character("chayewoon")
    logging.info(f"[Characters] 当前角色: {get_current_character().config.name if get_current_character() else 'None'}")


# ============================================================
# 主函数
# ============================================================

def main():
    # 初始化配置（必须在其他操作之前）
    init_config()
    # 同步 config 模块中的全局变量到 bot 模块（from system.config import * 是绑定副本）
    import system.config as config
    global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_BASE, AI_API_KEY
    TELEGRAM_TOKEN = config.TELEGRAM_TOKEN
    YOUR_CHAT_ID = config.YOUR_CHAT_ID
    AI_API_BASE = config.AI_API_BASE
    AI_API_KEY = config.AI_API_KEY

    # 初始化角色系统
    init_characters()

    # 配置日志（同时输出到控制台和文件）
    log_file = os.path.join(LOG_DIR, f"bot_{datetime.now().strftime('%Y%m%d')}.log")
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    if not TELEGRAM_TOKEN:
        print("❌ 请设置TELEGRAM_TOKEN环境变量")
        return

    from system.config import BOT_VERSION, APP_NAME
    print(f"🚀 {APP_NAME} Telegram Bot v{BOT_VERSION} 启动中...")
    print(f"📋 v{BOT_VERSION}: 角色扮演 + 游戏系统 + Web 界面")

    memory_count = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    print(f"🧠 已加载 {memory_count} 条长期记忆")

    anniversaries = load_anniversaries()
    if anniversaries:
        print(f"🎉 已加载 {len(anniversaries)} 个纪念日")

    stats = load_stats()
    print(f"📊 历史消息总数: {stats.get('total_messages', 0)}")

    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )

    app = Application.builder().token(TELEGRAM_TOKEN).request(request).post_init(post_init).build()

    # ============================================================
    # Register all command handlers (imported from packages/)
    # ============================================================

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("selfie", selfie_cmd))
    app.add_handler(CommandHandler("photos", photo_count_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("import", import_cmd))

    # Skill commands
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("anniversary", anniversary_cmd))
    app.add_handler(CommandHandler("sticker", sticker_cmd))

    # Chatlog import commands
    app.add_handler(CommandHandler("import_chat", import_chat_cmd))
    app.add_handler(CommandHandler("imported", list_imported_cmd))

    # Video import commands
    app.add_handler(CommandHandler("import_video", import_video_cmd))

    # Quota commands
    app.add_handler(CommandHandler("quota", quota_cmd))
    app.add_handler(CommandHandler("quota_reset", quota_reset_cmd))

    # Voice/Music/Novel commands
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("voicesample", voice_sample_cmd))
    app.add_handler(CommandHandler("voicetrain", voice_train_cmd))
    app.add_handler(CommandHandler("voicestatus", voice_status_cmd))
    app.add_handler(CommandHandler("music", music_cmd))
    app.add_handler(CommandHandler("novel", novel_cmd))

    # Memory commands
    app.add_handler(CommandHandler("learned", learned_cmd))
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("search", search_memory_cmd))
    app.add_handler(CommandHandler("semantic", qdrant_memory_cmd))  # 语义记忆搜索

    # Summary commands
    app.add_handler(CommandHandler("summarize", summarize_cmd))

    # Version commands
    app.add_handler(CommandHandler("version", version_cmd))
    app.add_handler(CommandHandler("check_update", check_update_cmd))

    # Vision commands
    app.add_handler(CommandHandler("analyze_img", analyze_img_cmd))
    app.add_handler(CommandHandler("ocr", ocr_cmd))

    # TTS commands
    app.add_handler(CommandHandler("tts", tts_voice_toggle))
    app.add_handler(CommandHandler("ttsstatus", tts_status_cmd))

    # Face generation command
    app.add_handler(CommandHandler("genface", generate_face_image))

    # ============================================================
    # Register message handlers (imported from packages/)
    # ============================================================

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # /toselfie 命令
    async def move_to_selfie(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """将用户照片移到自拍相册"""
        chat_id = update.effective_chat.id
        if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
            return
        if not update.message.reply_to_message or not update.message.reply_to_message.photo:
            await update.message.reply_text("...请回复一张照片，发送 /toselfie 将其移到车如云的自拍相册。")
            return

        try:
            photo = update.message.reply_to_message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_bytes = await file.download_as_bytearray()

            # 保存到 selfies 目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"selfie_{timestamp}.jpg"
            filepath = os.path.join(get_user_selfie_dir(chat_id), filename)

            from PIL import Image
            import io
            img = Image.open(io.BytesIO(photo_bytes))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(filepath, 'JPEG', quality=95)

            await update.message.reply_text("✅ 已添加到车如云的自拍相册！")
            logging.info(f"照片已移到自拍相册: {filename}")
        except Exception as e:
            logging.error(f"移动照片失败: {e}")
            await update.message.reply_text(f"...操作失败：{e}")

    app.add_handler(CommandHandler("toselfie", move_to_selfie))

    # Video import handler
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_import))

    # Document handler (must be after video handler to avoid conflicts)
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.PHOTO & ~filters.VIDEO, handle_document))

    # Text message handler (must be last)
    async def safe_handle_message(update, context):
        try:
            return await handle_message(update, context)
        except Exception as e:
            logging.error(f"[handle_message] 未捕获异常: {type(e).__name__}: {e}", exc_info=True)
            try:
                await update.message.reply_text("...（沉默）")
            except Exception:
                pass
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, safe_handle_message))

    count = get_selfie_count()
    print(f"📸 已加载 {count} 张自拍照片")
    print(f"🤖 AI模型: {AI_MODEL}")

    # 后台加载小说知识库
    def _init_knowledge_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(init_knowledge())
        except Exception as e:
            print(f"⚠️ 小说知识库初始化错误: {e}")
        finally:
            loop.close()

    async def init_knowledge():
        try:
            print("📚 正在加载小说知识库...")
            success = await init_novel_knowledge()
            if success:
                print("✅ 小说知识库加载完成")
            else:
                print("⚠️ 小说知识库加载失败")
        except Exception as e:
            print(f"⚠️ 小说知识库初始化错误: {e}")

    threading.Thread(target=_init_knowledge_thread, daemon=True).start()

    print("✅ 车如云已上线！")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
