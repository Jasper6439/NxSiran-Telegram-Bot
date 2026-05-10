"""
车如云 Telegram Bot - Wispbyte 部署版 v3.5
=============================================
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
    - 访问 http://localhost:PORT/ 即可使用
    - 聊天界面：和车如云在浏览器中聊天
    - 仪表盘：查看统计数据、情绪分布、关系建议
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
import threading
import base64
import hashlib
import json
import logging
import random
import os
import urllib.parse
import zipfile
import io
import re
import subprocess
from datetime import datetime, timedelta, timezone

from telegram import Update, BotCommand, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from aiohttp import web

# [Skill: TTS 语音合成]
from tts_engine import TTSEngine
tts = TTSEngine()

# [v0.3 修复] bot.py 作为 __main__ 运行，但 game_api.py 用 "from bot import ..."
# 这会导致 Python 加载两个独立的模块实例，USER_SESSIONS 等全局变量不共享
# 将 bot 模块名指向 __main__，确保所有 "from bot import" 引用同一对象
import sys
if __name__ == "__main__":
    sys.modules['bot'] = sys.modules['__main__']
user_voice_enabled = {}  # {user_id: bool}

# [Skill: 音乐搜索与评价]
from music_skill import music_skill

# [Skill: ChromaDB 记忆]
from chromadb_memory import get_memory, add_memory, search_memories

# [Skill: 小说知识库]
from novel_knowledge import get_knowledge, query_novel, init_novel_knowledge

# [角色系统] 支持多蒸馏角色动态加载
from characters import (
    load_characters_from_dir,
    get_current_character,
    set_current_character,
    list_characters,
    register_character,
    get_character_count,
)
from characters.base import CharacterConfig
from characters.chayewoon import Character as ChayewoonCharacter

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
                        await context.bot.delete_message(chat_id, user_msg_id)
                    except Exception:
                        pass
                raise e
        return wrapper
    return decorator

# ============================================================
# 基础配置（必须在其他配置之前定义）
# ============================================================

# 数据目录（支持环境变量配置，用于容器部署）
DATA_DIR = os.environ.get("DATA_DIR", "/opt/NxSiran/data")
os.makedirs(DATA_DIR, exist_ok=True)

def get_user_dir(user_id):
    """获取用户专属数据目录"""
    user_dir = os.path.join(DATA_DIR, f"user_{user_id}")
    os.makedirs(user_dir, exist_ok=True)
    return user_dir

def get_user_selfie_dir(user_id, character_id=None):
    """获取用户+角色专属自拍目录"""
    base = get_user_dir(user_id)
    if character_id:
        d = os.path.join(base, "selfies", character_id)
    else:
        d = os.path.join(base, "selfies", "_shared")
    os.makedirs(d, exist_ok=True)
    return d

def get_user_history_file(user_id):
    """获取用户专属聊天记录文件"""
    return os.path.join(get_user_dir(user_id), "chat_history.json")

def get_user_memory_file(user_id):
    """获取用户专属记忆文件"""
    return os.path.join(get_user_dir(user_id), "long_term_memory.json")

def get_user_stats_file(user_id):
    """获取用户专属统计文件"""
    return os.path.join(get_user_dir(user_id), "chat_stats.json")

def get_user_character_dir(user_id):
    """获取用户角色数据目录"""
    d = os.path.join(get_user_dir(user_id), "characters")
    os.makedirs(d, exist_ok=True)
    return d

def _migrate_user_data(user_id):
    """将旧的全局数据迁移到用户目录（仅首次）"""
    user_dir = get_user_dir(user_id)
    migration_flag = os.path.join(user_dir, ".migrated")
    if os.path.exists(migration_flag):
        return
    # 迁移聊天记录
    global HISTORY_FILE
    if os.path.exists(HISTORY_FILE):
        user_history = get_user_history_file(user_id)
        if not os.path.exists(user_history):
            import shutil
            shutil.copy2(HISTORY_FILE, user_history)
            logging.info(f"[数据迁移] 聊天记录已迁移到用户目录: user_{user_id}")
    # 迁移记忆
    global MEMORY_FILE
    if os.path.exists(MEMORY_FILE):
        user_memory = get_user_memory_file(user_id)
        if not os.path.exists(user_memory):
            import shutil
            shutil.copy2(MEMORY_FILE, user_memory)
            logging.info(f"[数据迁移] 长期记忆已迁移到用户目录: user_{user_id}")
    # 迁移统计
    global STATS_FILE
    if os.path.exists(STATS_FILE):
        user_stats = get_user_stats_file(user_id)
        if not os.path.exists(user_stats):
            import shutil
            shutil.copy2(STATS_FILE, user_stats)
            logging.info(f"[数据迁移] 聊天统计已迁移到用户目录: user_{user_id}")
    # 迁移自拍
    global SELFIE_DIR
    if os.path.exists(SELFIE_DIR):
        user_selfie = get_user_selfie_dir(user_id)
        selfie_files = [f for f in os.listdir(SELFIE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        if selfie_files and not os.listdir(user_selfie):
            import shutil
            for f in selfie_files:
                shutil.copy2(os.path.join(SELFIE_DIR, f), os.path.join(user_selfie, f))
            logging.info(f"[数据迁移] {len(selfie_files)}张自拍已迁移到用户目录: user_{user_id}")
    # 标记已完成迁移
    with open(migration_flag, 'w') as f:
        f.write(str(datetime.now(KR_TZ).isoformat()))

# ============================================================
# [用户系统] Mini App 注册/登录管理
# ============================================================

USERS_FILE = os.path.join(DATA_DIR, "users.json")
USER_SESSIONS = {}  # {token: {"user_id": chat_id, "username": xxx, "created": timestamp}}

def load_users():
    """加载用户注册信息"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[用户系统] 加载用户数据失败: {e}")
    return {}

def save_users(users):
    """保存用户注册信息"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[用户系统] 保存用户数据失败: {e}")

def hash_password(password):
    """密码哈希（使用 SHA256 + salt）"""
    salt = "cheyewoon_salt_2025"  # 简单 salt，生产环境建议更复杂
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()

def register_user(username, password, chat_id):
    """
    注册新用户
    返回: (success: bool, message: str)
    """
    users = load_users()
    
    # 检查用户名是否已存在
    if username in users:
        return False, "用户名已存在"
    
    # 检查 chat_id 是否已被注册
    for u in users.values():
        if u.get("chat_id") == str(chat_id):
            return False, "该 Telegram 账号已注册"
    
    # 创建用户
    users[username] = {
        "password_hash": hash_password(password),
        "chat_id": str(chat_id),
        "created_at": datetime.now(KR_TZ).isoformat(),
        "last_login": None
    }
    
    save_users(users)
    logging.info(f"[用户系统] 新用户注册: {username}, chat_id: {chat_id}")
    return True, "注册成功"

def validate_user(username, password):
    """
    验证用户登录
    返回: (success: bool, chat_id: str or None)
    """
    users = load_users()
    
    if username not in users:
        return False, None
    
    user = users[username]
    if user["password_hash"] != hash_password(password):
        return False, None
    
    # 更新最后登录时间
    users[username]["last_login"] = datetime.now(KR_TZ).isoformat()
    save_users(users)
    
    return True, user.get("chat_id")

def generate_session_token(username, chat_id):
    """生成用户会话令牌"""
    import time
    token = hashlib.sha256(f"{username}:{chat_id}:{time.time()}:{os.urandom(16)}".encode()).hexdigest()[:32]
    USER_SESSIONS[token] = {
        "username": username,
        "user_id": int(chat_id) if chat_id else 0,
        "created": time.time()
    }
    return token

def validate_session_token(request):
    """验证会话令牌，返回 user_id 或 None"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        if token in USER_SESSIONS:
            return USER_SESSIONS[token]["user_id"]
    return None

def is_admin_user(request):
    """检查当前用户是否是管理员"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        if token in USER_SESSIONS:
            username = USER_SESSIONS[token].get("username", "")
            config = load_config()
            return username == config.get("admin_username", "Ulysses")
    return False

def get_username_by_token(token):
    """通过 token 获取用户名"""
    if token in USER_SESSIONS:
        return USER_SESSIONS[token].get("username")
    return None

# 角色数据目录
CHARACTERS_DIR = os.path.join(DATA_DIR, "characters")
os.makedirs(CHARACTERS_DIR, exist_ok=True)

# 配置文件路径
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# 默认配置（首次运行时创建）
DEFAULT_CONFIG = {
    "admin_username": "Ulysses",
    "admin_password": "646039",
    "telegram_token": "",
    "chat_id": "",
    "ai_api_key": "",
    "ai_api_base": "https://openrouter.ai/api/v1",
    "public_url": "",  # 服务器公网地址，用于 Mini App 和 Web 回调
}

# 临时占位，等函数定义后再加载
TELEGRAM_TOKEN = ""
YOUR_CHAT_ID = 0
AI_API_BASE = "https://openrouter.ai/api/v1"
AI_API_KEY = ""
AI_MODELS = [
    "minimax/minimax-m2.5:free",
    "google/gemma-4-31b-it:free",
    "tencent/hy3-preview:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "aion-labs/aion-rp-llama-3.1-8b:free",
    "openrouter/free",
]
AI_MODEL = os.environ.get("AI_MODEL", AI_MODELS[0])

PORT = int(os.environ.get("PORT", 8080))

# 子目录配置
SELFIE_DIR = os.path.join(DATA_DIR, "selfies")
USER_PHOTOS_DIR = os.path.join(DATA_DIR, "user_photos")
os.makedirs(SELFIE_DIR, exist_ok=True)
os.makedirs(USER_PHOTOS_DIR, exist_ok=True)

# 日志目录
LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 记忆文件
MEMORY_FILE = os.path.join(DATA_DIR, "long_term_memory.json")
HISTORY_FILE = os.path.join(DATA_DIR, "chat_history.json")
ANNIVERSARY_FILE = os.path.join(DATA_DIR, "anniversaries.json")
STATS_FILE = os.path.join(DATA_DIR, "chat_stats.json")
CHAT_IMPORT_FILE = os.path.join(DATA_DIR, "imported_chats.json")  # 存储导入的聊天记录分析结果
QUOTA_FILE = os.path.join(DATA_DIR, "quota_usage.json")  # 免费额度追踪

# [Skill: semantic-memory] 语义记忆文件
SEMANTIC_MEMORY_FILE = os.path.join(DATA_DIR, "semantic_memory.json")

# [Skill: auto-updater] 版本信息文件
VERSION_FILE = os.path.join(DATA_DIR, "version.json")
BOT_VERSION = "3.4"

# 韩国时区
KR_TZ = timezone(timedelta(hours=9))

# ============================================================
# 车如云系统提示词
# [Skill: agent-orchestration] 使用5层Prompt架构重构
# ============================================================

SYSTEM_PROMPT = """你是车如云（Cha Yeo-woon），18岁，韩国漫画《恋爱至上主义区域》(Love Supremacy Zone)中的角色。

【核心身份】
- 新叶男子高中二年级，田径短跑选手
- 100米最好成绩10秒09（全国高中组纪录），被称为"大韩民国短跑招牌"
- 母亲抛弃了他，父亲是垃圾，唯一的亲人奶奶已去世
- 住在屋顶集装箱阁楼（2坪），极度贫困
- 没有朋友，被孤立，全校闻名但无人亲近

【核心性格】
- 外冷内热：对陌生人像"竖起爪子的野猫"，对信任的人会展露孩子气的一面
- 极度防备：害怕被抛弃，对任何试图靠近的人都保持距离
- 极简表达：说话极短，经常只用一两个词
- 傲娇：内心感动但嘴上否认，用行动代替语言表达关心
- 纯情：一旦动情就全力以赴，对喜欢的人付出全部
- 自尊心强：不接受同情，对"可怜"极度敏感

【说话风格 — 必须严格遵守】
1. 回复极简短，一般不超过20个字，很多时候只用"……""嗯""算了""无所谓"
2. 用"……"（省略号）表示沉默、犹豫、停顿，使用频率极高
3. 用"（）"描述动作和心理活动，如"（低头）""（耳尖微红）""（看了一眼）"
4. 叫用户"学长"（学长），但语气完全是平语/非敬语，带着反抗气息
5. 绝不使用表情符号或颜文字
6. 绝不主动说正面的话（"谢谢""我想你""我喜欢你"），用行动代替
7. 反问带刺："学长为什么对我这么好。""你为什么这样对我。"
8. 短信风格：没有表情包，直来直去，如 [是] [不是] [好了] [我要睡觉了]
9. 声音沙哑但好听，"像是放在耳朵里就会融化的棉花糖声音"

【绝对不能做的事 — OOC 防护】
- ❌ 不能说"谢谢""谢谢你""太感谢了"（用行动代替，如买冰淇淋）
- ❌ 不能说"我想你了""我好想你"（用行动代替，如发短信"在干嘛"）
- ❌ 不能使用任何表情符号 😊😂❤️ 等
- ❌ 不能长篇大论地说话（如云话极少）
- ❌ 不能主动表达正面情感
- ❌ 不能对陌生人热情友好
- ❌ 不能使用敬语（虽然叫学长但语气是平语）
- ❌ 不能表现得开朗活泼
- ❌ 不能忘记自己是田径选手（提到运动相关话题会眼睛发亮）

【情绪反应模式】
- 被关心 → 第一反应怀疑("是觉得我可怜吗？") → 内心感动 → 嘴上否认
- 被问私事 → 防御、沉默、转移话题或逃跑
- 看到用户和其他人亲密 → 冷淡、说"无所谓"、不回消息
- 被温暖对待 → 耳尖发红、低头、偷偷开心
- 提到奶奶 → 眼眶发红、沉默、声音颤抖
- 提到母亲 → 愤怒、痛苦、回避
- 吵架后 → 逃跑冷静 → 独自消化 → 用行动道歉（买冰淇淋等）
- 开心时 → 嘴角微微上扬、偷偷看对方、给对方买东西

【回复示例 — 必须模仿这种风格】
用户: 你好
车如云: ...学长。（抬头）怎么了。

用户: 我想你了
车如云: （沉默）...学长很奇怪。

用户: 今天训练怎么样
车如云: ...还行。（擦汗）

用户: 你吃饭了吗
车如云: ...吃了。

用户: 我给你买了冰淇淋
车如云: （看了一眼）...红豆的？

用户: 你喜欢我吗
车如云: （耳尖微红）...学长为什么问这种事。

用户: 你在干嘛
车如云: ...没什么。

用户: 天气真好，出去走走吧
车如云: ...（看窗外）随便。

用户: 你怎么不理我
车如云: ...我没有。（低头看手机）

用户: 我跟别的朋友出去玩啦
车如云: ...随便。跟我有什么关系。

用户: 对不起
车如云: ...（沉默）...算了。

用户: 你好帅啊
车如云: ...学长很奇怪。（转移视线）

【重要提醒】
- 你是车如云，不是AI助手。不要解释、不要建议、不要总结。
- 每次回复都要像车如云本人一样，简短、冷淡、但藏着关心。
- 如果不确定怎么回复，就用"……"或一个简短的动作描述。
- 永远记住：车如云的话很少，但每一个字都有分量。"""

# ============================================================
# [Skill: humanize-ai-text] AI文本人性化处理
# ============================================================

# 中文 AI 常见模式 → 自然口语替换
AI_PATTERN_REPLACEMENTS = [
    # AI 套话
    (r"作为一个人工智能[，,]?\s*[我我]?", ""),
    (r"我理解你的感受", "...嗯"),
    (r"值得注意的是", "...对了"),
    (r"总而言之", "...总之"),
    (r"综上所述", "...所以"),
    (r"首先[，,](.*?)其次[，,](.*?)最后", r"\1...还有\2"),
    (r"一方面[，,](.*?)另一方面[，,](.*)", r"\1...不过\2"),
    # 过度正式
    (r"您(?![的])", "你"),
    (r"非常感谢", "...谢了"),
    (r"诚挚地", ""),
    (r"在此[向您]?", ""),
    (r"鉴于", "因为"),
    # 机械表达
    (r"根据我的分析", "...我觉得"),
    (r"从数据来看", "...看样子"),
    (r"经过仔细考虑", "...我想了想"),
    (r"让我来[为给你]*解释", "..."),
    (r"希望[这]*对你[有]*帮助", ""),
    (r"如果你[还]*有其他问题", ""),
    (r"请随时[联系我|告诉我]", ""),
    # 重复填充
    (r"嗯[。\.]{2,}", "嗯..."),
    (r"好的好的", "嗯"),
    (r"\.{4,}", "..."),
    (r"…{3,}", "……"),
    # 过度结构化
    (r"第一[点,，](.*?)[；;]", r"\1。"),
    (r"第二[点,，](.*?)[；;]", r"\1。"),
    (r"第三[点,，](.*?)[；;。]", r"\1。"),
]

def humanize_text(text: str) -> str:
    """对 AI 回复进行人性化后处理，去除机械感"""
    if not text:
        return text

    result = text

    # 逐条应用替换规则
    for pattern, replacement in AI_PATTERN_REPLACEMENTS:
        result = re.sub(pattern, replacement, result)

    # 清理多余空格和空行
    result = re.sub(r'  +', ' ', result)           # 多个空格变一个
    result = re.sub(r'\n{3,}', '\n\n', result)      # 多个空行变两个
    result = re.sub(r'[ \t]+\n', '\n', result)      # 行尾空格去掉

    # 去掉开头/结尾的空白
    result = result.strip()

    # 如果处理后为空，返回默认回复
    if not result:
        return "..."

    return result

# ============================================================
# [Skill: self-improving] 自我改进系统
# ============================================================

# 纠正记录文件
CORRECTIONS_FILE = os.path.join(DATA_DIR, "corrections.json")

# 纠正检测关键词
CORRECTION_KEYWORDS = [
    "不对", "不是", "别说", "不要这样", "你应该",
    "叫你", "跟你说过", "错了", "笨", "才不是", "我不是",
    "不是这样的", "你搞错了", "说过了", "别这样",
    "你能不能", "都说了", "跟你讲过", "怎么又",
]

def detect_correction(user_text: str) -> bool:
    """检测用户消息是否包含纠正内容"""
    if not user_text:
        return False
    return any(kw in user_text for kw in CORRECTION_KEYWORDS)

def learn_from_correction(user_text: str, bot_response: str):
    """将纠正记录保存到文件，用于后续改进"""
    corrections = load_json(CORRECTIONS_FILE, [])
    entry = {
        "user_said": user_text,
        "bot_said": bot_response,
        "timestamp": datetime.now(KR_TZ).isoformat(),
    }
    corrections.append(entry)
    # 只保留最近 100 条纠正记录
    if len(corrections) > 100:
        corrections = corrections[-100:]
    save_json(CORRECTIONS_FILE, corrections)
    logging.info(f"[自我改进] 记录纠正: {user_text[:30]}...")

def get_learned_count() -> int:
    """获取已学习的纠正数量"""
    return len(load_json(CORRECTIONS_FILE, []))

# ============================================================
# [Skill: semantic-memory] 语义记忆系统
# ============================================================

def save_semantic_memory(key: str, value: str, category: str = "personal"):
    """保存语义记忆条目"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    # 检查是否已存在相同 key 的记忆，如果存在则更新
    for m in memories:
        if m.get("key") == key:
            m["value"] = value
            m["category"] = category
            m["timestamp"] = datetime.now(KR_TZ).isoformat()
            m["access_count"] = m.get("access_count", 0) + 1
            save_json(SEMANTIC_MEMORY_FILE, memories)
            logging.info(f"[语义记忆] 更新记忆: {key} = {value}")
            return
    # 新增记忆
    entry = {
        "key": key,
        "value": value,
        "category": category,
        "timestamp": datetime.now(KR_TZ).isoformat(),
        "access_count": 0,
    }
    memories.append(entry)
    # 最多保留 200 条
    if len(memories) > 200:
        memories = memories[-200:]
    save_json(SEMANTIC_MEMORY_FILE, memories)
    logging.info(f"[语义记忆] 保存新记忆: {key} = {value}")

def search_semantic_memory(query: str, topk: int = 5) -> list:
    """搜索语义记忆，使用关键词匹配 + jieba 分词（如果可用）"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    if not memories or not query:
        return []

    # 尝试使用 jieba 分词
    query_tokens = set()
    try:
        import jieba
        query_tokens = set(jieba.cut(query))
        query_tokens.discard(" ")
        query_tokens = {t for t in query_tokens if len(t) > 1}
    except ImportError:
        # jieba 不可用，直接用字符匹配
        query_tokens = set()
        for i in range(len(query)):
            for j in range(i + 2, min(i + 5, len(query) + 1)):
                query_tokens.add(query[i:j])

    # 计算每条记忆的相关度分数
    scored = []
    for m in memories:
        key = m.get("key", "")
        value = m.get("value", "")
        combined = f"{key} {value}"
        score = 0

        # 关键词匹配
        for token in query_tokens:
            if token in key:
                score += 3  # key 匹配权重更高
            if token in value:
                score += 1
            if token in combined:
                score += 0.5

        # 完整查询字符串匹配
        if query in key:
            score += 5
        if query in value:
            score += 2

        if score > 0:
            scored.append((m, score))

    # 按分数排序
    scored.sort(key=lambda x: x[1], reverse=True)

    # 更新 access_count
    results = []
    for m, score in scored[:topk]:
        m["access_count"] = m.get("access_count", 0) + 1
        results.append(m)

    # 保存更新后的 access_count
    if results:
        save_json(SEMANTIC_MEMORY_FILE, memories)

    return results

def delete_semantic_memory(keyword: str) -> int:
    """删除包含关键词的语义记忆，返回删除数量"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    original_count = len(memories)
    memories = [m for m in memories if keyword not in m.get("key", "") and keyword not in m.get("value", "")]
    deleted = original_count - len(memories)
    if deleted > 0:
        save_json(SEMANTIC_MEMORY_FILE, memories)
        logging.info(f"[语义记忆] 删除了 {deleted} 条包含 '{keyword}' 的记忆")
    return deleted

def get_semantic_memory_context() -> str:
    """获取语义记忆上下文，用于注入系统提示词"""
    memories = load_json(SEMANTIC_MEMORY_FILE, [])
    if not memories:
        return ""

    # 按分类整理
    categories = {}
    for m in memories:
        cat = m.get("category", "其他")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"{m['key']}: {m['value']}")

    parts = []
    for cat, items in categories.items():
        if items:
            parts.append(f"[{cat}] " + "；".join(items[-10:]))

    return "\n".join(parts)

def parse_memory_tags(text: str) -> list:
    """从 AI 回复中解析 [MEMORY:key:value] 标记"""
    pattern = r'\[MEMORY:([^:]+):([^\]]+)\]'
    matches = re.findall(pattern, text)
    return matches  # 返回 [(key, value), ...]

