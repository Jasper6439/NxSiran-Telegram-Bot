"""
api/deps.py - FastAPI 依赖注入 (v1.8)
======================================
提供认证、数据库会话等公共依赖。
v1.8: 统一用户 ID，确保 Web 认证用户与数据库用户正确关联。
支持 API Token 持久化（从 users.json 加载）。
"""

import os
import json
import logging
from fastapi import Depends, Header, HTTPException
from system.auth import validate_session_token_from_token, API_TOKENS
from system.config import load_config, DATA_DIR

logger = logging.getLogger(__name__)

# API Token 持久化文件
_API_TOKENS_FILE = os.path.join(DATA_DIR, "api_tokens.json")


def _load_persistent_api_tokens():
    """从文件加载持久化的 API Token 到内存"""
    if os.path.exists(_API_TOKENS_FILE):
        try:
            with open(_API_TOKENS_FILE, 'r', encoding='utf-8') as f:
                tokens = json.load(f)
            API_TOKENS.update(tokens)
            logger.info(f"[Auth] 已加载 {len(tokens)} 个持久化 API Token")
        except Exception as e:
            logger.warning(f"[Auth] 加载 API Token 失败: {e}")


def _save_persistent_api_tokens():
    """将内存中的 API Token 持久化到文件"""
    try:
        os.makedirs(os.path.dirname(_API_TOKENS_FILE), exist_ok=True)
        with open(_API_TOKENS_FILE, 'w', encoding='utf-8') as f:
            json.dump(API_TOKENS, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[Auth] 保存 API Token 失败: {e}")


# 模块加载时自动恢复持久化 Token
_load_persistent_api_tokens()


async def get_current_user(authorization: str = Header(None)) -> int:
    """统一认证依赖。

    依次尝试 session token、api token、数据库直接认证。
    返回认证成功的 user_id（数据库内部整数 ID）。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    token = authorization[7:]

    raw_user_id = None

    # 1. 尝试 session token
    raw_user_id = validate_session_token_from_token(token)

    # 2. 尝试 api token（内存 + 持久化）
    if not raw_user_id and token in API_TOKENS:
        raw_user_id = API_TOKENS[token].get("user_id")

    # 3. Fallback: 直接用数字 token 作为 telegram_id 认证
    if not raw_user_id:
        cfg = load_config()
        chat_id = cfg.get("your_chat_id", 0) or cfg.get("chat_id", 0)
        if chat_id and str(token) == str(chat_id):
            raw_user_id = str(chat_id)

    if not raw_user_id:
        raise HTTPException(status_code=401, detail="认证失败")

    # 统一转换为数据库内部 ID
    from database import get_db
    db = get_db()
    try:
        if str(raw_user_id).isdigit():
            db_user_id = db.get_or_create_user(
                int(raw_user_id),
                f"user_{raw_user_id}"
            )
            return db_user_id
        else:
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
                import hashlib
                fallback_id = abs(hash(raw_user_id)) % 100000000
                db_user_id = db.get_or_create_user(
                    fallback_id,
                    user_info.get("username", f"user_{raw_user_id}") if user_info else f"user_{raw_user_id}"
                )
                return db_user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"用户初始化失败: {str(e)}")


async def get_optional_user(authorization: str = Header(None)):
    """可选认证（未登录返回 None）。"""
    if not authorization:
        return None
    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None
