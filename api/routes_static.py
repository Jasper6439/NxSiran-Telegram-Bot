"""
api/routes_static.py - 静态文件服务 + SPA fallback (v1.7)
==========================================================
提供 web-v2 构建产物的静态文件服务，支持 SPA 路由 fallback。
注意：SPA fallback 使用 middleware 实现，避免与 FastAPI 内置路由冲突。
"""

import os

from fastapi import APIRouter, Request, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

router = APIRouter(tags=["static"])

# web-v2 构建产物目录
WEB_DIST = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web-v2", "dist")


def mount_static_files(app: FastAPI):
    """在 app 级别挂载静态文件（确保优先级高于 API 路由）"""
    # 挂载静态文件目录（/assets 对应 web-v2/dist/assets）
    _assets_dir = os.path.join(WEB_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")
    
    # 挂载 icons 目录
    _icons_dir = os.path.join(WEB_DIST, "icons")
    if os.path.isdir(_icons_dir):
        app.mount("/icons", StaticFiles(directory=_icons_dir), name="icons")


@router.get("/")
async def serve_index():
    """提供 web-v2 的 index.html"""
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


@router.get("/miniapp")
async def serve_miniapp():
    """Mini App 入口"""
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


@router.get("/game")
async def serve_game():
    """游戏入口"""
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    """SPA fallback 中间件。

    对于所有未匹配 FastAPI 路由的 GET 请求，
    返回 index.html（前端路由处理）。
    排除 /api/、/assets/、/icons/ 等路径。
    """

    # 不需要 fallback 的路径前缀
    SKIP_PREFIXES = ("/api/", "/assets/", "/icons/", "/docs", "/redoc", "/openapi.json")

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # 只对 404 的 GET 请求做 fallback
        if response.status_code == 404 and request.method == "GET":
            path = request.url.path
            # 跳过 API 和静态资源路径
            if not any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES):
                index_path = os.path.join(WEB_DIST, "index.html")
                if os.path.isfile(index_path):
                    return FileResponse(index_path)

        return response