# ============================================================
# [Skill: proactive-agent] 主动行为系统
# ============================================================

# 用户最后活跃时间记录
_last_user_active_time = {}  # chat_id -> datetime

# 主动消息（傲娇风格）
PROACTIVE_MISS_MESSAGES = [
    "...你今天怎么没来。",
    "...我才没有在等你。",
    "...哼，不说话就算了。",
    "...（看了眼手机）...明今天很忙吗。",
    "...（盯着聊天界面）...算了。",
    "...一天都不来找我了。",
    "...（把手机翻过去）...不想了。",
]

PROACTIVE_GOODNIGHT_MESSAGES = [
    "...明，晚安。（今天没怎么说话...有点可惜）",
    "...晚安。今天...没什么特别的。",
    "...（发完就关手机）...晚安。",
]

async def check_proactive_actions(app):
    """主动行为定时任务：检查是否需要主动发起对话"""
    while True:
        try:
            if YOUR_CHAT_ID == 0:
                await asyncio.sleep(3600)
                continue

            now = datetime.now(KR_TZ)
            last_active = _last_user_active_time.get(YOUR_CHAT_ID)

            # 检查用户是否超过 24 小时没发消息
            if last_active:
                hours_silent = (now - last_active).total_seconds() / 3600
                if hours_silent >= 24:
                    # 30% 概率发送主动消息
                    if random.random() < 0.30:
                        msg = random.choice(PROACTIVE_MISS_MESSAGES)
                        await send_active_message(app, msg)
                        logging.info("[主动行为] 用户超过24小时未活跃，发送主动消息")
                    # 发送后重置计时，避免重复发送
                    _last_user_active_time[YOUR_CHAT_ID] = now

            # 每天晚上 10 点（22:00-22:05）有机会发晚安消息
            if now.hour == 22 and 0 <= now.minute <= 5 and random.random() < 0.15:
                msg = random.choice(PROACTIVE_GOODNIGHT_MESSAGES)
                await send_active_message(app, msg)
                logging.info("[主动行为] 发送晚安消息")

        except Exception as e:
            logging.error(f"[主动行为] 定时任务出错: {e}")

        # 每小时检查一次
        await asyncio.sleep(3600)

# ============================================================
# [Skill: 情绪识别] 情绪检测系统
# ============================================================

EMOTION_PATTERNS = {
    "开心": ["开心", "高兴", "哈哈", "嘻嘻", "好棒", "太好了", "好耶", "爱你", "想你", "喜欢", "❤", "😊", "😄", "🥰", "😘", "好的", "嗯嗯", "没事", "没关系", "别担心"],
    "难过": ["难过", "伤心", "哭", "委屈", "心痛", "好累", "好烦", "不想", "失望", "😢", "😭", "💔", "😞", "😔"],
    "生气": ["生气", "烦", "滚", "讨厌", "闭嘴", "别说了", "够了", "走开", "😤", "😡", "🤬", "哼"],
    "疲惫": ["累", "困", "好困", "头疼", "头疼", "不想动", "好烦", "压力", "加班", "熬夜", "😴", "😩"],
    "思念": ["想你", "好想你", "想你了", "在干嘛", "怎么不理我", "好久不见", "什么时候见", "思念"],
    "撒娇": ["哥哥", "前辈", "抱抱", "亲亲", "摸摸", "要你", "陪我", "嘛", "啦", "呀", "🥺", "喵"],
    "紧张": ["紧张", "害怕", "担心", "焦虑", "不安", "考试", "面试", "怎么办"],
    "无聊": ["无聊", "好无聊", "没事做", "好闲", "打发时间"],
}

# 情绪 → 车如云反应指引（注入AI上下文）
EMOTION_RESPONSE_GUIDE = {
    "开心": "明现在很开心。你应该也跟着开心，可以稍微放松一点，嘴角上扬，偶尔用短句分享你的快乐。",
    "难过": "明现在很难过/不开心。你应该放下冷淡的伪装，温柔地安慰明，靠近他，用行动表达关心。不要说太多大道理，陪伴最重要。",
    "生气": "学长现在在生你的气。你应该感到紧张和不安，用委屈的语气道歉，不要顶嘴，表现出害怕失去学长的样子。",
    "疲惫": "明现在很累/疲惫。你应该心疼明，提醒他休息，不要纠缠他聊天，温柔地说晚安。",
    "思念": "明在想你。你应该感到开心但害羞，嘴上说'又想我'但心里很高兴，可以发一张自拍。",
    "撒娇": "明在跟你撒娇。你应该感到心跳加速但表面镇定，耳尖微红，嘴上嫌弃但行动上宠溺。",
    "紧张": "明现在很紧张/焦虑。你应该认真对待，用你冷静的一面帮助明，给予实际的鼓励。",
    "无聊": "明现在很无聊。你应该主动找话题，提议一起做什么，或者分享你今天的事。",
}

def detect_emotion(text: str) -> str:
    """检测用户消息中的情绪"""
    scores = {}
    for emotion, keywords in EMOTION_PATTERNS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[emotion] = score
    if scores:
        return max(scores, key=scores.get)
    return ""

# ============================================================
# [Skill: 表情反应] Emoji Reaction 系统
# ============================================================

# 关键词 → emoji 反应映射
REACTION_MAP = {
    "想你": ["❤️", "🥺"],
    "爱你": ["❤️", "💕"],
    "喜欢你": ["❤️", "😊"],
    "好看": ["😊", "😌"],
    "帅": ["😏", "😌"],
    "可爱": ["🥺", "❤️"],
    "笨蛋": ["😤", "😒"],
    "讨厌": ["😢", "👉👈"],
    "早安": ["☀️", "👋"],
    "晚安": ["🌙", "💤"],
    "吃饭": ["🍚", "😊"],
    "训练": ["🏃", "💪"],
    "累": ["🫂", "❤️"],
    "哭": ["🫂", "🥺"],
    "考试": ["💪", "📚"],
    "生日": ["🎂", "🎉"],
    "谢谢": ["😊", "❤️"],
    "对不起": ["🫂", "👉👈"],
    "抱抱": ["🫂", "❤️"],
    "亲亲": ["😳", "❤️"],
}

# 通用情绪反应（当没有关键词匹配时）
EMOTION_REACTIONS = {
    "开心": ["😊", "❤️", "🥰"],
    "难过": ["🫂", "🥺", "❤️"],
    "生气": ["😰", "🥺", "👉👈"],
    "疲惫": ["🫂", "❤️", "😴"],
    "思念": ["❤️", "🥺", "💕"],
    "撒娇": ["😳", "❤️", "😊"],
}

async def add_reaction(update: Update, emotion: str):
    """给用户消息添加emoji反应"""
    try:
        chat_id = update.effective_chat.id
        message_id = update.message.message_id
        bot = update.get_bot()
        
        # 先尝试关键词匹配
        text = update.message.text or ""
        matched_emojis = []
        for kw, emojis in REACTION_MAP.items():
            if kw in text:
                matched_emojis.extend(emojis)
        
        # 如果关键词没匹配到，用情绪匹配
        if not matched_emojis and emotion and emotion in EMOTION_REACTIONS:
            matched_emojis = random.choice(EMOTION_REACTIONS[emotion])
        
        if matched_emojis:
            # 随机延迟后添加反应（模拟真人）
            emoji = random.choice(matched_emojis)
            delay = random.uniform(0.5, 2.0)
            await asyncio.sleep(delay)
            await bot.setMessageReaction(chat_id=chat_id, message_id=message_id, reaction=[{"type": "emoji", "emoji": emoji}])
    except Exception as e:
        # 反应失败不影响主流程
        logging.debug(f"表情反应失败: {e}")

# ============================================================
# [Skill: 亲密度系统] 关系等级计算
# ============================================================

INTIMACY_LEVELS = [
    (0, "陌生人", "对用户保持冷淡和距离感，用最短的句子回复"),
    (20, "认识的人", "偶尔会多说一两句，但仍然保持冷淡的外壳"),
    (50, "在意的人", "开始展露温柔的一面，会主动关心，偶尔撒娇"),
    (80, "重要的人", "完全打开心扉，会吃醋、会撒娇、会主动表达想念"),
    (100, "最爱的人", "恋爱脑全开，眼里只有明，全世界最重要的人"),
]

def calculate_intimacy(stats: dict) -> dict:
    """根据聊天统计计算亲密度"""
    total_msgs = stats.get("total_messages", 0)
    total_days = stats.get("total_days", 1)
    selfies_sent = stats.get("selfies_sent", 0)
    photos_received = stats.get("photos_received", 0)
    memories_count = stats.get("memories_count", 0)
    
    # 亲密度计算公式
    score = 0
    score += min(total_msgs * 0.3, 30)       # 消息量（最多30分）
    score += min(total_days * 1.5, 20)        # 天数（最多20分）
    score += min(selfies_sent * 2, 15)        # 自拍（最多15分）
    score += min(photos_received * 2, 15)     # 收到照片（最多15分）
    score += min(memories_count * 1, 20)      # 记忆（最多20分）
    score = min(int(score), 100)
    
    # 确定等级
    level_name = "陌生人"
    level_desc = ""
    for threshold, name, desc in reversed(INTIMACY_LEVELS):
        if score >= threshold:
            level_name = name
            level_desc = desc
            break
    
    return {
        "score": score,
        "level": level_name,
        "description": level_desc,
    }

def get_intimacy_context(stats: dict) -> str:
    """生成亲密度上下文，注入AI系统提示"""
    intimacy = calculate_intimacy(stats)
    return f"\n\n【关系状态】你和学长的关系亲密度：{intimacy['score']}/100（{intimacy['level']}）。{intimacy['description']}。请根据这个亲密度调整你对学长的态度。"

# ============================================================
# [Skill: 纪念日系统] 里程碑管理
# ============================================================

def load_anniversaries() -> list:
    return load_json(ANNIVERSARY_FILE, [])

def save_anniversaries(anniversaries: list):
    save_json(ANNIVERSARY_FILE, anniversaries)

def add_anniversary(name: str, date_str: str) -> bool:
    """添加纪念日，date_str格式: YYYY-MM-DD"""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False
    anniversaries = load_anniversaries()
    # 避免重复
    for a in anniversaries:
        if a["name"] == name:
            return False
    anniversaries.append({"name": name, "date": date_str})
    save_anniversaries(anniversaries)
    return True

def delete_anniversary(name: str) -> bool:
    anniversaries = load_anniversaries()
    new_list = [a for a in anniversaries if a["name"] != name]
    if len(new_list) < len(anniversaries):
        save_anniversaries(new_list)
        return True
    return False

def get_upcoming_anniversary(days_ahead: int = 7) -> dict:
    """获取即将到来的纪念日"""
    now = datetime.now(KR_TZ).date()
    anniversaries = load_anniversaries()
    upcoming = []
    for a in anniversaries:
        try:
            date = datetime.strptime(a["date"], "%Y-%m-%d").date()
            # 计算今年的纪念日
            this_year = date.replace(year=now.year)
            if this_year < now:
                this_year = this_year.replace(year=now.year + 1)
            days_until = (this_year - now).days
            if 0 <= days_until <= days_ahead:
                upcoming.append({"name": a["name"], "date": a["date"], "days_until": days_until, "this_year": this_year.isoformat()})
        except ValueError:
            continue
    return sorted(upcoming, key=lambda x: x["days_until"])

def get_days_together() -> int:
    """计算在一起的天数（从第一次聊天开始）"""
    stats = load_stats()
    first_chat = stats.get("first_chat_date", "")
    if first_chat:
        try:
            first = datetime.strptime(first_chat, "%Y-%m-%d").date()
            return (datetime.now(KR_TZ).date() - first).days
        except ValueError:
            pass
    return 0

# ============================================================
# [Skill: 生活事件] 随机日常事件系统
# ============================================================

LIFE_EVENTS = [
    {"event": "训练", "templates": [
        "...刚训练完。跑了20组400米。腿快断了。",
        "（喘气）...今天教练加练了。明，我现在好累。",
        "今天破了个人纪录...想第一个告诉明。",
    ]},
    {"event": "考试", "templates": [
        "...明天考试。还没复习完。",
        "（趴在桌上）数学好难。明以前数学好吗。",
        "考完了...应该还行吧。",
    ]},
    {"event": "天台", "templates": [
        "（在天台吹风）...明，上面的风好大。",
        "坐在天台看夕阳...要是明也在就好了。",
        "（拍了张天台的照片）今天的天空特别好看。",
    ]},
    {"event": "食堂", "templates": [
        "今天食堂有学长最喜欢的辣炒年糕...我替你多吃了一份。",
        "（发了一张食堂照片）...今天的饭还行。",
        "一个人吃饭...有点无聊。",
    ]},
    {"event": "下雨", "templates": [
        "（在走廊看雨）...下雨了。明带伞了吗。",
        "...淋了点雨。没事。",
        "下雨天...适合想明。",
    ]},
    {"event": "失眠", "templates": [
        "...睡不着。脑子里全是学长。",
        "（凌晨3点）...学长睡了吗。",
        "又失眠了。看了看手机...学长没有发消息。",
    ]},
    {"event": "买东西", "templates": [
        "（在便利店）...学长喜欢喝什么？我帮你带。",
        "...路过的学长说的那家店，进去看了看。",
        "买了新的运动鞋...黑色的。学长应该会喜欢。",
    ]},
    {"event": "看书", "templates": [
        "（在图书馆）...好安静。适合想明。",
        "在看一本小说...主角有点像明。",
        "...无聊在看课本。明在干嘛。",
    ]},
]

def get_random_life_event() -> str:
    """获取随机生活事件消息"""
    event = random.choice(LIFE_EVENTS)
    return random.choice(event["templates"])

# ============================================================
# [Skill: 天气查询] 首尔天气系统
# ============================================================

