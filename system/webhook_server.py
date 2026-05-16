#!/usr/bin/env python3
"""
独立 Webhook + Bridge 服务 - v1.9.2.1
不依赖 bot 主进程，即使 bot 崩溃也能接收部署请求和执行远程命令

端口: 8082 (可通过 WEBHOOK_PORT 环境变量修改)
功能:
- GitHub Webhook 接收（签名验证 + 限流保护）
- 自动 git pull + 重启 bot 服务（原子操作 + 回滚）
- Bridge 远程命令执行（SOLO -> VM）
- 健康检查

v1.9.2.1 加固:
- 限流保护: 60 秒冷却窗口 + 部署锁
- 安全性: GitHub HMAC 签名验证 + Bearer Token 认证
- 日志增强: 请求来源/耗时/结果全链路记录
- 部署原子性: git fetch + reset --hard，失败自动回滚
"""

import asyncio
import hashlib
import hmac
import logging
import os
import subprocess
import sys
import time
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

# ============================================================
# 配置
# ============================================================

WEBHOOK_PORT = int(os.environ.get('WEBHOOK_PORT', 8082))
WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')
PROJECT_DIR = os.environ.get('PROJECT_DIR', '/opt/LoveSupremacy-Telegram-Bot')
BOT_SERVICE = os.environ.get('BOT_SERVICE', 'nx_siran.service')
BRIDGE_TOKEN = os.environ.get('BRIDGE_TOKEN', '')
BOT_VERSION = 'unknown'

# ============================================================
# 限流与部署锁
# ============================================================

_deploy_lock = asyncio.Lock()           # 部署互斥锁
_last_deploy_time = 0.0                 # 上次部署时间戳
_DEPLOY_COOLDOWN = 60                   # 部署冷却窗口（秒）
_last_request_time = {}                  # IP 级限流: {ip: timestamp}
_REQUEST_COOLDOWN = 10                   # 同一 IP 最小请求间隔（秒）
_MAX_REQUEST_COOLDOWN = 10               # 最大请求间隔记录数


def _check_rate_limit(client_ip: str) -> tuple:
    """检查请求频率限制

    Returns:
        (allowed: bool, reason: str)
    """
    now = time.time()

    # 清理过期的 IP 记录
    expired = [ip for ip, t in _last_request_time.items() if now - t > 300]
    for ip in expired:
        del _last_request_time[ip]

    # 同一 IP 限流
    if client_ip in _last_request_time:
        elapsed = now - _last_request_time[client_ip]
        if elapsed < _REQUEST_COOLDOWN:
            return False, f"请求过于频繁，请等待 {int(_REQUEST_COOLDOWN - elapsed)} 秒"

    _last_request_time[client_ip] = now
    return True, ""


def _check_deploy_cooldown() -> tuple:
    """检查部署冷却窗口

    Returns:
        (allowed: bool, reason: str)
    """
    global _last_deploy_time
    now = time.time()

    if _deploy_lock.locked():
        return False, "部署任务正在执行中，请等待完成"

    if now - _last_deploy_time < _DEPLOY_COOLDOWN:
        remaining = int(_DEPLOY_COOLDOWN - (now - _last_deploy_time))
        return False, f"部署冷却中，请等待 {remaining} 秒"

    return True, ""


# ============================================================
# Bridge 命令队列
# ============================================================

pending_commands = {}  # {vm_id: [commands]}
bridge_results = {}    # {command_id: result}


# ============================================================
# API Handlers
# ============================================================

async def health_check(request):
    """健康检查"""
    return web.json_response({
        'status': 'ok',
        'service': 'lovesupremacy-webhook',
        'version': '1.9.2.1',
        'deploy_lock': _deploy_lock.locked(),
        'timestamp': datetime.now().isoformat()
    })


