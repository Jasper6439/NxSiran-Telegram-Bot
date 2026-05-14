"""
页面服务模块
包含健康检查、主页、Mini App、游戏页面的路由处理函数。
v1.6.0: 主页指向 web-v2 (React SPA)，带降级容错
"""

import os
import traceback

from aiohttp import web


def _get_workspace_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_web_v2_index():
    """尝试读取 web-v2 的 index.html，失败返回 None"""
    try:
        index_path = os.path.join(_get_workspace_root(), 'web-v2', 'dist', 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception:
        traceback.print_exc()
    return None


async def health_check(request):
    from system.config import BOT_VERSION, APP_NAME
    return web.Response(text=f"🟢 {APP_NAME}在线 v{BOT_VERSION}")


async def serve_index(request):
    """提供 web-v2 主页 (React SPA)，降级到旧版或提示页"""
    # 优先尝试 web-v2
    html = _get_web_v2_index()
    if html:
        return web.Response(text=html, content_type='text/html')

    # web-v2 不可用时返回提示页
    return web.Response(
        text="""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>恋爱至上主义区域</title>
<style>body{font-family:system-ui;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;background:#f5f0eb;color:#333}
.card{text-align:center;padding:2rem;border-radius:1rem;background:rgba(255,255,255,0.8);backdrop-filter:blur(10px);box-shadow:0 4px 20px rgba(0,0,0,0.1)}
h1{color:#8A2BE2;margin-bottom:0.5rem}p{color:#666}</style></head>
<body><div class="card"><h1>恋爱至上主义区域</h1><p>Web 界面正在部署中，请稍后再试...</p></div></body></html>""",
        content_type='text/html'
    )


async def serve_miniapp(request):
    """Mini App 已融合到 web-v2，重定向到首页"""
    raise web.HTTPFound('/')


async def serve_game(request):
    """游戏已融合到 web-v2，重定向到首页 /game"""
    raise web.HTTPFound('/game')