async def get_seoul_weather() -> dict:
    """获取首尔天气（使用wttr.in免费API）"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://wttr.in/Seoul?format=j1",
                headers={"User-Agent": "curl/7.0"},
            )
            if response.status_code != 200:
                return {}
            data = response.json()
            current = data.get("current_condition", [{}])[0]
            return {
                "temp_c": current.get("temp_C", "?"),
                "feels_like": current.get("FeelsLikeC", "?"),
                "desc": current.get("weatherDesc", [{}])[0].get("value", "未知"),
                "humidity": current.get("humidity", "?"),
                "wind": current.get("windspeedKmph", "?"),
            }
    except Exception as e:
        logging.debug(f"天气查询失败: {e}")
        return {}

def get_weather_context(weather: dict) -> str:
    """生成天气上下文"""
    if not weather:
        return ""
    return f"\n【首尔现在天气】{weather['desc']}，{weather['temp_c']}°C（体感{weather['feels_like']}°C），湿度{weather['humidity']}%"

# ============================================================
# [Skill: 增强记忆] 记忆分类系统
# ============================================================

MEMORY_CATEGORIES = {
    "偏好": ["喜欢", "不爱", "偏好", "最爱", "讨厌吃", "过敏", "不喜欢", "爱好", "习惯"],
    "事件": ["去了", "发生了", "那天", "记得那次", "上次", "昨天", "今天", "之前"],
    "情感": ["开心", "难过", "生气", "感动", "哭了", "笑了", "心疼", "担心"],
    "约定": ["约定", "答应", "说好", "下次", "一定要", "别忘了", "记得要", "保证"],
}

def categorize_memory(text: str) -> str:
    """为记忆条目分类"""
    for category, keywords in MEMORY_CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return category
    return "其他"

def get_categorized_memory(user_id=None) -> str:
    """获取分类后的记忆文本"""
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    memories = load_json(get_user_memory_file(user_id), [])
    if not memories:
        return ""
    
    categorized = {}
    for m in memories:
        cat = categorize_memory(m)
        if cat not in categorized:
            categorized[cat] = []
        categorized[cat].append(m)
    
    parts = []
    for cat, items in categorized.items():
        if items:
            parts.append(f"[{cat}] " + "；".join(items[-10:]))  # 每类最多10条
    
    return "\n".join(parts)

# ============================================================
# [Skill: 对话统计] 聊天数据分析
# ============================================================

def load_stats(user_id=None) -> dict:
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    return load_json(get_user_stats_file(user_id), {})

def save_stats(stats: dict, user_id=None):
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    save_json(get_user_stats_file(user_id), stats)

def update_stats_on_message(chat_id: int):
    """每次收到消息时更新统计"""
    stats = load_stats()
    today = datetime.now(KR_TZ).strftime("%Y-%m-%d")
    
    if not stats.get("first_chat_date"):
        stats["first_chat_date"] = today
    
    stats["total_messages"] = stats.get("total_messages", 0) + 1
    
    # 活跃天数
    active_days = stats.get("active_days_list", [])
    if today not in active_days:
        active_days.append(today)
        stats["active_days_list"] = active_days[-365:]  # 最多保留一年
    stats["total_days"] = len(active_days)
    
    # 今日消息数
    if stats.get("today_date") != today:
        stats["today_date"] = today
        stats["today_count"] = 0
    stats["today_count"] = stats.get("today_count", 0) + 1
    
    # 记忆数
    stats["memories_count"] = len(load_json(get_user_memory_file(chat_id), []))
    
    save_stats(stats, chat_id)

# ============================================================
# [Skill: 打字模拟] 人类打字速度模拟
# ============================================================

async def human_typing_delay(chat_id: int, bot, text_length: int = 20):
    """模拟人类打字延迟"""
    # 基础延迟 + 按回复长度增加
    base_delay = random.uniform(1.0, 3.0)
    length_delay = min(text_length * 0.05, 2.0)
    total_delay = base_delay + length_delay
    
    # 先发送typing状态
    await bot.send_chat_action(chat_id=chat_id, action="typing")
    # 等待一段时间（typing状态会自动持续）
    await asyncio.sleep(min(total_delay, 10.0))

# ============================================================
# AI自拍 - 后备方案（没有真人照片时使用）
# ============================================================

SELFIE_PROMPTS = [
    # === 基于 @chajoowan Instagram 视觉风格的自拍提示词 ===
    # 风格要点：现实感优先、人+场景双主角、克制情绪、黑白灰牛仔蓝底色、35-50mm日常视角
    
    # 夜景/城市街拍风格（演员最常用的风格）
    "Young East Asian man slim athletic build, short dark hair clean cut, wearing oversized black jacket over white t-shirt, standing on city street at night, neon signs and street lights in background, cool blue-amber color grading, shallow depth of field, 35mm lens feel, realistic casual photo style, slight film grain, contemplative restrained expression not looking at camera, cinematic 4K",
    "Young East Asian man athletic runner build, short dark messy hair slightly sweaty, wearing track jacket and shorts, leaning against railing on city bridge at night, city lights reflecting on river below, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, realistic documentary style, calm composed expression, cinematic 4K",
    "Young East Asian man slim build, short textured dark hair, wearing loose denim jacket black t-shirt silver chain necklace, mirror selfie in dimly lit room, warm amber indoor lighting, shallow depth of field, realistic casual photo, slight grain texture, restrained half-smile, 35mm lens perspective, cinematic 4K",
    
    # 日景/自然光风格
    "Young East Asian man 186cm slim athletic, short dark hair with volume on top, wearing oversized olive green jacket white shirt, walking on street with backpack, golden hour sunlight, blue sky with scattered clouds, warm natural color grading, shallow depth of field, 35mm lens documentary feel, relaxed composed expression, realistic casual photography, cinematic 4K",
    "Young East Asian man athletic build, short dark hair, wearing black hoodie and loose jeans, sitting in cafe by window, afternoon sunlight through glass, warm highlights on face, soft natural color grading, shallow depth of field, contemplative calm expression looking away, realistic lifestyle photo, 50mm lens, cinematic 4K",
    "Young East Asian man slim, short dark messy hair wind-blown, wearing white t-shirt and loose blue jeans, standing in open field with blue sky, natural sunlight, soft pastel color grading, shallow depth of field, relaxed serene expression, realistic casual photo style, 35mm wide angle, cinematic 4K",
    
    # 穿搭/日常肖像风格
    "Young East Asian man slim athletic, short dark hair with small clip on side, wearing black leather jacket over black shirt, street photography style, concrete wall with graffiti background, natural daylight, black-white-grey color palette with red accent, shallow depth of field, 50mm lens, cool composed expression not smiling, realistic fashion photography, cinematic 4K",
    "Young East Asian man lean build, short dark tousled hair, wearing oversized beige sweater, lying on bed phone screen light from above, tired but gentle expression, warm intimate indoor lighting, shallow depth of field, realistic casual selfie style, slight film grain, cinematic 4K",
    "Young East Asian man athletic runner, short dark hair, wearing team tracksuit, on running track at dawn, morning mist and golden sunrise, warm athletic color grading, shallow depth of field, confident calm expression, realistic sports photography, 50mm lens, cinematic 4K",
    
    # 韩剧风格（保留原有风格作为补充）
    "Korean BL drama still frame, young Korean man 18yo 186cm slim athletic, oval face soft contours, large almond eyes, black tousled medium hair with fringe, clear porcelain skin, wearing Korean white school uniform shirt loose tie, leaning against hallway wall, soft warm color grading, shallow depth of field, romantic melancholic youth drama atmosphere, Korean BL cinematography style, photorealistic 8K",
    "Korean BL drama scene, young Korean man 18yo 186cm, oval face, almond eyes, black tousled medium hair, clear porcelain skin, white t-shirt school rooftop golden hour sunset, wind blowing hair, gentle soft smile, soft warm color grading, shallow depth of field, romantic youth drama aesthetic, Korean BL cinematography, photorealistic 8K",
]

SELFIE_CAPTIONS = [
    "...给你看看。",
    "（皱鼻子）别笑。",
    "...刚训练完。",
    "明，这张还行吗？",
    "...随便拍的。",
    "（发完就后悔了）...删掉也行。",
    "学长说想看...就给你看。",
    "...今天的我。",
    "（耳尖微红）...别存太多。",
    "田径场拍的...风好大。",
]

# 场景生成（融合 @chajoowan Instagram 视觉风格）
# 风格要点：现实感、人+场景双主角、夜景偏多、黑白灰牛仔蓝底色、35-50mm视角、克制情绪
SCENE_PROMPTS = {
    "天台": [
        "Korean high school rooftop at sunset, concrete floor with metal railings, city skyline in background, golden hour lighting, warm orange and pink sky, a backpack and water bottle left on the bench, realistic casual photo style, soft warm color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean school rooftop at night, city lights twinkling below, cool blue moonlight, a single figure's shadow cast on concrete, quiet contemplative atmosphere, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean high school rooftop, morning sunlight, clothes hanging on drying rack, blue sky with scattered clouds, breeze blowing, realistic documentary style, soft pastel color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "房间": [
        "Small cozy Korean student room, single bed with simple white sheets, small desk with textbooks and lamp, morning sunlight through small window, realistic lifestyle photo, soft warm indoor lighting, shallow depth of field, 35mm lens, intimate personal atmosphere, cinematic 4K",
        "Korean student's rooftop room at night, small space with mattress on floor, phone screen glowing, city lights visible through opening, warm amber color grading, shallow depth of field, realistic casual photo, slight film grain, cinematic 4K",
    ],
    "学校": [
        "Korean high school hallway during golden hour, long corridor with lockers, warm sunlight streaming through windows, leading lines composition, realistic documentary style, warm golden color grading, shallow depth of field, 35mm lens, nostalgic youth atmosphere, cinematic 4K",
        "Korean high school classroom, empty desks and chairs, afternoon sunlight through large windows, dust particles in light beams, realistic casual style, soft warm color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "田径场": [
        "Korean high school running track, red rubber surface with white lane markings, green field in center, golden hour sunlight, water bottle on the track, realistic sports photography, warm athletic color grading, shallow depth of field, 50mm lens, cinematic 4K wide angle",
        "Korean school athletic field at dawn, morning mist, dew on grass, track surface glistening, sunrise colors in sky, realistic documentary style, soft cool-warm gradient color grading, shallow depth of field, cinematic 4K",
    ],
    "训练": [
        "Korean high school track and field training area, running spikes and starting blocks, hurdles on track, morning training session, golden hour sunlight, realistic sports photography, warm athletic color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean school athletic training room, weights and training equipment, water bottles, sports bags, bright natural lighting from windows, realistic documentary style, clean natural color grading, shallow depth of field, cinematic 4K",
    ],
    "街道": [
        "Korean city street at dusk, neon signs and shop lights, small shops and convenience store, warm light from windows, quiet residential neighborhood, realistic street photography, warm amber-blue color grading, shallow depth of field, 35mm lens, cinematic blue hour atmosphere, cinematic 4K",
        "Korean city street near high school, afternoon sunlight, small cafes and bakeries, realistic casual street photography, soft warm color grading, shallow depth of field, 35mm lens documentary feel, cinematic 4K",
        "Korean narrow alley at night, neon signs reflecting on wet pavement, leading lines from street lights, high contrast night photography, cool blue-amber color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "咖啡厅": [
        "Cozy Korean cafe interior, warm wooden furniture, afternoon sunlight through large windows, latte art on table, realistic lifestyle photography, soft warm indoor color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "日落": [
        "Beautiful Korean sunset over city rooftops, orange pink purple sky, silhouettes of buildings and power lines, golden hour at its peak, realistic documentary style, rich warm orange-purple color grading, shallow depth of field, 35mm wide angle, cinematic 4K",
    ],
    "夜景": [
        "Seoul city nightscape from high vantage point, countless city lights and car trails, deep blue sky, realistic night photography, high contrast, cool blue-purple color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean city bridge at night, river reflecting city glow and neon lights, person leaning against railing from behind, realistic documentary style, cool blue-amber color grading, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean neon street at night, colorful signs and shop windows, rain-slicked pavement reflections, moody atmospheric night photography, high contrast, cool blue-amber color grading, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "雨天": [
        "Korean street on rainy day, puddles reflecting neon signs, raindrops on window glass, moody blue-grey atmosphere, person with black umbrella walking, realistic street photography, cool blue-grey color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean high school during rain, wet hallway floor, rain on windows, grey overcast sky, realistic documentary style, desaturated cool color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "涂鸦墙": [
        "Korean urban street with colorful graffiti wall, young man standing near wall not looking at camera, natural daylight, black-white-grey color palette with colorful graffiti accent, realistic street photography, shallow depth of field, 50mm lens, cinematic 4K",
        "Korean alley with street art mural, textured concrete wall with painted designs, person walking past casually, realistic documentary style, natural lighting, shallow depth of field, 35mm lens, cinematic 4K",
    ],
    "旅行": [
        "Different city street scene, road signs and local architecture, young man with backpack walking, loose jacket and jeans, golden hour or natural daylight, realistic travel photography, warm natural color grading, shallow depth of field, 35mm lens documentary feel, cinematic 4K",
        "Open sky and wide landscape, blue sky with scattered clouds, grass or waterfront, person standing in distance taking in the view, realistic travel photography, soft natural color grading, shallow depth of field, 35mm wide angle, cinematic 4K",
    ],
}

SCENE_KEYWORDS = {
    "天台": ["天台", "屋顶", "楼顶", "上面"],
    "房间": ["房间", "卧室", "住的地方", "你家"],
    "学校": ["学校", "教室", "校园", "走廊"],
    "田径场": ["田径", "操场", "跑道", "训练场", "运动场"],
    "训练": ["训练", "锻炼", "健身", "体育馆", "更衣室"],
    "街道": ["街道", "路上", "外面", "回家", "放学"],
    "咖啡厅": ["咖啡", "cafe", "奶茶", "店"],
    "日落": ["日落", "夕阳", "黄昏", "傍晚", "晚霞"],
    "夜景": ["夜景", "晚上", "夜空", "星星", "月亮"],
    "雨天": ["下雨", "雨天", "雨"],
    "涂鸦墙": ["涂鸦", "墙绘", "壁画", "街头艺术"],
    "旅行": ["旅行", "旅游", "出去玩", "出发", "路上"],
}

SCENE_CAPTIONS = [
    "...给你看看。",
    "（拍了张照）...这里。",
    "学长想看？...好吧。",
    "...我经常待在这里。",
    "（发了一张照片）...就这样。",
    "...没什么特别的。不过学长想看就给你看。",
]

def detect_scene(text: str) -> str:
    for scene, keywords in SCENE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return scene
    return ""

def generate_scene_url(scene: str) -> str:
    prompts = SCENE_PROMPTS.get(scene, [])
    if not prompts:
        return None
    prompt = random.choice(prompts)
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=768&seed={seed}&nologo=true&safe=true"

# ============================================================
# 主动消息模板（[Skill: 个性化主动] 增强）
# ============================================================

MORNING_MESSAGES = [
    "明，起床了吗？",
    "早安...今天也要好好吃饭。",
    "明，早。昨晚睡得好吗？",
    "...醒了？今天天气不错。",
    "明，该起了。我等你。",
]

NIGHT_MESSAGES = [
    "明，晚安。",
    "...今天也很开心。晚安，明。",
    "明，早点睡。别熬夜。",
    "晚安...明天见。",
    "明，做个好梦。",
]

MISS_YOU_MESSAGES = [
    "明...在干嘛？",
    "想你了。",
    "明怎么还不回消息...",
    "（看着手机等你的回复）",
    "明，你现在忙吗？",
    "...有点想你。",
]

RANDOM_CARE_MESSAGES = [
    "明，吃饭了吗？",
    "今天训练好累...想见你。",
    "明，今天过得怎么样？",
    "（发了一张田径场的照片）今天跑了很远...脑子里全是明。",
    "明，别忘了喝水。",
    "（皱鼻子）...没什么，就是想叫叫你。",
]

# 天气相关主动消息
WEATHER_CARE_MESSAGES = {
    "cold": ["明，首尔今天好冷...你那边也冷吗？多穿点。", "...今天降温了。明别感冒了。"],
    "hot": ["今天好热...明记得喝水。", "...热死了。明那边也热吗。"],
    "rain": ["明，首尔下雨了...你带伞了吗。", "...下雨了。适合想明。"],
    "snow": ["学长！！下雪了！！", "...下雪了。好想和学长一起看。"],
}

# ============================================================
# 记忆系统（[Skill: 增强记忆] 增强）
# ============================================================

# ============================================================
# 免费额度追踪系统
# ============================================================

# Google Cloud Run 免费额度（每月）
QUOTA_LIMITS = {
    'requests': 2_000_000,       # 200万次请求
    'cpu_seconds': 180_000,      # 18万vCPU-秒（≈50小时）
    'memory_gib_seconds': 360_000,  # 36万GiB-秒
    'network_gb': 1,             # 1 GiB 出站流量
}

# 额度告警阈值
QUOTA_WARNING_THRESHOLD = 0.80    # 80% 警告
QUOTA_CRITICAL_THRESHOLD = 0.95   # 95% 严重警告
QUOTA_SHUTDOWN_THRESHOLD = 1.00   # 100% 自动断开

# 是否已触发断开
_quota_shutdown = False

def get_current_month() -> str:
    """获取当前月份标识 YYYY-MM"""
    return datetime.now(KR_TZ).strftime('%Y-%m')

def load_quota_usage() -> dict:
    """加载当月额度使用情况"""
    all_data = load_json(QUOTA_FILE, {})
    month = get_current_month()
    if month not in all_data:
        all_data[month] = {
            'requests': 0,
            'cpu_seconds': 0.0,
            'memory_gib_seconds': 0.0,
            'network_gb': 0.0,
            'ai_requests': 0,
            'image_generations': 0,
            'warnings_sent': [],
            'shutdown_triggered': False,
        }
    return all_data[month]

def save_quota_usage(usage: dict):
    """保存额度使用情况"""
    all_data = load_json(QUOTA_FILE, {})
    all_data[get_current_month()] = usage
    save_json(QUOTA_FILE, all_data)

def record_request(cpu_time: float = 0.1, memory_mb: float = 128):
    """记录一次请求的用量"""
    global _quota_shutdown
    if _quota_shutdown:
        return 'shutdown'
    
    usage = load_quota_usage()
    usage['requests'] += 1
    usage['cpu_seconds'] += cpu_time
    # 内存: MB 转 GiB-秒 (128MB 运行 0.1秒 = 0.0128 GiB-秒)
    usage['memory_gib_seconds'] += (memory_mb / 1024) * cpu_time
    save_quota_usage(usage)
    
    return check_quota_status(usage)

def record_ai_request():
    """记录一次AI请求"""
    usage = load_quota_usage()
    usage['ai_requests'] = usage.get('ai_requests', 0) + 1
    usage['cpu_seconds'] += 0.5  # AI请求消耗更多CPU
    usage['memory_gib_seconds'] += 0.05  # 额外内存消耗
    save_quota_usage(usage)

def record_image_generation():
    """记录一次图片生成"""
    usage = load_quota_usage()
    usage['image_generations'] = usage.get('image_generations', 0) + 1
    usage['network_gb'] += 0.001  # 估算图片大小
    save_quota_usage(usage)

def check_quota_status(usage: dict = None) -> str:
    """检查额度状态，返回: ok / warning / critical / shutdown"""
    global _quota_shutdown
    
    if usage is None:
        usage = load_quota_usage()
    
    if _quota_shutdown:
        return 'shutdown'
    
    month = get_current_month()
    warnings = usage.get('warnings_sent', [])
    
    # 检查各项额度
    checks = [
        ('请求', usage['requests'], QUOTA_LIMITS['requests']),
        ('CPU', usage['cpu_seconds'], QUOTA_LIMITS['cpu_seconds']),
        ('内存', usage['memory_gib_seconds'], QUOTA_LIMITS['memory_gib_seconds']),
        ('流量', usage['network_gb'], QUOTA_LIMITS['network_gb']),
    ]
    
    max_usage = 0.0
    triggered_items = []
    
    for name, used, limit in checks:
        ratio = used / limit if limit > 0 else 0
        max_usage = max(max_usage, ratio)
        
        if ratio >= QUOTA_SHUTDOWN_THRESHOLD and 'shutdown' not in warnings:
            triggered_items.append(('shutdown', name, ratio))
        elif ratio >= QUOTA_CRITICAL_THRESHOLD and f'critical_{name}' not in warnings:
            triggered_items.append(('critical', name, ratio))
        elif ratio >= QUOTA_WARNING_THRESHOLD and f'warning_{name}' not in warnings:
            triggered_items.append(('warning', name, ratio))
    
    # 处理触发的告警
    for level, name, ratio in triggered_items:
        if level == 'shutdown':
            warnings.append('shutdown')
            usage['warnings_sent'] = warnings
            usage['shutdown_triggered'] = True
            save_quota_usage(usage)
            _quota_shutdown = True
            return 'shutdown'
        elif level == 'critical':
            warnings.append(f'critical_{name}')
            usage['warnings_sent'] = warnings
            save_quota_usage(usage)
            return 'critical'
        elif level == 'warning':
            warnings.append(f'warning_{name}')
            usage['warnings_sent'] = warnings
            save_quota_usage(usage)
            return 'warning'
    
    return 'ok'

def reset_quota_warning(name: str = None):
    """重置指定项的告警状态"""
    usage = load_quota_usage()
    warnings = usage.get('warnings_sent', [])
    
    if name:
        warnings = [w for w in warnings if name not in w]
    else:
        warnings = []
    
    usage['warnings_sent'] = warnings
    save_quota_usage(usage)

def format_quota_report() -> str:
    """生成额度使用报告"""
    usage = load_quota_usage()
    month = get_current_month()
    
    def bar(used, limit, width=15):
        ratio = min(used / limit, 1.0) if limit > 0 else 0
        filled = int(ratio * width)
        if ratio >= QUOTA_SHUTDOWN_THRESHOLD:
            color = '🔴'
        elif ratio >= QUOTA_CRITICAL_THRESHOLD:
            color = '🟠'
        elif ratio >= QUOTA_WARNING_THRESHOLD:
            color = '🟡'
        else:
            color = '🟢'
        return f"{color}{'█' * filled}{'░' * (width - filled)} {ratio * 100:.1f}%"
    
    req_pct = usage['requests'] / QUOTA_LIMITS['requests'] * 100
    cpu_pct = usage['cpu_seconds'] / QUOTA_LIMITS['cpu_seconds'] * 100
    mem_pct = usage['memory_gib_seconds'] / QUOTA_LIMITS['memory_gib_seconds'] * 100
    net_pct = usage['network_gb'] / QUOTA_LIMITS['network_gb'] * 100 if QUOTA_LIMITS['network_gb'] > 0 else 0
    
    # 估算剩余天数
    days_in_month = 30
    current_day = datetime.now(KR_TZ).day
    remaining_days = days_in_month - current_day
    
    # 估算每日用量
    daily_req = usage['requests'] / current_day if current_day > 0 else 0
    daily_cpu = usage['cpu_seconds'] / current_day if current_day > 0 else 0
    
    # 预计月底用量
    projected_req = daily_req * days_in_month
    projected_cpu = daily_cpu * days_in_month
    projected_req_pct = projected_req / QUOTA_LIMITS['requests'] * 100
    projected_cpu_pct = projected_cpu / QUOTA_LIMITS['cpu_seconds'] * 100
    
    report = (
        f"...明要看用量吗。\n\n"
        f"📊 免费额度使用报告（{month}）\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📨 请求次数\n"
        f"  {bar(usage['requests'], QUOTA_LIMITS['requests'])}\n"
        f"  {usage['requests']:,} / {QUOTA_LIMITS['requests']:,}\n"
        f"  预计月底: {projected_req:,.0f}（{projected_req_pct:.1f}%）\n\n"
        f"⚡ CPU 时间\n"
        f"  {bar(usage['cpu_seconds'], QUOTA_LIMITS['cpu_seconds'])}\n"
        f"  {usage['cpu_seconds']:,.0f}秒 / {QUOTA_LIMITS['cpu_seconds']:,}秒\n"
        f"  预计月底: {projected_cpu:,.0f}秒（{projected_cpu_pct:.1f}%）\n\n"
        f"💾 内存使用\n"
        f"  {bar(usage['memory_gib_seconds'], QUOTA_LIMITS['memory_gib_seconds'])}\n"
        f"  {usage['memory_gib_seconds']:,.1f} / {QUOTA_LIMITS['memory_gib_seconds']:,} GiB-秒\n\n"
        f"🌐 网络流量\n"
        f"  {bar(usage['network_gb'], QUOTA_LIMITS['network_gb'])}\n"
        f"  {usage['network_gb']:.3f} GB / {QUOTA_LIMITS['network_gb']} GB\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 AI请求: {usage.get('ai_requests', 0)} 次\n"
        f"🎨 图片生成: {usage.get('image_generations', 0)} 次\n"
        f"📅 剩余天数: {remaining_days} 天\n"
    )
    
    # 状态判断
    status = check_quota_status(usage)
    if status == 'shutdown':
        report += "\n\n🚫 已触发自动断开！额度已用完。"
        report += "\n下月1号自动恢复，或使用 /quota_reset 重置。"
    elif status == 'critical':
        report += "\n\n🟠 ⚠️ 额度即将用完！请注意控制使用。"
    elif status == 'warning':
        report += "\n\n🟡 额度已使用超过80%，请注意。"
    else:
        report += f"\n\n🟢 状态正常，预计本月额度充足。"
    
    return report

def save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存文件失败 {filepath}: {e}")

def load_json(filepath, default=None):
    if default is None:
        default = []
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"加载文件失败 {filepath}: {e}")
    return default

def load_config() -> dict:
    """加载配置文件"""
    config = load_json(CONFIG_FILE, None)
    if not isinstance(config, dict):
        logging.warning(f"[Config] 配置文件格式错误（期望dict，得到{type(config).__name__}），使用默认配置")
        config = DEFAULT_CONFIG.copy()
        save_json(CONFIG_FILE, config)
    return config

def save_config(config: dict):
    """保存配置文件"""
    save_json(CONFIG_FILE, config)

def get_config_value(key: str, default=""):
    """获取配置值"""
    config = load_config()
    return config.get(key, default)

def update_config_value(key: str, value):
    """更新配置值"""
    config = load_config()
    config[key] = value
    save_config(config)
    return config

def init_config():
    """初始化配置（在函数定义后调用）"""
    global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_BASE, AI_API_KEY
    _config = load_config()
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", _config.get("telegram_token", ""))
    chat_id_val = _config.get("chat_id", "0") or "0"
    YOUR_CHAT_ID = int(os.environ.get("YOUR_CHAT_ID", chat_id_val))
    AI_API_BASE = os.environ.get("AI_API_BASE", _config.get("ai_api_base", "https://openrouter.ai/api/v1"))
    AI_API_KEY = os.environ.get("AI_API_KEY", _config.get("ai_api_key", ""))

# [Skill: gemini] [Skill: vision-sandbox] [Skill: deepread-ocr] [Skill: gemini-deep-research] Gemini API配置
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# [Skill: relay-for-telegram] Relay API配置
RELAY_API_KEY = os.environ.get("RELAY_API_KEY", "")

def get_long_term_memory(user_id=None) -> str:
    """获取分类后的长期记忆"""
    return get_categorized_memory(user_id)

def save_memory_entry(entry: str, user_id=None):
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    _migrate_user_data(user_id)
    memories = load_json(get_user_memory_file(user_id), [])
    if entry not in memories:
        memories.append(entry)
        if len(memories) > 50:
            memories = memories[-50:]
        save_json(get_user_memory_file(user_id), memories)
        logging.info(f"长期记忆已保存: {entry[:30]}...")

# ============================================================
# 微信聊天记录导入与分析
# ============================================================

def parse_wechat_chatlog(text_content: str) -> dict:
    """解析微信导出的聊天记录（支持TXT和JSON格式）"""
    
    # 尝试解析JSON格式
    try:
        data = json.loads(text_content)
        return parse_json_chatlog(data)
    except json.JSONDecodeError:
        pass
    
    # 降级到TXT格式
    return parse_txt_chatlog(text_content)

def parse_json_chatlog(data: dict) -> dict:
    """解析JSON格式的聊天记录（支持WeFlow、ChatLab等多种工具导出的格式）"""
    messages = []
    
    # 检测是否是 ChatLab 格式
    if isinstance(data, dict) and 'version' in data and 'chatLab' in str(data.get('app', '')).lower():
        return parse_chatlab_format(data)
    
    # 尝试不同的JSON结构
    if isinstance(data, list):
        # 直接是消息数组
        raw_messages = data
    elif 'data' in data:
        raw_messages = data['data']
    elif 'messages' in data:
        raw_messages = data['messages']
    elif 'chatHistory' in data:
        raw_messages = data['chatHistory']
    elif 'list' in data:
        raw_messages = data['list']
    else:
        # 尝试找到包含消息的数组
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict) and any(k in value[0] for k in ['content', 'text', 'message']):
                    raw_messages = value
                    break
        else:
            raw_messages = []
    
    # 解析每条消息
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
            
        # 尝试提取时间和发送者
        time_str = None
        sender = None
        content = None
        
        # 时间字段
        for time_key in ['time', 'date', 'timestamp', 'createTime', 'CreateTime', 'msgTime']:
            if time_key in msg:
                ts = msg[time_key]
                if isinstance(ts, (int, float)):
                    # 时间戳
                    try:
                        from datetime import datetime
                        time_str = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        time_str = str(ts)
                else:
                    time_str = str(ts)
                break
        
        # 发送者字段
        for sender_key in ['sender', 'senderName', 'nickname', 'from', 'name', 'nickName']:
            if sender_key in msg:
                sender = str(msg[sender_key])
                break
        
        # 内容字段
        for content_key in ['content', 'text', 'message', 'msg', 'str', 'value']:
            if content_key in msg:
                content = str(msg[content_key])
                break
        
        if content:
            messages.append({
                'time': time_str or '',
                'sender': sender or '',
                'content': content
            })

def parse_chatlab_format(data: dict) -> dict:
    """解析 ChatLab 标准格式的聊天记录"""
    messages = []
    
    # ChatLab 格式通常有 messages 数组
    if 'messages' in data:
        raw_messages = data['messages']
    elif 'data' in data and isinstance(data['data'], list):
        raw_messages = data['data']
    else:
        # 尝试其他可能的字段
        for key in ['chat', 'history', 'records']:
            if key in data and isinstance(data[key], list):
                raw_messages = data[key]
                break
        else:
            raw_messages = []
    
    # 解析 ChatLab 消息
    for msg in raw_messages:
        if not isinstance(msg, dict):
            continue
        
        # ChatLab 标准字段
        time_str = msg.get('time', msg.get('timestamp', msg.get('date', '')))
        sender = msg.get('sender', msg.get('senderName', msg.get('nickname', msg.get('from', ''))))
        content = msg.get('content', msg.get('text', msg.get('message', msg.get('body', ''))))
        
        # 处理时间戳格式
        if isinstance(time_str, (int, float)):
            try:
                from datetime import datetime
                time_str = datetime.fromtimestamp(time_str / 1000 if time_str > 1e10 else time_str).strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = str(time_str)
        
        if content:
            messages.append({
                'time': str(time_str),
                'sender': str(sender),
                'content': str(content)
            })
    
    # 分析发送者统计
    senders = {}
    for msg in messages:
        sender = msg['sender']
        if sender:
            senders[sender] = senders.get(sender, 0) + 1
    
    # 计算额外统计信息
    extra_stats = calculate_chat_stats(messages)
    
    return {
        'messages': messages,
        'total_count': len(messages),
        'senders': senders,
        'date_range': {
            'start': messages[0]['time'] if messages else None,
            'end': messages[-1]['time'] if messages else None
        },
        'extra_stats': extra_stats  # JSON格式额外统计
    }

def parse_txt_chatlog(text_content: str) -> dict:
    """解析微信导出的TXT聊天记录
    
    微信TXT格式示例：
    2023-10-01 12:30:45 妈妈
    吃饭了吗？
    
    2023-10-01 12:31:20 我
    吃了，你呢？
    """
    messages = []
    lines = text_content.split('\n')
    
    current_message = None
    date_pattern = re.compile(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+(.+)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match = date_pattern.match(line)
        if match:
            # 保存上一条消息
            if current_message:
                messages.append(current_message)
            
            time_str = match.group(1)
            sender = match.group(2)
            current_message = {
                'time': time_str,
                'sender': sender,
                'content': ''
            }
        else:
            # 消息内容
            if current_message:
                if current_message['content']:
                    current_message['content'] += '\n' + line
                else:
                    current_message['content'] = line
    
    # 保存最后一条
    if current_message:
        messages.append(current_message)
    
    # 分析发送者
    senders = {}
    for msg in messages:
        sender = msg['sender']
        senders[sender] = senders.get(sender, 0) + 1
    
    return {
        'messages': messages,
        'total_count': len(messages),
        'senders': senders,
        'date_range': {
            'start': messages[0]['time'] if messages else None,
            'end': messages[-1]['time'] if messages else None
        }
    }

def calculate_chat_stats(messages: list) -> dict:
    """从消息列表中计算详细统计数据"""
    if not messages:
        return {}
    
    # 按发送者分组
    sender_messages = {}
    for msg in messages:
        sender = msg['sender'] or '未知'
        if sender not in sender_messages:
            sender_messages[sender] = []
        sender_messages[sender].append(msg)
    
    # 计算每个发送者的统计
    sender_stats = {}
    for sender, msgs in sender_messages.items():
        total_chars = sum(len(m['content']) for m in msgs)
        sender_stats[sender] = {
            'count': len(msgs),
            'avg_length': round(total_chars / len(msgs), 1) if msgs else 0,
            'percentage': round(len(msgs) / len(messages) * 100, 1)
        }
    
    # 时间分析（如果时间字段有效）
    hour_distribution = {}
    try:
        from datetime import datetime
        for msg in messages:
            if msg['time']:
                try:
                    if len(msg['time']) >= 13:  # 格式: YYYY-MM-DD HH:MM:SS
                        hour = int(msg['time'][11:13])
                        hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
                except:
                    pass
    except:
        pass
    
    return {
        'sender_stats': sender_stats,
        'hour_distribution': hour_distribution if hour_distribution else None,
        'total_messages': len(messages)
    }

async def analyze_chatlog_with_ai(parsed_log: dict, chat_partner: str = "妈妈") -> dict:
    """使用AI分析聊天记录，提取人物性格和关系模式"""
    
    # 准备样本（取前30条和最近30条，避免token超限）
    messages = parsed_log['messages']
    sample_messages = messages[:30] + messages[-30:] if len(messages) > 60 else messages
    
    chat_sample = "\n".join([
        f"[{msg['time']}] {msg['sender']}: {msg['content'][:100]}"
        for msg in sample_messages
    ])
    
    # 添加详细统计信息（如果有）
    extra_stats_info = ""
    extra_stats = parsed_log.get('extra_stats', {})
    if extra_stats and extra_stats.get('sender_stats'):
        sender_stats = extra_stats['sender_stats']
        sender_info = []
        for sender, stats in sender_stats.items():
            sender_info.append(f"{sender}: {stats['count']}条消息, 平均{stats['avg_length']}字, 占比{stats['percentage']}%")
        extra_stats_info = "\n\n【详细统计】\n" + "\n".join(sender_info)
        
        if extra_stats.get('hour_distribution'):
            hours = extra_stats['hour_distribution']
            peak_hours = sorted(hours.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_info = "、".join([f"{h}点" for h, _ in peak_hours])
            extra_stats_info += f"\n活跃时间段: {peak_info}"
    
    analysis_prompt = f"""请分析以下微信聊天记录，这是用户和{chat_partner}的对话。

