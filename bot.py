"""
车如云 Telegram Bot - Wispbyte 部署版 v3.5
=============================================
Slim entry point - all command/handler logic extracted to packages/.

v3.5 Skill集成：
  [agent-orchestration] 5层Prompt架构优化系统提示词
  [gemini] Gemini API集成（备选AI + /gemini命令）
  [vision-sandbox] 图片深度分析（Gemini Vision）
  [deepread-ocr] 文档OCR文字提取（Gemini Vision替代）
  [gemini-deep-research] 深度研究（/research命令）
  [relay-for-telegram] Telegram消息历史搜索（/search_msg, /my_chats）
v3.4 Skill集成：
  [semantic-memory] 语义记忆系统（自动提取+搜索+删除）
  [claw-summarize-pro] 摘要生成（文本/URL/回复消息）
  [auto-updater] 自动更新检查（启动检测+版本管理）
v3.2 新增：
  [ui-ux-pro-max] 韩剧配色 Web 界面（聊天 + 仪表盘）
v3.1 Skill整合：
  [notebooklm] 从原作小说提取剧情/角色设定注入AI
  [brainstorming] 深度角色设定 + OOC防护机制
  [meeting-insights] /analyze 对话模式分析
  [slack-gif-creator] /sticker 表情包生成
v3.0 功能：
  [情绪识别] [对话统计] [天气查询] [纪念日系统] [亲密度系统]
  [生活事件] [表情反应] [打字模拟] [增强记忆] [个性化主动]
原有功能：AI对话 + 6模型fallback + 长期记忆 + 主动消息 + 真人/AI自拍 + 场景生成 + 联网搜索 + 导出导入
"""

import asyncio
import logging
import random
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

# [Skill: TTS 语音合成]
from tts_engine import TTSEngine

# [统一 AI 调用模块]
from ai_client import call_ai as ai_client_call_ai

# [Phase 1 P0] 拆分模块
from config import *
from auth import *

# [Phase 2] 提示词和文本处理
from prompts import *

# [Phase 3] 拆分模块
from memory_legacy import *
from weather import *
from anniversary import *
from emotion import *
from stats import *

# [Phase 4] 拆分模块
from image_gen import *
from chat_history import *

# [Skill: 小说知识库]
from novel_knowledge import init_novel_knowledge

# [角色系统] 支持多蒸馏角色动态加载
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
    gemini_cmd, analyze_img_cmd, ocr_cmd, research_cmd,
    search_msg_cmd, my_chats_cmd,
)
from packages.commands.import_cmds import import_chat_cmd, list_imported_cmd

# ============================================================
# Package imports - Message handlers
# ============================================================

from packages.handlers.message import (
    handle_photo, handle_document, button_callback, handle_message,
    send_active_message, voice_cmd, music_cmd,
    novel_cmd, tts_voice_toggle, tts_status_cmd,
)

# ============================================================
# Package imports - Web routes
# ============================================================

from packages.web.routes import register_routes

# ============================================================
# Package imports - Bridge routes
# ============================================================

from packages.bridge.routes import register_bridge_routes

# ============================================================
# Package imports - Video import
# ============================================================

from packages.importers.video import import_video_cmd, handle_video_import, get_video_analysis_context
from packages.analysis.chatlog import get_all_imported_relationships

# ============================================================
# HTTP client for AI calls
# ============================================================

import httpx

# ============================================================
# AI Core Functions (kept in bot.py - the heart of the bot)
# ============================================================


