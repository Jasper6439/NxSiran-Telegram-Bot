"""
媒体路由模块
包含自拍上传/获取/删除、用户照片管理、文件服务、TTS 声音语料上传/获取/删除/训练等 API。
"""

import base64
import io
import logging
import os

from datetime import datetime

from aiohttp import web

from config import *
from auth import *


async def api_upload_selfies(request):
    """Mini App上传自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        data = await request.json()
        photos = data.get('photos', [])
        character_id = data.get('character_id')

        if not photos:
            return web.json_response({'success': False, 'error': '没有照片'})

        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        uploaded = []
        for photo_data in photos:
            try:
                # 解析base64图片
                if ',' in photo_data:
                    photo_data = photo_data.split(',')[1]

                img_bytes = base64.b64decode(photo_data)

                # 验证并打开图片
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes))

                # 生成文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"selfie_{timestamp}_{len(uploaded)}.jpg"
                filepath = os.path.join(user_selfie_dir, filename)

                # 保存为 JPEG（兼容所有格式）
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                img.save(filepath, 'JPEG', quality=90)
                uploaded.append(filename)

            except Exception as e:
                logging.error(f"处理上传照片失败: {e}")
                continue

        return web.json_response({
            'success': True,
            'uploaded': uploaded,
            'count': len(uploaded)
        })
    except Exception as e:
        logging.error(f"上传自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_selfies(request):
    """Mini App获取自拍列表API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        character_id = request.query.get('character_id')

        selfies = []
        user_selfie_dir = get_user_selfie_dir(user_id, character_id)
        if os.path.exists(user_selfie_dir):
            for f in sorted(os.listdir(user_selfie_dir), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    filepath = os.path.join(user_selfie_dir, f)
                    stat = os.stat(filepath)
                    selfies.append({
                        'filename': f,
                        # 返回带 character_id 的 URL，让前端能正确加载
                        'url': f'/uploads/{character_id or "_shared"}/{f}',
                        'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                        'size': stat.st_size
                    })

        return web.json_response({
            'success': True,
            'selfies': selfies,
            'photos': selfies,  # 兼容两种调用方式
            'count': len(selfies)
        })
    except Exception as e:
        logging.error(f"获取自拍列表API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_delete_selfie(request):
    """Mini App删除自拍API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        data = await request.json()
        filename = data.get('filename', '')
        character_id = data.get('character_id')

        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})

        filepath = os.path.join(get_user_selfie_dir(user_id, character_id), filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除自拍API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_delete_user_photo(request):
    """Mini App删除用户照片API"""
    try:
        data = await request.json()
        filename = data.get('filename', '')

        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})

        filepath = os.path.join(USER_PHOTOS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logging.error(f"删除用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_user_photos(request):
    """Mini App获取用户照片列表API"""
    try:
        photos = []
        if os.path.exists(USER_PHOTOS_DIR):
            for f in sorted(os.listdir(USER_PHOTOS_DIR), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    photos.append({
                        'filename': f,
                        'url': f'/files/user_photos/{f}'
                    })
        return web.json_response({'success': True, 'photos': photos, 'count': len(photos)})
    except Exception as e:
        logging.error(f"获取用户照片API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def serve_uploaded_file(request):
    """提供上传的文件"""
    try:
        folder = request.match_info.get('folder', '')
        filename = request.match_info.get('filename', '')

        if '..' in filename or '/' in filename:
            return web.Response(status=403)

        # 图片文件不需要身份验证（URL 本身已足够随机）
        is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))

        if not is_image:
            # 非图片文件需要验证身份
            user_id = validate_session_token(request)
            if not user_id:
                user_id = validate_api_token(request)
            if not user_id:
                token = request.query.get('token', '')
                if token:
                    user_id = validate_session_token_from_token(token)
            if not user_id:
                user_id = load_config().get('your_chat_id', 0)
            if not user_id:
                return web.Response(status=401)

        filepath = None

        if folder == 'selfies':
            # 只在当前用户的目录中查找
            user_selfie_dir = get_user_selfie_dir(user_id)
            if os.path.isdir(user_selfie_dir):
                # 检查直接路径
                candidate = os.path.join(user_selfie_dir, filename)
                if os.path.exists(candidate):
                    filepath = candidate
                else:
                    # 检查角色子目录
                    for sub in os.listdir(user_selfie_dir):
                        sub_path = os.path.join(user_selfie_dir, sub)
                        if os.path.isdir(sub_path):
                            candidate = os.path.join(sub_path, filename)
                            if os.path.exists(candidate):
                                filepath = candidate
                                break
            if not filepath:
                # 回退到旧的全局目录（仅用于兼容旧数据）
                filepath = os.path.join(SELFIE_DIR, filename)

        elif folder == 'user_photos':
            # 只在当前用户的照片目录中查找
            user_photos_dir = get_user_dir(user_id, 'photos')
            candidate = os.path.join(user_photos_dir, filename)
            if os.path.exists(candidate):
                filepath = candidate

        else:
            # folder 是 character_id 或 '_shared'，只在当前用户的目录中查找
            # 兼容旧数据：'default' 映射到 '_shared'
            if folder == 'default':
                folder = '_shared'
            user_selfie_dir = get_user_selfie_dir(user_id, folder)
            if os.path.isdir(user_selfie_dir):
                candidate = os.path.join(user_selfie_dir, filename)
                if os.path.exists(candidate):
                    filepath = candidate

        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                content = f.read()

            # 确定content type
            if filename.lower().endswith('.png'):
                content_type = 'image/png'
            elif filename.lower().endswith('.gif'):
                content_type = 'image/gif'
            else:
                content_type = 'image/jpeg'

            return web.Response(body=content, content_type=content_type)
        else:
            return web.Response(status=404)
    except Exception as e:
        logging.error(f"提供文件错误: {e}")
        return web.Response(status=500)


async def api_upload_voice_sample(request):
    """Web端上传声音语料API - v1.4.7.3"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        # 获取上传的文件
        reader = await request.multipart()
        character_id = "chayewoon"  # 默认角色

        async for field in reader:
            if field.name == 'character_id':
                character_id = (await field.read()).decode('utf-8')
            elif field.name == 'audio':
                # 读取音频文件
                audio_data = await field.read()
                filename = field.filename or 'audio.wav'

                # 确保目录存在
                samples_dir = os.path.join(DATA_DIR, "voices", character_id, "samples")
                os.makedirs(samples_dir, exist_ok=True)

                # 生成唯一文件名
                import uuid
                sample_id = str(uuid.uuid4())[:8]
                ext = os.path.splitext(filename)[1] or '.wav'
                target_path = os.path.join(samples_dir, f"{sample_id}{ext}")

                # 保存文件
                with open(target_path, 'wb') as f:
                    f.write(audio_data)

                # 统计当前语料数量
                samples_count = len([f for f in os.listdir(samples_dir)
                                    if f.endswith(('.wav', '.mp3', '.ogg', '.m4a'))])

                return web.json_response({
                    'success': True,
                    'sample_id': sample_id,
                    'filename': f"{sample_id}{ext}",
                    'samples_count': samples_count,
                    'message': f'语料已上传，当前共 {samples_count} 条'
                })

        return web.json_response({'success': False, 'error': '没有收到音频文件'})

    except Exception as e:
        logging.error(f"上传声音语料API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_voice_samples(request):
    """获取声音语料状态API"""
    try:
        character_id = request.query.get('character_id', 'chayewoon')

        samples_dir = os.path.join(DATA_DIR, "voices", character_id, "samples")
        min_required = 10

        if not os.path.exists(samples_dir):
            return web.json_response({
                'success': True,
                'character_id': character_id,
                'samples_count': 0,
                'min_required': min_required,
                'ready_to_train': False,
                'samples': []
            })

        samples = [f for f in os.listdir(samples_dir)
                  if f.endswith(('.wav', '.mp3', '.ogg', '.m4a'))]

        # 检查是否已训练
        model_path = os.path.join(DATA_DIR, "voices", character_id, "model.pth")
        trained = os.path.exists(model_path)

        return web.json_response({
            'success': True,
            'character_id': character_id,
            'samples_count': len(samples),
            'min_required': min_required,
            'ready_to_train': len(samples) >= min_required,
            'trained': trained,
            'samples': sorted(samples, reverse=True)[:10]  # 只返回最近10个
        })

    except Exception as e:
        logging.error(f"获取声音语料状态API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_delete_voice_sample(request):
    """删除声音语料API"""
    try:
        data = await request.json()
        filename = data.get('filename', '')
        character_id = data.get('character_id', 'chayewoon')

        if not filename or '..' in filename or '/' in filename:
            return web.json_response({'success': False, 'error': '无效文件名'})

        filepath = os.path.join(DATA_DIR, "voices", character_id, "samples", filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return web.json_response({'success': True, 'message': '已删除'})
        else:
            return web.json_response({'success': False, 'error': '文件不存在'})

    except Exception as e:
        logging.error(f"删除声音语料API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_start_voice_training(request):
    """启动声音训练API"""
    try:
        data = await request.json() if request.content_type == 'application/json' else {}
        character_id = data.get('character_id', 'chayewoon')

        samples_dir = os.path.join(DATA_DIR, "voices", character_id, "samples")
        min_required = 10

        if not os.path.exists(samples_dir):
            return web.json_response({
                'success': False,
                'error': '还没有上传任何语料'
            })

        samples = [f for f in os.listdir(samples_dir)
                  if f.endswith(('.wav', '.mp3', '.ogg', '.m4a'))]

        if len(samples) < min_required:
            return web.json_response({
                'success': False,
                'error': f'语料不足，需要至少 {min_required} 条，当前只有 {len(samples)} 条'
            })

        # 通过 VM Bridge 发送训练命令
        import aiohttp
        VM_BRIDGE_URL = os.environ.get("VM_BRIDGE_URL", "")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{VM_BRIDGE_URL}/start_training",
                    json={
                        "character_id": character_id,
                        "samples_dir": samples_dir,
                        "language": "ko"
                    },
                    timeout=10
                ) as resp:
                    result = await resp.json()
                    return web.json_response({
                        'success': True,
                        'message': '训练任务已启动',
                        'training_id': result.get('training_id'),
                        'estimated_time': '约30分钟'
                    })
        except Exception as e:
            return web.json_response({
                'success': False,
                'error': f'无法连接到训练服务器: {e}',
                'note': '请确保训练服务器已启动'
            })

    except Exception as e:
        logging.error(f"启动声音训练API错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})
