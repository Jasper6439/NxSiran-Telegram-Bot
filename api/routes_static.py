"""
api/routes_static.py - 静态文件服务 + SPA fallback (v1.7)
==========================================================
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
    """在 app 级别挂载静态文件"""
    _assets_dir = os.path.join(WEB_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    _icons_dir = os.path.join(WEB_DIST, "icons")
    if os.path.isdir(_icons_dir):
        app.mount("/icons", StaticFiles(directory=_icons_dir), name="icons")


@router.get("/")
async def serve_index():
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


@router.get("/miniapp")
async def serve_miniapp():
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


@router.get("/game")
async def serve_game():
    return FileResponse(os.path.join(WEB_DIST, "index.html"))


@router.get("/registerSW.js")
async def serve_register_sw():
    return FileResponse(
        os.path.join(WEB_DIST, "registerSW.js"),
        media_type="application/javascript"
    )


@router.get("/sw.js")
async def serve_sw():
    return FileResponse(
        os.path.join(WEB_DIST, "sw.js"),
        media_type="application/javascript"
    )


@router.get("/manifest.webmanifest")
async def serve_manifest_webmanifest():
    return FileResponse(
        os.path.join(WEB_DIST, "manifest.webmanifest"),
        media_type="application/manifest+json"
    )


@router.get("/manifest.json")
async def serve_manifest_json():
    return FileResponse(
        os.path.join(WEB_DIST, "manifest.json"),
        media_type="application/json"
    )


@router.get("/favicon.svg")
async def serve_favicon():
    return FileResponse(
        os.path.join(WEB_DIST, "favicon.svg"),
        media_type="image/svg+xml"
    )


@router.get("/icons/chayewoon.jpg")
async def serve_chayewoon_icon():
    """前端期待的 chayewoon.jpg - 用 SVG 图标替代"""
    return FileResponse(
        os.path.join(WEB_DIST, "icons", "icon.svg"),
        media_type="image/svg+xml"
    )


@router.get("/vite.svg")
async def serve_vite_svg():
    """Vite 图标 - 用 favicon.svg 作为 fallback"""
    return FileResponse(
        os.path.join(WEB_DIST, "favicon.svg"),
        media_type="image/svg+xml"
    )


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    """SPA fallback 中间件"""

    SKIP_PREFIXES = (
        "/api/", "/assets/", "/icons/", "/docs", "/redoc", "/openapi.json",
        "/registerSW.js", "/sw.js", "/manifest", "/favicon", "/vite.svg"
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if response.status_code == 404 and request.method == "GET":
            path = request.url.path
            if not any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES):
                index_path = os.path.join(WEB_DIST, "index.html")
                if os.path.isfile(index_path):
                    return FileResponse(index_path)

        return response