async def call_ai(user_message: str, chat_history: list = None, use_memory: bool = True, emotion: str = "") -> str:
    now = datetime.now(get_default_tz())
    weekdays = ['星期一','星期二','星期三','星期四','星期五','星期六','星期日']
    period = '凌晨' if now.hour < 6 else '上午' if now.hour < 12 else '下午' if now.hour < 18 else '晚上'
    time_info = f"当前时间：{now.strftime('%Y年%m月%d日 %H:%M')}，{period}，{weekdays[now.weekday()]}（韩国时间）"

    # [角色系统] 使用蒸馏角色的系统提示词
    character = get_current_character()
    if character:
        system_content = character.get_system_prompt({'user_name': '学长'})
    else:
        system_content = SYSTEM_PROMPT
    system_content += f"\n\n【实时信息】{time_info}"

    # [Skill: 亲密度系统] 注入关系状态
    stats = load_stats()
    stats["memories_count"] = len(load_json(get_user_memory_file(YOUR_CHAT_ID or 1), []))
    stats["selfies_sent"] = stats.get("selfies_sent", 0)
    stats["photos_received"] = stats.get("photos_received", 0)
    intimacy_ctx = get_intimacy_context(stats)
    system_content += intimacy_ctx

    # [Skill: 增强记忆] 注入分类记忆
    if use_memory:
        memory = get_long_term_memory()
        if memory:
            system_content += f"\n\n【你对学长的记忆】\n{memory}"

    # [Skill: semantic-memory] 注入语义记忆
    semantic_ctx = get_semantic_memory_context()
    if semantic_ctx:
        system_content += f"\n\n【你记住的关于学长的重要信息（语义记忆）】\n{semantic_ctx}"

    # [Skill: semantic-memory] 添加记忆提取提示
    system_content += "\n\n【记忆规则】如果学长提到了重要的个人信息（如生日、喜好、家人、工作、住址、重要约定等），请在回复末尾用 [MEMORY:关键词:具体内容] 标记。例如：如果学长说「我生日是3月15日」，你回复末尾加上 [MEMORY:学长的生日:3月15日]。只标记真正重要的信息，不要滥用。标记格式严格为 [MEMORY:key:value]，不要加多余空格。"

    # [Skill: 情绪识别] 注入情绪反应指引
    if emotion and emotion in EMOTION_RESPONSE_GUIDE:
        system_content += f"\n\n【当前情绪感知】{EMOTION_RESPONSE_GUIDE[emotion]}"

    # [Skill: 纪念日] 检查是否有即将到来的纪念日
    upcoming = get_upcoming_anniversary(3)
    if upcoming:
        ann_info = "，".join([f"{a['name']}还有{a['days_until']}天" for a in upcoming])
        system_content += f"\n\n【即将到来的纪念日】{ann_info}。如果合适的话，可以提起这件事。"

    # [Skill: 微信聊天记录导入] 注入已了解的人际关系
    imported_relationships = get_all_imported_relationships()
    if imported_relationships:
        system_content += f"\n\n【你了解学长的人际关系（从聊天记录分析得出）】{imported_relationships}\n\n在对话中，你可以自然地提及这些人，表现出你对学长生活的了解。比如当学长提到相关话题时，你可以说「你妈妈不是...」或「上次你提到...」"

    # [Skill: 视频分析] 注入从视频中学到的角色特点
    video_context = get_video_analysis_context()
    if video_context:
        system_content += f"\n\n{video_context}\n\n请尽量模仿上述说话风格和口头禅，让角色更加真实。"

    # [Skill: 天气] 注入天气信息
    weather = await get_seoul_weather()
    weather_ctx = get_weather_context(weather)
    if weather_ctx:
        system_content += weather_ctx

    # 联网搜索
    search_keywords = ["几点", "时间", "天气", "今天", "新闻", "最近", "现在", "多少度", "热搜", "发生了什么", "怎么了"]
    need_search = any(kw in user_message for kw in search_keywords)

    final_user_message = user_message
    if need_search:
        search_result = await web_search(user_message)
        if search_result:
            search_context = f"\n\n【联网搜索结果】\n{search_result}\n\n请结合以上搜索结果回答，如果搜索结果不相关就忽略。"
            final_user_message = user_message + search_context

    # 使用统一的 AI 调用模块
    try:
        content = await ai_client_call_ai(
            system_prompt=system_content,
            user_message=final_user_message,
            chat_history=chat_history,
        )
        # [Skill: humanize-ai-text] 对 AI 回复进行人性化后处理
        content = humanize_text(content)
        return content
    except RuntimeError:
        pass

    logging.error("所有OpenRouter模型都失败了")

    # [Skill: gemini] 所有OpenRouter模型失败时，fallback到Gemini
    if GEMINI_API_KEY:
        logging.info("[Skill: gemini] 尝试使用Gemini作为fallback...")
        try:
            gemini_result = await call_gemini(user_message)
            if gemini_result:
                gemini_result = humanize_text(gemini_result)
                logging.info("[Skill: gemini] Gemini fallback成功")
                return gemini_result
        except Exception as e:
            logging.error(f"[Skill: gemini] Gemini fallback失败: {e}")

    return "...（低头不说话）"


