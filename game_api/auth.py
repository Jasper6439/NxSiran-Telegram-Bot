# 认证工具函数（供各 API 复用）

import logging
from aiohttp import web
from database import get_db
from system.config import load_config
from system.auth import validate_session_token, validate_api_token

logger = logging.getLogger(__name__)


async def authenticate_request(request) -> tuple:
    """统一认证逻辑：session token > api token > config fallback

    Returns:
        (user_id, error_response) - 成功时返回用户ID（字符串或整数），失败时 error_response 有效
    """
    user_id = validate_session_token(request)
    if not user_id:
        user_id = validate_api_token(request)
    if not user_id:
        user_id = load_config().get('your_chat_id', 0)
    if not user_id:
        return 0, web.json_response({'success': False, 'error': '未登录'})

    # 如果 user_id 是字符串（UUID），直接返回
    # 如果是数字，需要转换为数据库内部 ID
    if isinstance(user_id, str) and not user_id.isdigit():
        return user_id, None

    # 旧的数字 ID 逻辑：将 telegram_id 转换为数据库内部 users.id
    try:
        db = get_db()
        internal_id = db.get_or_create_user(int(user_id), f"user_{user_id}")
        return internal_id, None
    except Exception:
        logging.exception("认证失败")
        return user_id, None
