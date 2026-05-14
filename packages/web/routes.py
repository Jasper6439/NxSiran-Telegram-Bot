"""
Web API Routes - 路由注册入口
所有路由处理函数已按业务域拆分到独立模块，本文件仅保留路由注册和 CORS 中间件。
"""

import os

from aiohttp import web

from packages.web.page_routes import health_check, serve_index, serve_miniapp, serve_game
from packages.web.chat_routes import api_chat, api_stats
from packages.web.media_routes import *
from packages.web.analysis_routes import *
from packages.web.auth_routes import *
from packages.web.character_routes import *
from packages.web.skills_routes import *
from packages.web.sync_routes import *


__all__ = [
    "health_check",
    "serve_index",
    "api_chat",
    "api_stats",
    "serve_miniapp",
    "serve_game",
    "api_upload_selfies",
    "api_get_selfies",
    "api_delete_selfie",
    "api_upload_voice_sample",
    "api_get_voice_samples",
    "api_delete_voice_sample",
    "api_start_voice_training",
    "api_delete_user_photo",
    "api_user_photos",
    "serve_uploaded_file",
    "api_analyze_chatlog",
    "api_analyze_video",
    "api_register",
    "api_login",
    "api_forgot_password",
    "api_verify_reset_code",
    "api_reset_password",
    "api_user_profile",
    "api_update_preferred_name",
    "api_bind_character",
    "api_get_character_bindings",
    "api_get_config",
    "api_update_config",
    "api_skills_list",
    "api_skill_toggle",
    "api_skill_install",
    "api_skill_uninstall",
    "api_quota_status",
    "api_list_characters",
    "api_switch_character",
    "api_messages_history",
    "api_messages_sync",
    "api_link_telegram",
    "api_get_linked_telegram",
    "api_send_message",
    "cors_middleware",
    "register_routes",
]


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


def register_routes(app):
    """Register all web routes"""
    app.router.add_get('/', serve_index)
    app.router.add_get('/health', health_check)
    app.router.add_post('/api/chat', api_chat)
    app.router.add_get('/api/stats', api_stats)
    app.router.add_get('/api/messages/history', api_messages_history)
    app.router.add_get('/api/messages/sync', api_messages_sync)
    app.router.add_post('/api/telegram/link', api_link_telegram)
    app.router.add_get('/api/telegram/link', api_get_linked_telegram)
    app.router.add_post('/api/messages/send', api_send_message)
    app.router.add_get('/miniapp', serve_miniapp)
    app.router.add_get('/game', serve_game)
    app.router.add_post('/api/upload-selfies', api_upload_selfies)
    app.router.add_post('/api/generate-face', api_generate_face)
    app.router.add_get('/api/selfies', api_get_selfies)
    app.router.add_post('/api/delete-selfie', api_delete_selfie)
    # [Skill: TTS v1.4.7.3] 声音语料 API
    app.router.add_post('/api/upload-voice-sample', api_upload_voice_sample)
    app.router.add_get('/api/voice-samples', api_get_voice_samples)
    app.router.add_post('/api/delete-voice-sample', api_delete_voice_sample)
    app.router.add_post('/api/start-voice-training', api_start_voice_training)
    app.router.add_post('/api/delete-user-photo', api_delete_user_photo)
    app.router.add_get('/api/user-photos', api_user_photos)
    app.router.add_get('/uploads/{folder}/{filename}', serve_uploaded_file)
    app.router.add_post('/api/analyze-chatlog', api_analyze_chatlog)
    app.router.add_post('/api/analyze-video', api_analyze_video)
    app.router.add_post('/api/register', api_register)
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/auth/login', api_login)  # 兼容前端 /api/auth/login 路径
    app.router.add_post('/api/forgot-password', api_forgot_password)
    app.router.add_post('/api/verify-reset-code', api_verify_reset_code)
    app.router.add_post('/api/reset-password', api_reset_password)
    app.router.add_post('/api/bind-character', api_bind_character)
    app.router.add_get('/api/character-bindings', api_get_character_bindings)
    app.router.add_get('/api/config', api_get_config)
    app.router.add_post('/api/config', api_update_config)
    app.router.add_get('/api/skills', api_skills_list)
    app.router.add_post('/api/skills/toggle', api_skill_toggle)
    app.router.add_post('/api/skills/install', api_skill_install)
    app.router.add_post('/api/skills/uninstall', api_skill_uninstall)
    app.router.add_get('/api/quota', api_quota_status)
    app.router.add_get('/api/characters', api_list_characters)
    app.router.add_post('/api/characters/switch', api_switch_character)
    app.router.add_get('/api/user/profile', api_user_profile)
    app.router.add_post('/api/user/preferred-name', api_update_preferred_name)
    app.router.add_post('/api/user/bind-telegram', api_bind_telegram)

    # Static files
    app.router.add_static('/static', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'static'))

    # web-v2 静态资源 (Vite 构建产物: JS/CSS/images)
    web_v2_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'web-v2', 'dist')
    web_v2_assets = os.path.join(web_v2_dist, 'assets')
    if os.path.isdir(web_v2_assets):
        app.router.add_static('/web-v2/assets', web_v2_assets)
    else:
        import logging
        logging.warning(f"[Routes] web-v2/assets 目录不存在: {web_v2_assets}")

    # web-v2 SPA fallback: 所有未匹配路由返回 index.html (前端路由)
    async def web_v2_fallback(request):
        try:
            with open(os.path.join(web_v2_dist, 'index.html'), 'r', encoding='utf-8') as f:
                return web.Response(text=f.read(), content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="web-v2 not found", status=404)

    # 注册常见前端路由的 fallback
    for _path in ['/game', '/chat', '/settings', '/home']:
        app.router.add_get(_path, web_v2_fallback)

    # CORS middleware
    app.middlewares.append(cors_middleware)
