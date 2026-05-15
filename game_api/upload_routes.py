"""
上传处理 API
v1.6.4.2 — 支持声音/聊天记录/视频上传

端点：
- POST /api/upload/voice — 上传角色声音
- POST /api/upload/chatlog — 上传聊天记录生成 soul.md
- POST /api/upload/video — 上传角色视频学习
"""

import os
import logging
import tempfile
import shutil
from aiohttp import web
from aiohttp.web_request import FileField

from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


# ============================================================
# 1. 声音上传
# ============================================================

async def api_upload_voice(request):
    """上传角色声音样本

    POST /api/upload/voice
    Form: voice_file, character_id, label, description
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        reader = await request.multipart()

        voice_file = None
        character_id = 'chayewoon'
        label = "用户上传"
        description = ""

        async for part in reader:
            if part.name == 'voice_file':
                voice_file = part
            elif part.name == 'character_id':
                character_id = (await part.text()).strip()
            elif part.name == 'label':
                label = (await part.text()).strip()
            elif part.name == 'description':
                description = (await part.text()).strip()

        if not voice_file:
            return web.json_response({'success': False, 'error': '未提供声音文件'})

        # 保存临时文件
        ext = voice_file.filename.split('.')[-1] if '.' in voice_file.filename else '.mp3'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            while True:
                chunk = await voice_file.read_chunk()
                if not chunk:
                    break
                tmp.write(chunk)
            tmp_path = tmp.name

        # 保存到角色声音库
        from characters.voice_manager import get_voice_manager
        vm = get_voice_manager(character_id)
        result = vm.save_voice_sample(tmp_path, label=label, description=description)

        # 清理临时文件
        os.unlink(tmp_path)

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Upload] 声音上传失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_clone_voice(request):
    """使用 Fish Speech 克隆声音

    POST /api/upload/voice/clone
    Body: { "character_id": "chayewoon", "sample_id": "sample_1", "api_key": "xxx" }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        character_id = data.get('character_id', 'chayewoon')
        sample_id = data.get('sample_id')
        api_key = data.get('api_key')

        if not sample_id or not api_key:
            return web.json_response({'success': False, 'error': '缺少 sample_id 或 api_key'})

        from characters.voice_manager import get_voice_manager
        vm = get_voice_manager(character_id)

        # 获取样本路径
        samples = vm.list_samples()
        sample_path = None
        for s in samples:
            if s['id'] == sample_id:
                sample_path = s.get('path')
                break

        if not sample_path or not os.path.exists(sample_path):
            return web.json_response({'success': False, 'error': '样本不存在'})

        result = await vm.clone_voice_fish(sample_path, api_key)
        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Upload] 声音克隆失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 2. 聊天记录上传
# ============================================================

async def api_upload_chatlog(request):
    """上传聊天记录生成 soul.md

    POST /api/upload/chatlog
    Form: chatlog_file, chat_partner
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        reader = await request.multipart()

        chatlog_file = None
        chat_partner = ""

        async for part in reader:
            if part.name == 'chatlog_file':
                chatlog_file = part
            elif part.name == 'chat_partner':
                chat_partner = (await part.text()).strip()

        if not chatlog_file:
            return web.json_response({'success': False, 'error': '未提供聊天记录文件'})

        # 读取文件内容
        content = b''
        while True:
            chunk = await chatlog_file.read_chunk()
            if not chunk:
                break
            content += chunk

        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = content.decode('gbk', errors='ignore')

        # 解析聊天记录
        from packages.analysis.chatlog import parse_wechat_chatlog
        parsed = parse_wechat_chatlog(text_content)

        if not parsed or not parsed.get('messages'):
            return web.json_response({'success': False, 'error': '无法解析聊天记录'})

        # 生成 soul.md
        from characters.soul_manager import generate_soul_from_chatlog
        result = await generate_soul_from_chatlog(parsed, chat_partner or "好友")

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Upload] 聊天记录上传失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 3. 视频上传
# ============================================================

async def api_upload_video(request):
    """上传角色视频进行学习

    POST /api/upload/video
    Form: video_file, character_id, content_type
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        reader = await request.multipart()

        video_file = None
        character_id = 'chayewoon'
        content_type = '剧集'

        async for part in reader:
            if part.name == 'video_file':
                video_file = part
            elif part.name == 'character_id':
                character_id = (await part.text()).strip()
            elif part.name == 'content_type':
                content_type = (await part.text()).strip()

        if not video_file:
            return web.json_response({'success': False, 'error': '未提供视频文件'})

        # 保存视频文件
        from system.config import VIDEO_DIR
        os.makedirs(VIDEO_DIR, exist_ok=True)

        ext = video_file.filename.split('.')[-1] if '.' in video_file.filename else 'mp4'
        video_path = os.path.join(VIDEO_DIR, f"upload_{character_id}_{int(os.times().system)}.{ext}")

        with open(video_path, 'wb') as f:
            while True:
                chunk = await video_file.read_chunk()
                if not chunk:
                    break
                f.write(chunk)

        # 处理视频
        from packages.importers.video_enhanced import import_video_for_learning
        result = await import_video_for_learning(video_path, character_id, content_type)

        # 清理视频文件（节省空间）
        if os.path.exists(video_path):
            os.remove(video_path)

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Upload] 视频上传失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 4. 状态查询
# ============================================================

async def api_upload_status(request):
    """获取上传功能状态

    GET /api/upload/status?character_id=chayewoon
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        character_id = request.query.get('character_id', 'chayewoon')

        # 检查各功能状态
        from characters.voice_manager import get_voice_manager
        from characters.soul_manager import get_soul_manager

        vm = get_voice_manager(character_id)
        sm = get_soul_manager()

        voice_status = vm.get_status()
        soul_exists = os.path.exists(sm.soul_path)

        return web.json_response({
            'success': True,
            'character_id': character_id,
            'voice': voice_status,
            'soul': {
                'exists': soul_exists,
                'path': sm.soul_path if soul_exists else None
            }
        })

    except Exception as e:
        logger.error(f"[Upload] 获取状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