async def github_webhook(request):
    """接收 GitHub Webhook（带签名验证 + 限流保护）"""
    client_ip = request.remote or 'unknown'

    try:
        # 1. 限流检查
        allowed, reason = _check_rate_limit(client_ip)
        if not allowed:
            logger.warning(f"[限流] {client_ip}: {reason}")
            return web.json_response({'error': reason}, status=429)

        # 2. 验证 GitHub HMAC 签名
        if WEBHOOK_SECRET:
            signature = request.headers.get('X-Hub-Signature-256', '')
            body = await request.read()
            expected = 'sha256=' + hmac.new(
                WEBHOOK_SECRET.encode(), body, hashlib.sha256
            ).hexdigest()
            if not hmac.compare_digest(signature, expected):
                logger.warning(f"[安全] 无效的 webhook 签名, IP={client_ip}")
                return web.json_response({'error': 'invalid signature'}, status=403)
        else:
            body = await request.read()
            logger.warning("[安全] WEBHOOK_SECRET 未配置，跳过签名验证")

        # 3. 检查事件类型
        event = request.headers.get('X-GitHub-Event', '')
        if event != 'push':
            return web.json_response({'status': 'ignored', 'event': event})

        # 4. 解析 payload
        try:
            import json
            payload = json.loads(body)
        except Exception:
            return web.json_response({'error': 'invalid json'}, status=400)

        repo = payload.get('repository', {}).get('full_name', 'unknown')
        ref = payload.get('ref', '')
        commits = payload.get('commits', [])
        pusher = payload.get('pusher', {}).get('name', 'unknown')

        logger.info(
            f"[Webhook] push 事件: repo={repo} ref={ref} "
            f"commits={len(commits)} pusher={pusher} ip={client_ip}"
        )

        # 5. 只部署 master 分支
        if ref != 'refs/heads/master':
            logger.info(f"[Webhook] 跳过非 master 分支: {ref}")
            return web.json_response({'status': 'skipped', 'ref': ref})

        # 6. 部署冷却检查
        allowed, reason = _check_deploy_cooldown()
        if not allowed:
            logger.warning(f"[限流] 部署被拒绝: {reason}")
            return web.json_response({'error': reason}, status=429)

        # 7. 异步执行部署
        asyncio.create_task(deploy())

        return web.json_response({
            'status': 'deploying',
            'repo': repo,
            'commits': len(commits)
        })

    except Exception as e:
        logger.error(f"[Webhook] 处理错误: {e}", exc_info=True)
        return web.json_response({'error': str(e)}, status=500)


async def deploy():
    """执行部署（原子操作 + 回滚保护）"""
    global _last_deploy_time
    async with _deploy_lock:
        _last_deploy_time = time.time()
        deploy_start = time.time()

        try:
            logger.info(f"[部署] 开始部署, 项目目录: {PROJECT_DIR}")

            # 记录当前版本（用于回滚）
            current_commit = _run_cmd(
                ['git', 'rev-parse', 'HEAD'],
                cwd=PROJECT_DIR, timeout=10
            ).get('stdout', '').strip()[:8]
            logger.info(f"[部署] 当前版本: {current_commit}")

            # 1. 清理 Python 缓存
            logger.info("[部署] 清理 Python 缓存...")
            _run_cmd(
                ['find', PROJECT_DIR, '-type', 'd', '-name', '__pycache__',
                 '-exec', 'rm', '-rf', '{}', '+'],
                timeout=30
            )
            _run_cmd(
                ['find', PROJECT_DIR, '-type', 'f', '-name', '*.pyc', '-delete'],
                timeout=30
            )

            # 2. Git 原子操作: fetch + reset --hard
            logger.info("[部署] 执行 git fetch origin...")
            fetch_result = _run_cmd(
                ['git', 'fetch', 'origin'],
                cwd=PROJECT_DIR, timeout=60
            )
            if fetch_result['returncode'] != 0:
                logger.error(f"[部署] git fetch 失败: {fetch_result['stderr']}")
                return

            new_commit = _run_cmd(
                ['git', 'rev-parse', 'origin/master'],
                cwd=PROJECT_DIR, timeout=10
            ).get('stdout', '').strip()[:8]

            if new_commit == current_commit:
                logger.info(f"[部署] 版本未变化 ({current_commit})，跳过部署")
                return

            logger.info(f"[部署] 版本变更: {current_commit} -> {new_commit}")
            logger.info("[部署] 执行 git reset --hard origin/master...")

            reset_result = _run_cmd(
                ['git', 'reset', '--hard', 'origin/master'],
                cwd=PROJECT_DIR, timeout=30
            )
            if reset_result['returncode'] != 0:
                logger.error(f"[部署] git reset 失败: {reset_result['stderr']}")
                # 尝试回滚到之前版本
                logger.info(f"[部署] 尝试回滚到 {current_commit}...")
                _run_cmd(['git', 'reset', '--hard', current_commit], cwd=PROJECT_DIR, timeout=30)
                return

            # 3. 安装依赖
            logger.info("[部署] 安装 Python 依赖...")
            pip_result = _run_cmd(
                ['pip', 'install', '-r', 'requirements.txt', '--break-system-packages', '-q'],
                cwd=PROJECT_DIR, timeout=180
            )
            if pip_result['returncode'] != 0:
                logger.error(f"[部署] pip install 失败: {pip_result['stderr']}")
                logger.info(f"[部署] 尝试回滚到 {current_commit}...")
                _run_cmd(['git', 'reset', '--hard', current_commit], cwd=PROJECT_DIR, timeout=30)
                return

            # 4. 构建 web-v2（如果需要）
            web_v2_dir = os.path.join(PROJECT_DIR, 'web-v2')
            web_v2_dist = os.path.join(web_v2_dir, 'dist', 'index.html')
            if os.path.isdir(web_v2_dir) and not os.path.exists(web_v2_dist):
                logger.info("[部署] 检测到 web-v2 无构建产物，执行 npm install && npm run build...")
                npm_install = _run_cmd(['npm', 'install'], cwd=web_v2_dir, timeout=120)
                if npm_install['returncode'] == 0:
                    npm_build = _run_cmd(['npm', 'run', 'build'], cwd=web_v2_dir, timeout=120)
                    if npm_build['returncode'] == 0:
                        logger.info("[部署] web-v2 构建完成")
                    else:
                        logger.error(f"[部署] web-v2 build 失败: {npm_build['stderr']}")
                else:
                    logger.error(f"[部署] web-v2 npm install 失败: {npm_install['stderr']}")
            elif os.path.exists(web_v2_dist):
                logger.info("[部署] web-v2 dist 已存在，跳过构建")

            # 5. 重启 bot 服务
            logger.info(f"[部署] 重启服务: {BOT_SERVICE}")
            restart_result = _run_cmd(
                ['systemctl', 'restart', BOT_SERVICE],
                timeout=30
            )
            if restart_result['returncode'] != 0:
                logger.error(f"[部署] 重启服务失败: {restart_result['stderr']}")
                return

            # 6. 验证服务启动
            await asyncio.sleep(3)
            status_result = _run_cmd(
                ['systemctl', 'is-active', BOT_SERVICE],
                timeout=10
            )
            if status_result['stdout'].strip() != 'active':
                logger.error(f"[部署] 服务启动失败: {status_result['stdout'].strip()}")
                logger.info(f"[部署] 尝试回滚到 {current_commit}...")
                _run_cmd(['git', 'reset', '--hard', current_commit], cwd=PROJECT_DIR, timeout=30)
                _run_cmd(['systemctl', 'restart', BOT_SERVICE], timeout=30)
                return

            elapsed = time.time() - deploy_start
            logger.info(f"[部署] ✅ 部署成功! {current_commit} -> {new_commit} ({elapsed:.1f}s)")

        except Exception as e:
            logger.error(f"[部署] 部署错误: {e}", exc_info=True)


