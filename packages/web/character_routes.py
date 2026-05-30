"""
角色管理 API 模块
包含角色绑定、获取绑定、配置获取/更新、角色列表/切换等 API 端点。
"""

import logging

from aiohttp import web

from system.config import (
    load_config, save_config,
    TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_KEY, AI_API_BASE,
)
from system.auth import validate_session_token, validate_api_token, is_admin_user
from characters import (
    get_current_character,
    set_current_character,
    list_characters,
)


async def api_bind_character(request):
    """绑定角色 Bot Token - v1.4.12.13: 绑定该角色对应的 Telegram Bot Token"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        data = await request.json()
        character_id = data.get('character_id', '')
        bot_token = data.get('bot_token', '').strip()

        if not character_id:
            return web.json_response({'success': False, 'error': '角色ID不能为空'})
        if not bot_token:
            return web.json_response({'success': False, 'error': 'Bot Token 不能为空'})

        # 验证 Bot Token 格式（数字:字母数字混合）
        if ':' not in bot_token:
            return web.json_response({'success': False, 'error': 'Bot Token 格式不正确，应为 数字:字母数字混合'})

        from system.auth import bind_character_bot_token
        success, message = bind_character_bot_token(user_id, character_id, bot_token)

        if success:
            return web.json_response({'success': True, 'message': message})
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[绑定角色] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})


async def api_get_character_bindings(request):
    """获取用户的角色绑定"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        from system.auth import get_user_character_bindings
        bindings = get_user_character_bindings(user_id)

        return web.json_response({
            'success': True,
            'bindings': bindings
        })
    except Exception as e:
        logging.error(f"[获取角色绑定] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})


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
            'smtp_email': config.get('smtp_email', ''),
        }
        return web.json_response({'success': True, 'config': safe_config})
    except Exception as e:
        logging.error(f"[配置获取] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})


async def api_update_config(request):
    """Mini App更新配置API - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可修改配置'})

        data = await request.json()
        config = load_config()

        # 允许更新的字段
        updatable = ['telegram_token', 'chat_id', 'ai_api_key', 'ai_api_base', 'admin_username', 'admin_password', 'public_url', 'smtp_email', 'smtp_password']
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
        logging.error(f"[配置更新] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})


async def api_list_characters(request):
    """列出所有可用角色"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        characters = list_characters()
        current = get_current_character()
        return web.json_response({
            'success': True,
            'characters': characters,
            'current': current.config.id if current else None,
            'count': len(characters),
        })
    except Exception as e:
        logging.error(f"[角色列表] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})


async def api_switch_character(request):
    """切换当前角色"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

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
        logging.error(f"[切换角色] 错误: {e}")
        return web.json_response({'success': False, 'error': 'Character error'})