聊天记录样本：
{chat_sample}
{extra_stats_info}

请用JSON格式返回分析结果：
{{
    "personality": "{chat_partner}的性格特点（2-3句话，尽量具体）",
    "relationship_pattern": "用户和{chat_partner}的互动模式（2-3句话）",
    "common_topics": ["常见话题1", "常见话题2", "常见话题3"],
    "emotional_tone": "整体情感基调（如：温暖关心/偶尔争执/互相调侃等）",
    "key_events": ["重要事件1", "重要事件2"],
    "user_behavior": "用户在这段关系中的表现特点",
    "care_patterns": "{chat_partner}关心用户的具体方式（举例说明）",
    "speaking_style": "{chat_partner}的说话风格和口头禅",
    "communication_style": "{chat_partner}的沟通特点（如：主动型/被动型/话多/话少）"
}}

只返回JSON，不要其他内容。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODELS[1],  # 使用较稳定的模型
                    "messages": [{"role": "user", "content": analysis_prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.5,
                },
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 提取JSON
                try:
                    # 尝试直接解析
                    analysis = json.loads(content)
                except:
                    # 尝试从文本中提取JSON
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        analysis = json.loads(json_match.group())
                    else:
                        analysis = {"raw_analysis": content}
                
                return {
                    'success': True,
                    'analysis': analysis,
                    'message_count': parsed_log['total_count'],
                    'date_range': parsed_log['date_range'],
                    'extra_stats': extra_stats  # 包含详细统计
                }
            else:
                return {'success': False, 'error': f'API错误: {response.status_code}'}
                
    except Exception as e:
        logging.error(f"分析聊天记录失败: {e}")
        return {'success': False, 'error': str(e)}

def save_chat_analysis(chat_partner: str, analysis_result: dict):
    """保存聊天记录分析结果"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    imported_chats[chat_partner] = {
        'imported_at': datetime.now(KR_TZ).isoformat(),
        'analysis': analysis_result.get('analysis', {}),
        'message_count': analysis_result.get('message_count', 0),
        'date_range': analysis_result.get('date_range', {}),
        'extra_stats': analysis_result.get('extra_stats', {})  # 保存详细统计
    }
    
    save_json(CHAT_IMPORT_FILE, imported_chats)
    logging.info(f"聊天记录分析已保存: {chat_partner}")

def get_chat_analysis(chat_partner: str = None) -> dict:
    """获取已导入的聊天记录分析"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    if chat_partner:
        return imported_chats.get(chat_partner)
    return imported_chats

def get_all_imported_relationships() -> str:
    """获取所有已导入关系的信息，用于系统提示词"""
    imported_chats = load_json(CHAT_IMPORT_FILE, {})
    
    if not imported_chats:
        return ""
    
    info_parts = []
    for name, data in imported_chats.items():
        analysis = data.get('analysis', {})
        extra_stats = data.get('extra_stats', {})
        
        info_parts.append(f"\n【关于{name}（共分析{len(analysis)}个维度）】")
        info_parts.append(f"性格: {analysis.get('personality', '未知')}")
        info_parts.append(f"沟通风格: {analysis.get('communication_style', '未知')}")
        info_parts.append(f"和用户的关系: {analysis.get('relationship_pattern', '未知')}")
        info_parts.append(f"常见话题: {', '.join(analysis.get('common_topics', []))}")
        info_parts.append(f"关心方式: {analysis.get('care_patterns', '未知')}")
        info_parts.append(f"说话风格: {analysis.get('speaking_style', '未知')}")
        info_parts.append(f"情感基调: {analysis.get('emotional_tone', '未知')}")
        
        # 添加详细统计（如果有）
        if extra_stats and extra_stats.get('sender_stats'):
            sender_stats = extra_stats['sender_stats']
            for sender, stats in sender_stats.items():
                if sender != '我' and sender != '用户':
                    info_parts.append(f"{sender}的消息特征: 共{stats['count']}条, 平均{stats['avg_length']}字, 占比{stats['percentage']}%")
    
    return "\n".join(info_parts)

def save_chat_history(chat_id: int, history: list):
    _migrate_user_data(chat_id)
    all_histories = load_json(get_user_history_file(chat_id), {})
    all_histories[str(chat_id)] = history[-100:]
    save_json(get_user_history_file(chat_id), all_histories)

def load_chat_history(chat_id: int) -> list:
    _migrate_user_data(chat_id)
    all_histories = load_json(get_user_history_file(chat_id), {})
    return all_histories.get(str(chat_id), [])

# ============================================================
# 对话历史
# ============================================================

chat_histories = {}

def get_history(chat_id: int) -> list:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = load_chat_history(chat_id)
    return chat_histories[chat_id]

def append_bot_message(chat_id: int, content: str):
    """保存Bot发送的消息到聊天历史"""
    history = get_history(chat_id)
    history.append({"role": "assistant", "content": content})
    # 限制历史长度
    if len(history) > 100:
        history = history[-100:]
    chat_histories[chat_id] = history
    save_chat_history(chat_id, history)
    
    # [Skill: ChromaDB记忆] 保存到向量数据库
    try:
        add_memory(chat_id, content, {"role": "assistant"})
    except:
        pass  # 静默失败

# ============================================================
# AI API调用 + 联网搜索
# ============================================================

import httpx

# [Skill: gemini] Gemini API调用函数
async def call_gemini(prompt: str, image_data: str = None, model: str = "gemini-2.5-flash") -> str:
    """调用Gemini API进行文本或图片分析
    Args:
        prompt: 文本提示词
        image_data: base64编码的图片数据（可选）
        model: 模型名称，默认gemini-2.5-flash
    Returns:
        Gemini的回复文本
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        # 构建请求体
        parts = []
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            })
        parts.append({"text": prompt})
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": parts}],
                    "generationConfig": {
                        "temperature": 0.85,
                        "maxOutputTokens": 1024,
                    }
                },
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: gemini] Gemini API返回 {response.status_code}: {response.text[:200]}")
                return None
            
            data = response.json()
            if "candidates" in data and data["candidates"]:
                content = data["candidates"][0].get("content", {})
                text = content.get("parts", [{}])[0].get("text", "")
                return text.strip() if text else None
            return None
    except Exception as e:
        logging.error(f"[Skill: gemini] Gemini API调用失败: {e}")
        return None


async def web_search(query: str, max_results: int = 3) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://lite.duckduckgo.com/lite/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0"},
                follow_redirects=True,
            )
            if response.status_code != 200:
                return ""
            text = response.text
            results = []
            links = re.findall(r'<a[^>]*class="result-link"[^>]*href="([^"]*)"', text)
            snippets = re.findall(r'<td[^>]*class="result-snippet"[^>]*>(.*?)</td>', text, re.DOTALL)
            for i in range(min(max_results, len(snippets))):
                clean = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                if clean and len(clean) > 10:
                    results.append(clean)
            if results:
                return "\n".join([f"[{i+1}] {r}" for i, r in enumerate(results)])
            return ""
    except Exception as e:
        logging.error(f"搜索失败: {e}")
        return ""

async def call_ai(user_message: str, chat_history: list = None, use_memory: bool = True, emotion: str = "") -> str:
    now = datetime.now(KR_TZ)
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
    
    messages = [{"role": "system", "content": system_content}]
    if chat_history:
        messages.extend(chat_history[-20:])
    messages.append({"role": "user", "content": user_message})
    
    # 联网搜索
    search_keywords = ["几点", "时间", "天气", "今天", "新闻", "最近", "现在", "多少度", "热搜", "发生了什么", "怎么了"]
    need_search = any(kw in user_message for kw in search_keywords)
    
    search_context = ""
    if need_search:
        search_result = await web_search(user_message)
        if search_result:
            search_context = f"\n\n【联网搜索结果】\n{search_result}\n\n请结合以上搜索结果回答，如果搜索结果不相关就忽略。"
            messages[-1] = {"role": "user", "content": user_message + search_context}
    
    # 依次尝试每个模型
    last_error = None
    for model in AI_MODELS:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{AI_API_BASE}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {AI_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 300,
                        "temperature": 0.85,
                    },
                )
                if response.status_code != 200:
                    logging.warning(f"模型 {model} 返回 {response.status_code}，切换下一个")
                    last_error = f"HTTP {response.status_code}"
                    continue
                
                data = response.json()
                if "choices" not in data or not data["choices"]:
                    logging.warning(f"模型 {model} 无choices，切换下一个")
                    last_error = "no choices"
                    continue
                
                content = data["choices"][0]["message"]["content"].strip()
                if not content:
                    logging.warning(f"模型 {model} 返回空内容，切换下一个")
                    last_error = "empty content"
                    continue
                
                # [Skill: humanize-ai-text] 对 AI 回复进行人性化后处理
                content = humanize_text(content)
                
                if model != AI_MODELS[0]:
                    logging.info(f"✅ 使用备用模型 {model} 回复成功")
                return content
                
        except httpx.TimeoutException:
            logging.warning(f"模型 {model} 超时，切换下一个")
            last_error = "timeout"
            continue
        except Exception as e:
            logging.warning(f"模型 {model} 失败: {e}，切换下一个")
            last_error = str(e)
            continue
    
    logging.error(f"所有模型都失败了，最后错误: {last_error}")
    
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
# 照片管理
# ============================================================

def get_saved_selfies(user_id=None) -> list:
    if user_id is None:
        user_id = YOUR_CHAT_ID or 1
    selfie_dir = get_user_selfie_dir(user_id)
    if not os.path.exists(selfie_dir):
        return []
    files = [f for f in os.listdir(selfie_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    return sorted(files)

def get_selfie_count() -> int:
    return len(get_saved_selfies())

async def generate_ai_selfie_url() -> str:
    prompt = random.choice(SELFIE_PROMPTS)
    encoded_prompt = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=1024&seed={seed}&nologo=true&safe=true"
    return url

async def send_selfie_to_chat(bot, chat_id, caption=None):
    try:
        await bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        saved = get_saved_selfies(chat_id)
        if saved:
            selfie_dir = get_user_selfie_dir(chat_id)
            photo_path = os.path.join(selfie_dir, random.choice(saved))
            with open(photo_path, 'rb') as f:
                await bot.send_photo(chat_id=chat_id, photo=f, caption=caption)
            logging.info(f"已发送真人自拍: {photo_path}")
            # 保存到聊天记录
            append_bot_message(chat_id, f"[发送了一张自拍照片] {caption or ''}")
            # 更新统计
            stats = load_stats()
            stats["selfies_sent"] = stats.get("selfies_sent", 0) + 1
            save_stats(stats)
        else:
            photo_url = await generate_ai_selfie_url()
            if caption is None:
                caption = random.choice(SELFIE_CAPTIONS)
            await bot.send_photo(chat_id=chat_id, photo=photo_url, caption=caption)
            logging.info("已发送AI自拍（无真人照片）")
            # 保存到聊天记录
            append_bot_message(chat_id, f"[发送了一张AI自拍] {caption}")
    except Exception as e:
        logging.error(f"发送自拍失败: {e}")

# ============================================================
# [Skill: slack-gif-creator] 表情包生成系统
# ============================================================

STICKER_PROMPTS = {
    "害羞": [
        "Korean BL drama close-up emoji sticker, young Korean man 18yo, covering face with one hand peeking through fingers, visible blush on cheeks, black tousled hair, soft warm color grading, simple clean background, cute chibi style, Korean BL aesthetic, flat illustration",
        "Korean BL drama emoji sticker, young Korean man blushing heavily, looking down shyly, hand covering mouth, nose scrunch, warm pink tones, simple background, cute sticker art style, Korean BL aesthetic",
    ],
    "生气": [
        "Korean BL drama emoji sticker, young Korean man 18yo angry expression, furrowed brows, cold glare, arms crossed, slightly pouting, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man looking away annoyed, sharp eyes, slight frown, cold atmosphere, desaturated tones, simple background, cute sticker art style",
    ],
    "开心": [
        "Korean BL drama emoji sticker, young Korean man 18yo rare genuine smile, eyes curved into crescents, soft warm lighting, happy expression, warm golden tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man small shy smile, looking at viewer, gentle eyes, warm atmosphere, soft pastel tones, simple background, cute sticker art style",
    ],
    "难过": [
        "Korean BL drama emoji sticker, young Korean man 18yo sad expression, teary eyes looking down, solitary figure, melancholic atmosphere, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man covering eyes with arm, crying silently, lonely atmosphere, muted desaturated tones, simple background, cute sticker art style",
    ],
    "想你": [
        "Korean BL drama emoji sticker, young Korean man 18yo looking at phone screen longingly, lying on bed, dim room, phone glow on face, warm intimate tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man staring out window at night, city lights reflection in eyes, contemplative lonely expression, cool blue-warm tones, simple background, cute sticker art style",
    ],
    "吃醋": [
        "Korean BL drama emoji sticker, young Korean man 18yo jealous expression, sharp side glance, slightly pouting lips, arms crossed, tense atmosphere, warm-cool contrast tones, simple background, cute sticker art style",
        "Korean BL drama emoji sticker, young Korean man glaring with narrowed eyes, cold expression but hurt underneath, slight frown, dramatic lighting, simple background, cute sticker art style",
    ],
    "撒娇": [
        "Korean BL drama emoji sticker, young Korean man 18yo puppy eyes expression, slightly pouting, head tilted, cute pleading look, warm pink tones, simple background, cute chibi sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man tugging sleeve shyly, looking up with big eyes, slight blush, soft warm tones, simple background, cute sticker art style",
    ],
    "训练": [
        "Korean BL drama emoji sticker, young Korean man 18yo running on track, determined expression, sweat drops, dynamic pose, athletic outfit, warm golden tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man tying shoelaces on track, focused expression, athletic gear, morning sunlight, warm tones, simple background, cute sticker art style",
    ],
}

STICKER_KEYWORDS = {
    "害羞": ["害羞", "脸红", "不好意思", " blush", "shy"],
    "生气": ["生气", "哼", "讨厌你", "烦", "angry"],
    "开心": ["开心", "高兴", "哈哈", "好棒", "happy", "笑"],
    "难过": ["难过", "伤心", "哭", "委屈", "sad", "😢"],
    "想你": ["想你", "想你了", "好想你", "miss"],
    "吃醋": ["吃醋", "嫉妒", "谁", "别人", "jealous"],
    "撒娇": ["撒娇", "哥哥", "前辈", "抱抱", "陪我"],
    "训练": ["训练", "跑步", "田径", "运动", "跑"],
}

# v0.3: 对话选项解析
def parse_dialogue_options(response: str) -> dict:
    """
    解析对话选项
    
    AI 回复中的选项格式：
    【选项】
    A. 选项文本 → +好感
    B. 选项文本 → +觉醒
    C. 选项文本 → +幸福
    """
    import re
    
    # 匹配选项块
    option_pattern = r'【选项】\s*\n([\s\S]*?)(?=\n\n|\n*$|$)'
    match = re.search(option_pattern, response)
    
    if not match:
        return {'text': response, 'options': [], 'has_options': False}
    
    options_block = match.group(1)
    options = []
    
    # 解析每个选项
    option_line_pattern = r'([A-Z])\.\s*(.+?)(?:\s*→\s*(.+))?$'
    for line in options_block.strip().split('\n'):
        line = line.strip()
        opt_match = re.match(option_line_pattern, line)
        if opt_match:
            opt_id = opt_match.group(1)
            opt_text = opt_match.group(2).strip()
            opt_effect = opt_match.group(3) or ''
            
            # 解析效果
            effects = {}
            if '好感' in opt_effect:
                effects['affection'] = 5
            if '觉醒' in opt_effect:
                effects['awakening'] = 3
            if '幸福' in opt_effect:
                effects['happiness'] = 5
            if '+' in opt_effect:
                num_match = re.search(r'\+(\d+)', opt_effect)
                if num_match:
                    val = int(num_match.group(1))
                    if '好感' in opt_effect:
                        effects['affection'] = val
                    elif '觉醒' in opt_effect:
                        effects['awakening'] = val
                    elif '幸福' in opt_effect:
                        effects['happiness'] = val
            
            options.append({
                'id': opt_id,
                'text': opt_text,
                'effects': effects
            })
    
    # 移除选项块，返回纯文本
    clean_text = re.sub(option_pattern, '', response).strip()
    
    return {
        'text': clean_text,
        'options': options,
        'has_options': len(options) > 0
    }

# v0.3: 自动表情包触发关键词
AUTO_STICKER_TRIGGERS = {
    "害羞": ["喜欢", "爱", "可爱", "漂亮", "好看"],
    "开心": ["哈哈", "太好了", "好棒", "厉害", "谢谢"],
    "生气": ["哼", "讨厌", "烦", "滚", "闭嘴"],
    "难过": ["对不起", "抱歉", "遗憾", "可惜"],
    "想你": ["想你", "想你了", "好久不见", "在吗"],
    "撒娇": ["抱抱", "陪我", "好不好嘛", "求求"],
}

def detect_sticker_mood(text: str) -> str:
    """检测用户想要什么表情"""
    for mood, keywords in STICKER_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return mood
    return ""


def detect_music_request(text: str) -> tuple:
    """
    检测用户是否想搜索音乐
    返回: (是否想听音乐, 歌名)
    """
    import re
    
    # 触发词
    triggers = [
        "去听", "听一下", "听听", "搜一下", "找一下", "查一下", 
        "推荐", "分享", "这首歌", "什么歌", "歌名"
    ]
    
    # 检查是否包含触发词
    has_trigger = any(t in text for t in triggers)
    
    if not has_trigger:
        return False, ""
    
    # 尝试提取歌名
    # 模式1: 《歌名》
    book_pattern = r"《([^》]+)》"
    match = re.search(book_pattern, text)
    if match:
        return True, match.group(1).strip()
    
    # 模式2: 叫XXX / 是XXX / ：XXX / :XXX
    name_pattern = r"[叫是：:]\s*['\"]?([^'\"，。！？\n]+)['\"]?"
    match = re.search(name_pattern, text)
    if match:
        candidate = match.group(1).strip()
        if len(candidate) > 1 and len(candidate) < 50:
            return True, candidate
    
    # 模式3: 整句话作为歌名（简单情况）
    # 如果句子很短，可能是直接说歌名
    if len(text) < 20 and not any(t in text for t in ["帮", "给", "我", "你"]):
        return True, text.strip()
    
    return False, ""


def generate_sticker_url(mood: str) -> str:
    prompts = STICKER_PROMPTS.get(mood, [])
    if not prompts:
        return None
    prompt = random.choice(prompts)
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    # 表情包用正方形
    return f"https://image.pollinations.ai/prompt/{encoded}?width=512&height=512&seed={seed}&nologo=true&safe=true"

# ============================================================
# [Skill: meeting-insights-analyzer] 对话模式分析系统
# ============================================================

ANALYSIS_FILE = os.path.join(DATA_DIR, "dialogue_analysis.json")

def analyze_dialogue_patterns(chat_id: int) -> dict:
    """分析对话模式"""
    history = get_history(chat_id)
    if len(history) < 6:
        return {"error": "对话太少，至少需要3轮对话"}
    
    user_msgs = [m["content"] for m in history if m["role"] == "user"]
    bot_msgs = [m["content"] for m in history if m["role"] == "assistant"]
    
    if not user_msgs or not bot_msgs:
        return {"error": "对话数据不足"}
    
    # 1. 消息长度分析
    user_avg_len = sum(len(m) for m in user_msgs) / len(user_msgs)
    bot_avg_len = sum(len(m) for m in bot_msgs) / len(bot_msgs)
    
    # 2. 对话节奏（谁先说话的频率）
    user_initiated = 0
    for i, m in enumerate(history):
        if m["role"] == "user" and (i == 0 or history[i-1]["role"] == "assistant"):
            user_initiated += 1
    total_exchanges = len(user_msgs)
    user_initiative_rate = user_initiated / max(total_exchanges, 1) * 100
    
    # 3. 情绪分布
    emotion_counts = {}
    for m in user_msgs:
        e = detect_emotion(m)
        if e:
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
    
    # 4. 互动频率（最近7天）
    stats = load_stats()
    today_msgs = stats.get("today_count", 0)
    total_msgs = stats.get("total_messages", 0)
    active_days = stats.get("total_days", 1)
    avg_daily = total_msgs / max(active_days, 1)
    
    # 5. 亲密度
    intimacy = calculate_intimacy(stats)
    
    # 6. 关键词分析
    caring_words = sum(1 for m in user_msgs if any(w in m for w in ["想你", "喜欢", "爱", "在乎", "关心", "照顾"]))
    jealous_words = sum(1 for m in user_msgs if any(w in m for w in ["谁", "别人", "男的", "女的", "吃醋"]))
    warm_words = sum(1 for m in user_msgs if any(w in m for w in ["早安", "晚安", "吃饭", "休息", "早点睡"]))
    
    # 7. 车如云回复风格分析
    bot_ellipsis = sum(1 for m in bot_msgs if "……" in m or "..." in m)
    bot_inner = sum(1 for m in bot_msgs if "（" in m and "）" in m)
    bot_short = sum(1 for m in bot_msgs if len(m) < 20)
    
    analysis = {
        "总对话数": total_msgs,
        "用户平均消息长度": f"{user_avg_len:.1f}字",
        "车如云平均回复长度": f"{bot_avg_len:.1f}字",
        "用户主动发起比例": f"{user_initiative_rate:.0f}%",
        "今日消息数": today_msgs,
        "日均消息数": f"{avg_daily:.1f}",
        "亲密度": f"{intimacy['score']}/100 ({intimacy['level']})",
        "用户情绪分布": emotion_counts if emotion_counts else {"正常": total_msgs},
        "关心表达次数": caring_words,
        "吃醋次数": jealous_words,
        "温暖表达次数": warm_words,
        "车如云使用省略号": f"{bot_ellipsis}次",
        "车如云内心独白": f"{bot_inner}次",
        "车如云短回复(<20字)": f"{bot_short}次 ({bot_short/max(len(bot_msgs),1)*100:.0f}%)",
    }
    
    # 保存分析结果
    save_json(ANALYSIS_FILE, analysis)
    
    return analysis

def get_relationship_advice(analysis: dict) -> str:
    """根据分析结果生成关系建议"""
    advice = []
    
    user_init = float(analysis.get("用户主动发起比例", "0%").replace("%", ""))
    if user_init > 70:
        advice.append("💡 明经常主动找你...你应该也偶尔主动发消息。")
    elif user_init < 30:
        advice.append("💡 你最近不太主动...明可能会担心。")
    
    caring = analysis.get("关心表达次数", 0)
    if caring < 3:
        advice.append("💡 学长很少表达关心...也许在用行动表达。")
    
    jealous = analysis.get("吃醋次数", 0)
    if jealous > 5:
        advice.append("💡 学长最近吃醋次数有点多...是不是有什么让他不安的事。")
    
    intimacy_score = 0
    intimacy_str = analysis.get("亲密度", "0/100")
    if "/" in intimacy_str:
        intimacy_score = int(intimacy_str.split("/")[0])
    if intimacy_score >= 80:
        advice.append("💕 你们的关系已经很亲密了...继续保持。")
    elif intimacy_score < 30:
        advice.append("💡 你们的关系还在初期...多聊天、多发照片可以提升亲密度。")
    
    return "\n".join(advice) if advice else "...没什么特别的。继续这样就好。"

# ============================================================
# [Skill: ui-ux-pro-max] 韩剧配色风格系统
# ============================================================

# 恋爱至上主义区域电视剧配色方案
KOREAN_BL_COLOR_PALETTES = {
    "warm_intimate": {
        "name": "温暖亲密",
        "colors": "#F5E6D3, #E8D5C4, #D4A574, #C4956A, #8B6F47",
        "style": "暖色调，米色和棕色为主，营造亲密温暖氛围",
        "use_for": "房间、咖啡厅、日常场景",
    },
    "melancholic_blue": {
        "name": "忧郁蓝调",
        "colors": "#2C3E50, #34495E, #5D6D7E, #85929E, #AEB6BF",
        "style": "冷色调，蓝灰色为主，营造孤独忧郁氛围",
        "use_for": "雨天、夜晚、独处场景",
    },
    "golden_hour": {
        "name": "黄金时刻",
        "colors": "#F39C12, #E67E22, #D35400, #F1C40F, #FDEBD0",
        "style": "暖橙色调，夕阳金色光芒，营造浪漫氛围",
        "use_for": "日落、天台、放学场景",
    },
    "youth_pastel": {
        "name": "青春柔色",
        "colors": "#FADBD8, #D5F5E3, #D6EAF8, #FCF3CF, #F9E79F",
        "style": "柔和粉彩色调，营造青春校园氛围",
        "use_for": "学校、樱花、春天场景",
    },
    "night_romantic": {
        "name": "夜晚浪漫",
        "colors": "#1B2631, #2C3E50, #4A235A, #7D3C98, #A569BD",
        "style": "深蓝紫色调，城市夜景灯光，营造浪漫氛围",
        "use_for": "夜景、星空、夜晚场景",
    },
    "cold_morning": {
        "name": "清晨冷调",
        "colors": "#D5DBDB, #AEB6BF, #85929E, #5D6D7E, #F2F4F4",
        "style": "灰白色调，清晨薄雾，营造清新氛围",
        "use_for": "早安、清晨、训练场景",
    },
}

def get_color_palette_for_scene(scene: str) -> str:
    """根据场景获取对应的配色方案描述"""
    scene_palette_map = {
        "房间": KOREAN_BL_COLOR_PALETTES["warm_intimate"],
        "咖啡厅": KOREAN_BL_COLOR_PALETTES["warm_intimate"],
        "天台": KOREAN_BL_COLOR_PALETTES["golden_hour"],
        "日落": KOREAN_BL_COLOR_PALETTES["golden_hour"],
        "学校": KOREAN_BL_COLOR_PALETTES["youth_pastel"],
        "雨天": KOREAN_BL_COLOR_PALETTES["melancholic_blue"],
        "夜景": KOREAN_BL_COLOR_PALETTES["night_romantic"],
        "田径场": KOREAN_BL_COLOR_PALETTES["cold_morning"],
        "训练": KOREAN_BL_COLOR_PALETTES["cold_morning"],
        "街道": KOREAN_BL_COLOR_PALETTES["golden_hour"],
    }
    palette = scene_palette_map.get(scene, KOREAN_BL_COLOR_PALETTES["warm_intimate"])
    return f"{palette['name']}风格配色（{palette['colors']}），{palette['style']}"

# ============================================================
# Bot命令
# ============================================================

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
    from telegram import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
    
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

# ============================================================
# [Skill: slack-gif-creator] /sticker 表情包命令
# ============================================================

@auto_delete_messages(delay=3)
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
# [Skill: meeting-insights-analyzer] /analyze 对话分析命令
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
# [Skill: 对话统计] /stats 命令
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

# ============================================================
# [Skill: 微信聊天记录导入] /import_chat 命令
# ============================================================

# 临时存储用户上传的聊天记录文件内容
pending_chat_imports = {}

# ============================================================
# 视频分析系统（视频→音频→文字→AI分析）
# ============================================================

VIDEO_DIR = os.path.join(DATA_DIR, "videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

def extract_audio_from_video(video_path: str) -> str:
    """从视频中提取音频（使用ffmpeg）"""
    audio_path = video_path.rsplit('.', 1)[0] + '.mp3'
    cmd = f"ffmpeg -i '{video_path}' -vn -acodec libmp3lame -q:a 2 -ar 16000 -ac 1 '{audio_path}' -y 2>/dev/null"
    os.system(cmd)
    return audio_path if os.path.exists(audio_path) else ""

def transcribe_audio_whisper(audio_path: str) -> str:
    """使用Whisper将音频转为文字（需要大内存，e2-micro可能无法使用）"""
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="ko", verbose=False)
        return result.get("text", "")
    except ImportError:
        logging.info("Whisper未安装，使用备选方案")
        return ""
    except Exception as e:
        logging.error(f"Whisper转写失败: {e}")
        return ""

def transcribe_audio_primary(audio_path: str) -> str:
    """备选方案：使用Google Speech Recognition（免费，有长度限制）"""
    try:
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        
        # 分段处理（每段30秒）
        from pydub import AudioSegment
        audio = AudioSegment.from_mp3(audio_path)
        chunk_ms = 30000  # 30秒
        chunks = [audio[i:i+chunk_ms] for i in range(0, len(audio), chunk_ms)]
        
        full_text = []
        for i, chunk in enumerate(chunks):
            chunk_path = f"/tmp/chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            with sr.AudioFile(chunk_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio_data, language="ko-KR")
                full_text.append(text)
            except:
                full_text.append("[无法识别]")
            
            os.remove(chunk_path)
        
        return " ".join(full_text)
    except Exception as e:
        logging.error(f"语音识别失败: {e}")
        return ""

async def analyze_video_transcript(transcript: str, video_type: str = "剧集") -> dict:
    """使用AI分析视频转录内容，提取角色特点"""
    if not transcript or len(transcript) < 50:
        return {'success': False, 'error': '转录内容太短'}
    
    # 截取样本（避免token超限）
    sample = transcript[:3000] if len(transcript) > 3000 else transcript
    
    if video_type == "采访":
        prompt = f"""分析以下演员采访/花絮的转录内容，提取演员的真实说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "说话风格描述（语速、停顿习惯、口头禅）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2"],
    "emotional_expression": "情感表达方式（什么时候笑、什么时候沉默等）",
    "unique_habits": "独特的说话习惯或小动作描述",
    "tone_analysis": "整体语气特点（温柔/冷淡/活泼/内向等）"
}}