def _run_cmd(cmd, cwd=None, timeout=60) -> dict:
    """执行 shell 命令并返回结果"""
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
        return {
            'returncode': result.returncode,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {'returncode': -1, 'stdout': '', 'stderr': f'命令超时 ({timeout}s)'}
    except Exception as e:
        return {'returncode': -1, 'stdout': '', 'stderr': str(e)}


async def manual_deploy(request):
    """手动触发部署（Bearer Token 认证）"""
    client_ip = request.remote or 'unknown'

    try:
        # Bearer Token 认证
        auth = request.headers.get('Authorization', '')
        token = auth.replace('Bearer ', '') if auth.startswith('Bearer ') else request.query.get('token', '')

        if not token or token != WEBHOOK_SECRET:
            logger.warning(f"[安全] 手动部署认证失败, IP={client_ip}")
            return web.json_response({'error': 'auth failed'}, status=401)

        # 限流检查
        allowed, reason = _check_deploy_cooldown()
        if not allowed:
            return web.json_response({'error': reason}, status=429)

        logger.info(f"[部署] 手动触发部署, IP={client_ip}")
        asyncio.create_task(deploy())

        return web.json_response({'status': 'deploying'})

    except Exception as e:
        logger.error(f"[部署] 手动部署错误: {e}")
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
        result = _run_cmd(
            ['git', 'log', '-1', '--oneline'],
            cwd=PROJECT_DIR, timeout=10
        )
        last_commit = result['stdout'] if result['returncode'] == 0 else 'unknown'

        # 检查服务状态
        result = _run_cmd(
            ['systemctl', 'is-active', BOT_SERVICE],
            timeout=10
        )
        service_status = result['stdout'] if result['returncode'] == 0 else 'inactive'

        # 动态读取版本号
        version = BOT_VERSION
        try:
            result = _run_cmd(
                ['python3', '-c', 'from system.config import BOT_VERSION; print(BOT_VERSION)'],
                cwd=PROJECT_DIR, timeout=10
            )
            if result['returncode'] == 0 and result['stdout'].strip():
                version = result['stdout'].strip()
        except Exception:
            pass

        return web.json_response({
            'status': 'ok',
            'project_dir': PROJECT_DIR,
            'last_commit': last_commit,
            'bot_service': BOT_SERVICE,
            'service_status': service_status,
            'version': version,
            'deploy_lock': _deploy_lock.locked(),
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
    logger.info(f"启动 Webhook 服务 v1.9.2.1, 端口: {WEBHOOK_PORT}")
    logger.info(f"项目目录: {PROJECT_DIR}")
    logger.info(f"Bot 服务: {BOT_SERVICE}")
    logger.info(f"签名验证: {'已启用' if WEBHOOK_SECRET else '⚠️ 未配置 WEBHOOK_SECRET'}")
    logger.info(f"部署冷却: {_DEPLOY_COOLDOWN}秒")

    # 确保项目目录存在
    if not Path(PROJECT_DIR).exists():
        logger.error(f"项目目录不存在: {PROJECT_DIR}")
        sys.exit(1)

    # 启动服务
    web.run_app(create_app(), host='0.0.0.0', port=WEBHOOK_PORT, print=None)


if __name__ == '__main__':
    main()
