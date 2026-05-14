"""
auth.py - 恋爱至上主义区域 认证模块
v1.4.5: 支持邮箱注册，角色独立绑定 Telegram Chat ID
"""

import hashlib
import time
import json
import logging
import os
import secrets
from datetime import datetime, timedelta

from system.config import USERS_FILE, load_config, get_default_tz


# ============================================================
# 用户会话存储（内存，重启后失效）
# ============================================================

USER_SESSIONS = {}  # {token: {"user_id": chat_id, "username": xxx, "created": timestamp}}

# API 认证令牌存储（内存，重启后失效）
API_TOKENS = {}  # {token: {"user_id": xxx, "created": timestamp}}

# 自动登录令牌（长期有效）
AUTO_LOGIN_TOKENS = {}  # {token: {"user_id": xxx, "expires": timestamp}}
AUTO_LOGIN_FILE = os.path.join(os.path.dirname(USERS_FILE), "auto_login.json")


# ============================================================
# 用户数据结构 v2.5
# ============================================================
# 支持邮箱注册，角色独立绑定 Chat ID
#
# {
#   "5315601134": {
#     "username": "jasper",
#     "email": "user@example.com",      # 新增：邮箱
#     "password_hash": "sha256...",
#     "display_name": "Jasper",
#     "role": "admin",
#     "created_at": "2026-05-12T...",
#     "last_login": "2026-05-12T...",
#     "login_count": 5,
#     "preferences": {...},
#     "character_bindings": {            # 新增：角色绑定
#       "chayewoon": {"chat_id": "123456", "bound_at": "..."}
#     },
#     "reset_code": null,                # 新增：密码重置码
#     "reset_code_expires": null         # 新增：重置码过期时间
#   }
# }

USER_DATA_VERSION = 2.5


# ============================================================
# 数据迁移
# ============================================================

def _migrate_users(data):
    """将旧版用户数据迁移到新格式（以 chat_id 为主键）"""
    if not data or isinstance(data, dict) and data.get("_version") == USER_DATA_VERSION:
        return data

    migrated = {"_version": USER_DATA_VERSION, "users": {}}

    if isinstance(data, dict):
        for key, value in data.items():
            if key.startswith("_"):
                continue
            if isinstance(value, dict) and "chat_id" in value:
                chat_id = value["chat_id"]
                migrated["users"][chat_id] = {
                    "username": key,
                    "password_hash": value.get("password_hash", ""),
                    "display_name": key.capitalize(),
                    "role": "user",
                    "created_at": value.get("created_at", ""),
                    "last_login": value.get("last_login"),
                    "login_count": 1 if value.get("last_login") else 0,
                    "preferences": {
                        "language": "zh-CN",
                        "theme": "auto"
                    }
                }

    logging.info(f"[用户系统] 数据迁移完成，共 {len(migrated['users'])} 个用户")
    save_users(migrated)
    return migrated


# ============================================================
# 用户数据读写
# ============================================================

def load_users():
    """加载用户数据（自动迁移旧格式）"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return _migrate_users(data)
        except Exception as e:
            logging.error(f"[用户系统] 加载用户数据失败: {e}")
    return {"_version": USER_DATA_VERSION, "users": {}}

def save_users(data):
    """保存用户数据"""
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[用户系统] 保存用户数据失败: {e}")

def _get_users_dict():
    """获取用户字典（便捷方法）"""
    data = load_users()
    return data.get("users", {})

def _save_users_dict(users_dict):
    """保存用户字典（便捷方法）"""
    save_users({"_version": USER_DATA_VERSION, "users": users_dict})


# ============================================================
# 密码哈希
# ============================================================

def hash_password(password):
    """密码哈希（SHA256 + 随机 salt，每次生成不同）"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{password}:{salt}".encode()).hexdigest()
    return f"{salt}${hashed}"

def _verify_password(password, stored_hash):
    """验证密码"""
    try:
        salt, hashed = stored_hash.split("$", 1)
        return hashlib.sha256(f"{password}:{salt}".encode()).hexdigest() == hashed
    except (ValueError, AttributeError):
        return False


# ============================================================
# 用户注册
# ============================================================