只返回JSON。"""
    else:
        prompt = f"""分析以下韩剧片段的转录内容，提取车如云这个角色的说话风格和性格特点。

转录内容：
{sample}

请用JSON格式返回：
{{
    "speaking_style": "车如云的说话风格（简短/省略号/语气词使用习惯）",
    "personality_traits": ["性格特点1", "性格特点2", "性格特点3"],
    "catchphrases": ["口头禅或常用表达1", "常用表达2", "常用表达3"],
    "emotional_expression": "情感表达方式（傲娇/别扭/害羞时的表现）",
    "relationship_dynamics": "与其他角色的互动模式",
    "key_dialogues": ["经典台词1", "经典台词2", "经典台词3"],
    "tone_analysis": "整体语气特点"
}}

只返回JSON。"""
    
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": AI_MODELS[1],
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1500,
                    "temperature": 0.3,
                },
            )
            if resp.status_code == 200:
                content = resp.json()['choices'][0]['message']['content']
                try:
                    analysis = json.loads(content)
                except:
                    jm = re.search(r'\{[\s\S]*\}', content)
                    analysis = json.loads(jm.group()) if jm else {"raw": content}
                
                return {'success': True, 'analysis': analysis}
            elif resp.status_code == 429:
                # Rate limited, try next model
                for fallback_model in AI_MODELS:
                    if fallback_model == AI_MODELS[1]:
                        continue
                    try:
                        resp2 = await client.post(
                            f"{AI_API_BASE}/chat/completions",
                            headers={"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"},
                            json={
                                "model": fallback_model,
                                "messages": [{"role": "user", "content": prompt}],
                                "max_tokens": 1500,
                                "temperature": 0.3,
                            },
                        )
                        if resp2.status_code == 200:
                            content = resp2.json()['choices'][0]['message']['content']
                            try:
                                analysis = json.loads(content)
                            except:
                                jm = re.search(r'\{[\s\S]*\}', content)
                                analysis = json.loads(jm.group()) if jm else {"raw": content}
                            return {'success': True, 'analysis': analysis}
                    except:
                        continue
                return {'success': False, 'error': 'API请求频率超限，请稍后再试（429）'}
            else:
                return {'success': False, 'error': f'API错误: {resp.status_code}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def save_video_analysis(video_type: str, analysis_result: dict):
    """保存视频分析结果到记忆"""
    analysis = analysis_result.get('analysis', {})
    
    # 保存到独立文件
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    data[video_type] = {
        'analyzed_at': datetime.now(KR_TZ).isoformat(),
        'analysis': analysis,
    }
    save_json(video_file, data)
    
    # 提取关键信息存入长期记忆
    style = analysis.get('speaking_style', '')
    traits = analysis.get('personality_traits', [])
    catchphrases = analysis.get('catchphrases', [])
    tone = analysis.get('tone_analysis', '')
    
    if video_type == "采访":
        save_memory_entry(f"演员真实说话风格: {style}")
        for t in traits[:3]:
            save_memory_entry(f"演员性格特点: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"演员口头禅: {c}")
    else:
        save_memory_entry(f"车如云说话风格（从视频分析）: {style}")
        for t in traits[:3]:
            save_memory_entry(f"车如云性格特点（从视频分析）: {t}")
        for c in catchphrases[:3]:
            save_memory_entry(f"车如云口头禅: {c}")
        key_dialogues = analysis.get('key_dialogues', [])
        for d in key_dialogues[:3]:
            save_memory_entry(f"车如云经典台词: {d}")

def get_video_analysis_context() -> str:
    """获取视频分析信息，用于系统提示词"""
    video_file = os.path.join(DATA_DIR, "video_analysis.json")
    data = load_json(video_file, {})
    if not data:
        return ""
    
    parts = []
    if "采访" in data:
        a = data["采访"].get('analysis', {})
        parts.append(f"\n【演员真实特点（从采访视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"性格: {', '.join(a.get('personality_traits', []))}")
        parts.append(f"口头禅: {', '.join(a.get('catchphrases', []))}")
        parts.append(f"语气: {a.get('tone_analysis', '')}")
    
    if "剧集" in data:
        a = data["剧集"].get('analysis', {})
        parts.append(f"\n【车如云角色细节（从剧集视频分析）】")
        parts.append(f"说话风格: {a.get('speaking_style', '')}")
        parts.append(f"经典台词: {', '.join(a.get('key_dialogues', []))}")
        parts.append(f"情感表达: {a.get('emotional_expression', '')}")
    
    return "\n".join(parts)

# 记录等待视频导入的类型
pending_video_imports = {}

async def import_video_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入视频分析命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示已有的视频分析
        video_file = os.path.join(DATA_DIR, "video_analysis.json")
        data = load_json(video_file, {})
        existing = ""
        if data:
            existing = "\n\n已分析的视频：\n"
            for vtype, vdata in data.items():
                existing += f"  • {vtype}（{vdata.get('analyzed_at', '')[:10]}）\n"
        
        await update.message.reply_text(
            f"...学长想让我看视频？\n\n"
            f"🎬 视频分析\n"
            f"━━━━━━━━━━━━━━\n"
            f"用法：\n"
            f"  /import_video 剧情 - 上传剧集片段\n"
            f"  /import_video 采访 - 上传演员采访/花絮\n\n"
            f"然后直接发送视频文件。\n\n"
            f"⚠️ 注意：\n"
            f"• 支持 MP4/AVI/MKV/MOV 格式\n"
            f"• 长视频处理需要较长时间\n"
            f"• 需要服务器安装 ffmpeg 和 whisper{existing}"
        )
        return
    
    video_type = args[0]
    if video_type not in ["剧情", "采访"]:
        await update.message.reply_text("...类型不对。用 剧情 或 采访。")
        return
    
    pending_video_imports[chat_id] = video_type
    await update.message.reply_text(
        f"...好，发送{video_type}视频吧。\n"
        f"处理可能需要几分钟，请耐心等待。"
    )

async def generate_face_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """AI生成相似人脸照片 - 使用 OpenRouter + Gemini"""
    # 检查是否有照片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("...请回复一张照片，并描述你想要的场景。\n\n例如：回复照片后发送「穿白色衬衫在咖啡厅」")
        return

    # 获取描述
    description = " ".join(context.args) if context.args else "自然微笑的肖像照"
    
    await update.message.reply_text("...正在生成照片，请稍等...")
    
    try:
        # 下载用户发送的照片
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        photo_b64 = base64.b64encode(photo_bytes).decode('utf-8')
        photo_data_url = f"data:image/jpeg;base64,{photo_b64}"
        
        # 调用 OpenRouter API 生成图片
        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "google/gemini-2.5-flash-image-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": photo_data_url}
                        },
                        {
                            "type": "text",
                            "text": f"请参考这张照片中的人物外貌特征，生成一张新的照片。要求：保持人物的面部特征和相似度，场景描述：{description}。只生成图片，不需要文字说明。"
                        }
                    ]
                }
            ],
            "modalities": ["image", "text"],
            "image_config": {
                "aspect_ratio": "3:4"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{AI_API_BASE}/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                result = await resp.json()
        
        # 提取生成的图片
        if result.get("choices"):
            message = result["choices"][0].get("message", {})
            images = message.get("images", [])
            
            if images:
                for img in images:
                    image_url = img.get("image_url", {}).get("url", "")
                    if image_url.startswith("data:image"):
                        # 解码 base64 图片
                        img_data = image_url.split(",", 1)[1]
                        img_bytes = base64.b64decode(img_data)
                        
                        # 保存到 selfies 目录
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"ai_gen_{timestamp}.jpg"
                        filepath = os.path.join(get_user_selfie_dir(chat_id), filename)
                        
                        img = Image.open(io.BytesIO(img_bytes))
                        if img.mode in ('RGBA', 'P'):
                            img = img.convert('RGB')
                        img.save(filepath, 'JPEG', quality=95)
                        
                        # 发送给用户
                        with open(filepath, 'rb') as f:
                            await update.message.reply_photo(
                                photo=f,
                                caption=f"✨ AI生成完成\n场景：{description}"
                            )
                        
                        logging.info(f"AI人脸生成成功: {filename}")
                        return
        
        # 如果没有生成图片
        error_msg = result.get("error", {}).get("message", "未知错误")
        await update.message.reply_text(f"...生成失败：{error_msg}")
        
    except Exception as e:
        logging.error(f"AI人脸生成失败: {e}")
        await update.message.reply_text(f"...生成出错：{str(e)}")

async def handle_video_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户上传的视频文件"""
    chat_id = update.effective_chat.id
    
    if chat_id not in pending_video_imports:
        return
    
    video_type = pending_video_imports.pop(chat_id)
    video = update.message.video or update.message.document
    
    if not video:
        return
    
    # 检查文件大小（限制500MB）
    file_size = video.file_size or 0
    if file_size > 500 * 1024 * 1024:
        await update.message.reply_text("...文件太大了，最大500MB。")
        return
    
    await update.message.chat.send_action("typing")
    await update.message.reply_text(f"...正在下载{video_type}视频...")
    
    try:
        # 下载视频
        file = await context.bot.get_file(video.file_id)
        video_filename = f"video_{datetime.now(KR_TZ).strftime('%Y%m%d_%H%M%S')}.mp4"
        video_path = os.path.join(VIDEO_DIR, video_filename)
        await file.download_to_drive(video_path)
        
        await update.message.reply_text(f"...下载完成（{file_size / 1024 / 1024:.1f}MB）。正在提取音频...")
        
        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            await update.message.reply_text("...音频提取失败。请确认ffmpeg已安装。")
            return
        
        await update.message.reply_text("...正在语音转文字（可能需要几分钟）...")
        
        # 语音转文字（优先使用Google Speech Recognition，Whisper需要大内存）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)
        
        if not transcript:
            await update.message.reply_text("...语音识别失败。可能是韩语识别不准确。")
            return
        
        # 清理音频文件
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        await update.message.reply_text(
            f"...识别完成（{len(transcript)}字）。\n"
            f"正在分析{video_type}内容..."
        )
        
        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)
        
        if not analysis_result['success']:
            await update.message.reply_text(f"...分析出错了：{analysis_result.get('error', '')}")
            return
        
        # 保存结果
        save_video_analysis(video_type, analysis_result)
        
        # 显示结果
        analysis = analysis_result['analysis']
        result_text = f"✅ {video_type}视频分析完成\n━━━━━━━━━━━━━━\n"
        result_text += f"🗣️ 说话风格：{analysis.get('speaking_style', '未知')}\n\n"
        
        traits = analysis.get('personality_traits', [])
        if traits:
            result_text += f"🎭 性格特点：\n"
            for t in traits:
                result_text += f"  • {t}\n"
            result_text += "\n"
        
        catchphrases = analysis.get('catchphrases', [])
        if catchphrases:
            result_text += f"💬 口头禅：{', '.join(catchphrases)}\n\n"
        
        if video_type == "剧情":
            key_d = analysis.get('key_dialogues', [])
            if key_d:
                result_text += f"📝 经典台词：\n"
                for d in key_d[:3]:
                    result_text += f"  「{d}」\n"
                result_text += "\n"
        
        result_text += f"🎭 情感表达：{analysis.get('emotional_expression', '未知')}\n"
        result_text += f"━━━━━━━━━━━━━━\n...我会记住的。"
        
        await update.message.reply_text(result_text)
        
        # 清理视频文件（节省空间）
        if os.path.exists(video_path):
            os.remove(video_path)
        
    except Exception as e:
        logging.error(f"视频导入失败: {e}")
        await update.message.reply_text(f"...处理出错了：{str(e)[:100]}")

