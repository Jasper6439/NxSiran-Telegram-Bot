"""
Web API Routes - Extracted from bot.py (lines 3128-4066)
Contains all HTTP endpoint handlers for the web interface, Mini App, and API.
"""

import asyncio
import base64
import json
import logging
import os
import subprocess
import io
from datetime import datetime

from aiohttp import web

from config import *
from auth import *
from prompts import *
from memory_legacy import *
from weather import *
from anniversary import *
from emotion import *
from stats import *
from image_gen import *
from chat_history import *
from characters import (
    get_current_character,
    set_current_character,
    list_characters,
)

# AI client - use the same alias as bot.py
from ai_client import call_ai as call_ai

# Functions from packages modules
from packages.analysis.chatlog import (
    parse_wechat_chatlog,
    analyze_chatlog_with_ai,
)
from packages.importers.video import (
    extract_audio_from_video,
    transcribe_audio_primary,
    transcribe_audio_whisper,
    analyze_video_transcript,
    save_video_analysis,
)

# Skills manager imports
from config import SKILLS_REGISTRY, SKILLS_STATE_FILE, load_json, save_json

# Skills state management functions
def _load_skills_state():
    """Load skills persistent state from disk."""
    global SKILLS_REGISTRY
    if os.path.exists(SKILLS_STATE_FILE):
        try:
            state = load_json(SKILLS_STATE_FILE, {})
            for sid, sdata in state.get('skills', {}).items():
                if sid in SKILLS_REGISTRY:
                    SKILLS_REGISTRY[sid].update(sdata)
                else:
                    SKILLS_REGISTRY[sid] = sdata
        except Exception as e:
            logging.error(f"[skills-manager] 加载 skills 状态失败: {e}")

def _save_skills_state():
    """Save skills persistent state to disk."""
    try:
        state = {'skills': {sid: dict(sdata) for sid, sdata in SKILLS_REGISTRY.items()}}
        save_json(SKILLS_STATE_FILE, state)
    except Exception as e:
        logging.error(f"[skills-manager] 保存 skills 状态失败: {e}")

def load_character_skill_overrides():
    """Load character-specific skill overrides."""
    pass  # Character skill overrides are handled by the characters module

def is_skill_enabled_for_character(skill_id, character_id=None):
    """Check if a skill is enabled for a specific character."""
    if skill_id not in SKILLS_REGISTRY:
        return False
    return SKILLS_REGISTRY[skill_id].get('enabled', True)

def set_skill_for_character(skill_id, character_id, enabled):
    """Enable/disable a skill for a specific character."""
    if skill_id in SKILLS_REGISTRY:
        SKILLS_REGISTRY[skill_id]['enabled'] = enabled
        _save_skills_state()


# Helper imports for skills functions (defined in bot.py or config.py)
# These need to be imported from bot since they modify global state
def _get_skills_functions():
    """Lazy import skills functions from bot module to avoid circular imports."""
    import bot
    return bot


__all__ = [
    "health_check",
    "serve_index",
    "api_chat",
    "api_stats",
    "serve_miniapp",
    "serve_game",
    "api_upload_selfies",
    "api_get_selfies",
    "api_delete_selfie",
    "api_delete_user_photo",
    "api_user_photos",
    "serve_uploaded_file",
    "api_analyze_chatlog",
    "api_analyze_video",
    "api_register",
    "api_login",
    "api_get_config",
    "api_update_config",
    "api_skills_list",
    "api_skill_toggle",
    "api_skill_install",
    "api_skill_uninstall",
    "api_quota_status",
    "api_list_characters",
    "api_switch_character",
    "cors_middleware",
]


async def health_check(request):
    return web.Response(text="🟢 车如云在线 v3.2")


