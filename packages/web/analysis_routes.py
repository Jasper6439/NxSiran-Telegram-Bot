"""
分析 API 模块
包含聊天记录分析和视频分析的 API 端点。
"""

import logging
import os

from datetime import datetime

from aiohttp import web

from system.config import *

from packages.analysis.chatlog import (
    parse_wechat_chatlog,
    analyze_chatlog_with_ai,
    save_chat_analysis,
)
from packages.importers.video import (
    extract_audio_from_video,
    transcribe_audio_primary,
    transcribe_audio_whisper,
    analyze_video_transcript,
    save_video_analysis,
)


async def api_analyze_chatlog(request):
    """Mini App聊天记录分析API"""
    try:
        if parse_wechat_chatlog is None or analyze_chatlog_with_ai is None:
            return web.json_response({'success': False, 'error': '聊天分析功能未加载'})

        data = await request.json()
        content = data.get('content', '')
        partner = data.get('partner', '对方')

        if not content:
            return web.json_response({'success': False, 'error': '没有内容'})

        # 解析聊天记录
        parsed = parse_wechat_chatlog(content)

        if parsed['total_count'] == 0:
            return web.json_response({'success': False, 'error': '未能解析出消息，请检查格式'})

        # AI分析
        analysis_result = await analyze_chatlog_with_ai(parsed, partner)

        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})

        # 保存分析结果
        save_chat_analysis(partner, analysis_result)

        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'message_count': analysis_result['message_count'],
            'date_range': analysis_result['date_range']
        })

    except Exception as e:
        logging.error(f"Mini App聊天记录分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_analyze_video(request):
    """Mini App视频分析API"""
    try:
        if extract_audio_from_video is None or transcribe_audio_primary is None:
            return web.json_response({'success': False, 'error': '视频分析功能未加载'})

        reader = await request.multipart()
        video_type = "剧情"
        video_path = None

        while True:
            part = await reader.next()
            if part is None:
                break
            if part.name == 'type':
                video_type = (await part.text()).strip()
            elif part.name == 'video':
                filename = part.filename or f"video_{datetime.now(get_default_tz()).strftime('%Y%m%d_%H%M%S')}.mp4"
                video_path = os.path.join(VIDEO_DIR, filename)
                with open(video_path, 'wb') as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        f.write(chunk)

        if not video_path or not os.path.exists(video_path):
            return web.json_response({'success': False, 'error': '视频上传失败'})

        # 提取音频
        audio_path = extract_audio_from_video(video_path)
        if not audio_path:
            return web.json_response({'success': False, 'error': '音频提取失败，请确认ffmpeg已安装'})

        # 语音转文字（优先使用Google Speech Recognition）
        transcript = transcribe_audio_primary(audio_path)
        if not transcript:
            transcript = transcribe_audio_whisper(audio_path)

        # 清理音频
        if os.path.exists(audio_path):
            os.remove(audio_path)

        if not transcript:
            return web.json_response({'success': False, 'error': '语音识别失败'})

        # AI分析
        analysis_result = await analyze_video_transcript(transcript, video_type)

        if not analysis_result['success']:
            return web.json_response({'success': False, 'error': analysis_result.get('error', '分析失败')})

        # 保存结果
        save_video_analysis(video_type, analysis_result)

        # 清理视频文件
        if os.path.exists(video_path):
            os.remove(video_path)

        return web.json_response({
            'success': True,
            'analysis': analysis_result['analysis'],
            'transcript_length': len(transcript)
        })

    except Exception as e:
        logging.error(f"Mini App视频分析错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})