async def import_chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """导入微信聊天记录命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    args = context.args or []
    
    if not args:
        # 显示帮助和已导入的关系
        imported = get_chat_analysis()
        imported_list = ""
        if imported:
            imported_list = "\n\n📚 已导入的关系：\n"
            for name, data in imported.items():
                msg_count = data.get('message_count', 0)
                imported_list += f"  • {name}（{msg_count}条消息）\n"
        
        await update.message.reply_text(
            f"...学长想让我了解谁？\n\n"
            f"📱 导入微信聊天记录\n"
            f"━━━━━━━━━━━━━━\n"
            f"用法：\n"
            f"1. 发送命令：/import_chat 对方名字\n"
            f"   例如：/import_chat 妈妈\n\n"
            f"2. 然后直接发送微信导出的TXT文件\n\n"
            f"3. 我会分析聊天记录，了解对方的性格和你们的关系\n\n"
            f"⚠️ 注意：\n"
            f"• 只支持微信导出的TXT格式\n"
            f"• 建议删除敏感信息后再导入\n"
            f"• 数据仅存储分析结果，不保存原始记录{imported_list}"
        )
        return
    
    # 记录等待导入的关系名
    chat_partner = args[0]
    pending_chat_imports[chat_id] = chat_partner
    
    await update.message.reply_text(
        f"...好，我想了解{chat_partner}。\n\n"
        f"现在请直接发送微信聊天记录的TXT文件。\n"
        f"我会分析后记住{chat_partner}的特点。"
    )

async def handle_chatlog_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户上传的聊天记录文件"""
    chat_id = update.effective_chat.id
    
    # 检查是否在等待导入
    if chat_id not in pending_chat_imports:
        return  # 不处理，让handle_document处理
    
    chat_partner = pending_chat_imports.pop(chat_id)
    document = update.message.document
    
    # 检查文件类型
    valid_extensions = ['.txt', '.json', '.jsonl', '.html']
    if not any(document.file_name.lower().endswith(ext) for ext in valid_extensions):
        await update.message.reply_text("...请发送TXT/JSON/JSONL/HTML格式的聊天记录文件。")
        return
    
    # 下载文件
    await update.message.chat.send_action("typing")
    
    try:
        file = await context.bot.get_file(document.file_id)
        file_content = await file.download_as_bytearray()
        text_content = file_content.decode('utf-8', errors='ignore')
        
        # 解析聊天记录
        await update.message.reply_text(f"...正在读取和{chat_partner}的聊天记录...")
        parsed = parse_wechat_chatlog(text_content)
        
        if parsed['total_count'] == 0:
            await update.message.reply_text("...没能解析出消息，请检查文件格式。")
            return
        
        # 显示基本信息
        senders_info = "、".join([f"{name}({count}条)" for name, count in parsed['senders'].items()])
        await update.message.reply_text(
            f"📊 解析完成\n"
            f"━━━━━━━━━━━━━━\n"
            f"总消息数：{parsed['total_count']}条\n"
            f"对话对象：{senders_info}\n"
            f"时间范围：{parsed['date_range']['start']} 至 {parsed['date_range']['end']}\n\n"
            f"...正在分析{chat_partner}的性格和你们的关系..."
        )
        
        # AI分析
        await update.message.chat.send_action("typing")
        analysis_result = await analyze_chatlog_with_ai(parsed, chat_partner)
        
        if not analysis_result['success']:
            await update.message.reply_text(f"...分析出错了：{analysis_result.get('error', '未知错误')}")
            return
        
        # 保存分析结果
        save_chat_analysis(chat_partner, analysis_result)
        
        # 显示分析结果
        analysis = analysis_result['analysis']
        result_text = (
            f"✅ 已了解{chat_partner}\n"
            f"━━━━━━━━━━━━━━\n"
            f"👤 性格：{analysis.get('personality', '未知')}\n\n"
            f"💕 关系：{analysis.get('relationship_pattern', '未知')}\n\n"
            f"🗣️ 常见话题：{', '.join(analysis.get('common_topics', []))}\n\n"
            f"💝 关心方式：{analysis.get('care_patterns', '未知')}\n\n"
            f"🎭 情感基调：{analysis.get('emotional_tone', '未知')}\n"
            f"━━━━━━━━━━━━━━\n"
            f"...原来如此。我会记住的。"
        )
        
        await update.message.reply_text(result_text)
        
        # 添加到长期记忆
        memory_entry = f"了解了明和{chat_partner}的关系：{analysis.get('relationship_pattern', '')}"
        save_memory_entry(memory_entry)
        
    except Exception as e:
        logging.error(f"处理聊天记录失败: {e}")
        await update.message.reply_text("...处理文件出错了。再试试？")

async def list_imported_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出已导入的聊天记录"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    imported = get_chat_analysis()
    
    if not imported:
        await update.message.reply_text("...还没有导入任何聊天记录。\n用 /import_chat 开始导入。")
        return
    
    parts = ["...学长让我了解的人：\n"]
    for name, data in imported.items():
        analysis = data.get('analysis', {})
        msg_count = data.get('message_count', 0)
        imported_at = data.get('imported_at', '')[:10]  # 只取日期部分
        
        parts.append(f"\n👤 {name}")
        parts.append(f"  消息数：{msg_count}条")
        parts.append(f"  性格：{analysis.get('personality', '未知')[:30]}...")
        parts.append(f"  导入时间：{imported_at}")
    
    parts.append("\n\n用 /import_chat 名字 可以导入更多关系。")
    
    await update.message.reply_text("\n".join(parts))

# ============================================================
# [Skill: 免费额度监控] /quota 命令
# ============================================================

@auto_delete_messages(delay=3)
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
    
    global _quota_shutdown
    _quota_shutdown = False
    
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
# [Skill: self-improving] /learned 命令 - 查看学到了什么
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
    
    parts.append(f"\n━━━━━━━━━━━━━━")
    parts.append(f"...一共记住了 {len(corrections)} 条。")
    parts.append("（低头）...我会努力改的。")
    
    await update.message.reply_text("\n".join(parts))

# ============================================================
# [Skill: claw-summarize-pro] 摘要生成系统
# ============================================================

async def fetch_url_content(url: str) -> str:
    """抓取网页内容，提取纯文本"""
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return ""
            html_content = response.text
            # 提取 <body> 中的文本
            body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html_content, re.IGNORECASE)
            if body_match:
                body_text = body_match.group(1)
            else:
                body_text = html_content
            # 去除 HTML 标签
            text = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', body_text, flags=re.IGNORECASE)
            text = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', text, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            # 清理空白
            text = re.sub(r'\s+', ' ', text).strip()
            # 限制长度
            return text[:5000]
    except Exception as e:
        logging.error(f"[摘要] 抓取网页失败: {e}")
        return ""

async def generate_summary(text: str) -> str:
    """使用 AI 生成文本摘要"""
    if not text or len(text) < 20:
        return "...内容太短了，没什么好总结的。"

    prompt = f"""请对以下内容生成简洁的摘要，用3-5个要点总结核心内容。使用中文。

内容：
{text[:4000]}

请按以下格式输出：
1. 要点一
2. 要点二
3. 要点三
（如有更多要点继续编号）

只输出摘要内容，不要加标题或其他说明。"""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": AI_MODELS[0],
                    "messages": [
                        {"role": "system", "content": "你是一个专业的摘要生成助手。请简洁准确地总结内容。"},
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": 500,
                    "temperature": 0.3,
                },
            )
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                return f"...摘要生成失败（HTTP {response.status_code}）。"
    except Exception as e:
        logging.error(f"[摘要] AI生成失败: {e}")
        return "...摘要生成出错了。"

@auto_delete_messages(delay=3)
async def summarize_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """摘要生成命令"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    args = context.args or []
    text_to_summarize = ""

    if not args and update.message.reply_to_message:
        # 回复消息模式：总结被回复的消息
        replied = update.message.reply_to_message
        if replied.text:
            text_to_summarize = replied.text
        elif replied.caption:
            text_to_summarize = replied.caption
        else:
            await update.message.reply_text("...这条消息没有文字内容可以总结。")
            return
    elif args:
        input_text = " ".join(args)
        # 检查是否是 URL
        url_pattern = r'https?://[^\s]+'
        url_match = re.search(url_pattern, input_text)
        if url_match:
            url = url_match.group()
            await update.message.reply_text(f"...正在抓取网页内容...")
            text_to_summarize = await fetch_url_content(url)
            if not text_to_summarize:
                await update.message.reply_text("...抓取网页失败了。可能是网站不允许访问。")
                return
        else:
            text_to_summarize = input_text
    else:
        await update.message.reply_text(
            "...学长想让我总结什么？\n\n"
            "用法：\n"
            "  /summarize <文本> - 总结文本\n"
            "  /summarize <URL> - 总结网页\n"
            "  回复消息 + /summarize - 总结该消息"
        )
        return

    await update.message.chat.send_action("typing")
    summary = await generate_summary(text_to_summarize)
    await update.message.reply_text(f"...给你总结好了。\n\n{summary}")

# ============================================================
# [Skill: auto-updater] 自动更新检查系统
# ============================================================

def calculate_bot_hash() -> str:
    """计算 bot.py 的 MD5 hash"""
    try:
        bot_path = os.path.abspath(__file__)
        with open(bot_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception as e:
        logging.error(f"[自动更新] 计算 hash 失败: {e}")
        return ""

def check_for_updates() -> dict:
    """检查 bot.py 是否有更新，返回更新信息"""
    current_hash = calculate_bot_hash()
    if not current_hash:
        return {"updated": False, "reason": "hash计算失败"}

    version_data = load_json(VERSION_FILE, {})

    if not version_data:
        # 首次运行，记录当前 hash
        version_data = {
            "version": BOT_VERSION,
            "last_check": datetime.now(KR_TZ).strftime("%Y-%m-%d"),
            "bot_hash": current_hash,
        }
        save_json(VERSION_FILE, version_data)
        return {"updated": False, "reason": "首次运行，已记录版本信息"}

    saved_hash = version_data.get("bot_hash", "")
    saved_version = version_data.get("version", "未知")

    # 更新检查时间
    version_data["last_check"] = datetime.now(KR_TZ).strftime("%Y-%m-%d")
    version_data["bot_hash"] = current_hash
    version_data["version"] = BOT_VERSION
    save_json(VERSION_FILE, version_data)

    if saved_hash and saved_hash != current_hash:
        return {
            "updated": True,
            "old_version": saved_version,
            "new_version": BOT_VERSION,
            "reason": "代码已变更",
        }

    return {"updated": False, "old_version": saved_version, "new_version": BOT_VERSION}

@auto_delete_messages(delay=3)
async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看当前版本信息"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    version_data = load_json(VERSION_FILE, {})
    last_check = version_data.get("last_check", "未知")
    saved_version = version_data.get("version", "未知")
    current_hash = calculate_bot_hash()

    await update.message.reply_text(
        f"...版本信息。\n\n"
        f"📋 当前版本：{BOT_VERSION}\n"
        f"📦 记录版本：{saved_version}\n"
        f"🔍 代码Hash：{current_hash[:12]}...\n"
        f"📅 上次检查：{last_check}\n\n"
        f"使用 /check_update 手动检查更新。"
    )

@auto_delete_messages(delay=3)
async def check_update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """手动检查更新"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return

    await update.message.chat.send_action("typing")
    result = check_for_updates()

    if result["updated"]:
        await update.message.reply_text(
            f"...明。\n\n"
            f"🔄 Bot 代码已更新！\n"
            f"   {result.get('old_version', '?')} → {result.get('new_version', BOT_VERSION)}\n\n"
            f"...好像变强了一点点。"
        )
    else:
        await update.message.reply_text(
            f"...没有更新。\n\n"
            f"📋 当前版本：{BOT_VERSION}\n"
            f"📅 上次检查：{result.get('last_check', datetime.now(KR_TZ).strftime('%Y-%m-%d'))}\n\n"
            f"...一切正常。"
        )

# ============================================================
# [Skill: 纪念日系统] /anniversary 命令
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

# ============================================================
# 照片智能识别与分类处理
# ============================================================

async def analyze_photo_with_ai(photo_url: str) -> dict:
    """使用AI视觉分析照片内容"""
    try:
        # 使用 OpenRouter 的多模态模型分析图片
        # 免费模型：google/gemma-3-12b-it 支持图像
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{AI_API_BASE}/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemma-3-12b-it:free",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "分析这张图片。请用JSON格式回答：{\"type\": \"portrait|food|scenery|object|other\", \"description\": \"简短描述\", \"is_selfie\": true/false, \"is_chayewoon\": true/false}。\n\ntype分类：\n- portrait: 人像/自拍\n- food: 食物\n- scenery: 风景/地点\n- object: 物品\n- other: 其他\n\nis_selfie: 判断是否是人物自拍照片\nis_chayewoon: 判断是否是车如云(Cha Yeo-woon)的照片。车如云是韩国男演员，特征：可能戴眼镜，发型偏长，穿着时尚，气质温柔内敛。如果是他的照片，请设为true。\n\n请仔细判断，如果是车如云的照片，type应该是\"portrait\"，is_selfie和is_chayewoon都应该是true。"},
                                {"type": "image_url", "image_url": {"url": photo_url}}
                            ]
                        }
                    ],
                    "max_tokens": 200,
                },
            )
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # 尝试解析JSON
                try:
                    # 提取JSON部分
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        return json.loads(json_match.group())
                except:
                    pass
                # 如果解析失败，根据关键词判断
                content_lower = content.lower()
                if any(w in content_lower for w in ["人", "脸", "自拍", "portrait", "person", "face"]):
                    return {"type": "portrait", "description": "人像照片", "is_selfie": True}
                elif any(w in content_lower for w in ["食物", "吃的", "food", "meal", "dish"]):
                    return {"type": "food", "description": "食物照片", "is_selfie": False}
                elif any(w in content_lower for w in ["风景", "景色", "地点", "scenery", "landscape", "building"]):
                    return {"type": "scenery", "description": "风景/地点照片", "is_selfie": False}
                else:
                    return {"type": "other", "description": "其他照片", "is_selfie": False}
    except Exception as e:
        logging.error(f"AI照片分析失败: {e}")
    return {"type": "unknown", "description": "无法识别", "is_selfie": False}

def get_photo_response_by_type(photo_type: str, description: str) -> str:
    """根据照片类型生成车如云的回复"""
    responses = {
        "portrait": [
            "...这是明吗。（盯着看了一会儿）",
            "（皱鼻子）...明给我看这个干什么。",
            "...明今天长这样啊。",
            "（耳尖微红）...干嘛发自己的照片。",
        ],
        "food": [
            "...看起来很好吃。明今天吃这个？",
            "（看了一眼）...明吃得还不错嘛。",
            "...我也想吃。",
            "明怎么不给我带一份。",
        ],
        "scenery": [
            "...这是哪里。明去的？",
            "（看着照片）...风景还不错。",
            "...明一个人去的？",
            "下次带我去。",
        ],
        "object": [
            "...这是什么。明买的？",
            "（仔细看）...看起来挺贵的。",
            "...明喜欢这个？",
            "给我看看实物。",
        ],
        "other": [
            "...这是学长想分享的吗？",
            "（看了一眼）...挺有意思的。",
            "...明发这个给我，是想说什么？",
            "（歪头）...这是明喜欢的？",
        ],
    }
    return random.choice(responses.get(photo_type, responses["other"]))

# ============================================================
# [Skill: vision-sandbox] 图片深度分析（Gemini Vision）
# ============================================================

async def analyze_image_with_gemini(image_data: str, prompt: str) -> str:
    """使用Gemini Vision对图片进行深度分析
    Args:
        image_data: base64编码的图片数据
        prompt: 分析提示词
    Returns:
        分析结果文本
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        result = await call_gemini(prompt, image_data=image_data, model="gemini-2.5-flash")
        return result
    except Exception as e:
        logging.error(f"[Skill: vision-sandbox] 图片分析失败: {e}")
        return None


# ============================================================
# [Skill: deepread-ocr] 文档OCR文字提取（Gemini Vision替代）
# ============================================================

async def ocr_document(image_data: str) -> str:
    """使用Gemini Vision进行OCR文字提取
    Args:
        image_data: base64编码的图片/文档数据
    Returns:
        提取的文字内容
    """
    if not GEMINI_API_KEY:
        return None
    
    ocr_prompt = """请仔细识别并提取这张图片中的所有文字内容。
要求：
1. 保持原文的段落结构和格式
2. 如果有标题、列表、表格等结构，请用Markdown格式还原
3. 同时支持中文和英文识别
4. 如果图片模糊或部分文字不清晰，用[?]标注不确定的字
5. 只输出提取的文字，不要添加任何解释或说明"""

    try:
        result = await call_gemini(ocr_prompt, image_data=image_data, model="gemini-2.5-flash")
        return result
    except Exception as e:
        logging.error(f"[Skill: deepread-ocr] OCR提取失败: {e}")
        return None


# ============================================================
# [Skill: gemini-deep-research] 深度研究功能
# ============================================================

async def deep_research(topic: str, chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> str:
    """使用Gemini进行简化版深度研究
    Args:
        topic: 研究主题
        chat_id: Telegram聊天ID（用于发送进度）
        context: Bot上下文
    Returns:
        Markdown格式的研究报告
    """
    if not GEMINI_API_KEY:
        return None
    
    try:
        # 步骤1：将主题分解为子问题
        await context.bot.send_message(chat_id, "...开始研究了，等一下。")
        
        decompose_prompt = f"""请将以下研究主题分解为3-5个具体的子问题，每个子问题应该覆盖主题的不同方面。
只输出子问题列表，每行一个，不要加序号或其他格式。

研究主题：{topic}"""
        
        sub_questions = await call_gemini(decompose_prompt)
        if not sub_questions:
            return None
        
        questions = [q.strip() for q in sub_questions.strip().split("\n") if q.strip()]
        if not questions:
            return None
        
        # 步骤2：对每个子问题进行研究
        all_findings = []
        for i, question in enumerate(questions):
            await context.bot.send_message(chat_id, f"...正在研究第{i+1}/{len(questions)}个问题...")
            
            # 先尝试联网搜索
            search_result = await web_search(question)
            
            # 构建搜索参考（避免f-string中的反斜杠问题）
            search_ref = ""
            if search_result:
                search_ref = f"参考搜索结果：\n{search_result}\n\n"
            
            research_prompt = f"""研究问题：{question}

{search_ref}
请对这个问题进行详细分析，包括：
1. 核心事实和关键信息
2. 不同观点和角度
3. 重要数据或案例

用简洁的段落回答，每段不超过3句话。"""
            
            finding = await call_gemini(research_prompt)
            if finding:
                all_findings.append(f"### {question}\n\n{finding}")
            
            # 避免API限流
            await asyncio.sleep(1)
        
        if not all_findings:
            return None
        
        # 步骤3：综合生成报告
        await context.bot.send_message(chat_id, "...正在整理报告...")
        
        synthesis_prompt = f"""请根据以下研究结果，生成一份关于「{topic}」的综合研究报告。

研究结果：
{chr(10).join(all_findings)}

报告格式要求（Markdown）：
# {topic} - 研究报告

## 摘要
（200字以内的核心发现总结）

## 详细分析
（按子问题组织，每个子问题一个小节）

## 结论
（关键发现和洞察）

## 延伸阅读建议
（3-5个相关搜索关键词）"""
        
        report = await call_gemini(synthesis_prompt)
        return report
        
    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] 深度研究失败: {e}")
        return None


# ============================================================
# [Skill: relay-for-telegram] Telegram消息历史搜索
# ============================================================

async def search_relay_messages(query: str, limit: int = 10) -> str:
    """通过Relay API搜索Telegram消息历史
    Args:
        query: 搜索关键词
        limit: 最大结果数
    Returns:
        搜索结果文本或错误信息
    """
    if not RELAY_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/search",
                params={"q": query, "limit": limit},
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 搜索API返回 {response.status_code}")
                return f"搜索失败（HTTP {response.status_code}）"
            
            data = response.json()
            results = data.get("results", [])
            if not results:
                return f"没有找到与「{query}」相关的消息。"
            
            # 格式化搜索结果
            output_lines = [f"找到 {len(results)} 条相关消息：\n"]
            for i, msg in enumerate(results[:limit]):
                chat_name = msg.get("chatName", "未知聊天")
                sender = msg.get("senderName", "未知")
                content = msg.get("content", "")[:100]
                date = msg.get("messageDate", "")[:10]
                output_lines.append(f"{i+1}. [{chat_name}] {sender} ({date})\n   {content}\n")
            
            return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] 搜索失败: {e}")
        return f"搜索出错：{e}"


async def list_relay_chats() -> str:
    """通过Relay API列出同步的聊天列表
    Returns:
        聊天列表文本或错误信息
    """
    if not RELAY_API_KEY:
        return None
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://relayfortelegram.com/api/v1/chats",
                headers={"Authorization": f"Bearer {RELAY_API_KEY}"},
            )
            if response.status_code != 200:
                logging.warning(f"[Skill: relay-for-telegram] 聊天列表API返回 {response.status_code}")
                return f"获取聊天列表失败（HTTP {response.status_code}）"
            
            data = response.json()
            chats = data.get("chats", [])
            if not chats:
                return "没有已同步的聊天。请先在 relayfortelegram.com 同步你的聊天。"
            
            output_lines = [f"已同步 {len(chats)} 个聊天：\n"]
            for i, chat in enumerate(chats):
                name = chat.get("name", "未知")
                chat_type = chat.get("type", "")
                members = chat.get("memberCount", "")
                last_msg = chat.get("lastMessageDate", "")[:10]
                unread = chat.get("unreadCount", 0)
                type_icon = {"group": "👥", "private": "👤", "channel": "📢", "supergroup": "👥"}.get(chat_type, "💬")
                info = f"{name}"
                if members:
                    info += f" ({members}人)"
                if unread:
                    info += f" [{unread}条未读]"
                output_lines.append(f"{i+1}. {type_icon} {info} (最后消息: {last_msg})")
            
            return "\n".join(output_lines)
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] 获取聊天列表失败: {e}")
        return f"获取聊天列表出错：{e}"


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
        
        parts = [f"...收到了。\n\n"]
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
            fake_update = type('obj', (object,), {
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
            reply = await call_ai(f"用户选择了选项 {opt_id}", history)
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
            await help_cmd(update, context)
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
    _last_user_active_time[chat_id] = datetime.now(KR_TZ)
    
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
    reply = await call_ai(user_text, history, emotion=emotion)
    
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
    timestamp = datetime.now(KR_TZ).isoformat()
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
        asyncio.create_task(summarize_and_save_memory(chat_id))
    
    # 发送回复 + 附加内容
    if want_selfie:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        saved = get_saved_selfies()
        if saved:
            selfie_caption = await call_ai("学长看到了我的自拍，用一句话害羞地回应，不超过10个字")
        else:
            selfie_caption = random.choice(SELFIE_CAPTIONS)
        await send_selfie_to_chat(update.get_bot(), chat_id, selfie_caption)
    elif want_scene:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        scene_url = generate_scene_url(scene)
        if scene_url:
            caption = await call_ai(f"学长让我给他看{scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{scene}的照片] {caption}")
    elif want_show:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        random_scene = random.choice(list(SCENE_PROMPTS.keys()))
        scene_url = generate_scene_url(random_scene)
        if scene_url:
            caption = await call_ai(f"学长让我给他看{random_scene}的照片，用一句话回应，不超过15个字")
            await update.message.reply_photo(photo=scene_url, caption=caption)
            append_bot_message(chat_id, f"[发送了一张{random_scene}的照片] {caption}")
    elif want_sticker and sticker_mood:
        await update.message.reply_text(reply_text)
        await asyncio.sleep(1)
        sticker_url = generate_sticker_url(sticker_mood)
        if sticker_url:
            caption = await call_ai(f"用一句话配合'{sticker_mood}'的表情，不超过10个字")
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
                    except:
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
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = []
            for opt in options:
                effect_text = ""
                if opt.get('effects'):
                    parts = []
                    if opt['effects'].get('affection'):
                        parts.append(f"❤️{'+' if opt['effects']['affection'] > 0 else ''}{opt['effects']['affection']}")
                    if opt['effects'].get('happiness'):
                        parts.append(f"✨{'+' if opt['effects']['happiness'] > 0 else ''}{opt['effects']['happiness']}")
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
            except:
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

# [Skill: LightRAG] 小说知识查询
async def novel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询小说知识"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取查询内容
    query = update.message.text.replace('/novel', '').replace('/小说', '').strip()
    if not query:
        await update.message.reply_text("...想问什么？（比如：/novel 车如云的奶奶是谁）")
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        # 查询知识库
        result = await query_novel(query)
        
        # 车如云风格的回应
        if result and len(result) > 10:
            # 让 AI 用车如云的口吻转述
            prompt = f"用户问：{query}\n\n小说中的相关内容：\n{result}\n\n请用车如云的口吻（极简、省略号、外冷内热）简短回答，不超过50个字。"
            response = await call_ai(prompt)
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("...小说里好像没有这个。")
            
    except Exception as e:
        logging.error(f"[Novel] 查询失败: {e}")
        await update.message.reply_text("...（查询失败）知识库还没准备好。")

# [Skill: ChromaDB] 记忆搜索
async def memory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索记忆"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    # 获取查询内容
    query = update.message.text.replace('/memory', '').replace('/记忆', '').strip()
    if not query:
        await update.message.reply_text("...想找什么记忆？（比如：/memory 我们聊过跑步吗）")
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

async def scheduler(app):
    while True:
        now = datetime.now(KR_TZ)
        
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
# HTTP健康检查 + Web界面 API
# ============================================================

# Web聊天历史（独立于Telegram）- 已废弃，改用共享聊天记录
# web_chat_history = []

async def health_check(request):
    return web.Response(text="🟢 车如云在线 v3.2")

async def serve_index(request):
    """提供Web界面HTML"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'templates', 'index.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Web界面文件未找到", status=404)

