"""
api/routes_user.py - 用户认证路由 (v1.7)
=========================================
从 packages/web/auth_routes.py 迁移的用户认证 API。
包含注册、登录、版本查询、健康检查等端点。
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from system.config import BOT_VERSION, APP_NAME, load_config, get_default_tz
from system.auth import (
    generate_session_token,
    generate_auto_login_token,
    validate_auto_login_token,
    load_users,
    save_users,
    hash_password,
    _verify_password,
)

router = APIRouter(tags=["user"])


# ============================================================
# Pydantic 请求模型
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    auto_login: bool = False
    auto_token: str = ""


class RegisterRequest(BaseModel):
    email: str = ""
    username: str
    password: str
    telegram_chat_id: str = ""


class ForgotPasswordRequest(BaseModel):
    email_or_username: str


class VerifyResetCodeRequest(BaseModel):
    email_or_username: str
    code: str


class ResetPasswordRequest(BaseModel):
    user_id: str
    new_password: str


class UpdatePreferredNameRequest(BaseModel):
    preferred_name: str


class BindTelegramRequest(BaseModel):
    telegram_chat_id: str


# ============================================================
# 路由
# ============================================================

@router.get("/api/version")
async def get_version():
    """获取后端版本号"""
    return {"version": BOT_VERSION, "name": APP_NAME}


@router.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok", "version": BOT_VERSION}


@router.post("/api/register")
async def register(req: RegisterRequest):
    """用户注册 - 支持邮箱注册，telegram_chat_id 选填"""
    try:
        email = req.email.strip().lower()
        username = req.username.strip()
        password = req.password
        telegram_chat_id = req.telegram_chat_id.strip()

        # 验证必填字段
        if not email or not username or not password:
            raise HTTPException(status_code=400, detail="邮箱、用户名和密码不能为空")

        # Telegram Chat ID 选填，如果提供则验证格式
        if telegram_chat_id:
            if not telegram_chat_id.isdigit():
                raise HTTPException(status_code=400, detail="Telegram Chat ID 必须是纯数字")

        # 验证邮箱格式
        if '@' not in email or '.' not in email.split('@')[-1]:
            raise HTTPException(status_code=400, detail="邮箱格式不正确")

        # 验证密码长度
        if len(password) < 6:
            raise HTTPException(status_code=400, detail="密码长度至少6位")

        # 检查邮箱是否已注册
        user_data = load_users()
        users = user_data.get("users", {})
        for u in users.values():
            if u.get('email', '').lower() == email:
                raise HTTPException(status_code=400, detail="该邮箱已注册")

        # 检查用户名是否已被使用
        for u in users.values():
            if u.get('username', '').lower() == username.lower():
                raise HTTPException(status_code=400, detail="用户名已被使用")

        # 检查 Telegram Chat ID 是否已被绑定
        if telegram_chat_id:
            for uid, u in users.items():
                if u.get('telegram_chat_id') == telegram_chat_id:
                    raise HTTPException(status_code=400, detail="该 Telegram Chat ID 已被其他账号绑定")

        # 创建用户
        user_id = str(uuid.uuid4())[:8]
        cfg = load_config()
        role = "admin" if username == cfg.get("admin_username", "") else "user"

        users[user_id] = {
            "email": email,
            "username": username,
            "password_hash": hash_password(password),
            "display_name": "",
            "role": role,
            "created_at": datetime.now(get_default_tz()).isoformat(),
            "last_login": None,
            "login_count": 0,
            "preferences": {"language": "zh-CN", "theme": "auto"},
            "character_bindings": {},
            "telegram_chat_id": telegram_chat_id,
            "reset_code": None,
            "reset_code_expires": None,
        }
        user_data["users"] = users
        save_users(user_data)

        logging.info(f"[API注册] 新用户: {username} ({email}, telegram_chat_id: {telegram_chat_id}, role: {role})")

        # 注册成功后自动登录
        token = generate_session_token(username, user_id)
        return {
            "success": True,
            "message": "注册成功",
            "token": token,
            "user_id": user_id,
            "username": username,
            "is_admin": role == "admin",
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[API注册] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/login")
async def login(req: LoginRequest):
    """用户登录 - 支持自动登录令牌"""
    try:
        username = req.username.strip()
        password = req.password
        auto_login = req.auto_login
        auto_token = req.auto_token

        # 如果有自动登录令牌，优先使用
        if auto_token:
            user_id = validate_auto_login_token(auto_token)
            if user_id:
                user_data_loaded = load_users()
                users = user_data_loaded.get("users", {})
                user = users.get(str(user_id))
                if user:
                    token = generate_session_token(user['username'], user_id)
                    return {
                        "success": True,
                        "token": token,
                        "user_id": user_id,
                        "username": user['username'],
                        "is_admin": user.get('role') == 'admin',
                        "display_name": user.get('display_name', user['username']),
                        "auto_token": auto_token,
                    }
            raise HTTPException(status_code=401, detail="自动登录已过期，请重新登录")

        if not username or not password:
            raise HTTPException(status_code=400, detail="用户名和密码不能为空")

        # 验证用户（支持用户名或邮箱登录）
        user_data_loaded = load_users()
        users = user_data_loaded.get("users", {})
        user_id = None
        user_data = None

        # 先尝试用邮箱查找
        for uid, u in users.items():
            if u.get('email', '').lower() == username.lower():
                user_id = uid
                user_data = u
                break

        # 再尝试用用户名查找
        if not user_data:
            for uid, u in users.items():
                if u.get('username', '').lower() == username.lower():
                    user_id = uid
                    user_data = u
                    break

        if not user_data:
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 验证密码
        if not _verify_password(password, user_data['password_hash']):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 检查是否为管理员
        cfg = load_config()
        if user_data['username'] == cfg.get('admin_username', ''):
            user_data['role'] = 'admin'

        # 更新登录信息
        user_data['last_login'] = datetime.now(get_default_tz()).isoformat()
        user_data['login_count'] = user_data.get('login_count', 0) + 1
        users[user_id] = user_data
        user_data_loaded["users"] = users
        save_users(user_data_loaded)

        # 生成会话令牌
        token = generate_session_token(user_data['username'], user_id)

        # 生成自动登录令牌
        return_auto_token = None
        if auto_login:
            return_auto_token = generate_auto_login_token(user_id)

        return {
            "success": True,
            "token": token,
            "user_id": user_id,
            "username": user_data['username'],
            "is_admin": user_data.get('role') == 'admin',
            "display_name": user_data.get('display_name', user_data['username']),
            "auto_token": return_auto_token,
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[API登录] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user/profile")
async def user_profile(authorization: str = None):
    """获取当前用户信息 - 用于验证 token"""
    from api.deps import get_current_user
    try:
        user_id = await get_current_user(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="未登录")

    try:
        user_data = load_users()
        users = user_data.get("users", {})
        user = users.get(str(user_id), {})

        return {
            "success": True,
            "user_id": user_id,
            "username": user.get('username', ''),
            "email": user.get('email', ''),
            "is_admin": user.get('role') == 'admin',
            "display_name": user.get('display_name', user.get('username', '')),
            "preferred_name": user.get('preferred_name', ''),
            "character_bindings": user.get('character_bindings', {}),
            "telegram_chat_id": user.get('telegram_chat_id', ''),
        }
    except Exception as e:
        logging.error(f"[API用户资料] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/user/preferred-name")
async def update_preferred_name(req: UpdatePreferredNameRequest, authorization: str = None):
    """更新用户自定义称呼（角色叫你什么）"""
    from api.deps import get_current_user
    try:
        user_id = await get_current_user(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="未登录")

    preferred_name = req.preferred_name.strip()
    if not preferred_name:
        raise HTTPException(status_code=400, detail="称呼不能为空")
    if len(preferred_name) > 20:
        raise HTTPException(status_code=400, detail="称呼最长20个字符")

    try:
        user_data = load_users()
        users = user_data.get("users", {})
        user = users.get(str(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        user['preferred_name'] = preferred_name
        user_data["users"] = users
        save_users(user_data)

        return {"success": True, "message": f"角色现在会叫你「{preferred_name}」", "preferred_name": preferred_name}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[API更新称呼] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/user/bind-telegram")
async def bind_telegram(req: BindTelegramRequest, authorization: str = None):
    """绑定 Telegram Chat ID"""
    from api.deps import get_current_user
    try:
        user_id = await get_current_user(authorization)
    except HTTPException:
        raise HTTPException(status_code=401, detail="未登录")

    telegram_chat_id = req.telegram_chat_id.strip()
    if not telegram_chat_id:
        raise HTTPException(status_code=400, detail="请输入 Telegram Chat ID")
    if not telegram_chat_id.isdigit():
        raise HTTPException(status_code=400, detail="Chat ID 必须是纯数字")

    try:
        user_data = load_users()
        users = user_data.get("users", {})
        user = users.get(str(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        user['telegram_chat_id'] = telegram_chat_id
        users[str(user_id)] = user
        user_data["users"] = users
        save_users(user_data)

        logging.info(f"[API绑定Telegram] 用户 {user.get('username')} 绑定 Chat ID: {telegram_chat_id}")
        return {"success": True, "message": "绑定成功"}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[API绑定Telegram] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """找回密码 - 发送验证码"""
    try:
        email_or_username = req.email_or_username.strip()
        if not email_or_username:
            raise HTTPException(status_code=400, detail="请输入邮箱或用户名")

        from system.auth import generate_reset_code
        success, code, message = generate_reset_code(email_or_username)

        if success:
            # 尝试通过邮件发送验证码
            from system.email_sender import is_smtp_configured, send_verification_code
            if is_smtp_configured():
                users_data = load_users()
                users = users_data.get("users", {})
                user_email = None
                for u in users.values():
                    if u.get('username', '').lower() == email_or_username.lower() or u.get('email', '').lower() == email_or_username.lower():
                        user_email = u.get('email')
                        break

                if user_email:
                    sent = await send_verification_code(user_email, code)
                    if sent:
                        return {"success": True, "message": f"验证码已发送到 {user_email}", "sent_email": True}
                    else:
                        return {"success": True, "message": "邮件发送失败，请使用下方测试验证码", "code": code}
                else:
                    return {"success": True, "message": "未找到关联邮箱，请使用下方测试验证码", "code": code}
            else:
                logging.info(f"[找回密码] 验证码: {code}")
                return {"success": True, "message": "验证码已生成（测试模式：SMTP 未配置）", "code": code}
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[找回密码] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/verify-reset-code")
async def verify_reset_code(req: VerifyResetCodeRequest):
    """验证重置码"""
    try:
        email_or_username = req.email_or_username.strip()
        code = req.code.strip()
        if not email_or_username or not code:
            raise HTTPException(status_code=400, detail="请输入邮箱/用户名和验证码")

        from system.auth import verify_reset_code as _verify_reset_code
        success, user_id, message = _verify_reset_code(email_or_username, code)

        if success:
            return {"success": True, "user_id": user_id, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[验证重置码] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """重置密码"""
    try:
        user_id = req.user_id
        new_password = req.new_password
        if not user_id or not new_password:
            raise HTTPException(status_code=400, detail="参数不完整")
        if len(new_password) < 6:
            raise HTTPException(status_code=400, detail="密码长度至少6位")

        from system.auth import reset_password as _reset_password
        success, message = _reset_password(user_id, new_password)

        if success:
            return {"success": True, "message": message}
        else:
            raise HTTPException(status_code=400, detail=message)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"[重置密码] 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
