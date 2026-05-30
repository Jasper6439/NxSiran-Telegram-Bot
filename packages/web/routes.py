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
from packages.web.mobile_routes import *
logger = logging.getLogger(__name__)


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
    # v1.6.5 — 移动端触控 API
    "api_mobile_dpad_move",
    "api_mobile_tap_interact",
    "api_mobile_swipe",
    "api_mobile_config",
]


# CORS 中间件 - 允许 Telegram Mini App 跨域访问
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    origin = request.headers.get('Origin', '')
    if origin:
        response.headers['Access-Control-Allow-Origin'] = origin
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


async def api_version(request):
    """获取后端版本号"""
    try:
        from system.config import BOT_VERSION
        return web.json_response({
            'success': True,
            'version': BOT_VERSION,
            'app_name': '恋爱至上主义区域'
        })
    except Exception as e:
        logger.error(f"{type(e).__name__}: {e}")
        return web.json_response({
            'success': False,
            'version': 'unknown',
            'error': 'Internal error'
        })


def register_routes(app):
    """Register all web routes"""
    app.router.add_get('/', serve_index)
    app.router.add_get('/health', health_check)
    app.router.add_get('/api/version', api_version)
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
    app.router.add_get('/api/user/info', api_user_profile)  # 别名
    app.router.add_post('/api/user/preferred-name', api_update_preferred_name)
    app.router.add_post('/api/user/bind-telegram', api_bind_telegram)

    # v1.6.5 — 移动端触控 API
    app.router.add_post('/api/mobile/dpad', api_mobile_dpad_move)
    app.router.add_post('/api/mobile/tap', api_mobile_tap_interact)
    app.router.add_post('/api/mobile/swipe', api_mobile_swipe)
    app.router.add_get('/api/mobile/config', api_mobile_config)

    # Static files
    app.router.add_static('/static', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'static'))

    # web-v2 静态资源 (Vite 构建产物: JS/CSS/images)
    # 注意：Vite 构建的 index.html 中资源路径是 /assets/...，需要映射到 web-v2/dist/assets
    web_v2_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'web-v2', 'dist')
    web_v2_assets = os.path.join(web_v2_dist, 'assets')
    if os.path.isdir(web_v2_assets):
        app.router.add_static('/assets', web_v2_assets)
        app.router.add_static('/icons', web_v2_dist)  # icons 目录
    else:
        import logging
        logging.warning(f"[Routes] web-v2/assets 目录不存在: {web_v2_assets}")

    # PWA 和其他静态资源
    for filename in ['registerSW.js', 'manifest.webmanifest', 'manifest.json', 'favicon.svg', 'vite.svg', 'sw.js']:
        fpath = os.path.join(web_v2_dist, filename)
        if os.path.isfile(fpath):
            content_type = 'application/javascript' if filename.endswith('.js') else \
                          'application/manifest+json' if filename.endswith('.webmanifest') or filename.endswith('.json') else \
                          'image/svg+xml' if filename.endswith('.svg') else 'text/plain'
            
            def make_handler(fp, ct):
                async def handler(request):
                    with open(fp, 'r', encoding='utf-8') as f:
                        return web.Response(text=f.read(), content_type=ct)
                return handler
            
            app.router.add_get(f'/{filename}', make_handler(fpath, content_type))

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