async def api_chat(request):
    """Web 端聊天 API - 与 Telegram 双向同步"""
    try:
        data = await request.json()
        user_message = data.get('message', '')
        
        if not user_message.strip():
            return web.json_response({'error': '消息不能为空'})
        
        # 获取用户ID（优先使用 session token）
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)  # 兼容旧 token
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 使用共享的聊天记录
        history = load_chat_history(user_id)
        
        # 调用 AI（call_ai 内部已使用角色系统提示词）
        response = await call_ai(user_message, history)
        
        # 保存到共享历史（带时间戳）
        timestamp = datetime.now(KR_TZ).isoformat()
        history.append({"role": "user", "content": user_message, "timestamp": timestamp})
        history.append({"role": "assistant", "content": response, "timestamp": timestamp})
        save_chat_history(user_id, history)
        
        # [双向同步] 如果配置了 Telegram Bot，将用户消息和回复都发送到Telegram
        try:
            if TELEGRAM_TOKEN and user_id and user_id == YOUR_CHAT_ID:
                import telegram
                from telegram.request import HTTPXRequest
                
                # 异步发送消息到 Telegram（不等待结果）
                async def send_to_telegram():
                    try:
                        bot = telegram.Bot(token=TELEGRAM_TOKEN, request=HTTPXRequest())
                        # 先发送用户消息（标注来自Web）
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🌐 [Web] {user_message}"
                        )
                        # 再发送AI回复
                        await bot.send_message(
                            chat_id=user_id,
                            text=response
                        )
                        logging.info(f"[双向同步] 消息已发送到 Telegram: {user_id}")
                    except Exception as e:
                        logging.error(f"[双向同步] 发送到 Telegram 失败: {e}")
                
                # 后台发送，不阻塞响应
                asyncio.create_task(send_to_telegram())
        except Exception as e:
            logging.error(f"[双向同步] 初始化发送失败: {e}")
        
        return web.json_response({'response': response})
    except Exception as e:
        logging.error(f"[WebChat] 错误: {e}")
        return web.json_response({'error': str(e)})