async def serve_index(request):
    """提供Web界面HTML"""
    try:
        # Use workspace root for template paths
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(workspace_root, 'templates', 'index.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="Web界面文件未找到", status=404)


async def api_chat(request):
    """Web 端聊天 API - 与 Telegram 双向同步"""
    try:
        data = await request.json()
        user_message = data.get('message', '')

        if not user_message.strip():
            return web.json_response({'error': '消息不能为空'})

        # 获取用户ID（优先使用 session token）
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)  # 兼容旧 token
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        # 使用共享的聊天记录
        history = load_chat_history(user_id)

        # 调用 AI（call_ai 内部已使用角色系统提示词）
        response = await call_ai(user_message, history)

        # 保存到共享历史（带时间戳）
        timestamp = datetime.now(get_default_tz()).isoformat()
        history.append({"role": "user", "content": user_message, "timestamp": timestamp})
        history.append({"role": "assistant", "content": response, "timestamp": timestamp})
        save_chat_history(user_id, history)

        # [双向同步] 如果配置了 Telegram Bot，将用户消息和回复都发送到Telegram
        try:
            if TELEGRAM_TOKEN and user_id and user_id == YOUR_CHAT_ID:
                import telegram
                from telegram.request import HTTPXRequest

                # 异步发送消息到 Telegram（不等待结果）
                async def send_to_telegram():
                    try:
                        bot = telegram.Bot(token=TELEGRAM_TOKEN, request=HTTPXRequest())
                        # 先发送用户消息（标注来自Web）
                        await bot.send_message(
                            chat_id=user_id,
                            text=f"🌐 [Web] {user_message}"
                        )
                        # 再发送AI回复
                        await bot.send_message(
                            chat_id=user_id,
                            text=response
                        )
                        logging.info(f"[双向同步] 消息已发送到 Telegram: {user_id}")
                    except Exception as e:
                        logging.error(f"[双向同步] 发送到 Telegram 失败: {e}")

                # 后台发送，不阻塞响应
                asyncio.create_task(send_to_telegram())
        except Exception as e:
            logging.error(f"[双向同步] 初始化发送失败: {e}")

        return web.json_response({'response': response})
    except Exception as e:
        logging.error(f"[WebChat] 错误: {e}")
        return web.json_response({'error': str(e)})


