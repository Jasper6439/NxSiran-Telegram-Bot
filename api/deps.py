"""
api/deps.py - FastAPI 依赖注入 (v1.9)
======================================
提供认证、数据库会话等公共依赖。
v1.9: API Token 统一存储到 SQLite 数据库，实现单一数据源。
v1.8: 统一用户 ID，确保 Web 认证用户与数据库用户正确关联。
"""

import os
import json
import logging
from fastapi import Depends, Header, HTTPException
from system.auth import validate_session_token_from_token, API_TOKENS
from system.config import load_config, DATA_DIR

logger = logging.getLogger(__name__)

# API Token 持久化文件（向后兼容，迁移后不再使用）
_API_TOKENS_FILE = os.path.join(DATA_DIR, "api_tokens.json")


def _load_persistent_api_tokens():
    """从文件加载持久化的 API Token 到内存（向后兼容）"""
    if os.path.exists(_API_TOKENS_FILE):
        try:
            with open(_API_TOKENS_FILE, 'r', encoding='utf-8') as f:
                tokens = json.load(f)
            API_TOKENS.update(tokens)
            logger.info(f"[Auth] 已加载 {len(tokens)} 个持久化 API Token（向后兼容）")
        except Exception as e:
            logger.warning(f"[Auth] 加载 API Token 失败: {e}")


# 模块加载时自动恢复持久化 Token（向后兼容）
_load_persistent_api_tokens()


async def get_current_user(authorization: str = Header(None)) -> int:
    """统一认证依赖。

    依次尝试 session token、api token（数据库优先）、数据库直接认证。
    返回认证成功的 user_id（数据库内部整数 ID）。

    Raises:
        HTTPException: 401 未认证 / 404 用户不存在
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = authorization[7:]

    raw_user_id = None

    # 1. 尝试 session token
    try:
        raw_user_id = validate_session_token_from_token(token)
    except Exception as e:
        logger.debug(f"[Auth] Session token 验证失败: {e}")

    # 2. 尝试 api token（数据库优先，内存作为后备）
    if not raw_user_id:
        try:
            from database import get_db
            db = get_db()
            token_info = db.validate_api_token(token)
            if token_info:
                raw_user_id = token_info['user_id']
                logger.debug(f"[Auth] 数据库 Token 验证成功: user_id={raw_user_id}")
        except Exception as e:
            logger.warning(f"[Auth] 数据库 Token 验证失败: {e}")

        # 后备：检查内存中的 Token（向后兼容）
        if not raw_user_id and token in API_TOKENS:
            raw_user_id = API_TOKENS[token].get("user_id")
            logger.debug(f"[Auth] 内存 Token 验证成功: user_id={raw_user_id}")

    # 3. Fallback: 直接用数字 token 作为 telegram_id 认证
    if not raw_user_id:
        try:
            cfg = load_config()
            chat_id = cfg.get("your_chat_id", 0) or cfg.get("chat_id", 0)
            if chat_id and str(token) == str(chat_id):
                raw_user_id = str(chat_id)
                logger.debug(f"[Auth] Chat ID 认证成功: {raw_user_id}")
        except Exception as e:
            logger.debug(f"[Auth] Chat ID 认证失败: {e}")

    if not raw_user_id:
        raise HTTPException(status_code=401, detail="认证失败：无效的令牌")

    # 统一转换为数据库内部 ID
    try:
        from database import get_db
        db = get_db()

        # 如果 raw_user_id 已经是数据库内部 ID，直接验证存在性
        if isinstance(raw_user_id, int) or (isinstance(raw_user_id, str) and raw_user_id.isdigit()):
            user_id_int = int(raw_user_id)
            # 检查用户是否存在
            user = db.get_user_by_id(user_id_int)
            if user:
                return user_id_int
            # 用户不存在，可能是 telegram_id
            raw_user_id = user_id_int

        # 通过 telegram_id 获取或创建用户
        if isinstance(raw_user_id, (int, str)) and str(raw_user_id).isdigit():
            telegram_id = int(raw_user_id)
            db_user_id = db.get_or_create_user(
                telegram_id,
                f"user_{telegram_id}"
            )
            return db_user_id
        else:
            # 处理非数字 ID（如 session token 中的用户标识）
            from system.auth import get_user_info
            user_info = get_user_info(raw_user_id)
            telegram_id = user_info.get("telegram_chat_id") if user_info else None
            if telegram_id:
                db_user_id = db.get_or_create_user(
                    int(telegram_id),
                    user_info.get("username", f"user_{raw_user_id}")
                )
                return db_user_id
            else:
                # 使用 hash 生成稳定的 telegram_id
                import hashlib
                fallback_id = abs(hash(raw_user_id)) % 100000000
                db_user_id = db.get_or_create_user(
                    fallback_id,
                    user_info.get("username", f"user_{raw_user_id}") if user_info else f"user_{raw_user_id}"
                )
                return db_user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auth] 用户初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"用户初始化失败: {str(e)}")


async def get_optional_user(authorization: str = Header(None)):
    """可选认证（未登录返回 None）。"""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


async def get_admin_user(authorization: str = Header(None)) -> int:
    """管理员认证依赖。

    返回认证成功的 user_id，并验证用户是否为管理员。

    Raises:
        HTTPException: 401 未认证 / 403 无权限 / 404 用户不存在
    """
    user_id = await get_current_user(authorization)

    try:
        from database import get_db
        db = get_db()
        user = db.get_user_by_id(user_id)

        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")

        if not user.get('is_admin'):
            raise HTTPException(status_code=403, detail="需要管理员权限")

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Auth] 管理员验证失败: {e}")
        raise HTTPException(status_code=500, detail="管理员验证失败")


# ============================================================
# 负面测试用例支持
# ============================================================

class UserNotFoundException(HTTPException):
    """用户不存在异常"""
    def __init__(self, user_id=None):
        detail = f"用户不存在: {user_id}" if user_id else "用户不存在"
        super().__init__(status_code=404, detail=detail)


class AuthenticationRequiredException(HTTPException):
    """需要认证异常"""
    def __init__(self):
        super().__init__(status_code=401, detail="需要认证")


async def get_user_or_404(user_id: int) -> dict:
    """获取用户，不存在时抛出 404。

    Args:
        user_id: 用户数据库 ID

    Returns:
        用户信息字典

    Raises:
        HTTPException: 404 用户不存在
    """
    from database import get_db
    db = get_db()
    user = db.get_user_by_id(user_id)

    if not user:
        raise UserNotFoundException(user_id)

    return user


async def verify_user_access(current_user_id: int, target_user_id: int, allow_admin: bool = True):
    """验证用户是否有权访问目标用户数据。

    Args:
        current_user_id: 当前用户 ID
        target_user_id: 目标用户 ID
        allow_admin: 是否允许管理员访问其他用户数据

    Raises:
        HTTPException: 403 无权限 / 404 目标用户不存在
    """
    # 自己访问自己总是允许的
    if current_user_id == target_user_id:
        return True

    from database import get_db
    db = get_db()

    # 检查目标用户是否存在
    target_user = db.get_user_by_id(target_user_id)
    if not target_user:
        raise UserNotFoundException(target_user_id)

    # 检查是否为管理员
    if allow_admin:
        current_user = db.get_user_by_id(current_user_id)
        if current_user and current_user.get('is_admin'):
            return True

    raise HTTPException(status_code=403, detail="无权访问该用户数据")
