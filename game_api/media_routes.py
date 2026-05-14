# 多媒体生成 API

import logging
import os
import random
import shutil
import urllib.parse
from datetime import datetime
from aiohttp import web
from database import get_db
from system.prompts import SELFIE_PROMPTS, STICKER_PROMPTS, SCENE_PROMPTS
from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


def _generate_image_url(prompt: str, width: int = 768, height: int = 1024) -> str:
    """生成 Pollinations.ai 图片 URL"""
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&safe=true"


async def api_generate_selfie(request):
    """生成 AI 自拍 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        prompt = random.choice(SELFIE_PROMPTS)
        url = _generate_image_url(prompt, 768, 1024)

        return web.json_response({
            'success': True,
            'url': url,
            'type': 'selfie',
            'width': 768,
            'height': 1024
        })

    except Exception as e:
        logger.error(f"[Game API] 生成自拍失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_generate_sticker(request):
    """生成表情包 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        mood = data.get('mood', '默认')

        prompts = STICKER_PROMPTS.get(mood, STICKER_PROMPTS.get('默认', []))
        if not prompts:
            prompts = STICKER_PROMPTS['默认']

        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 512, 512)

        return web.json_response({
            'success': True,
            'url': url,
            'type': 'sticker',
            'mood': mood,
            'width': 512,
            'height': 512
        })

    except Exception as e:
        logger.error(f"[Game API] 生成表情包失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_generate_scene(request):
    """生成场景图 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        scene = data.get('scene', '天台')

        prompts = SCENE_PROMPTS.get(scene, SCENE_PROMPTS.get('天台', []))
        if not prompts:
            prompts = SCENE_PROMPTS['天台']

        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 1024, 768)

        return web.json_response({
            'success': True,
            'url': url,
            'type': 'scene',
            'scene': scene,
            'width': 1024,
            'height': 768
        })

    except Exception as e:
        logger.error(f"[Game API] 生成场景图失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_tts(request):
    """文本转语音 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        text = data.get('text', '')

        if not text or len(text) > 300:
            return web.json_response({'success': False, 'error': '文本为空或超过300字符'})

        # 使用 tts_engine 生成语音
        try:
            from characters.tts_engine import TTSEngine
            tts = TTSEngine()
            audio_path = await tts.synthesize(text)

            if audio_path:
                # 返回音频文件路径（相对于 static）
                audio_filename = os.path.basename(audio_path)
                return web.json_response({
                    'success': True,
                    'audio_url': f'/static/tts/{audio_filename}',
                    'duration': len(text) * 0.15  # 估算时长
                })
            # synthesize 返回 None，走 edge_tts fallback
            raise ImportError("TTSEngine synthesize failed")

        except ImportError:
            # tts_engine 不可用或失败，直接使用 Edge TTS
            import edge_tts
            import tempfile

            communicate = edge_tts.Communicate(text, "zh-CN-XiaoyiNeural")
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            # 移动到 static/tts 目录
            tts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'tts')
            os.makedirs(tts_dir, exist_ok=True)

            audio_filename = f"tts_{user_id}_{int(datetime.now().timestamp())}.ogg"
            final_path = os.path.join(tts_dir, audio_filename)
            shutil.move(tmp_path, final_path)

            return web.json_response({
                'success': True,
                'audio_url': f'/static/tts/{audio_filename}',
                'duration': len(text) * 0.15
            })

    except Exception as e:
        logger.error(f"[Game API] TTS 失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
