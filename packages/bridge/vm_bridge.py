"""
VM Bridge 模块 - SOLO 与 VM 之间的命令/文件桥接
以及 MiniApp 消息同步 API
"""

import base64
import logging
import os
from datetime import datetime

from aiohttp import web

from auth import validate_session_token, validate_api_token
from config import load_config
from chat_history import load_chat_history

# 存储待处理的命令和文件
bridge_pending_commands = []
bridge_uploaded_files = {}

__all__ = [
    "bridge_pending_commands",
    "bridge_uploaded_files",
    "bridge_vm_poll",
    "bridge_vm_result",
    "setup_bridge_routes",
    "bridge_send_command",
    "bridge_upload_file",
    "api_messages_history",
    "api_messages_sync",
]


async def bridge_vm_poll(request):
    """VM 轮询端点 - VM 定期调用获取命令"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id')
        auth_token = data.get('token')

        if auth_token != 'nxsiran_bridge_2024':
            return web.json_response({'error': 'auth failed'}, status=401)

        # 获取 VM 上传的文件（如果有）
        files = data.get('files', [])
        for file_info in files:
            filename = file_info.get('filename')
            content = base64.b64decode(file_info.get('content'))
            filepath = f"/tmp/vm_uploads/{vm_id}_{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(content)
            bridge_uploaded_files[filename] = filepath
            logging.info(f"[Bridge] Received from {vm_id}: {filename}")

        # 返回待执行的命令
        global bridge_pending_commands
        commands_to_execute = []
        for cmd in bridge_pending_commands:
            if cmd.get('vm_id') == vm_id or cmd.get('vm_id') == '*':
                commands_to_execute.append(cmd)
        bridge_pending_commands = [cmd for cmd in bridge_pending_commands if cmd not in commands_to_execute]

        return web.json_response({
            'status': 'ok',
            'commands': commands_to_execute,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def bridge_vm_result(request):
    """VM 返回命令执行结果"""
    try:
        data = await request.json()
        logging.info(f"[Bridge] Result from {data.get('vm_id')}:")
        logging.info(f"  Command: {data.get('command')}")
        logging.info(f"  Return code: {data.get('returncode')}")
        if data.get('stdout'):
            logging.info(f"  STDOUT: {data.get('stdout')[:500]}")
        if data.get('stderr'):
            logging.info(f"  STDERR: {data.get('stderr')[:500]}")

        return web.json_response({'status': 'received'})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


def setup_bridge_routes(app):
    """设置 bridge 路由"""
    app.router.add_post('/bridge/poll', bridge_vm_poll)
    app.router.add_post('/bridge/result', bridge_vm_result)
    app.router.add_post('/bridge/send', bridge_send_command)
    app.router.add_post('/bridge/upload', bridge_upload_file)
    logging.info("[Bridge] HTTP Bridge routes registered")


async def bridge_send_command(request):
    """从 SOLO 发送命令到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        command = data.get('command')

        bridge_pending_commands.append({
            'vm_id': vm_id,
            'command': command,
            'timestamp': datetime.now().isoformat()
        })

        return web.json_response({
            'status': 'command_queued',
            'vm_id': vm_id,
            'command': command
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def bridge_upload_file(request):
    """从 SOLO 发送文件到 VM"""
    try:
        data = await request.json()
        vm_id = data.get('vm_id', '*')
        filename = data.get('filename')
        dest_path = data.get('dest_path', '/tmp/')
        content = data.get('content')  # base64 encoded

        bridge_pending_commands.append({
            'vm_id': vm_id,
            'type': 'file_download',
            'filename': filename,
            'dest_path': dest_path,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })

        return web.json_response({
            'status': 'file_queued',
            'vm_id': vm_id,
            'filename': filename
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def api_messages_history(request):
    """获取聊天历史消息 - 用于Web端加载历史"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        # 获取limit参数
        limit = int(request.query.get('limit', 50))

        # 加载聊天历史
        history = load_chat_history(user_id)

        # 只返回最近的N条消息
        if len(history) > limit:
            history = history[-limit:]

        # 格式化返回
        messages = []
        for msg in history:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })

        return web.json_response({
            'messages': messages,
            'total_count': len(messages)
        })
    except Exception as e:
        logging.error(f"[消息历史] 获取失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_messages_sync(request):
    """同步新消息 - Telegram新消息推送到Web端"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        # 获取since参数（从第几条消息开始）
        since = int(request.query.get('since', 0))

        # 加载聊天历史
        history = load_chat_history(user_id)
        total_count = len(history)

        # 只返回新增的消息
        if since >= total_count:
            return web.json_response({
                'messages': [],
                'total_count': total_count
            })

        new_messages = history[since:]

        # 格式化返回
        messages = []
        for msg in new_messages:
            messages.append({
                'role': msg.get('role', 'user'),
                'content': msg.get('content', ''),
                'timestamp': msg.get('timestamp', '')
            })

        return web.json_response({
            'messages': messages,
            'total_count': total_count
        })
    except Exception as e:
        logging.error(f"[消息同步] 同步失败: {e}")
        return web.json_response({'error': str(e)}, status=500)