async def api_stats(request):
    """仪表盘数据API端点"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        stats = load_stats(user_id)
        stats["memories_count"] = len(load_json(get_user_memory_file(user_id), []))

        # 分析对话
        analysis = analyze_dialogue_patterns(YOUR_CHAT_ID) if YOUR_CHAT_ID else {}

        # 亲密度
        intimacy = calculate_intimacy(stats)

        # 情绪分布
        emotions = analysis.get("用户情绪分布", {})

        # 建议列表
        advice_str = get_relationship_advice(analysis)
        advice_list = [line.strip() for line in advice_str.split('\n') if line.strip()]

        return web.json_response({
            'total_messages': stats.get('total_messages', 0),
            'total_days': stats.get('total_days', 0),
            'today_count': stats.get('today_count', 0),
            'memory_count': stats.get('memories_count', 0),
            'caring_count': analysis.get('关心表达次数', 0) if isinstance(analysis.get('关心表达次数'), int) else 0,
            'jealous_count': analysis.get('吃醋次数', 0) if isinstance(analysis.get('吃醋次数'), int) else 0,
            'warm_count': analysis.get('温暖表达次数', 0) if isinstance(analysis.get('温暖表达次数'), int) else 0,
            'intimacy_score': intimacy['score'],
            'intimacy_level': intimacy['level'],
            'emotions': emotions,
            'user_avg_len': analysis.get('用户平均消息长度', '--'),
            'bot_avg_len': analysis.get('车如云平均回复长度', '--'),
            'user_initiative': analysis.get('用户主动发起比例', '--'),
            'avg_daily': analysis.get('日均消息数', '--'),
            'bot_ellipsis': analysis.get('车如云使用省略号', '--'),
            'bot_inner': analysis.get('车如云内心独白', '--'),
            'advice': advice_list,
            'selfie_count': get_selfie_count(),
            'user_photo_count': len([f for f in os.listdir(USER_PHOTOS_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))]) if os.path.exists(USER_PHOTOS_DIR) else 0,
        })
    except Exception as e:
        logging.error(f"仪表盘API错误: {e}")
        return web.json_response({'error': str(e)})


# ============================================================
# Telegram Mini App API
# ============================================================

async def serve_miniapp(request):
    """提供Telegram Mini App HTML（新版模块化）"""
    try:
        # 优先使用配置的 public_url，否则从请求中获取
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
            logging.info(f"[MiniApp] 使用配置的 public_url: {api_base}")
        else:
            # 自动检测当前 URL
            host = request.host
            scheme = request.scheme
            # 如果是 Cloudflare Tunnel，使用 https
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"
            logging.info(f"[MiniApp] 自动检测 API_BASE: {api_base}")

        # Use workspace root for template paths
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(workspace_root, 'static', 'miniapp', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE（替换占位符）
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[MiniApp] 服务新版 Mini App, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        logging.warning("[MiniApp] 新版文件未找到，回退到旧版")
        # 回退到旧版
        try:
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            template_path = os.path.join(workspace_root, 'templates', 'miniapp.html')
            with open(template_path, 'r', encoding='utf-8') as f:
                html = f.read()
            config = load_config()
            public_url = config.get('public_url', '').strip()
            if public_url:
                api_base = public_url.rstrip('/')
            else:
                host = request.host
                scheme = request.scheme
                if 'trycloudflare.com' in host or 'ngrok' in host:
                    scheme = 'https'
                api_base = f"{scheme}://{host}"
            html = html.replace(
                'const API_BASE = window.location.origin;',
                f'const API_BASE = "{api_base}";'
            )
            return web.Response(text=html, content_type='text/html')
        except FileNotFoundError:
            return web.Response(text="Mini App文件未找到", status=404)


async def serve_game(request):
    """提供独立游戏网站 HTML"""
    try:
        # 检测 API_BASE
        config = load_config()
        public_url = config.get('public_url', '').strip()

        if public_url:
            api_base = public_url.rstrip('/')
        else:
            host = request.host
            scheme = request.scheme
            if 'trycloudflare.com' in host or 'ngrok' in host:
                scheme = 'https'
            api_base = f"{scheme}://{host}"

        # Use workspace root for template paths
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(workspace_root, 'static', 'game', 'index.html')

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 注入 API_BASE
        html = html.replace('__API_BASE__', api_base)

        logging.info(f"[Game] 服务游戏网站, API_BASE: {api_base}")
        return web.Response(text=html, content_type='text/html')
    except FileNotFoundError:
        return web.Response(text="游戏文件未找到", status=404)
    except Exception as e:
        logging.error(f"[Game] 服务游戏网站失败: {e}")
        return web.Response(text=f"游戏加载失败: {e}", status=500)


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
                        'url': f'/uploads/selfies/{f}',
                        'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d'),
                        'size': stat.st_size
                    })

        return web.json_response({
            'success': True,
            'selfies': selfies,
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

        if folder == 'selfies':
            # 在所有用户目录中查找自拍文件（包括角色子目录）
            filepath = None
            if os.path.exists(DATA_DIR):
                for entry in os.listdir(DATA_DIR):
                    if entry.startswith("user_"):
                        user_dir = os.path.join(DATA_DIR, entry, "selfies")
                        if os.path.isdir(user_dir):
                            # 先检查直接路径
                            candidate = os.path.join(user_dir, filename)
                            if os.path.exists(candidate):
                                filepath = candidate
                                break
                            # 再检查角色子目录
                            for sub in os.listdir(user_dir):
                                sub_path = os.path.join(user_dir, sub)
                                if os.path.isdir(sub_path):
                                    candidate = os.path.join(sub_path, filename)
                                    if os.path.exists(candidate):
                                        filepath = candidate
                                        break
                            if filepath:
                                break
            if not filepath:
                # 回退到旧的全局目录
                filepath = os.path.join(SELFIE_DIR, filename)
        elif folder == 'user_photos':
            filepath = os.path.join(USER_PHOTOS_DIR, filename)
        else:
            return web.Response(status=404)

        if os.path.exists(filepath):
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


async def api_register(request):
    """用户注册API"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        chat_id = data.get('chat_id', '').strip()

        # 验证必填字段
        if not username or not password or not chat_id:
            return web.json_response({'success': False, 'error': '用户名、密码和Chat ID不能为空'})

        # 验证 chat_id 是否为数字
        try:
            int(chat_id)
        except ValueError:
            return web.json_response({'success': False, 'error': 'Chat ID 必须是数字'})

        # 验证密码长度
        if len(password) < 6:
            return web.json_response({'success': False, 'error': '密码长度至少6位'})

        # 注册用户
        success, message = register_user(username, password, chat_id)

        if success:
            # 注册成功后自动登录
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True,
                'message': message,
                'token': token,
                'user_id': int(chat_id),
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[API注册] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_login(request):
    """Mini App登录API - 新用户系统"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        if not username or not password:
            return web.json_response({'success': False, 'error': '用户名和密码不能为空'})

        # 验证用户
        success, chat_id = validate_user(username, password)

        if success and chat_id:
            user_id = int(chat_id)
            token = generate_session_token(username, chat_id)
            config = load_config()
            is_admin = (username == config.get("admin_username", "Ulysses"))
            return web.json_response({
                'success': True,
                'token': token,
                'user_id': user_id,
                'username': username,
                'is_admin': is_admin
            })
        else:
            return web.json_response({'success': False, 'error': '用户名或密码错误'})

    except Exception as e:
        logging.error(f"[API登录] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_config(request):
    """Mini App获取配置API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        config = load_config()
        # 不返回完整密钥，只返回部分
        safe_config = {
            'telegram_token': config.get('telegram_token', '')[:10] + '***' if config.get('telegram_token') else '',
            'chat_id': config.get('chat_id', ''),
            'ai_api_key': config.get('ai_api_key', '')[:15] + '***' if config.get('ai_api_key') else '',
            'ai_api_base': config.get('ai_api_base', ''),
            'admin_username': config.get('admin_username', ''),
            'public_url': config.get('public_url', ''),
        }
        return web.json_response({'success': True, 'config': safe_config})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_update_config(request):
    """Mini App更新配置API - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可修改配置'})

        data = await request.json()
        config = load_config()

        # 允许更新的字段
        updatable = ['telegram_token', 'chat_id', 'ai_api_key', 'ai_api_base', 'admin_username', 'admin_password', 'public_url']
        updated = []

        for key in updatable:
            if key in data and data[key]:
                config[key] = data[key]
                updated.append(key)

        save_config(config)

        # 如果更新了关键配置，重新加载全局变量
        global TELEGRAM_TOKEN, YOUR_CHAT_ID, AI_API_KEY, AI_API_BASE
        if 'telegram_token' in updated:
            TELEGRAM_TOKEN = config.get('telegram_token', '')
        if 'chat_id' in updated:
            YOUR_CHAT_ID = int(config.get('chat_id', '0'))
        if 'ai_api_key' in updated:
            AI_API_KEY = config.get('ai_api_key', '')
        if 'ai_api_base' in updated:
            AI_API_BASE = config.get('ai_api_base', '')

        return web.json_response({'success': True, 'updated': updated, 'message': f'已更新: {", ".join(updated)}'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# [Skill: skills-manager] Skills 管理功能
# ============================================================

async def api_skills_list(request):
    """[Skill: skills-manager] 获取所有 skills 列表"""
    try:
        character_id = request.query.get('character_id')

        skills_list = []
        for sid, sdata in SKILLS_REGISTRY.items():
            enabled = is_skill_enabled_for_character(sid, character_id)
            skills_list.append({
                "id": sid,
                "name": sdata.get("name", sid),
                "description": sdata.get("desc", ""),
                "desc": sdata.get("desc", ""),
                "enabled": enabled,
                "category": sdata.get("category", "其他"),
                "version": sdata.get("version", "1.0"),
            })

        return web.json_response({'success': True, 'skills': skills_list})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_toggle(request):
    """[Skill: skills-manager] 启用/禁用 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可管理技能'})

        data = await request.json()
        skill_id = data.get('skill_id', '')
        enabled = data.get('enabled', True)
        character_id = data.get('character_id')

        if character_id:
            set_skill_for_character(skill_id, character_id, enabled)
        else:
            # Global toggle
            if skill_id in SKILLS_REGISTRY:
                SKILLS_REGISTRY[skill_id]['enabled'] = enabled
                _save_skills_state()

        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_install(request):
    """[Skill: skills-manager] 安装新 skill - 仅管理员"""
    try:
        if not is_admin_user(request):
            return web.json_response({'success': False, 'error': '仅管理员可安装技能'})

        data = await request.json()
        skill_name = data.get('skill_name', '').strip()

        if not skill_name:
            return web.json_response({'success': False, 'error': '缺少 skill_name 参数'})

        # 执行 clawhub install
        logging.info(f"[skills-manager] 正在安装 skill: {skill_name}")
        result = subprocess.run(
            ["clawhub", "install", skill_name, "--force"],
            capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip() or "安装失败（未知错误）"
            logging.warning(f"[skills-manager] 安装 skill '{skill_name}' 失败: {error_msg}")
            return web.json_response({
                'success': False,
                'error': f'安装失败: {error_msg}',
            })

        # 安装成功，尝试读取 SKILL.md 提取描述
        desc = ""
        skill_md_path = f"/workspace/skills/{skill_name}/SKILL.md"
        try:
            if os.path.exists(skill_md_path):
                with open(skill_md_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # 从前几行提取描述信息
                for line in lines[:20]:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        desc = line[:200]  # 取前200字符作为描述
                        break
        except Exception:
            pass

        # 添加到 SKILLS_REGISTRY
        SKILLS_REGISTRY[skill_name] = {
            "name": skill_name,
            "desc": desc or f"通过 clawhub 安装的 skill: {skill_name}",
            "enabled": True,
            "category": "自定义",
        }
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_name}' 安装成功")
        return web.json_response({
            'success': True,
            'skill_id': skill_name,
            'desc': desc,
            'message': f'Skill "{skill_name}" 安装成功',
        })
    except subprocess.TimeoutExpired:
        return web.json_response({'success': False, 'error': '安装超时（60秒）'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_skill_uninstall(request):
    """[Skill: skills-manager] 卸载 skill（从注册表移除，不删除代码）"""
    try:
        data = await request.json()
        skill_id = data.get('skill_id', '')

        if not skill_id:
            return web.json_response({'success': False, 'error': '缺少 skill_id 参数'})

        if skill_id not in SKILLS_REGISTRY:
            return web.json_response({'success': False, 'error': f'Skill "{skill_id}" 不存在'})

        # 从注册表移除（不删除代码文件）
        removed = SKILLS_REGISTRY.pop(skill_id)
        _save_skills_state()

        logging.info(f"[skills-manager] Skill '{skill_id}' 已从注册表移除（代码未删除）")
        return web.json_response({
            'success': True,
            'skill_id': skill_id,
            'removed': removed,
            'message': f'Skill "{skill_id}" 已卸载（代码文件保留）',
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_quota_status(request):
    """额度监控 API"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            user_id = 1

        usage = load_quota_usage()
        status = check_quota_status(usage)
        month = get_current_month()

        items = [
            {
                'name': 'API 请求',
                'icon': '📡',
                'used': usage.get('requests', 0),
                'limit': QUOTA_LIMITS['requests'],
                'unit': '次',
                'color': '#8E24AA',
            },
            {
                'name': 'CPU 用量',
                'icon': '⚡',
                'used': round(usage.get('cpu_seconds', 0), 1),
                'limit': QUOTA_LIMITS['cpu_seconds'],
                'unit': '秒',
                'color': '#2a5290',
            },
            {
                'name': '内存用量',
                'icon': '🧠',
                'used': round(usage.get('memory_gib_seconds', 0), 1),
                'limit': QUOTA_LIMITS['memory_gib_seconds'],
                'unit': 'GiB·s',
                'color': '#6CD9A8',
            },
            {
                'name': '网络流量',
                'icon': '🌐',
                'used': round(usage.get('network_gb', 0), 3),
                'limit': QUOTA_LIMITS['network_gb'],
                'unit': 'GB',
                'color': '#F4A4A4',
            },
        ]

        # 计算各项百分比
        for item in items:
            item['percent'] = round(min(item['used'] / item['limit'] * 100, 100), 1) if item['limit'] > 0 else 0

        # AI 请求统计
        ai_requests = usage.get('ai_requests', 0)
        image_gens = usage.get('image_generations', 0)

        return web.json_response({
            'success': True,
            'status': status,
            'month': month,
            'items': items,
            'ai_requests': ai_requests,
            'image_generations': image_gens,
            'shutdown': usage.get('shutdown_triggered', False),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_list_characters(request):
    """列出所有可用角色"""
    try:
        characters = list_characters()
        current = get_current_character()
        return web.json_response({
            'success': True,
            'characters': characters,
            'current': current.config.id if current else None,
            'count': len(characters),
        })
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_switch_character(request):
    """切换当前角色"""
    try:
        data = await request.json()
        character_id = data.get('character_id', '')

        if not character_id:
            return web.json_response({'success': False, 'error': '缺少 character_id 参数'})

        if set_current_character(character_id):
            character = get_current_character()
            return web.json_response({
                'success': True,
                'character': character.to_dict() if character else None,
                'message': f'已切换到角色: {character.config.name if character else character_id}',
            })
        else:
            return web.json_response({'success': False, 'error': f'角色 "{character_id}" 不存在'})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


# 启动时加载 skills 持久化状态
_load_skills_state()
load_character_skill_overrides()


# CORS 中间件 - 允许 Telegram Mini App 跨域访问
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        response = web.Response()
    else:
        response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response
