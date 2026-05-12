#!/usr/bin/env python3
"""
独立 Webhook 服务 - v1.4.8.1
不依赖 bot 主进程，即使 bot 崩溃也能接收部署请求

端口: 8082 (可通过 WEBHOOK_PORT 环境变量修改)
功能:
- GitHub Webhook 接收
- 自动 git pull + 重启 bot 服务
- 健康检查
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Webhook] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入 aiohttp
try:
    from aiohttp import web
except ImportError:
    logger.error("aiohttp 未安装，请执行: pip install aiohttp")
    sys.exit(1)

# 配置
WEBHOOK_PORT = int(os.environ.get('WEBHOOK_PORT', 8082))
WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
PROJECT_DIR = os.environ.get('PROJECT_DIR', '/root/NxSiran-Telegram-Bot')
BOT_SERVICE = os.environ.get('BOT_SERVICE', 'nxsiran-bot.service')


# ============================================================
# API Handlers
# ============================================================

async def health_check(request):
    """健康检查"""
    return web.json_response({
        'status': 'ok',
        'service': 'nxsiran-webhook',
        'version': '1.4.8.1',
        'timestamp': datetime.now().isoformat()
    })


async def github_webhook(request):
    """接收 GitHub Webhook"""
    try:
        # 验证签名
        if WEBHOOK_SECRET:
            signature = request.headers.get('X-Hub-Signature-256', '')
            body = await request.read()
            expected = 'sha256=' + hmac.new(
                WEBHOOK_SECRET.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning("无效的 webhook 签名")
                return web.json_response({'error': 'invalid signature'}, status=403)

        # 检查事件类型
        event = request.headers.get('X-GitHub-Event', '')
        if event != 'push':
            return web.json_response({'status': 'ignored', 'event': event})

        # 解析 payload
        try:
            payload = await request.json()
        except:
            return web.json_response({'error': 'invalid json'}, status=400)

        repo = payload.get('repository', {}).get('full_name', 'unknown')
        ref = payload.get('ref', '')
        commits = payload.get('commits', [])

        logger.info(f"收到 push: {repo} -> {ref} ({len(commits)} commits)")

        # 只部署 master 分支
        if ref != 'refs/heads/master':
            logger.info(f"跳过非 master 分支: {ref}")
            return web.json_response({'status': 'skipped', 'ref': ref})

        # 异步执行部署
        asyncio.create_task(deploy())

        return web.json_response({
            'status': 'deploying',
            'repo': repo,
            'commits': len(commits)
        })

    except Exception as e:
        logger.error(f"Webhook 处理错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def deploy():
    """执行部署"""
    try:
        logger.info("开始部署...")
        logger.info(f"项目目录: {PROJECT_DIR}")

        # 1. Git pull
        logger.info("执行 git pull...")
        result = subprocess.run(
            ['git', 'pull'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            logger.error(f"git pull 失败: {result.stderr}")
            return
        logger.info(f"git pull: {result.stdout.strip()}")

        # 2. 重启 bot 服务
        logger.info(f"重启服务: {BOT_SERVICE}")
        result = subprocess.run(
            ['systemctl', 'restart', BOT_SERVICE],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.error(f"重启服务失败: {result.stderr}")
            return

        logger.info("✅ 部署完成")

    except Exception as e:
        logger.error(f"部署错误: {e}")


async def manual_deploy(request):
    """手动触发部署"""
    try:
        # 简单的 token 验证
        token = request.query.get('token', '')
        if token != WEBHOOK_SECRET and token != 'nxsiran_deploy_2024':
            return web.json_response({'error': 'auth failed'}, status=401)

        logger.info("手动触发部署")
        asyncio.create_task(deploy())

        return web.json_response({'status': 'deploying'})

    except Exception as e:
        logger.error(f"手动部署错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def deploy_status(request):
    """部署状态"""
    try:
        # 检查 git 状态
        result = subprocess.run(
            ['git', 'log', '-1', '--oneline'],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        last_commit = result.stdout.strip() if result.returncode == 0 else 'unknown'

        # 检查服务状态
        result = subprocess.run(
            ['systemctl', 'is-active', BOT_SERVICE],
            capture_output=True,
            text=True,
            timeout=10
        )
        service_status = result.stdout.strip() if result.returncode == 0 else 'inactive'

        return web.json_response({
            'status': 'ok',
            'project_dir': PROJECT_DIR,
            'last_commit': last_commit,
            'bot_service': BOT_SERVICE,
            'service_status': service_status,
            'version': '1.4.8.1'
        })

    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


# ============================================================
# Main
# ============================================================

async def create_app():
    """创建 aiohttp 应用"""
    app = web.Application()

    # 路由
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_post('/webhook/github', github_webhook)
    app.router.add_get('/deploy', manual_deploy)
    app.router.add_post('/deploy', manual_deploy)
    app.router.add_get('/status', deploy_status)

    return app


def main():
    """主入口"""
    logger.info(f"启动 Webhook 服务，端口: {WEBHOOK_PORT}")
    logger.info(f"项目目录: {PROJECT_DIR}")
    logger.info(f"Bot 服务: {BOT_SERVICE}")

    # 确保项目目录存在
    if not Path(PROJECT_DIR).exists():
        logger.error(f"项目目录不存在: {PROJECT_DIR}")
        sys.exit(1)

    # 启动服务
    web.run_app(create_app(), host='0.0.0.0', port=WEBHOOK_PORT, print=None)


if __name__ == '__main__':
    main()
