"""
config.py - 车如云 Telegram Bot 配置模块
从 bot.py Phase 1 (P0) 拆分提取
包含：路径常量、环境变量、工具函数、JSON/Config 工具
时区由各角色文件独立定义（见 characters/*/config.json）
"""

import os
import json
import logging
import shutil
from datetime import datetime, timezone

# ============================================================
# 基础配置（必须在其他配置之前定义）
# ============================================================

# 数据目录（支持环境变量配置，用于容器部署）
DATA_DIR = os.environ.get("DATA_DIR", "/opt/NxSiran/data")
os.makedirs(DATA_DIR, exist_ok=True)

# 默认时区（UTC+9，韩国时间）- 仅作为 fallback
# 实际时区由各角色配置文件定义（见 characters/*/config.json）
DEFAULT_TZ_OFFSET = 9

def get_default_tz() -> timezone:
    """获取默认时区（可通过环境变量覆盖）"""
    offset = int(os.environ.get("TZ_OFFSET", str(DEFAULT_TZ_OFFSET)))
    from datetime import timedelta
    return timezone(timedelta(hours=offset))

# ============================================================
# 路径常量
# ============================================================

# 用户系统
USERS_FILE = os.path.join(DATA_DIR, "users.json")

# 角色数据目录
CHARACTERS_DIR = os.path.join(DATA_DIR, "characters")
os.makedirs(CHARACTERS_DIR, exist_ok=True)

# 配置文件路径
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# 默认配置（首次运行时创建）
DEFAULT_CONFIG = {
    "admin_username": "",
    "admin_password": "",
    "telegram_token": "",
    "chat_id": "",
    "ai_api_key": "",
    "ai_api_base": "https://openrouter.ai/api/v1",
    "public_url": "",  # 服务器公网地址，用于 Mini App 和 Web 回调
}

# 临时占位，等 init_config() 调用后再加载
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
BOT_VERSION = "1.4.7.3"
APP_NAME = "恋爱至上主义区域"
APP_NAME_EN = "Love Supremacy Zone"

# 视频目录
VIDEO_DIR = os.path.join(DATA_DIR, "videos")
os.makedirs(VIDEO_DIR, exist_ok=True)

# [Skill: skills-manager] Skills 状态持久化文件路径
SKILLS_STATE_FILE = os.path.join(DATA_DIR, "skills_state.json")

# Skills 注册表：记录所有已集成的 skills
# v1.4.7.3 - 新增: Web端声音语料上传功能
SKILLS_REGISTRY = {
    "humanize-ai-text": {"name": "AI文本人性化", "desc": "让回复更像真人，去除机械感", "enabled": True, "category": "对话优化"},
    "self-improving": {"name": "自我改进", "desc": "从用户纠正中学习", "enabled": True, "category": "学习"},
    "proactive-agent": {"name": "主动行为", "desc": "主动发起对话", "enabled": True, "category": "行为"},
    "semantic-memory": {"name": "语义记忆", "desc": "长期语义记忆系统", "enabled": True, "category": "记忆"},
    "claw-summarize-pro": {"name": "摘要生成", "desc": "文本/URL摘要", "enabled": True, "category": "工具"},
    "auto-updater": {"name": "自动更新", "desc": "代码变更检测", "enabled": True, "category": "运维"},
    "agent-orchestration": {"name": "Prompt架构", "desc": "5层Prompt工程", "enabled": True, "category": "核心"},
    "vision-sandbox": {"name": "图片分析", "desc": "Gemini图片深度分析", "enabled": True, "category": "AI"},
    "deepread-ocr": {"name": "文档OCR", "desc": "文档文字识别", "enabled": True, "category": "工具"},
    "tts": {"name": "语音合成", "desc": "TTS语音回复(韩语男声+声音克隆)", "enabled": True, "category": "工具"},
    "qdrant-memory": {"name": "Qdrant记忆", "desc": "Qdrant Cloud向量记忆(语义搜索)", "enabled": True, "category": "记忆"},
    "lightrag": {"name": "知识库", "desc": "原作小说知识查询", "enabled": True, "category": "知识"},
}

# 每角色技能禁用列表: {character_id: {skill_id: True}}
CHARACTER_SKILL_OVERRIDES = {}

# [Skill: gemini] [Skill: vision-sandbox] [Skill: deepread-ocr] [Skill: gemini-deep-research] Gemini API配置
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# [Skill: relay-for-telegram] Relay API配置
RELAY_API_KEY = os.environ.get("RELAY_API_KEY", "")

# ============================================================
# 用户目录工具函数
# ============================================================

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
    if os.path.exists(HISTORY_FILE):
        user_history = get_user_history_file(user_id)
        if not os.path.exists(user_history):
            shutil.copy2(HISTORY_FILE, user_history)
            logging.info(f"[数据迁移] 聊天记录已迁移到用户目录: user_{user_id}")
    # 迁移记忆
    if os.path.exists(MEMORY_FILE):
        user_memory = get_user_memory_file(user_id)
        if not os.path.exists(user_memory):
            shutil.copy2(MEMORY_FILE, user_memory)
            logging.info(f"[数据迁移] 长期记忆已迁移到用户目录: user_{user_id}")
    # 迁移统计
    if os.path.exists(STATS_FILE):
        user_stats = get_user_stats_file(user_id)
        if not os.path.exists(user_stats):
            shutil.copy2(STATS_FILE, user_stats)
            logging.info(f"[数据迁移] 聊天统计已迁移到用户目录: user_{user_id}")
    # 迁移自拍
    if os.path.exists(SELFIE_DIR):
        user_selfie = get_user_selfie_dir(user_id)
        selfie_files = [f for f in os.listdir(SELFIE_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        if selfie_files and not os.listdir(user_selfie):
            for f in selfie_files:
                shutil.copy2(os.path.join(SELFIE_DIR, f), os.path.join(user_selfie, f))
            logging.info(f"[数据迁移] {len(selfie_files)}张自拍已迁移到用户目录: user_{user_id}")
    # 标记已完成迁移
    with open(migration_flag, 'w') as f:
        from datetime import timedelta
        tz = timezone(timedelta(hours=DEFAULT_TZ_OFFSET))
        f.write(str(datetime.now(tz).isoformat()))

# ============================================================
# JSON/Config 工具函数
# ============================================================

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

# 模块加载时自动初始化配置
init_config()