async def api_stats(request):
    """仪表盘数据API端点"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        stats = load_stats(user_id)
        stats["memories_count"] = len(load_json(get_user_memory_file(user_id), []))
        
        # 分析对话
        analysis = analyze_dialogue_patterns(YOUR_CHAT_ID) if YOUR_CHAT_ID else {}
        
        # 亲密度
        intimacy = calculate_intimacy(stats)
        
        # 情绪分布
        emotions = analysis.get("用户情绪分布", {})
        
        # 建议列表
        advice_str = get_relationship_advice(analysis)
        advice_list = [line.strip() for line in advice_str.split('\n') if line.strip()]
        
        return web.json_response({
            'total_messages': stats.get('total_messages', 0),
            'total_days': stats.get('total_days', 0),
            'today_count': stats.get('today_count', 0),
            'memory_count': stats.get('memories_count', 0),
            'caring_count': analysis.get('关心表达次数', 0) if isinstance(analysis.get('关心表达次数'), int) else 0,
            'jealous_count': analysis.get('吃醋次数', 0) if isinstance(analysis.get('吃醋次数'), int) else 0,
            'warm_count': analysis.get('温暖表达次数', 0) if isinstance(analysis.get('温暖表达次数'), int) else 0,
            'intimacy_score': intimacy['score'],
            'intimacy_level': intimacy['level'],
            'emotions': emotions,
            'user_avg_len': analysis.get('用户平均消息长度', '--'),
            'bot_avg_len': analysis.get('车如云平均回复长度', '--'),
            'user_initiative': analysis.get('用户主动发起比例', '--'),
            'avg_daily': analysis.get('日均消息数', '--'),
            'bot_ellipsis': analysis.get('车如云使用省略号', '--'),
            'bot_inner': analysis.get('车如云内心独白', '--'),
            'advice': advice_list,
            'selfie_count': get_selfie_count(),
            'user_photo_count': len([f for f in os.listdir(USER_PHOTOS_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]) if os.path.exists(USER_PHOTOS_DIR) else 0,
        })
    except Exception as e:
        logging.error(f"仪表盘API错误: {e}")
        return web.json_response({'error': str(e)})

# ============================================================
# Telegram Mini App API
# ============================================================

async def serve_miniapp(request):
    """提供Telegram Mini App HTML（新版模块化）"""
    try:
        # 优先使用配置的 public_url，否则从请求中获取
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
            logging.info(f"[MiniApp] 使用配置的 public_url: {api_base}")
        else:
            # 自动检测当前 URL
            host = request.host
            scheme = request.scheme
            # 如果是 Cloudflare Tunnel，使用 https
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"
            logging.info(f"[MiniApp] 自动检测 API_BASE: {api_base}")

        # 使用新版模块化 Mini App
        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'static', 'miniapp', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE（替换占位符）
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[MiniApp] 服务新版 Mini App, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        logging.warning("[MiniApp] 新版文件未找到，回退到旧版")
        # 回退到旧版
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            template_path = os.path.join(script_dir, 'templates', 'miniapp.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            config = load_config()
            public_url = config.get('public_url', '').strip()
            if public_url:
                api_base = public_url.rstrip('/')
            else:
                host = request.host
                scheme = request.scheme
                if 'trycloudflare.com' in host or 'ngrok' in host:
                    scheme = 'https'
                api_base = f"{scheme}://{host}"
            html = html.replace(
                'const API_BASE = window.location.origin;',
                f'const API_BASE = "{api_base}";'
            )
            return web.Response(text=html, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Mini App文件未找到", status=404)

async def serve_game(request):
    """提供独立游戏网站 HTML"""
    try:
        # 检测 API_BASE
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
        else:
            host = request.host
            scheme = request.scheme
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"

        script_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(script_dir, 'static', 'game', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[Game] 服务游戏网站, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="游戏文件未找到", status=404)
    except Exception as e:
        logging.error(f"[Game] 服务游戏网站失败: {e}")
        return web.Response(text=f"游戏加载失败: {e}", status=500)


async def api_upload_selfies(request):
    """Mini App上传自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        data = await request.json()
        photos = data.get('photos', [])
        character_id = data.get('character_id')
        
        if not photos:
            return web.json_response({'success': False, 'error': '没有照片'})
        
        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        uploaded = []
        for photo_data in photos:
            try:
                # 解析base64图片
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]
                
                img_bytes = base64.b64decode(photo_data)
                
                # 验证并打开图片
                img = Image.open(io.BytesIO(img_bytes))
                
                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"selfie_{timestamp}_{len(uploaded)}.jpg"
                filepath = os.path.join(user_selfie_dir, filename)
                
                # 保存为 JPEG（兼容所有格式）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(filepath, 'JPEG', quality=90)
                uploaded.append(filename)
                
            except Exception as e:
                logging.error(f"处理上传照片失败: {e}")
                continue
        
        return web.json_response({
            'success': True,
            'uploaded': uploaded,
            'count': len(uploaded)
        })
    except Exception as e:
        logging.error(f"上传自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_get_selfies(request):
    """Mini App获取自拍列表API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        character_id = request.query.get('character_id')
        
        selfies = []
        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        if os.path.exists(user_selfie_dir):
            for f in sorted(os.listdir(user_selfie_dir), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    filepath = os.path.join(user_selfie_dir, f)
                    stat = os.stat(filepath)
                    selfies.append({
                        'filename': f,
                        'url': f'/uploads/selfies/{f}',
                        'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                        'size': stat.st_size
                    })
        
        return web.json_response({
            'success': True,
            'selfies': selfies,
            'count': len(selfies)
        })
    except Exception as e:
        logging.error(f"获取自拍列表API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_delete_selfie(request):
    """Mini App删除自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        data = await request.json()
        filename = data.get('filename', '')
        character_id = data.get('character_id')
        
        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})
        
        filepath = os.path.join(get_user_selfie_dir(user_id, character_id), filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_delete_user_photo(request):
    """Mini App删除用户照片API"""
    try:
        data = await request.json()
        filename = data.get('filename', '')
        
        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})
        
        filepath = os.path.join(USER_PHOTOS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_user_photos(request):
    """Mini App获取用户照片列表API"""
    try:
        photos = []
        if os.path.exists(USER_PHOTOS_DIR):
            for f in sorted(os.listdir(USER_PHOTOS_DIR), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    photos.append({
                        'filename': f,
                        'url': f'/files/user_photos/{f}'
                    })
        return web.json_response({'success': True, 'photos': photos, 'count': len(photos)})
    except Exception as e:
        logging.error(f"获取用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def serve_uploaded_file(request):
    """提供上传的文件"""
    try:
        folder = request.match_info.get('folder', '')
        filename = request.match_info.get('filename', '')
        
        if '..' in filename or '/' in filename:
            return web.Response(status=403)
        
        if folder == 'selfies':
            # 在所有用户目录中查找自拍文件（包括角色子目录）
            filepath = None
            if os.path.exists(DATA_DIR):
                for entry in os.listdir(DATA_DIR):
                    if entry.startswith("user_"):
                        user_dir = os.path.join(DATA_DIR, entry, "selfies")
                        if os.path.isdir(user_dir):
                            # 先检查直接路径
                            candidate = os.path.join(user_dir, filename)
                            if os.path.exists(candidate):
                                filepath = candidate
                                break
                            # 再检查角色子目录
                            for sub in os.listdir(user_dir):
                                sub_path = os.path.join(user_dir, sub)
                                if os.path.isdir(sub_path):
                                    candidate = os.path.join(sub_path, filename)
                                    if os.path.exists(candidate):
                                        filepath = candidate
                                        break
                            if filepath:
                                break
            if not filepath:
                # 回退到旧的全局目录
                filepath = os.path.join(SELFIE_DIR, filename)
        elif folder == 'user_photos':
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
        else:
            return web.Response(status=404)
        
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content = f.read()
            
            # 确定content type
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'
            
            return web.Response(body=content, content_type=content_type)
        else:
            return web.Response(status=404)
    except Exception as e:
        logging.error(f"提供文件错误: {e}")
        return web.Response(status=500)

async def api_analyze_chatlog(request):
    """Mini App聊天记录分析API"""
    try:
        data = await request.json()
        content = data.get('content', '')
        partner = data.get('partner', '对方')
        
        if not content:
            return web.json_response({'success': False, 'error': '没有内容'})
        
        # 解析聊天记录
        parsed = parse_wechat_chatlog(content)
        
        if parsed['total_count'] == 0:
            return web.json_response({'success': False, 'error': '未能解析出消息，请检查格式'})
        
        # AI分析
        analysis_result = await analyze_chatlog_with_ai(parsed, partner)
        
        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})
        
        # 保存分析结果
        save_chat_analysis(partner, analysis_result)
        
        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'message_count': analysis_result['message_count'],
            'date_range': analysis_result['date_range']
        })
        
    except Exception as e:
        logging.error(f"Mini App聊天记录分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_analyze_video(request):
    """Mini App视频分析API"""
    try:
        reader = await request.multipart()
        video_type = "剧情"
        video_path = None
        
        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == 'type':
                video_type = (await part.text()).strip()
            elif part.name == 'video':
                filename = part.filename or f"video_{datetime.now(KR_TZ).strftime('%Y%m%d_%H%M%S')}.mp4"
                video_path = os.path.join(VIDEO_DIR, filename)
                with open(video_path, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)
        
        if not video_path or not os.path.exists(video_path):
            return web.json_response({'success': False, 'error': '视频上传失败'})
        
        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            return web.json_response({'success': False, 'error': '音频提取失败，请确认ffmpeg已安装'})
        
        # 语音转文字（优先使用Google Speech Recognition）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)
        
        # 清理音频
        if os.path.exists(audio_path):
            os.remove(audio_path)
        
        if not transcript:
            return web.json_response({'success': False, 'error': '语音识别失败'})
        
        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)
        
        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})
        
        # 保存结果
        save_video_analysis(video_type, analysis_result)
        
        # 清理视频文件
        if os.path.exists(video_path):
            os.remove(video_path)
        
        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'transcript_length': len(transcript)
        })
        
    except Exception as e:
        logging.error(f"Mini App视频分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_register(request):
    """用户注册API"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        chat_id = data.get('chat_id', '').strip()
        
        # 验证必填字段
        if not username or not password or not chat_id:
            return web.json_response({'success': False, 'error': '用户名、密码和Chat ID不能为空'})
        
        # 验证 chat_id 是否为数字
        try:
            int(chat_id)
        except ValueError:
            return web.json_response({'success': False, 'error': 'Chat ID 必须是数字'})
        
        # 验证密码长度
        if len(password) < 6:
            return web.json_response({'success': False, 'error': '密码长度至少6位'})
        
        # 注册用户
        success, message = register_user(username, password, chat_id)
        
        if success:
            # 注册成功后自动登录
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True, 
                'message': message,
                'token': token,
                'user_id': int(chat_id),
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': message})
            
    except Exception as e:
        logging.error(f"[API注册] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_login(request):
    """Mini App登录API - 新用户系统"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return web.json_response({'success': False, 'error': '用户名和密码不能为空'})
        
        # 验证用户
        success, chat_id = validate_user(username, password)
        
        if success and chat_id:
            user_id = int(chat_id)
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True, 
                'token': token, 
                'user_id': user_id,
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': '用户名或密码错误'})
            
    except Exception as e:
        logging.error(f"[API登录] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})

async def api_get_config(request):
    """Mini App获取配置API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        config = load_config()
        # 不返回完整密钥，只返回部分
        safe_config = {
            'telegram_token': config.get('telegram_token', '')[:10] + '***' if config.get('telegram_token') else '',
            'chat_id': config.get('chat_id', ''),
            'ai_api_key': config.get('ai_api_key', '')[:15] + '***' if config.get('ai_api_key') else '',
            'ai_api_base': config.get('ai_api_base', ''),
            'admin_username': config.get('admin_username', ''),
            'public_url': config.get('public_url', ''),
        }
        return web.json_response({'success': True, 'config': safe_config})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})

async def api_update_config(request):
    """Mini App更新配置API - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可修改配置'})
        
        data = await request.json()
        config = load_config()
        
        # 允许更新的字段
        updatable = ['telegram_token', 'chat_id', 'ai_api_key', 'ai_api_base', 'admin_username', 'admin_password', 'public_url']
        updated = []
        
        for key in updatable:
            if key in data and data[key]:
                config[key] = data[key]
                updated.append(key)
        
        save_config(config)
        
        # 如果更新了关键配置，重新加载全局变量
        global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_KEY, AI_API_BASE
        if 'telegram_token' in updated:
            TELEGRAM_TOKEN = config.get('telegram_token', '')
        if 'chat_id' in updated:
            YOUR_CHAT_ID = int(config.get('chat_id', '0'))
        if 'ai_api_key' in updated:
            AI_API_KEY = config.get('ai_api_key', '')
        if 'ai_api_base' in updated:
            AI_API_BASE = config.get('ai_api_base', '')
        
        return web.json_response({'success': True, 'updated': updated, 'message': f'已更新: {", ".join(updated)}'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})

# ============================================================
# [Skill: skills-manager] Skills 管理功能
# ============================================================

# Skills 状态持久化文件路径
SKILLS_STATE_FILE = os.path.join(DATA_DIR, "skills_state.json")

# Skills 注册表：记录所有已集成的 skills
SKILLS_REGISTRY = {
    "humanize-ai-text": {"name": "AI文本人性化", "desc": "让回复更像真人，去除机械感", "enabled": True, "category": "对话优化"},
    "self-improving": {"name": "自我改进", "desc": "从用户纠正中学习", "enabled": True, "category": "学习"},
    "proactive-agent": {"name": "主动行为", "desc": "主动发起对话", "enabled": True, "category": "行为"},
    "semantic-memory": {"name": "语义记忆", "desc": "长期语义记忆系统", "enabled": True, "category": "记忆"},
    "claw-summarize-pro": {"name": "摘要生成", "desc": "文本/URL摘要", "enabled": True, "category": "工具"},
    "auto-updater": {"name": "自动更新", "desc": "代码变更检测", "enabled": True, "category": "运维"},
    "agent-orchestration": {"name": "Prompt架构", "desc": "5层Prompt工程", "enabled": True, "category": "核心"},
    "gemini": {"name": "Gemini API", "desc": "Google Gemini集成", "enabled": True, "category": "AI"},
    "vision-sandbox": {"name": "图片分析", "desc": "Gemini图片深度分析", "enabled": True, "category": "AI"},
    "deepread-ocr": {"name": "文档OCR", "desc": "文档文字识别", "enabled": True, "category": "工具"},
    "gemini-deep-research": {"name": "深度研究", "desc": "复杂研究任务", "enabled": True, "category": "工具"},
    "relay-for-telegram": {"name": "消息历史", "desc": "Telegram消息搜索", "enabled": True, "category": "工具"},
    "tts": {"name": "语音合成", "desc": "TTS语音回复(Edge/SoVITS/Fish)", "enabled": True, "category": "工具"},
    "chromadb-memory": {"name": "ChromaDB记忆", "desc": "向量数据库记忆(语义搜索)", "enabled": True, "category": "记忆"},
    "lightrag": {"name": "知识库", "desc": "原作小说知识查询", "enabled": True, "category": "知识"},
}

# 每角色技能禁用列表: {character_id: {skill_id: True}}
CHARACTER_SKILL_OVERRIDES = {}

def load_character_skill_overrides():
    """加载角色技能覆盖配置"""
    global CHARACTER_SKILL_OVERRIDES
    f = os.path.join(DATA_DIR, "character_skill_overrides.json")
    CHARACTER_SKILL_OVERRIDES = load_json(f, {})

def save_character_skill_overrides():
    """保存角色技能覆盖配置"""
    f = os.path.join(DATA_DIR, "character_skill_overrides.json")
    save_json(f, CHARACTER_SKILL_OVERRIDES)

def is_skill_enabled_for_character(skill_id, character_id=None):
    """检查技能对特定角色是否启用"""
    if not character_id:
        character = get_current_character()
        character_id = character.config.id if character else None
    if not character_id:
        return SKILLS_REGISTRY.get(skill_id, {}).get('enabled', True)
    
    # 检查角色覆盖
    overrides = CHARACTER_SKILL_OVERRIDES.get(character_id, {})
    if skill_id in overrides:
        return not overrides[skill_id]  # True in overrides means disabled
    
    # 默认使用技能全局设置
    return SKILLS_REGISTRY.get(skill_id, {}).get('enabled', True)

def set_skill_for_character(skill_id, character_id, enabled):
    """设置技能对特定角色的启用状态"""
    if character_id not in CHARACTER_SKILL_OVERRIDES:
        CHARACTER_SKILL_OVERRIDES[character_id] = {}
    CHARACTER_SKILL_OVERRIDES[character_id][skill_id] = not enabled  # True = disabled
    save_character_skill_overrides()


def _load_skills_state():
    """从文件加载 skills 状态，覆盖默认 enabled 值"""
    global SKILLS_REGISTRY
    try:
        if os.path.exists(SKILLS_STATE_FILE):
            with open(SKILLS_STATE_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            for skill_id, state in saved.items():
                if skill_id in SKILLS_REGISTRY:
                    SKILLS_REGISTRY[skill_id]["enabled"] = state.get("enabled", SKILLS_REGISTRY[skill_id]["enabled"])
                else:
                    # 文件中有但注册表中没有的 skill，也加载进来（可能是之前安装的）
                    SKILLS_REGISTRY[skill_id] = state
            logging.info(f"[skills-manager] 已从 {SKILLS_STATE_FILE} 加载 skills 状态")
    except Exception as e:
        logging.warning(f"[skills-manager] 加载 skills 状态失败: {e}")


def _save_skills_state():
    """将当前 skills 状态保存到文件"""
    try:
        os.makedirs(os.path.dirname(SKILLS_STATE_FILE), exist_ok=True)
        state = {}
        for skill_id, info in SKILLS_REGISTRY.items():
            state[skill_id] = {
                "name": info.get("name", ""),
                "desc": info.get("desc", ""),
                "enabled": info.get("enabled", False),
                "category": info.get("category", ""),
            }
        with open(SKILLS_STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        logging.info(f"[skills-manager] skills 状态已保存到 {SKILLS_STATE_FILE}")
    except Exception as e:
        logging.warning(f"[skills-manager] 保存 skills 状态失败: {e}")


async def api_skills_list(request):
    """[Skill: skills-manager] 获取所有 skills 列表"""
    try:
        character_id = request.query.get('character_id')
        
        skills_list = []
        for sid, sdata in SKILLS_REGISTRY.items():
            enabled = is_skill_enabled_for_character(sid, character_id)
            skills_list.append({
                "id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("desc", ""),
                "desc": sdata.get("desc", ""),
                "enabled": enabled,
                "category": sdata.get("category", "其他"),
                "version": sdata.get("version", "1.0"),
            })
        
        return web.json_response({'success': True, 'skills': skills_list})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_toggle(request):
    """[Skill: skills-manager] 启用/禁用 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可管理技能'})
        
        data = await request.json()
        skill_id = data.get('skill_id', '')
        enabled = data.get('enabled', True)
        character_id = data.get('character_id')
        
        if character_id:
            set_skill_for_character(skill_id, character_id, enabled)
        else:
            # Global toggle
            if skill_id in SKILLS_REGISTRY:
                SKILLS_REGISTRY[skill_id]['enabled'] = enabled
                _save_skills_state()
        
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_install(request):
    """[Skill: skills-manager] 安装新 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可安装技能'})
        
        data = await request.json()
        skill_name = data.get('skill_name', '').strip()

        if not skill_name:
            return web.json_response({'success': False, 'error': '缺少 skill_name 参数'})

        # 执行 clawhub install
        logging.info(f"[skills-manager] 正在安装 skill: {skill_name}")
        result = subprocess.run(
            ["clawhub", "install", skill_name, "--force"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "安装失败（未知错误）"
            logging.warning(f"[skills-manager] 安装 skill '{skill_name}' 失败: {error_msg}")
            return web.json_response({
                'success': False,
                'error': f'安装失败: {error_msg}',
            })

        # 安装成功，尝试读取 SKILL.md 提取描述
        desc = ""
        skill_md_path = f"/workspace/skills/{skill_name}/SKILL.md"
        try:
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 从前几行提取描述信息
                for line in lines[:20]:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        desc = line[:200]  # 取前200字符作为描述
                        break
        except Exception:
            pass

        # 添加到 SKILLS_REGISTRY
        SKILLS_REGISTRY[skill_name] = {
            "name": skill_name,
            "desc": desc or f"通过 clawhub 安装的 skill: {skill_name}",
            "enabled": True,
            "category": "自定义",
        }
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_name}' 安装成功")
        return web.json_response({
            'success': True,
            'skill_id': skill_name,
            'desc': desc,
            'message': f'Skill "{skill_name}" 安装成功',
        })
    except subprocess.TimeoutExpired:
        return web.json_response({'success': False, 'error': '安装超时（60秒）'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_uninstall(request):
    """[Skill: skills-manager] 卸载 skill（从注册表移除，不删除代码）"""
    try:
        data = await request.json()
        skill_id = data.get('skill_id', '')

        if not skill_id:
            return web.json_response({'success': False, 'error': '缺少 skill_id 参数'})

        if skill_id not in SKILLS_REGISTRY:
            return web.json_response({'success': False, 'error': f'Skill "{skill_id}" 不存在'})

        # 从注册表移除（不删除代码文件）
        removed = SKILLS_REGISTRY.pop(skill_id)
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_id}' 已从注册表移除（代码未删除）")
        return web.json_response({
            'success': True,
            'skill_id': skill_id,
            'removed': removed,
            'message': f'Skill "{skill_id}" 已卸载（代码文件保留）',
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_quota_status(request):
    """额度监控 API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        usage = load_quota_usage()
        status = check_quota_status(usage)
        month = get_current_month()

        items = [
            {
                'name': 'API 请求',
                'icon': '📡',
                'used': usage.get('requests', 0),
                'limit': QUOTA_LIMITS['requests'],
                'unit': '次',
                'color': '#8E24AA',
            },
            {
                'name': 'CPU 用量',
                'icon': '⚡',
                'used': round(usage.get('cpu_seconds', 0), 1),
                'limit': QUOTA_LIMITS['cpu_seconds'],
                'unit': '秒',
                'color': '#2a5290',
            },
            {
                'name': '内存用量',
                'icon': '🧠',
                'used': round(usage.get('memory_gib_seconds', 0), 1),
                'limit': QUOTA_LIMITS['memory_gib_seconds'],
                'unit': 'GiB·s',
                'color': '#6CD9A8',
            },
            {
                'name': '网络流量',
                'icon': '🌐',
                'used': round(usage.get('network_gb', 0), 3),
                'limit': QUOTA_LIMITS['network_gb'],
                'unit': 'GB',
                'color': '#F4A4A4',
            },
        ]

        # 计算各项百分比
        for item in items:
            item['percent'] = round(min(item['used'] / item['limit'] * 100, 100), 1) if item['limit'] > 0 else 0

        # AI 请求统计
        ai_requests = usage.get('ai_requests', 0)
        image_gens = usage.get('image_generations', 0)

        return web.json_response({
            'success': True,
            'status': status,
            'month': month,
            'items': items,
            'ai_requests': ai_requests,
            'image_generations': image_gens,
            'shutdown': usage.get('shutdown_triggered', False),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_list_characters(request):
    """列出所有可用角色"""
    try:
        characters = list_characters()
        current = get_current_character()
        return web.json_response({
            'success': True,
            'characters': characters,
            'current': current.config.id if current else None,
            'count': len(characters),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_switch_character(request):
    """切换当前角色"""
    try:
        data = await request.json()
        character_id = data.get('character_id', '')
        
        if not character_id:
            return web.json_response({'success': False, 'error': '缺少 character_id 参数'})
        
        if set_current_character(character_id):
            character = get_current_character()
            return web.json_response({
                'success': True,
                'character': character.to_dict() if character else None,
                'message': f'已切换到角色: {character.config.name if character else character_id}',
            })
        else:
            return web.json_response({'success': False, 'error': f'角色 "{character_id}" 不存在'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


# 启动时加载 skills 持久化状态
_load_skills_state()
load_character_skill_overrides()

# CORS 中间件 - 允许 Telegram Mini App 跨域访问
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# API 认证令牌
API_TOKENS = {}  # {token: {"user_id": xxx, "created": timestamp}}

def generate_api_token(user_id):
    """生成 API 认证令牌"""
    import time
    token = hashlib.sha256(f"{user_id}:{time.time()}:{os.urandom(16)}".encode()).hexdigest()[:32]
    API_TOKENS[token] = {"user_id": user_id, "created": time.time()}
    return token

def validate_api_token(request):
    """验证 API 令牌，返回 user_id 或 None"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        if token in API_TOKENS:
            return API_TOKENS[token]["user_id"]
    return None

# ============================================================
# HTTP Bridge for SOLO Sandbox File Transfer
# ============================================================
import base64
from datetime import datetime

# 存储待处理的命令和文件
bridge_pending_commands = []
bridge_uploaded_files = {}

async def bridge_vm_poll(request):
    """VM 轮询端点 - VM 定期调用获取命令"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id')
        auth_token = data.get('token')

        if auth_token != 'nxsiran_bridge_2024':
            return web.json_response({'error': 'auth failed'}, status=401)

        # 获取 VM 上传的文件（如果有）
        files = data.get('files', [])
        for file_info in files:
            filename = file_info.get('filename')
            content = base64.b64decode(file_info.get('content'))
            filepath = f"/tmp/vm_uploads/{vm_id}_{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(content)
            bridge_uploaded_files[filename] = filepath
            logging.info(f"[Bridge] Received from {vm_id}: {filename}")

        # 返回待执行的命令
        global bridge_pending_commands
        commands_to_execute = []
        for cmd in bridge_pending_commands:
            if cmd.get('vm_id') == vm_id or cmd.get('vm_id') == '*':
                commands_to_execute.append(cmd)
        bridge_pending_commands = [cmd for cmd in bridge_pending_commands if cmd not in commands_to_execute]

        return web.json_response({
            'status': 'ok',
            'commands': commands_to_execute,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def bridge_vm_result(request):
    """VM 返回命令执行结果"""
    try:
        data = await request.json()
        logging.info(f"[Bridge] Result from {data.get('vm_id')}:")
        logging.info(f"  Command: {data.get('command')}")
        logging.info(f"  Return code: {data.get('returncode')}")
        if data.get('stdout'):
            logging.info(f"  STDOUT: {data.get('stdout')[:500]}")
        if data.get('stderr'):
            logging.info(f"  STDERR: {data.get('stderr')[:500]}")

        return web.json_response({'status': 'received'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

def setup_bridge_routes(app):
    """设置 bridge 路由"""
    app.router.add_post('/bridge/poll', bridge_vm_poll)
    app.router.add_post('/bridge/result', bridge_vm_result)
    app.router.add_post('/bridge/send', bridge_send_command)
    app.router.add_post('/bridge/upload', bridge_upload_file)
    logging.info("[Bridge] HTTP Bridge routes registered")

async def bridge_send_command(request):
    """从 SOLO 发送命令到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        command = data.get('command')
        
        bridge_pending_commands.append({
            'vm_id': vm_id,
            'command': command,
            'timestamp': datetime.now().isoformat()
        })
        
        return web.json_response({
            'status': 'command_queued',
            'vm_id': vm_id,
            'command': command
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def bridge_upload_file(request):
    """从 SOLO 发送文件到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        filename = data.get('filename')
        dest_path = data.get('dest_path', '/tmp/')
        content = data.get('content')  # base64 encoded
        
        bridge_pending_commands.append({
            'vm_id': vm_id,
            'type': 'file_download',
            'filename': filename,
            'dest_path': dest_path,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        
        return web.json_response({
            'status': 'file_queued',
            'vm_id': vm_id,
            'filename': filename
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

# ============================================================
# 消息同步 API（Web <-> Telegram 双向同步）
# ============================================================

async def api_messages_history(request):
    """获取聊天历史消息 - 用于Web端加载历史"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 获取limit参数
        limit = int(request.query.get('limit', 50))
        
        # 加载聊天历史
        history = load_chat_history(user_id)
        
        # 只返回最近的N条消息
        if len(history) > limit:
            history = history[-limit:]
        
        # 格式化返回
        messages = []
        for msg in history:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })
        
        return web.json_response({
            'messages': messages,
            'total_count': len(messages)
        })
    except Exception as e:
        logging.error(f"[消息历史] 获取失败: {e}")
        return web.json_response({'error': str(e)}, status=500)

async def api_messages_sync(request):
    """同步新消息 - Telegram新消息推送到Web端"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1
        
        # 获取since参数（从第几条消息开始）
        since = int(request.query.get('since', 0))
        
        # 加载聊天历史
        history = load_chat_history(user_id)
        total_count = len(history)
        
        # 只返回新增的消息
        if since >= total_count:
            return web.json_response({
                'messages': [],
                'total_count': total_count
            })
        
        new_messages = history[since:]
        
        # 格式化返回
        messages = []
        for msg in new_messages:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })
        
        return web.json_response({
            'messages': messages,
            'total_count': total_count
        })
    except Exception as e:
        logging.error(f"[消息同步] 同步失败: {e}")
        return web.json_response({'error': str(e)}, status=500)

# ============================================================
# Web Server
# ============================================================
async def web_server():
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get("/", serve_index)
    app.router.add_get("/health", health_check)
    app.router.add_post("/api/chat", api_chat)
    app.router.add_get("/api/stats", api_stats)
    # 消息同步API（Web <-> Telegram 双向同步）
    app.router.add_get("/api/messages/history", api_messages_history)
    app.router.add_get("/api/messages/sync", api_messages_sync)
    app.router.add_get("/miniapp", serve_miniapp)
    app.router.add_get("/game", serve_game)
    app.router.add_post("/api/upload-selfies", api_upload_selfies)
    app.router.add_get("/api/selfies", api_get_selfies)
    app.router.add_post("/api/delete-selfie", api_delete_selfie)
    app.router.add_post("/api/delete-user-photo", api_delete_user_photo)
    app.router.add_get("/api/user-photos", api_user_photos)
    app.router.add_get("/uploads/{folder}/{filename}", serve_uploaded_file)
    # 静态文件服务（游戏引擎等）
    app.router.add_static("/static", os.path.join(os.path.dirname(__file__), 'static'))
    app.router.add_post("/api/analyze-chatlog", api_analyze_chatlog)
    app.router.add_post("/api/analyze-video", api_analyze_video)
    app.router.add_post("/api/register", api_register)
    app.router.add_post("/api/login", api_login)
    app.router.add_get("/api/config", api_get_config)
    app.router.add_post("/api/config", api_update_config)
    # [Skill: skills-manager] Skills 管理 API 路由
    app.router.add_get("/api/skills", api_skills_list)
    app.router.add_post("/api/skills/toggle", api_skill_toggle)
    app.router.add_post("/api/skills/install", api_skill_install)
    app.router.add_post("/api/skills/uninstall", api_skill_uninstall)
    # 额度监控 API
    app.router.add_get("/api/quota", api_quota_status)
    # 角色系统 API
    app.router.add_get("/api/characters", api_list_characters)
    app.router.add_post("/api/characters/switch", api_switch_character)
    # 游戏系统 API
    from game_api import register_game_routes
    register_game_routes(app)
    # HTTP Bridge for SOLO sandbox file transfer
    setup_bridge_routes(app)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"HTTP服务器已启动，端口: {PORT}")
    logging.info(f"Web界面: http://localhost:{PORT}/")
    return runner

# ============================================================
# 主函数
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
# [Skill: gemini] /gemini 命令 - 直接使用Gemini回答
# ============================================================

async def gemini_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini直接回答问题"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...问什么。用法：/gemini <问题>")
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...Gemini没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    question = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        result = await call_gemini(question)
        if result:
            # 截断过长回复
            if len(result) > 4000:
                result = result[:4000] + "\n\n...太长了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...Gemini没有回复。再试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini] /gemini命令失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: vision-sandbox] /analyze_img 命令 - 图片深度分析
# ============================================================

# [Skill: vision-sandbox] 记录待分析的图片
_pending_analyze_img = {}  # chat_id -> image_data (base64)

async def analyze_img_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片发送 /analyze_img 进行深度分析"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...图片分析没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        # 如果没有回复图片，提示用户
        _pending_analyze_img[chat_id] = True
        await update.message.reply_text("...发一张图片过来，我来分析。")
        return
    
    # 直接分析回复的图片
    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
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
    except Exception as e:
        logging.error(f"[Skill: vision-sandbox] /analyze_img失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: deepread-ocr] /ocr 命令 - 文档OCR文字提取
# ============================================================

# [Skill: deepread-ocr] 记录待OCR的图片
_pending_ocr = {}  # chat_id -> True

async def ocr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """回复图片/文件发送 /ocr 提取文字"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...OCR没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    # 检查是否回复了一张图片
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        _pending_ocr[chat_id] = True
        await update.message.reply_text("...发一张图片或文档过来，我来提取文字。")
        return
    
    await update.message.chat.send_action("typing")
    try:
        photo = update.message.reply_to_message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        image_b64 = base64.b64encode(bytes(photo_bytes)).decode("utf-8")
        
        result = await ocr_document(image_b64)
        if result:
            if len(result) > 4000:
                # 分段发送长文本
                for i in range(0, len(result), 4000):
                    await update.message.reply_text(result[i:i+4000])
            else:
                await update.message.reply_text(result)
        else:
            await update.message.reply_text("...没识别出文字。图片太模糊或者没有文字。")
    except Exception as e:
        logging.error(f"[Skill: deepread-ocr] /ocr失败: {e}")
        await update.message.reply_text("...出错了。")


# ============================================================
# [Skill: gemini-deep-research] /research 命令 - 深度研究
# ============================================================

async def research_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """使用Gemini进行深度研究"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...研究什么。用法：/research <主题>")
        return
    
    if not GEMINI_API_KEY:
        await update.message.reply_text("...深度研究没配置。需要设置 GEMINI_API_KEY 环境变量。")
        return
    
    topic = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        report = await deep_research(topic, chat_id, context)
        if report:
            # 分段发送长报告
            if len(report) > 4000:
                for i in range(0, len(report), 4000):
                    await context.bot.send_message(chat_id, report[i:i+4000])
            else:
                await context.bot.send_message(chat_id, report)
        else:
            await context.bot.send_message(chat_id, "...研究失败了。换个主题试试。")
    except Exception as e:
        logging.error(f"[Skill: gemini-deep-research] /research失败: {e}")
        await context.bot.send_message(chat_id, "...出错了。")


# ============================================================
# [Skill: relay-for-telegram] /search_msg 和 /my_chats 命令
# ============================================================

async def search_msg_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """搜索Telegram消息历史"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not context.args:
        await update.message.reply_text("...搜什么。用法：/search_msg <关键词>")
        return
    
    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...消息搜索没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return
    
    query = " ".join(context.args)
    await update.message.chat.send_action("typing")
    
    try:
        result = await search_relay_messages(query)
        if result:
            if len(result) > 4000:
                result = result[:4000] + "\n\n...结果太多了，就这些。"
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...搜索失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /search_msg失败: {e}")
        await update.message.reply_text("...出错了。")


async def my_chats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """列出已同步的Telegram聊天"""
    chat_id = update.effective_chat.id
    if YOUR_CHAT_ID != 0 and chat_id != YOUR_CHAT_ID:
        return
    
    if not RELAY_API_KEY:
        await update.message.reply_text(
            "...聊天列表没配置。\n\n"
            "需要设置 RELAY_API_KEY 环境变量。\n"
            "获取方式：\n"
            "1. 访问 https://relayfortelegram.com\n"
            "2. 用Telegram手机号注册\n"
            "3. 获取API Key\n"
            "4. 设置环境变量 RELAY_API_KEY=rl_live_xxx"
        )
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        result = await list_relay_chats()
        if result:
            await update.message.reply_text(result)
        else:
            await update.message.reply_text("...获取失败了。")
    except Exception as e:
        logging.error(f"[Skill: relay-for-telegram] /my_chats失败: {e}")
        await update.message.reply_text("...出错了。")


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


def main():
    # 初始化配置（必须在其他操作之前）
    init_config()
    
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
    
    print("🚀 车如云 Telegram Bot v3.4 启动中...")
    print("📋 v3.4 Skill集成：")
    print("  [🧠 semantic-memory] 语义记忆系统（自动提取+搜索+删除）")
    print("  [📝 claw-summarize-pro] 摘要生成（文本/URL/回复消息）")
    print("  [🔄 auto-updater] 自动更新检查（启动检测+版本管理）")
    print("📋 v3.3 Google Cloud VM 新增：")
    print("  [🎤 语音消息] TTS韩语语音合成")
    print("  [🔔 主动消息] 早安/晚安/想你/关心/天气")
    print("  [📱 Mini App] 自拍上传+聊天记录导入")
    print("  [💬 微信导入] JSON/TXT双格式支持")
    print("  [💰 额度监控] 三级阈值自动断开")
    print("📋 v3.2 Skill整合：")
    print("  [notebooklm] 原作剧情知识注入AI系统提示词")
    print("  [brainstorming] 深度角色设定 + OOC防护机制")
    print("  [meeting-insights] /analyze 对话模式分析")
    print("  [slack-gif-creator] /sticker 表情包生成（8种表情）")
    print("📋 v3.0 功能：")
    print("  [情绪识别] [对话统计] [天气查询] [纪念日系统] [亲密度系统]")
    print("  [生活事件] [表情反应] [打字模拟] [增强记忆] [个性化主动]")
    
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
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("selfie", selfie_cmd))
    app.add_handler(CommandHandler("photos", photo_count_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("export", export_cmd))
    app.add_handler(CommandHandler("import", import_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("analyze", analyze_cmd))
    app.add_handler(CommandHandler("anniversary", anniversary_cmd))
    app.add_handler(CommandHandler("sticker", sticker_cmd))
    app.add_handler(CommandHandler("import_chat", import_chat_cmd))
    app.add_handler(CommandHandler("imported", list_imported_cmd))
    app.add_handler(CommandHandler("import_video", import_video_cmd))
    app.add_handler(CommandHandler("quota", quota_cmd))
    app.add_handler(CommandHandler("quota_reset", quota_reset_cmd))
    app.add_handler(CommandHandler("voice", voice_cmd))
    app.add_handler(CommandHandler("music", music_cmd))
    app.add_handler(CommandHandler("novel", novel_cmd))
    app.add_handler(CommandHandler("memory", memory_cmd))
    app.add_handler(CommandHandler("learned", learned_cmd))
    # [Skill: semantic-memory] 语义记忆命令
    app.add_handler(CommandHandler("forget", forget_cmd))
    app.add_handler(CommandHandler("search", search_memory_cmd))
    # [Skill: claw-summarize-pro] 摘要生成命令
    app.add_handler(CommandHandler("summarize", summarize_cmd))
    # [Skill: auto-updater] 版本检查命令
    app.add_handler(CommandHandler("version", version_cmd))
    app.add_handler(CommandHandler("check_update", check_update_cmd))
    # [Skill: gemini] Gemini直接回答命令
    app.add_handler(CommandHandler("gemini", gemini_cmd))
    # [Skill: vision-sandbox] 图片深度分析命令
    app.add_handler(CommandHandler("analyze_img", analyze_img_cmd))
    # [Skill: deepread-ocr] OCR文字提取命令
    app.add_handler(CommandHandler("ocr", ocr_cmd))
    # [Skill: gemini-deep-research] 深度研究命令
    app.add_handler(CommandHandler("research", research_cmd))
    # [Skill: relay-for-telegram] 消息历史搜索命令
    app.add_handler(CommandHandler("search_msg", search_msg_cmd))
    app.add_handler(CommandHandler("my_chats", my_chats_cmd))
    # [Skill: TTS] 语音合成命令
    app.add_handler(CommandHandler("tts", tts_voice_toggle))
    app.add_handler(CommandHandler("ttsstatus", tts_status_cmd))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(CommandHandler("genface", generate_face_image))

    # 移动照片命令：回复照片发送 /toselfie 将其移到自拍相册
    async def move_to_selfie(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """将用户照片移到自拍相册"""
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
            
            img = Image.open(io.BytesIO(photo_bytes))
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(filepath, 'JPEG', quality=95)
            
            await update.message.reply_text(f"✅ 已添加到车如云的自拍相册！")
            logging.info(f"照片已移到自拍相册: {filename}")
        except Exception as e:
            logging.error(f"移动照片失败: {e}")
            await update.message.reply_text(f"...操作失败：{e}")

    app.add_handler(CommandHandler("toselfie", move_to_selfie))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.ALL, handle_video_import))
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.PHOTO & ~filters.VIDEO, handle_document))
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
