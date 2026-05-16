"""
api/__init__.py - FastAPI 应用工厂 (v1.7)
==========================================
创建并配置 FastAPI 应用实例，注册所有路由和中间件。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例，注册路由和中间件。

    Returns:
        配置好的 FastAPI 应用实例
    """
    app = FastAPI(
        title="LoveSupremacy Universe",
        version="1.7.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS 中间件 - 允许所有来源跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from api.routes_user import router as user_router
    from api.routes_chat import router as chat_router
    from api.routes_static import router as static_router, SPAFallbackMiddleware
    from api.routes_game import router as game_router
    from api.routes_character import router as character_router
    from api.routes_sync import router as sync_router
    from api.routes_media import router as media_router
    from api.routes_world import router as world_router

    app.include_router(user_router)
    app.include_router(chat_router)
    app.include_router(game_router)
    app.include_router(character_router)
    app.include_router(sync_router)
    app.include_router(media_router)
    app.include_router(world_router)
    app.include_router(static_router)

    # SPA fallback 中间件（必须在路由注册之后添加）
    app.add_middleware(SPAFallbackMiddleware)

    return app