def register_user(username, password, chat_id):
    """
    注册新用户（以 chat_id 为主键）

    返回: (success: bool, message: str)
    """
    if not username or not password or not chat_id:
        return False, "用户名、密码和 Chat ID 不能为空"

    if len(password) < 6:
        return False, "密码长度至少 6 位"

    if len(username) < 2 or len(username) > 20:
        return False, "用户名长度 2-20 个字符"

    # 验证 chat_id 是数字
    try:
        chat_id_str = str(int(chat_id))
    except ValueError:
        return False, "Chat ID 必须是数字"

    users = _get_users_dict()

    # 检查 chat_id 是否已注册
    if chat_id_str in users:
        return False, "该 Telegram 账号已注册，请直接登录"

    # 检查用户名是否已被使用
    for u in users.values():
        if u.get("username", "").lower() == username.lower():
            return False, "用户名已被使用"

    # 检查是否为管理员
    config = load_config()
    role = "admin" if username == config.get("admin_username", "Ulysses") else "user"

    # 创建用户
    now = datetime.now(get_default_tz()).isoformat()
    users[chat_id_str] = {
        "username": username,
        "password_hash": hash_password(password),
        "display_name": username.capitalize(),
        "role": role,
        "created_at": now,
        "last_login": None,
        "login_count": 0,
        "preferences": {
            "language": "zh-CN",
            "theme": "auto"
        }
    }

    _save_users_dict(users)
    logging.info(f"[用户系统] 新用户注册: {username} (chat_id: {chat_id_str}, role: {role})")
    return True, "注册成功"


# ============================================================
# 用户登录
# ============================================================

def validate_user(username, password):
    """
    验证用户登录（支持用户名或 chat_id 登录）

    返回: (success: bool, user_data: dict or None)
    """
    users = _get_users_dict()

    # 查找用户（支持用户名或 chat_id）
    user_key = None
    user_data = None

    # 先尝试用 chat_id 查找
    if username.isdigit():
        if username in users:
            user_key = username
            user_data = users[username]

    # 再尝试用用户名查找
    if not user_data:
        for cid, u in users.items():
            if u.get("username", "").lower() == username.lower():
                user_key = cid
                user_data = u
                break

    if not user_data:
        return False, None

    # 验证密码
    if not _verify_password(password, user_data["password_hash"]):
        return False, None

    # 更新登录信息
    now = datetime.now(get_default_tz()).isoformat()
    user_data["last_login"] = now
    user_data["login_count"] = user_data.get("login_count", 0) + 1
    users[user_key] = user_data
    _save_users_dict(users)

    # 添加 chat_id 到返回数据（chat_id 是字典的 key）
    user_data["chat_id"] = user_key

    return True, user_data


# ============================================================
# 会话管理（持久化存储）
# ============================================================

USER_SESSIONS = {}  # 内存缓存
SESSIONS_FILE = os.path.join(os.path.dirname(USERS_FILE), "sessions.json")

def _load_sessions():
    """从文件加载会话"""
    global USER_SESSIONS
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 过滤掉过期的会话（7天）
                now = time.time()
                USER_SESSIONS = {
                    k: v for k, v in data.items()
                    if now - v.get("created", 0) < 7 * 24 * 3600
                }
    except Exception as e:
        logging.warning(f"[会话] 加载会话失败: {e}")
        USER_SESSIONS = {}