async def summarize_and_save_memory(chat_id: int):
    history = get_history(chat_id)
    if len(history) < 4:
        return

    recent = history[-10:]
    conversation_text = "\n".join([f"{'明' if m['role']=='user' else '车如云'}: {m['content']}" for m in recent])

    prompt = f"""请从以下对话中提取1-2条值得长期记住的关键信息，用简短的句子描述。
只提取关于学长的偏好、重要事件、情感变化、约定等信息。
如果没有值得记住的信息，回复"无"。

对话：
{conversation_text}

请直接输出记忆内容，每条一行，不要加序号或其他格式："""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODEL,
                    "messages": [
                        {"role": "system", "content": "你是记忆提取助手，只提取关键信息，保持简洁。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 100,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()

            if content and content != "无":
                for line in content.split("\n"):
                    line = line.strip().lstrip("-•· ").strip()
                    if line and len(line) > 3:
                        save_memory_entry(line)
    except Exception as e:
        logging.error(f"记忆提取失败: {e}")


# ============================================================
# Background scheduler
# ============================================================

async def scheduler(app):
    while True:
        now = datetime.now(get_default_tz())

        # [Skill: 纪念日提醒] 每天早上8点检查
        if now.hour == 8 and 0 <= now.minute <= 5:
            upcoming = get_upcoming_anniversary(1)
            for u in upcoming:
                if u["days_until"] == 0:
                    await send_active_message(app, f"...明。今天是{u['name']}。\n\n（低头，声音很小）...我记得。")
                else:
                    await send_active_message(app, f"...明。{u['name']}还有{u['days_until']}天。\n\n...我只是随便说说。")
            await asyncio.sleep(3600)  # 每小时检查一次就够了

        # 早安消息（7:00-7:30）
        if now.hour == 7 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(MORNING_MESSAGES))

        # 晚安消息（23:00-23:30）
        if now.hour == 23 and 0 <= now.minute <= 30 and random.random() < 0.02:
            await send_active_message(app, random.choice(NIGHT_MESSAGES))

        # 想你消息（10:00-22:00 每小时）
        if 10 <= now.hour <= 22 and now.minute == 0 and random.random() < 0.05:
            await send_active_message(app, random.choice(MISS_YOU_MESSAGES))

        # 关心消息（12:00-21:00 每半小时）
        if 12 <= now.hour <= 21 and now.minute == 30 and random.random() < 0.03:
            await send_active_message(app, random.choice(RANDOM_CARE_MESSAGES))

        # [Skill: 生活事件] 随机生活事件（15:00-22:00）
        if 15 <= now.hour <= 22 and now.minute == 15 and random.random() < 0.02:
            event_msg = get_random_life_event()
            await send_active_message(app, event_msg)

        # [Skill: 天气关怀] 天气相关主动消息（7:30）
        if now.hour == 7 and 30 <= now.minute <= 35 and random.random() < 0.03:
            weather = await get_seoul_weather()
            if weather:
                desc = weather.get("desc", "").lower()
                temp = int(weather.get("temp_c", 20))
                if "rain" in desc or "drizzle" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("rain", ["...下雨了。"])))
                elif "snow" in desc:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("snow", ["...下雪了。"])))
                elif temp <= 5:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("cold", ["...好冷。"])))
                elif temp >= 30:
                    await send_active_message(app, random.choice(WEATHER_CARE_MESSAGES.get("hot", ["...好热。"])))

        # 主动发自拍（14:00-22:00）
        if 14 <= now.hour <= 22 and now.minute == 45 and random.random() < 0.02:
            caption = random.choice(SELFIE_CAPTIONS)
            await send_selfie_to_chat(app.bot, YOUR_CHAT_ID, caption)

        await asyncio.sleep(60)


# ============================================================
# Web Server
# ============================================================

