"""
消息同步 API 模块
包含 Web <-> Telegram 双向同步的消息历史、同步、Telegram 关联、发送消息、AI 回复等功能。
"""

import asyncio
import logging

from datetime import datetime

from aiohttp import web

from config import *
from system.auth import *
from characters.chat_history import *
from database import get_db
from game_api import authenticate_request


async def api_messages_history(request):
    """获取聊天历史消息 - 用于Web端加载历史"""
    try:
        # 直接使用 session token 获取 chat_id（与 api_chat 一致）
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({
                'messages': [],
                'total_count': 0,
                'linked': False,
                'error': '未登录'
            })

        limit = int(request.query.get('limit', 50))
        history = load_chat_history(user_id)

        if len(history) > limit:
            history = history[-limit:]

        messages = [{
            'role': msg.get('role', 'user'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', '')
        } for msg in history]

        return web.json_response({
            'messages': messages,
            'total_count': len(messages),
            'linked': True
        })
    except Exception as e:
        logging.error(f"[消息历史] 获取失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_messages_sync(request):
    """同步新消息 - Web端拉取新消息"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'messages': [], 'total_count': 0, 'linked': False})

        since = int(request.query.get('since', 0))
        history = load_chat_history(user_id)
        total_count = len(history)

        if since >= total_count:
            return web.json_response({
                'messages': [],
                'total_count': total_count,
                'linked': True
            })

        new_messages = history[since:]
        messages = [{
            'role': msg.get('role', 'user'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', '')
        } for msg in new_messages]

        return web.json_response({
            'messages': messages,
            'total_count': total_count,
            'linked': True
        })
    except Exception as e:
        logging.error(f"[消息同步] 同步失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_link_telegram(request):
    """关联 Telegram 账号 - 设置用户的 telegram_id"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        telegram_id = data.get('telegram_id')

        if not telegram_id:
            return web.json_response({'error': 'telegram_id 不能为空'}, status=400)

        try:
            telegram_id = int(telegram_id)
        except (ValueError, TypeError):
            return web.json_response({'error': 'telegram_id 必须是数字'}, status=400)

        db = get_db()
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE users SET telegram_id = ? WHERE id = ?",
                (telegram_id, user_id)
            )

        return web.json_response({
            'success': True,
            'telegram_id': telegram_id,
            'message': f'已关联 Telegram ID: {telegram_id}'
        })
    except Exception as e:
        logging.error(f"[关联Telegram] 失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_get_linked_telegram(request):
    """获取已关联的 Telegram ID"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()
        user = db.get_user_by_id(user_id)

        return web.json_response({
            'telegram_id': user.get('telegram_id') if user else None,
            'linked': user and bool(user.get('telegram_id'))
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def api_send_message(request):
    """从 Web 端发送消息到 Telegram"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        message = data.get('message', '').strip()

        if not message:
            return web.json_response({'error': '消息不能为空'}, status=400)

        if len(message) > 2000:
            return web.json_response({'error': '消息过长 (最大2000字符)'}, status=400)

        # Get user's telegram_id
        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user or not user.get('telegram_id'):
            return web.json_response({
                'error': '请先关联 Telegram 账号',
                'linked': False
            }, status=403)

        telegram_id = user['telegram_id']

        # Save user message to chat history
        from characters.chat_history import get_history, save_chat_history
        history = get_history(telegram_id)
        history.append({"role": "user", "content": message})
        if len(history) > 100:
            history = history[-100:]
        save_chat_history(telegram_id, history)

        # Trigger AI reply asynchronously (don't wait for it)
        asyncio.create_task(generate_ai_reply(telegram_id, message))

        return web.json_response({
            'success': True,
            'message': '消息已发送，AI 正在思考...',
            'timestamp': datetime.now().isoformat(),
            'pending_reply': True
        })
    except Exception as e:
        logging.error(f"[发送消息] 失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def generate_ai_reply(telegram_id: int, user_message: str):
    """生成 AI 回复并保存到聊天记录"""
    try:
        from characters.ai_client import call_ai
        from characters.chat_history import load_chat_history, append_bot_message
        from characters import get_current_character

        # Load recent chat history for context
        history = load_chat_history(telegram_id)
        recent_history = history[-10:] if len(history) > 10 else history

        # Build messages for AI
        messages = []
        for msg in recent_history:
            role = 'user' if msg.get('role') == 'user' else 'assistant'
            messages.append({'role': role, 'content': msg.get('content', '')})

        # Add current user message
        messages.append({'role': 'user', 'content': user_message})

        # Get character info
        char = get_current_character()
        char_name = char.config.name if char and hasattr(char, 'config') else '车如云'

        # Build system prompt
        system_prompt = build_web_chat_system_prompt(char)

        # Call AI
        response = await call_ai(
            messages=messages,
            system_prompt=system_prompt,
            temperature=0.85,
            max_tokens=300
        )

        if response and not response.startswith('ERROR'):
            append_bot_message(telegram_id, response)
            await push_to_telegram(telegram_id, response)
            logging.info(f"[AI回复] 已生成并保存到用户 {telegram_id}")
        else:
            fallback = f"{char_name}正在思考..."
            append_bot_message(telegram_id, fallback)
            await push_to_telegram(telegram_id, fallback)

    except Exception as e:
        logging.error(f"[AI回复] 生成失败: {e}")


def build_web_chat_system_prompt(char):
    """构建 Web 聊天的系统提示词"""
    char_name = char.config.name if char and hasattr(char, 'config') else '车如云'
    char_personality = char.config.personality if char and hasattr(char, 'config') else ''

    prompt = f"""你是{char_name}，正在通过 Web 聊天界面与用户对话。

角色设定：
{char_personality}

当前场景：
- 用户正在使用网页版 Mini App 与你聊天
- 保持角色性格，用第一人称回复
- 回复要简洁自然，适合聊天界面
- 可以适当使用表情符号增加亲和力

回复要求：
- 长度控制在 100-200 字
- 语气要符合角色性格
- 不要暴露你是 AI"""

    return prompt


async def push_to_telegram(telegram_id: int, message: str):
    """将 AI 回复推送到 Telegram"""
    try:
        from config import TELEGRAM_TOKEN
        import aiohttp

        if not TELEGRAM_TOKEN:
            logging.warning("[推送Telegram] TELEGRAM_TOKEN 未设置")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json={
                'chat_id': telegram_id,
                'text': message,
                'parse_mode': 'HTML'
            }) as resp:
                if resp.status != 200:
                    logging.error(f"[推送Telegram] 失败: {await resp.text()}")
                else:
                    logging.info(f"[推送Telegram] 成功发送到 {telegram_id}")

    except Exception as e:
        logging.error(f"[推送Telegram] 错误: {e}")
