"""
main.py - LoveSupremacy Universe v1.7 统一入口
========================================
FastAPI + python-telegram-bot 共享事件循环。

使用 asyncio.gather() 同时运行 uvicorn 和 telegram polling。
复用 bot.py 中所有的 handler 注册逻辑和 post_init 回调逻辑。
保留 bot.py 不删除（作为回滚入口）。
"""

import asyncio
import logging
import os
import signal
import atexit
import sys
import threading
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
import uvicorn

# ============================================================
# Core imports (与 bot.py 完全一致)
# ============================================================

# TTS engine
from characters.tts_engine import TTSEngine

from system.config import *

from characters.emotion import check_proactive_actions
from characters.stats import load_stats
from characters.anniversary import load_anniversaries
from characters.image_gen import generate_face_image, get_selfie_count

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
# Package imports - Command handlers (与 bot.py 完全一致)
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
# Package imports - Message handlers (与 bot.py 完全一致)
# ============================================================

from packages.handlers.message import (
    handle_photo, handle_document, button_callback, handle_message,
    send_active_message, voice_cmd, voice_sample_cmd, voice_train_cmd, voice_status_cmd,
    music_cmd, novel_cmd, tts_voice_toggle, tts_status_cmd, semantic_memory_cmd,
)

# ============================================================
# Package imports - Video import (与 bot.py 完全一致)
# ============================================================

from packages.importers.video import import_video_cmd, handle_video_import, get_video_analysis_context
from packages.analysis.chatlog import get_all_imported_relationships

# ============================================================
# Re-exports for backward compatibility (与 bot.py 完全一致)
# ============================================================

from characters.ai_core import call_ai, summarize_and_save_memory  # re-export for backward compatibility
from system.scheduler import scheduler

# ============================================================
# FastAPI 应用（v1.7 新增）
# ============================================================

from api import create_app
fastapi_app = create_app()


# ============================================================
# Post-init callback (与 bot.py 相同，但移除 aiohttp web_server)
# ============================================================

async def post_init(tg_app: Application):
    """Telegram Application 初始化回调。

    设置命令菜单、启动后台任务。
    与 bot.py 的 post_init 相同，但移除了 aiohttp web_server（已替换为 FastAPI/uvicorn）。
    """
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
    await tg_app.bot.set_my_commands(commands)
    logging.info("Bot 命令菜单已设置")

    # 保存 tg_app 实例到通知模块（用于 Web->Telegram 通知桥接）
    from core.notification import set_tg_app
    set_tg_app(tg_app)

    asyncio.create_task(scheduler(tg_app))

    # 主动行为后台任务
    asyncio.create_task(check_proactive_actions(tg_app))

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
                await send_active_message(tg_app, msg)
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
# 角色系统初始化 (与 bot.py 完全相同)
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
# 注册所有 handler (从 bot.py main() 提取)
# ============================================================

def register_handlers(tg_app: Application):
    """注册所有 Telegram handler（与 bot.py main() 中的 app.add_handler(...) 完全一致）"""

    # Basic commands
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CommandHandler("reset", reset))
    tg_app.add_handler(CommandHandler("selfie", selfie_cmd))
    tg_app.add_handler(CommandHandler("photos", photo_count_cmd))
    tg_app.add_handler(CommandHandler("memory", memory_cmd))
    tg_app.add_handler(CommandHandler("export", export_cmd))
    tg_app.add_handler(CommandHandler("import", import_cmd))

    # Skill commands
    tg_app.add_handler(CommandHandler("stats", stats_cmd))
    tg_app.add_handler(CommandHandler("analyze", analyze_cmd))
    tg_app.add_handler(CommandHandler("anniversary", anniversary_cmd))
    tg_app.add_handler(CommandHandler("sticker", sticker_cmd))

    # Chatlog import commands
    tg_app.add_handler(CommandHandler("import_chat", import_chat_cmd))
    tg_app.add_handler(CommandHandler("imported", list_imported_cmd))

    # Video import commands
    tg_app.add_handler(CommandHandler("import_video", import_video_cmd))

    # Quota commands
    tg_app.add_handler(CommandHandler("quota", quota_cmd))
    tg_app.add_handler(CommandHandler("quota_reset", quota_reset_cmd))

    # Voice/Music/Novel commands
    tg_app.add_handler(CommandHandler("voice", voice_cmd))
    tg_app.add_handler(CommandHandler("voicesample", voice_sample_cmd))
    tg_app.add_handler(CommandHandler("voicetrain", voice_train_cmd))
    tg_app.add_handler(CommandHandler("voicestatus", voice_status_cmd))
    tg_app.add_handler(CommandHandler("music", music_cmd))
    tg_app.add_handler(CommandHandler("novel", novel_cmd))

    # Memory commands
    tg_app.add_handler(CommandHandler("learned", learned_cmd))
    tg_app.add_handler(CommandHandler("forget", forget_cmd))
    tg_app.add_handler(CommandHandler("search", search_memory_cmd))
    tg_app.add_handler(CommandHandler("semantic", semantic_memory_cmd))  # 语义记忆搜索

    # Summary commands
    tg_app.add_handler(CommandHandler("summarize", summarize_cmd))

    # Version commands
    tg_app.add_handler(CommandHandler("version", version_cmd))
    tg_app.add_handler(CommandHandler("check_update", check_update_cmd))

    # Vision commands
    tg_app.add_handler(CommandHandler("analyze_img", analyze_img_cmd))
    tg_app.add_handler(CommandHandler("ocr", ocr_cmd))

    # TTS commands
    tg_app.add_handler(CommandHandler("tts", tts_voice_toggle))
    tg_app.add_handler(CommandHandler("ttsstatus", tts_status_cmd))

    # Face generation command
    tg_app.add_handler(CommandHandler("genface", generate_face_image))

    # ============================================================
    # Message handlers
    # ============================================================

    tg_app.add_handler(CallbackQueryHandler(button_callback))
    tg_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

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

    tg_app.add_handler(CommandHandler("toselfie", move_to_selfie))

    # Video import handler
    tg_app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_import))

    # Document handler (must be after video handler to avoid conflicts)
    tg_app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.PHOTO & ~filters.VIDEO, handle_document))

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
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, safe_handle_message))


