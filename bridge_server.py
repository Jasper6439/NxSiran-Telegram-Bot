#!/usr/bin/env python3
"""
独立 Bridge 服务 - v1.4.8.1
不依赖 bot 主进程，即使 bot 崩溃也能工作

端口: 8081 (可通过 BRIDGE_PORT 环境变量修改)
功能:
- VM 轮询命令
- 文件上传/下载
- 健康检查
"""

import asyncio
import base64
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [Bridge] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# 尝试导入 aiohttp
try:
    from aiohttp import web
except ImportError:
    logger.error("aiohttp 未安装，请执行: pip install aiohttp")
    sys.exit(1)

# 配置
BRIDGE_PORT = int(os.environ.get('BRIDGE_PORT', 8081))
BRIDGE_TOKEN = os.environ.get('BRIDGE_TOKEN', 'nxsiran_bridge_2024')
DATA_DIR = os.environ.get('DATA_DIR', '/opt/NxSiran/data')

# 命令队列和文件存储
pending_commands = {}  # {vm_id: [commands]}
uploaded_files = {}    # {vm_id: {filename: content}}


# ============================================================
# API Handlers
# ============================================================

async def health_check(request):
    """健康检查"""
    return web.json_response({
        'status': 'ok',
        'service': 'nxsiran-bridge',
        'version': '1.4.8.1',
        'timestamp': datetime.now().isoformat()
    })


async def bridge_poll(request):
    """VM 轮询端点 - VM 定期调用获取命令"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', 'default')
        auth_token = data.get('token', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        # 获取该 VM 的待处理命令
        commands = pending_commands.pop(vm_id, [])

        # 处理 VM 上传的文件
        files = data.get('files', [])
        for file_info in files:
            filename = file_info.get('filename')
            content_b64 = file_info.get('content', '')
            if filename and content_b64:
                if vm_id not in uploaded_files:
                    uploaded_files[vm_id] = {}
                uploaded_files[vm_id][filename] = base64.b64decode(content_b64)
                logger.info(f"收到文件: {vm_id}/{filename}")

        return web.json_response({
            'status': 'ok',
            'commands': commands,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        logger.error(f"轮询处理错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_send(request):
    """发送命令到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', 'default')
        auth_token = data.get('token', '')
        command = data.get('command', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        if not command:
            return web.json_response({'error': 'no command'}, status=400)

        # 添加到命令队列
        if vm_id not in pending_commands:
            pending_commands[vm_id] = []
        pending_commands[vm_id].append({
            'command': command,
            'timestamp': datetime.now().isoformat()
        })

        logger.info(f"命令已排队: {vm_id} -> {command[:50]}...")

        return web.json_response({
            'status': 'queued',
            'vm_id': vm_id,
            'command': command[:50]
        })

    except Exception as e:
        logger.error(f"发送命令错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_get_file(request):
    """获取上传的文件"""
    try:
        vm_id = request.match_info.get('vm_id', 'default')
        filename = request.match_info.get('filename', '')
        auth_token = request.query.get('token', '')

        if auth_token != BRIDGE_TOKEN:
            return web.json_response({'error': 'auth failed'}, status=401)

        if vm_id not in uploaded_files or filename not in uploaded_files[vm_id]:
            return web.json_response({'error': 'file not found'}, status=404)

        content = uploaded_files[vm_id][filename]
        del uploaded_files[vm_id][filename]

        return web.Response(body=content, content_type='application/octet-stream')

    except Exception as e:
        logger.error(f"获取文件错误: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def bridge_status(request):
    """Bridge 状态"""
    return web.json_response({
        'status': 'running',
        'pending_commands': {k: len(v) for k, v in pending_commands.items()},
        'uploaded_files': {k: list(v.keys()) for k, v in uploaded_files.items()},
        'version': '1.4.8.1'
    })


# ============================================================
# Main
# ============================================================

async def create_app():
    """创建 aiohttp 应用"""
    app = web.Application()
    
    # 路由
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_post('/bridge/poll', bridge_poll)
    app.router.add_post('/bridge/send', bridge_send)
    app.router.add_get('/bridge/file/{vm_id}/{filename}', bridge_get_file)
    app.router.add_get('/bridge/status', bridge_status)
    
    return app


def main():
    """主入口"""
    logger.info(f"启动 Bridge 服务，端口: {BRIDGE_PORT}")
    logger.info(f"数据目录: {DATA_DIR}")
    
    # 确保数据目录存在
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    
    # 启动服务
    web.run_app(create_app(), host='0.0.0.0', port=BRIDGE_PORT, print=None)


if __name__ == '__main__':
    main()