async def web_server():
    app = web.Application()
    register_routes(app)
    register_bridge_routes(app)

    # Game API routes
    from game_api import register_game_routes
    register_game_routes(app)
    # HTTP Bridge for SOLO sandbox file transfer
    setup_bridge_routes(app)

    # GitHub Webhook 自动部署
    GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    async def github_webhook(request):
        """接收 GitHub push 事件，自动部署"""
        try:
            import hmac
            import hashlib

            # 验证签名（如果配置了 secret）
            if GITHUB_WEBHOOK_SECRET:
                signature = request.headers.get('X-Hub-Signature-256', '')
                body = await request.read()
                expected = 'sha256=' + hmac.new(
                    GITHUB_WEBHOOK_SECRET.encode(), body, hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    return web.json_response({'error': 'Invalid signature'}, status=403)
            else:
                body = await request.read()

            data = json.loads(body)
            event = request.headers.get('X-GitHub-Event', '')

            # 只处理 push 事件
            if event != 'push':
                return web.json_response({'status': 'ignored', 'event': event})

            repo = data.get('repository', {}).get('full_name', '')
            ref = data.get('ref', '')
            commits = data.get('commits', [])

            logging.info(f"[Webhook] GitHub push: {repo} {ref} ({len(commits)} commits)")

            # 异步执行部署（不阻塞 webhook 响应）
            import asyncio
            asyncio.create_task(_auto_deploy(repo, ref, commits))

            return web.json_response({'status': 'deploying', 'repo': repo, 'commits': len(commits)})

        except Exception as e:
            logging.error(f"[Webhook] Error: {e}")
            return web.json_response({'error': str(e)}, status=500)

    async def _auto_deploy(repo, ref, commits):
        """后台执行自动部署"""
        try:
            import subprocess

            # 只部署 master 分支
            if ref != 'refs/heads/master':
                logging.info(f"[Webhook] Skipping non-master push: {ref}")
                return

            logging.info(f"[Webhook] Starting auto-deploy...")

            # 获取项目目录
            project_dir = os.path.dirname(os.path.abspath(__file__))

            # git pull
            result = subprocess.run(
                ['git', 'pull', 'origin', 'master'],
                cwd=project_dir, capture_output=True, text=True, timeout=60
            )
            logging.info(f"[Webhook] git pull: {result.stdout.strip()} {result.stderr.strip()}")

            if result.returncode != 0:
                logging.error(f"[Webhook] git pull failed: {result.stderr}")
                return

            # 检查是否有 docker-compose
            compose_file = os.path.join(project_dir, 'docker-compose.yml')
            if os.path.exists(compose_file):
                logging.info("[Webhook] Restarting Docker containers...")
                result = subprocess.run(
                    ['docker', 'compose', 'down'],
                    cwd=project_dir, capture_output=True, text=True, timeout=60
                )
                result = subprocess.run(
                    ['docker', 'compose', 'up', '-d', '--build'],
                    cwd=project_dir, capture_output=True, text=True, timeout=300
                )
                logging.info(f"[Webhook] Docker restart: {result.stdout.strip()}")

            logging.info(f"[Webhook] Deploy complete!")

        except Exception as e:
            logging.error(f"[Webhook] Deploy failed: {e}")

    app.router.add_post('/webhook/github', github_webhook)
    logging.info("[Webhook] GitHub auto-deploy route registered: POST /webhook/github")

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
    asyncio.create_task(web_server())
    # [Skill: proactive-agent] 启动主动行为后台任务
    asyncio.create_task(check_proactive_actions(app))
    # [Skill: auto-updater] 启动时检查更新
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
    # [Skill: TTS] 缓存清理
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
    # 同步 config 模块中的全局变量到 bot 模块（from config import * 是绑定副本）
    import config
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

    print("🚀 车如云 Telegram Bot v3.5 启动中...")
    print("📋 v3.5 重构：所有命令/处理器已提取到 packages/")

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
    app.add_handler(CommandHandler("music", music_cmd))
    app.add_handler(CommandHandler("novel", novel_cmd))

    # Memory commands
    app.add_handler(CommandHandler("learned", learned_cmd))
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("search", search_memory_cmd))

    # Summary commands
    app.add_handler(CommandHandler("summarize", summarize_cmd))

    # Version commands
    app.add_handler(CommandHandler("version", version_cmd))
    app.add_handler(CommandHandler("check_update", check_update_cmd))

    # Gemini commands
    app.add_handler(CommandHandler("gemini", gemini_cmd))
    app.add_handler(CommandHandler("analyze_img", analyze_img_cmd))
    app.add_handler(CommandHandler("ocr", ocr_cmd))
    app.add_handler(CommandHandler("research", research_cmd))

    # Relay commands
    app.add_handler(CommandHandler("search_msg", search_msg_cmd))
    app.add_handler(CommandHandler("my_chats", my_chats_cmd))

    # TTS commands
    app.add_handler(CommandHandler("tts", tts_voice_toggle))
    app.add_handler(CommandHandler("ttsstatus", tts_status_cmd))

    # Face generation command (from image_gen)
    app.add_handler(CommandHandler("genface", generate_face_image))

    # ============================================================
    # Register message handlers (imported from packages/)
    # ============================================================

    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Move to selfie command (inline definition - small enough to keep here)
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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    count = get_selfie_count()
    print(f"📸 已加载 {count} 张自拍照片")
    print(f"🤖 AI模型: {AI_MODEL}")

    # [Skill: LightRAG] 后台加载小说知识库
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
