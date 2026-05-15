#!/usr/bin/env python3
"""
独立 Webhook + Bridge 服务 - v1.4.12.13
不依赖 bot 主进程，即使 bot 崩溃也能接收部署请求和执行远程命令

端口: 8082 (可通过 WEBHOOK_PORT 环境变量修改)
功能:
- GitHub Webhook 接收
- 自动 git pull + 重启 bot 服务
- Bridge 远程命令执行（SOLO -> VM）
- 健康检查
"""

import asyncio
import hashlib
import hmac
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
BRIDGE_TOKEN = os.environ.get('BRIDGE_TOKEN', '')
BOT_VERSION = 'unknown'  # 默认值，会在 deploy_status 中动态获取

# Bridge 命令队列
pending_commands = {}  # {vm_id: [commands]}
bridge_results = {}    # {command_id: result}  # 存储最近的结果


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

        # 1. 清理 Python 缓存
        logger.info("清理 Python 缓存...")
        subprocess.run(
            ['find', PROJECT_DIR, '-type', 'd', '-name', '__pycache__', '-exec', 'rm', '-rf', '{}', '+'],
            capture_output=True,
            text=True,
            timeout=30
        )
        subprocess.run(
            ['find', PROJECT_DIR, '-type', 'f', '-name', '*.pyc', '-delete'],
            capture_output=True,
            text=True,
            timeout=30
        )

        # 2. Git pull
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

        # 2.5 构建 web-v2 (如果存在 web-v2 目录且没有 dist)
        web_v2_dir = os.path.join(PROJECT_DIR, 'web-v2')
        web_v2_dist = os.path.join(web_v2_dir, 'dist', 'index.html')
        if os.path.isdir(web_v2_dir) and not os.path.exists(web_v2_dist):
            logger.info("检测到 web-v2 无构建产物，执行 npm install && npm run build...")
            npm_install = subprocess.run(
                ['npm', 'install'],
                cwd=web_v2_dir,
                capture_output=True, text=True, timeout=120
            )
            if npm_install.returncode != 0:
                logger.error(f"web-v2 npm install 失败: {npm_install.stderr}")
            else:
                npm_build = subprocess.run(
                    ['npm', 'run', 'build'],
                    cwd=web_v2_dir,
                    capture_output=True, text=True, timeout=120
                )
                if npm_build.returncode != 0:
                    logger.error(f"web-v2 npm run build 失败: {npm_build.stderr}")
                else:
                    logger.info("✅ web-v2 构建完成")
        elif os.path.exists(web_v2_dist):
            logger.info("web-v2 dist 已存在，跳过构建")

        # 3. 重启 bot 服务
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

        # 4. 等待服务启动并验证
        await asyncio.sleep(3)
        result = subprocess.run(
            ['systemctl', 'is-active', BOT_SERVICE],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.stdout.strip() != 'active':
            logger.error(f"服务启动失败: {result.stdout.strip()}")
        else:
            logger.info("✅ 部署完成，服务已启动")

    except Exception as e:
        logger.error(f"部署错误: {e}")


async def manual_deploy(request):
    """手动触发部署"""
    try:
        # 简单的 token 验证
        token = request.query.get('token', '')
        if token != WEBHOOK_SECRET:
            return web.json_response({'error': 'auth failed'}, status=401)

        logger.info("手动触发部署")
        asyncio.create_task(deploy())

        return web.json_response({'status': 'deploying'})

    except Exception as e:
        logger.error(f"部署状态错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


# ============================================================
# Bridge 路由（远程命令执行）
# ============================================================

async def bridge_send(request):
    """SOLO 发送命令到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', 'default')
        auth_token = data.get('token', '')
        command = data.get('command', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)
        if not command:
            return web.json_response({'error': 'no command'}, status=400)

        import uuid
        cmd_id = str(uuid.uuid4())[:8]
        if vm_id not in pending_commands:
            pending_commands[vm_id] = []
        pending_commands[vm_id].append({
            'id': cmd_id,
            'command': command,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"[Bridge] 命令入队: [{cmd_id}] {command[:80]}...")
        return web.json_response({'status': 'queued', 'id': cmd_id, 'vm_id': vm_id})

    except Exception as e:
        logger.error(f"[Bridge] 发送错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_poll(request):
    """VM 轮询获取命令"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', 'default')
        auth_token = data.get('token', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        commands = pending_commands.pop(vm_id, [])
        return web.json_response({
            'status': 'ok',
            'commands': commands,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"[Bridge] 轮询错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_result(request):
    """VM 回传命令执行结果"""
    try:
        data = await request.json()
        auth_token = data.get('token', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        cmd_id = data.get('id', '')
        command = data.get('command', '')
        returncode = data.get('returncode', -1)
        stdout = data.get('stdout', '')
        stderr = data.get('stderr', '')

        bridge_results[cmd_id] = {
            'command': command,
            'returncode': returncode,
            'stdout': stdout[:2000],
            'stderr': stderr[:1000],
            'timestamp': datetime.now().isoformat()
        }

        # 只保留最近 50 条结果
        if len(bridge_results) > 50:
            oldest = list(bridge_results.keys())[:len(bridge_results) - 50]
            for k in oldest:
                del bridge_results[k]

        logger.info(f"[Bridge] 结果回传: [{cmd_id}] rc={returncode} | {stdout[:100]}")
        return web.json_response({'status': 'received'})

    except Exception as e:
        logger.error(f"[Bridge] 结果回传错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_get_result(request):
    """获取命令执行结果"""
    try:
        cmd_id = request.match_info.get('cmd_id', '')
        auth_token = request.query.get('token', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        result = bridge_results.get(cmd_id)
        if result:
            return web.json_response(result)
        else:
            return web.json_response({'status': 'pending'}, status=202)

    except Exception as e:
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

        # 动态读取版本号
        version = BOT_VERSION
        try:
            result = subprocess.run(
                ['python3', '-c', 'from system.config import BOT_VERSION; print(BOT_VERSION)'],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                version = result.stdout.strip()
        except Exception:
            pass

        return web.json_response({
            'status': 'ok',
            'project_dir': PROJECT_DIR,
            'last_commit': last_commit,
            'bot_service': BOT_SERVICE,
            'service_status': service_status,
            'version': version
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

    # Bridge 路由
    app.router.add_post('/bridge/send', bridge_send)
    app.router.add_post('/bridge/poll', bridge_poll)
    app.router.add_post('/bridge/result', bridge_result)
    app.router.add_get('/bridge/result/{cmd_id}', bridge_get_result)

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
