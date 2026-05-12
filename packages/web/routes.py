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
from database import get_db
from game_api import authenticate_request

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
    "api_messages_history",
    "api_messages_sync",
    "cors_middleware",
    "register_routes",
]


async def health_check(request):
    from config import BOT_VERSION, APP_NAME
    return web.Response(text=f"🟢 {APP_NAME}在线 v{BOT_VERSION}")


async def serve_index(request):
    """提供Web界面HTML"""
    try:
        from config import BOT_VERSION, APP_NAME, APP_NAME_EN
        # Use workspace root for template paths
        workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        template_path = os.path.join(workspace_root, 'templates', 'index.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()
        # 注入动态版本号和项目名称
        html = html.replace('__APP_VERSION__', BOT_VERSION)
        html = html.replace('__APP_NAME__', APP_NAME)
        html = html.replace('__APP_NAME_EN__', APP_NAME_EN)
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

        # 调用 AI
        response = await call_ai(
            system_prompt="你是车如云，一个傲娇但内心温柔的角色。用简洁自然的中文回复。",
            user_message=user_message,
            chat_history=history
        )

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
    """Mini App 已融合到主页，重定向到首页"""
    raise web.HTTPFound('/')


async def serve_game(request):
    """游戏已融合到主页，重定向到首页游戏页面"""
    raise web.HTTPFound('/')


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
    """用户注册API - v1.4.5: 邮箱注册，角色独立绑定Chat ID"""
    try:
        data = await request.json()
        email = data.get('email', '').strip().lower()
        username = data.get('username', '').strip()
        password = data.get('password', '')

        # 验证必填字段
        if not email or not username or not password:
            return web.json_response({'success': False, 'error': '邮箱、用户名和密码不能为空'})

        # 验证邮箱格式
        if '@' not in email or '.' not in email.split('@')[-1]:
            return web.json_response({'success': False, 'error': '邮箱格式不正确'})

        # 验证密码长度
        if len(password) < 6:
            return web.json_response({'success': False, 'error': '密码长度至少6位'})

        # 检查邮箱是否已注册
        from auth import load_users, save_users, hash_password
        user_data = load_users()
        users = user_data.get("users", {})
        for u in users.values():
            if u.get('email', '').lower() == email:
                return web.json_response({'success': False, 'error': '该邮箱已注册'})

        # 检查用户名是否已被使用
        for u in users.values():
            if u.get('username', '').lower() == username.lower():
                return web.json_response({'success': False, 'error': '用户名已被使用'})

        # 创建用户
        from config import get_default_tz
        from datetime import datetime
        import uuid

        user_id = str(uuid.uuid4())[:8]
        config = load_config()
        role = "admin" if username == config.get("admin_username", "Ulysses") else "user"

        users[user_id] = {
            "email": email,
            "username": username,
            "password_hash": hash_password(password),
            "display_name": username.capitalize(),
            "role": role,
            "created_at": datetime.now(get_default_tz()).isoformat(),
            "last_login": None,
            "login_count": 0,
            "preferences": {"language": "zh-CN", "theme": "auto"},
            "character_bindings": {},
            "reset_code": None,
            "reset_code_expires": None
        }
        user_data["users"] = users
        save_users(user_data)

        logging.info(f"[API注册] 新用户: {username} ({email}, role: {role})")

        # 注册成功后自动登录
        token = generate_session_token(username, user_id)
        return web.json_response({
            'success': True,
            'message': '注册成功',
            'token': token,
            'user_id': user_id,
            'username': username,
            'is_admin': role == "admin"
        })

    except Exception as e:
        logging.error(f"[API注册] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_login(request):
    """Mini App登录API - v1.4.5: 支持自动登录"""
    try:
        data = await request.json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        auto_login = data.get('auto_login', False)  # 是否记住登录
        auto_token = data.get('auto_token', '')  # 自动登录令牌

        from auth import load_users, save_users, _verify_password, generate_auto_login_token

        # 如果有自动登录令牌，优先使用
        if auto_token:
            from auth import validate_auto_login_token
            user_id = validate_auto_login_token(auto_token)
            if user_id:
                user_data_loaded = load_users()
                users = user_data_loaded.get("users", {})
                user = users.get(str(user_id))
                if user:
                    token = generate_session_token(user['username'], user_id)
                    return web.json_response({
                        'success': True,
                        'token': token,
                        'user_id': user_id,
                        'username': user['username'],
                        'is_admin': user.get('role') == 'admin',
                        'display_name': user.get('display_name', user['username']),
                        'auto_token': auto_token
                    })
            return web.json_response({'success': False, 'error': '自动登录已过期，请重新登录'})

        if not username or not password:
            return web.json_response({'success': False, 'error': '用户名和密码不能为空'})

        # 验证用户（支持用户名或邮箱登录）
        user_data_loaded = load_users()
        users = user_data_loaded.get("users", {})
        user_id = None
        user_data = None

        # 先尝试用邮箱查找
        for uid, u in users.items():
            if u.get('email', '').lower() == username.lower():
                user_id = uid
                user_data = u
                break

        # 再尝试用用户名查找
        if not user_data:
            for uid, u in users.items():
                if u.get('username', '').lower() == username.lower():
                    user_id = uid
                    user_data = u
                    break

        if not user_data:
            return web.json_response({'success': False, 'error': '用户名或密码错误'})

        # 验证密码
        if not _verify_password(password, user_data['password_hash']):
            return web.json_response({'success': False, 'error': '用户名或密码错误'})

        # 检查是否为管理员（根据配置文件中的 admin_username）
        config = load_config()
        if user_data['username'] == config.get('admin_username', 'Jasper'):
            user_data['role'] = 'admin'

        # 更新登录信息
        from datetime import datetime
        from config import get_default_tz
        user_data['last_login'] = datetime.now(get_default_tz()).isoformat()
        user_data['login_count'] = user_data.get('login_count', 0) + 1
        users[user_id] = user_data
        user_data_loaded["users"] = users
        save_users(user_data_loaded)

        # 生成会话令牌
        token = generate_session_token(user_data['username'], user_id)

        # 生成自动登录令牌
        return_auto_token = None
        if auto_login:
            return_auto_token = generate_auto_login_token(user_id)

        return web.json_response({
            'success': True,
            'token': token,
            'user_id': user_id,
            'username': user_data['username'],
            'is_admin': user_data.get('role') == 'admin',
            'display_name': user_data.get('display_name', user_data['username']),
            'auto_token': return_auto_token
        })

    except Exception as e:
        logging.error(f"[API登录] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_user_profile(request):
    """获取当前用户信息 - 用于验证 token"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        # 从请求头获取 token
        auth = request.headers.get('Authorization', '')
        token = auth[7:] if auth.startswith('Bearer ') else ''

        # 获取用户详细信息
        from auth import load_users
        user_data = load_users()
        users = user_data.get("users", {})
        user = users.get(str(user_id), {})

        return web.json_response({
            'success': True,
            'user_id': user_id,
            'username': user.get('username', ''),
            'email': user.get('email', ''),
            'is_admin': user.get('role') == 'admin',
            'display_name': user.get('display_name', user.get('username', '')),
            'character_bindings': user.get('character_bindings', {})
        })
    except Exception as e:
        logging.error(f"[API用户资料] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def api_forgot_password(request):
    """找回密码 - 发送验证码"""
    try:
        data = await request.json()
        email_or_username = data.get('email_or_username', '').strip()

        if not email_or_username:
            return web.json_response({'success': False, 'error': '请输入邮箱或用户名'})

        from auth import generate_reset_code
        success, code, message = generate_reset_code(email_or_username)

        if success:
            # 这里应该发送邮件，但暂时直接返回验证码（测试用）
            # 生产环境应该调用邮件服务
            logging.info(f"[找回密码] 验证码: {code}")
            return web.json_response({
                'success': True,
                'message': '验证码已生成（测试模式：请在日志中查看）',
                'code': code  # 测试时返回，生产环境应删除
            })
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[找回密码] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_verify_reset_code(request):
    """验证重置码"""
    try:
        data = await request.json()
        email_or_username = data.get('email_or_username', '').strip()
        code = data.get('code', '').strip()

        if not email_or_username or not code:
            return web.json_response({'success': False, 'error': '请输入邮箱/用户名和验证码'})

        from auth import verify_reset_code
        success, user_id, message = verify_reset_code(email_or_username, code)

        if success:
            return web.json_response({
                'success': True,
                'user_id': user_id,
                'message': message
            })
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[验证重置码] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_reset_password(request):
    """重置密码"""
    try:
        data = await request.json()
        user_id = data.get('user_id', '')
        new_password = data.get('new_password', '')

        if not user_id or not new_password:
            return web.json_response({'success': False, 'error': '参数不完整'})

        if len(new_password) < 6:
            return web.json_response({'success': False, 'error': '密码长度至少6位'})

        from auth import reset_password
        success, message = reset_password(user_id, new_password)

        if success:
            return web.json_response({'success': True, 'message': message})
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[重置密码] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_bind_character(request):
    """绑定角色 Chat ID"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        data = await request.json()
        character_id = data.get('character_id', '')
        chat_id = data.get('chat_id', '').strip()

        if not character_id or not chat_id:
            return web.json_response({'success': False, 'error': '角色ID和Chat ID不能为空'})

        from auth import bind_character_chat_id
        success, message = bind_character_chat_id(user_id, character_id, chat_id)

        if success:
            return web.json_response({'success': True, 'message': message})
        else:
            return web.json_response({'success': False, 'error': message})

    except Exception as e:
        logging.error(f"[绑定角色] 错误: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_character_bindings(request):
    """获取用户的角色绑定"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'}, status=401)

        from auth import get_user_character_bindings
        bindings = get_user_character_bindings(user_id)

        return web.json_response({
            'success': True,
            'bindings': bindings
        })

    except Exception as e:
        logging.error(f"[获取角色绑定] 错误: {e}")
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


# ============================================================
# 消息同步 API（Web <-> Telegram 双向同步）
# ============================================================

async def api_messages_history(request):
    """获取聊天历史消息 - 用于Web端加载历史"""
    try:
        # 直接使用 session token 获取 chat_id（与 api_chat 一致）
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({
                'messages': [],
                'total_count': 0,
                'linked': False,
                'error': '未登录'
            })

        limit = int(request.query.get('limit', 50))
        history = load_chat_history(user_id)

        if len(history) > limit:
            history = history[-limit:]

        messages = [{
            'role': msg.get('role', 'user'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', '')
        } for msg in history]

        return web.json_response({
            'messages': messages,
            'total_count': len(messages),
            'linked': True
        })
    except Exception as e:
        logging.error(f"[消息历史] 获取失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_messages_sync(request):
    """同步新消息 - Web端拉取新消息"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'messages': [], 'total_count': 0, 'linked': False})

        since = int(request.query.get('since', 0))
        history = load_chat_history(user_id)
        total_count = len(history)

        if since >= total_count:
            return web.json_response({
                'messages': [],
                'total_count': total_count,
                'linked': True
            })

        new_messages = history[since:]
        messages = [{
            'role': msg.get('role', 'user'),
            'content': msg.get('content', ''),
            'timestamp': msg.get('timestamp', '')
        } for msg in new_messages]

        return web.json_response({
            'messages': messages,
            'total_count': total_count,
            'linked': True
        })
    except Exception as e:
        logging.error(f"[消息同步] 同步失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_link_telegram(request):
    """关联 Telegram 账号 - 设置用户的 telegram_id"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err
        
        data = await request.json()
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return web.json_response({'error': 'telegram_id 不能为空'}, status=400)
        
        try:
            telegram_id = int(telegram_id)
        except (ValueError, TypeError):
            return web.json_response({'error': 'telegram_id 必须是数字'}, status=400)
        
        db = get_db()
        with db.get_connection() as conn:
            conn.execute(
                "UPDATE users SET telegram_id = ? WHERE id = ?",
                (telegram_id, user_id)
            )
        
        return web.json_response({
            'success': True,
            'telegram_id': telegram_id,
            'message': f'已关联 Telegram ID: {telegram_id}'
        })
    except Exception as e:
        logging.error(f"[关联Telegram] 失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


async def api_get_linked_telegram(request):
    """获取已关联的 Telegram ID"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err
        
        db = get_db()
        user = db.get_user_by_id(user_id)
        
        return web.json_response({
            'telegram_id': user.get('telegram_id') if user else None,
            'linked': user and bool(user.get('telegram_id'))
        })
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)


async def api_send_message(request):
    """从 Web 端发送消息到 Telegram"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err
        
        data = await request.json()
        message = data.get('message', '').strip()
        
        if not message:
            return web.json_response({'error': '消息不能为空'}, status=400)
        
        if len(message) > 2000:
            return web.json_response({'error': '消息过长 (最大2000字符)'}, status=400)
        
        # Get user's telegram_id
        db = get_db()
        user = db.get_user_by_id(user_id)
        if not user or not user.get('telegram_id'):
            return web.json_response({
                'error': '请先关联 Telegram 账号',
                'linked': False
            }, status=403)
        
        telegram_id = user['telegram_id']
        
        # Save message to chat history
        from chat_history import append_message
        append_message(telegram_id, 'user', message)
        
        # Trigger bot to generate reply (async)
        # This will be handled by the bot's message handler
        # For now, just acknowledge receipt
        
        return web.json_response({
            'success': True,
            'message': '消息已发送',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logging.error(f"[发送消息] 失败: {e}")
        return web.json_response({'error': str(e)}, status=500)


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


def register_routes(app):
    """Register all web routes"""
    app.router.add_get('/', serve_index)
    app.router.add_get('/health', health_check)
    app.router.add_post('/api/chat', api_chat)
    app.router.add_get('/api/stats', api_stats)
    app.router.add_get('/api/messages/history', api_messages_history)
    app.router.add_get('/api/messages/sync', api_messages_sync)
    app.router.add_post('/api/telegram/link', api_link_telegram)
    app.router.add_get('/api/telegram/link', api_get_linked_telegram)
    app.router.add_post('/api/messages/send', api_send_message)
    app.router.add_get('/miniapp', serve_miniapp)
    app.router.add_get('/game', serve_game)
    app.router.add_post('/api/upload-selfies', api_upload_selfies)
    app.router.add_get('/api/selfies', api_get_selfies)
    app.router.add_post('/api/delete-selfie', api_delete_selfie)
    app.router.add_post('/api/delete-user-photo', api_delete_user_photo)
    app.router.add_get('/api/user-photos', api_user_photos)
    app.router.add_get('/uploads/{folder}/{filename}', serve_uploaded_file)
    app.router.add_post('/api/analyze-chatlog', api_analyze_chatlog)
    app.router.add_post('/api/analyze-video', api_analyze_video)
    app.router.add_post('/api/register', api_register)
    app.router.add_post('/api/login', api_login)
    app.router.add_post('/api/forgot-password', api_forgot_password)
    app.router.add_post('/api/verify-reset-code', api_verify_reset_code)
    app.router.add_post('/api/reset-password', api_reset_password)
    app.router.add_post('/api/bind-character', api_bind_character)
    app.router.add_get('/api/character-bindings', api_get_character_bindings)
    app.router.add_get('/api/config', api_get_config)
    app.router.add_post('/api/config', api_update_config)
    app.router.add_get('/api/skills', api_skills_list)
    app.router.add_post('/api/skills/toggle', api_skill_toggle)
    app.router.add_post('/api/skills/install', api_skill_install)
    app.router.add_post('/api/skills/uninstall', api_skill_uninstall)
    app.router.add_get('/api/quota', api_quota_status)
    app.router.add_get('/api/characters', api_list_characters)
    app.router.add_post('/api/characters/switch', api_switch_character)
    app.router.add_get('/api/user/profile', api_user_profile)

    # Static files
    app.router.add_static('/static', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'static'))

    # CORS middleware
    app.middlewares.append(cors_middleware)