def _save_sessions():
    """保存会话到文件"""
    try:
        os.makedirs(os.path.dirname(SESSIONS_FILE), exist_ok=True)
        with open(SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(USER_SESSIONS, f, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[会话] 保存会话失败: {e}")

# 启动时加载会话
_load_sessions()

def generate_session_token(username, user_id):
    """生成用户会话令牌（持久化）"""
    token = secrets.token_hex(32)
    USER_SESSIONS[token] = {
        "username": username,
        "user_id": user_id,  # 支持 UUID 字符串或数字
        "created": time.time()
    }
    _save_sessions()
    return token

def validate_session_token(request):
    """验证会话令牌，返回 user_id 或 None"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        return _validate_token_string(token)
    return None

def validate_session_token_from_token(token):
    """直接从 token 字符串验证，返回 user_id 或 None"""
    return _validate_token_string(token)

def _validate_token_string(token):
    """验证 token 字符串，返回 user_id 或 None"""
    # 如果内存中没有，尝试重新加载
    if token not in USER_SESSIONS:
        _load_sessions()
    if token in USER_SESSIONS:
        # 检查是否过期
        session = USER_SESSIONS[token]
        if time.time() - session.get("created", 0) < 7 * 24 * 3600:
            return session["user_id"]
        else:
            # 过期删除
            del USER_SESSIONS[token]
            _save_sessions()
    return None

def is_admin_user(request):
    """检查当前用户是否是管理员"""
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        if token in USER_SESSIONS:
            user_id = USER_SESSIONS[token].get("user_id")
            users = _get_users_dict()
            user = users.get(str(user_id), {})
            return user.get("role") == "admin"
    return False

def get_username_by_token(token):
    """通过 token 获取用户名"""
    if token in USER_SESSIONS:
        return USER_SESSIONS[token].get("username")
    return None

def get_user_by_chat_id(chat_id):
    """通过 chat_id 获取用户数据"""
    users = _get_users_dict()
    return users.get(str(chat_id))


# ============================================================
# API Token 函数
# ============================================================

def generate_api_token(user_id):
    """生成 API 认证令牌"""
    token = secrets.token_hex(32)
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
# 自动登录 Token（长期有效）
# ============================================================

def _load_auto_login():
    """加载自动登录令牌"""
    global AUTO_LOGIN_TOKENS
    try:
        if os.path.exists(AUTO_LOGIN_FILE):
            with open(AUTO_LOGIN_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                now = time.time()
                AUTO_LOGIN_TOKENS = {
                    k: v for k, v in data.items()
                    if v.get("expires", 0) > now
                }
    except Exception as e:
        logging.warning(f"[自动登录] 加载失败: {e}")
        AUTO_LOGIN_TOKENS = {}

def _save_auto_login():
    """保存自动登录令牌"""
    try:
        os.makedirs(os.path.dirname(AUTO_LOGIN_FILE), exist_ok=True)
        with open(AUTO_LOGIN_FILE, 'w', encoding='utf-8') as f:
            json.dump(AUTO_LOGIN_TOKENS, f, ensure_ascii=False)
    except Exception as e:
        logging.warning(f"[自动登录] 保存失败: {e}")

# 启动时加载
_load_auto_login()

def generate_auto_login_token(user_id):
    """生成自动登录令牌（30天有效）"""
    token = secrets.token_hex(32)
    AUTO_LOGIN_TOKENS[token] = {
        "user_id": user_id,
        "expires": time.time() + 30 * 24 * 3600
    }
    _save_auto_login()
    return token

def validate_auto_login_token(token):
    """验证自动登录令牌，返回 user_id 或 None"""
    if token not in AUTO_LOGIN_TOKENS:
        return None
    session = AUTO_LOGIN_TOKENS[token]
    if session.get("expires", 0) < time.time():
        del AUTO_LOGIN_TOKENS[token]
        _save_auto_login()
        return None
    return session.get("user_id")

def revoke_auto_login_token(token):
    """撤销自动登录令牌"""
    if token in AUTO_LOGIN_TOKENS:
        del AUTO_LOGIN_TOKENS[token]
        _save_auto_login()


# ============================================================
# 角色绑定 Chat ID
# ============================================================

def bind_character_chat_id(user_id, character_id, chat_id):
    """
    绑定角色的 Telegram Chat ID（已废弃，保留兼容）
    返回: (success: bool, message: str)
    """
    if not chat_id:
        return False, "Chat ID 不能为空"
    try:
        chat_id_str = str(int(chat_id))
    except ValueError:
        return False, "Chat ID 必须是数字"

    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return False, "用户不存在"

    if "character_bindings" not in user:
        user["character_bindings"] = {}

    user["character_bindings"][character_id] = {
        "chat_id": chat_id_str,
        "bound_at": datetime.now(get_default_tz()).isoformat()
    }
    users[str(user_id)] = user
    _save_users_dict(users)
    logging.info(f"[角色绑定] {user_id} -> {character_id} ({chat_id_str})")
    return True, "绑定成功"


def bind_character_bot_token(user_id, character_id, bot_token):
    """
    绑定角色的 Telegram Bot Token - v1.4.12.13
    用户绑定该角色对应的 Bot Token，系统通过该 token 发送消息到用户的 telegram_chat_id
    返回: (success: bool, message: str)
    """
    if not bot_token:
        return False, "Bot Token 不能为空"
    if ':' not in bot_token:
        return False, "Bot Token 格式不正确"

    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return False, "用户不存在"

    # 检查用户是否已绑定 telegram_chat_id
    telegram_chat_id = user.get('telegram_chat_id')
    if not telegram_chat_id:
        return False, "请先在设置页绑定您的 Telegram Chat ID"

    if "character_bindings" not in user:
        user["character_bindings"] = {}

    user["character_bindings"][character_id] = {
        "bot_token": bot_token,
        "bound_at": datetime.now(get_default_tz()).isoformat()
    }
    users[str(user_id)] = user
    _save_users_dict(users)
    logging.info(f"[角色绑定] {user_id} -> {character_id} (bot_token: {bot_token[:10]}...)")
    return True, f"绑定成功！角色 {character_id} 的消息将通过该 Bot 发送到您的 Telegram"


def get_character_bot_token(user_id, character_id):
    """获取用户绑定的角色 Bot Token"""
    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return None
    bindings = user.get("character_bindings", {})
    binding = bindings.get(character_id, {})
    return binding.get("bot_token")


def get_user_info(user_id):
    """获取用户信息"""
    users = _get_users_dict()
    return users.get(str(user_id))


def get_character_chat_id(user_id, character_id):
    """获取用户绑定的角色 Chat ID"""
    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return None
    bindings = user.get("character_bindings", {})
    return bindings.get(character_id, {}).get("chat_id")

def get_user_character_bindings(user_id):
    """获取用户的所有角色绑定"""
    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return {}
    return user.get("character_bindings", {})


# ============================================================
# 找回密码
# ============================================================

def generate_reset_code(email_or_username):
    """
    生成密码重置验证码
    返回: (success: bool, code: str or None, message: str)
    """
    users = _get_users_dict()

    # 查找用户（支持邮箱或用户名）
    user_key = None
    user_data = None

    for cid, u in users.items():
        if u.get("email", "").lower() == email_or_username.lower():
            user_key = cid
            user_data = u
            break
        if u.get("username", "").lower() == email_or_username.lower():
            user_key = cid
            user_data = u
            break

    if not user_data:
        return False, None, "该用户不存在"

    # 生成6位数字验证码
    code = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
    expires = (datetime.now(get_default_tz()) + timedelta(minutes=10)).isoformat()

    user_data["reset_code"] = code
    user_data["reset_code_expires"] = expires
    users[user_key] = user_data
    _save_users_dict(users)

    logging.info(f"[找回密码] 生成重置码: {user_data.get('username')}")
    return True, code, "验证码已生成"

def verify_reset_code(email_or_username, code):
    """
    验证重置码
    返回: (success: bool, user_id: str or None, message: str)
    """
    users = _get_users_dict()

    user_key = None
    user_data = None

    for cid, u in users.items():
        if u.get("email", "").lower() == email_or_username.lower():
            user_key = cid
            user_data = u
            break
        if u.get("username", "").lower() == email_or_username.lower():
            user_key = cid
            user_data = u
            break

    if not user_data:
        return False, None, "用户不存在"

    stored_code = user_data.get("reset_code")
    expires = user_data.get("reset_code_expires")

    if not stored_code or not expires:
        return False, None, "请先获取验证码"

    if datetime.now(get_default_tz()) > datetime.fromisoformat(expires):
        return False, None, "验证码已过期"

    if code != stored_code:
        return False, None, "验证码错误"

    return True, user_key, "验证成功"

def reset_password(user_id, new_password):
    """重置密码"""
    if len(new_password) < 6:
        return False, "密码长度至少 6 位"

    users = _get_users_dict()
    user = users.get(str(user_id))
    if not user:
        return False, "用户不存在"

    user["password_hash"] = hash_password(new_password)
    user["reset_code"] = None
    user["reset_code_expires"] = None
    users[str(user_id)] = user
    _save_users_dict(users)

    logging.info(f"[找回密码] 密码重置: {user_id}")
    return True, "密码重置成功"


# ============================================================
# v3 增强功能（从 auth_v3.py 合并）
# ============================================================

def register_user_by_email(email, username, password):
    """
    通过邮箱注册新用户（v3 增强）
    返回: (success: bool, message: str)
    """
    if not email or not username or not password:
        return False, "邮箱、用户名和密码不能为空"

    if len(password) < 6:
        return False, "密码长度至少 6 位"

    if len(username) < 2 or len(username) > 20:
        return False, "用户名长度 2-20 个字符"

    if "@" not in email or "." not in email.split("@")[-1]:
        return False, "邮箱格式不正确"

    email = email.lower().strip()
    users = _get_users_dict()

    # 检查邮箱是否已被使用
    for u in users.values():
        if u.get("email", "").lower() == email:
            return False, "该邮箱已注册，请直接登录"

    # 检查用户名是否已被使用
    for u in users.values():
        if u.get("username", "").lower() == username.lower():
            return False, "用户名已被使用"

    config = load_config()
    role = "admin" if username == config.get("admin_username", "Ulysses") else "user"

    now = datetime.now(get_default_tz()).isoformat()
    temp_key = f"email_{secrets.token_hex(8)}"
    users[temp_key] = {
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "display_name": username.capitalize(),
        "role": role,
        "email_verified": False,
        "created_at": now,
        "last_login": None,
        "login_count": 0,
        "preferences": {"language": "zh-CN", "theme": "auto"},
        "character_bindings": {},
        "reset_code": None,
        "reset_code_expires": None,
    }

    _save_users_dict(users)
    logging.info(f"[用户系统] 邮箱注册: {username} ({email}, role: {role})")
    return True, "注册成功"


def get_user_by_email(email):
    """通过邮箱获取用户数据"""
    email = email.lower().strip()
    users = _get_users_dict()
    for u in users.values():
        if u.get("email", "").lower() == email:
            return u
    return None


def get_user_by_id(user_id):
    """通过 user_id 获取用户数据"""
    users = _get_users_dict()
    return users.get(str(user_id))


def is_admin_user_by_id(user_id):
    """通过 user_id 检查是否为管理员"""
    user = get_user_by_id(user_id)
    return user and user.get("role") == "admin"