# ============================================================
# 统一入口
# ============================================================


# ============================================================
# PID Lock - 防止重复启动
# ============================================================
PID_FILE = "/tmp/lovesupremacy-bot.pid"

def check_pid_lock():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                old_pid = int(f.read().strip())
            try:
                os.kill(old_pid, 0)
                print(f"[PID Lock] 进程 {old_pid} 已在运行，退出")
                sys.exit(0)
            except OSError:
                pass
        except (ValueError, OSError):
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

def release_pid_lock():
    try:
        if os.path.exists(PID_FILE):
            with open(PID_FILE, "r") as f:
                stored_pid = int(f.read().strip())
            if stored_pid == os.getpid():
                os.remove(PID_FILE)
    except (ValueError, OSError):
        pass

atexit.register(release_pid_lock)
async def main():
    """v1.7 统一入口：FastAPI + Telegram Bot 共享事件循环。"""
    # 初始化配置（必须在其他操作之前）
    init_config()

    # PID Lock 检查
    check_pid_lock()

    # SIGTERM 信号处理 - 清理 PID 文件
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, lambda: (release_pid_lock(), sys.exit(0)))
    # 同步 config 模块中的全局变量（from system.config import * 是绑定副本）
    import system.config as config_module
    global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_BASE, AI_API_KEY
    TELEGRAM_TOKEN = config_module.TELEGRAM_TOKEN
    YOUR_CHAT_ID = config_module.YOUR_CHAT_ID
    AI_API_BASE = config_module.AI_API_BASE
    AI_API_KEY = config_module.AI_API_KEY

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

    from system.config import BOT_VERSION, APP_NAME
    print(f"{APP_NAME} v{BOT_VERSION} 启动中...")

    # 配置 uvicorn（Web 服务始终启动，不依赖 Telegram Token）
    uv_config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(uv_config)

    if not TELEGRAM_TOKEN:
        print("⚠️  未设置 TELEGRAM_TOKEN，仅启动 Web 服务（Telegram Bot 已跳过）")
        print(f"🌐 Web 界面: http://0.0.0.0:{PORT}")
        await server.serve()
        return

    print(f"v{BOT_VERSION}: 角色扮演 + 游戏系统 + Web 界面 (FastAPI)")

    memory_count = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    print(f"已加载 {memory_count} 条长期记忆")

    anniversaries = load_anniversaries()
    if anniversaries:
        print(f"已加载 {len(anniversaries)} 个纪念日")

    stats = load_stats()
    print(f"历史消息总数: {stats.get('total_messages', 0)}")

    # 创建 Telegram Application
    request = HTTPXRequest(
        connect_timeout=30.0,
        read_timeout=60.0,
        write_timeout=30.0,
        pool_timeout=30.0,
    )
    tg_app = Application.builder().token(TELEGRAM_TOKEN).request(request).post_init(post_init).build()

    # 注册所有 handler
    register_handlers(tg_app)

    count = get_selfie_count()
    print(f"已加载 {count} 张自拍照片")
    print(f"AI模型: {AI_MODEL}")

    # 后台加载小说知识库（独立线程，不阻塞主循环）
    def _init_knowledge_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(init_knowledge())
        except Exception as e:
            print(f"小说知识库初始化错误: {e}")
        finally:
            loop.close()

    async def init_knowledge():
        try:
            print("正在加载小说知识库...")
            success = await init_novel_knowledge()
            if success:
                print("小说知识库加载完成")
            else:
                print("小说知识库加载失败")
        except Exception as e:
            print(f"小说知识库初始化错误: {e}")

    threading.Thread(target=_init_knowledge_thread, daemon=True).start()

    print("车如云已上线！（FastAPI + Telegram 模式）")

    # ============================================================
    # 共享事件循环：FastAPI + Telegram Bot 并行运行
    # ============================================================
    async with tg_app:
        await tg_app.start()
        await tg_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await server.serve()
        await tg_app.stop()


if __name__ == "__main__":
    asyncio.run(main())
