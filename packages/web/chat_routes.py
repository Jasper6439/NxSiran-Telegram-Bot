"""
聊天 + 统计 API 模块
包含 Web 端聊天和仪表盘数据统计的 API 端点。
"""

import asyncio
import logging
import os

from datetime import datetime

from aiohttp import web

from config import *
from auth import *
from prompts import *
from memory_legacy import *
from emotion import *
from stats import *
from image_gen import *
from chat_history import *

# AI client - use the same alias as bot.py
from ai_client import call_ai as call_ai


async def api_chat(request):
    """Web 端聊天 API - 使用蒸馏角色模块，与 Telegram 双向同步"""
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

        # 获取用户显示名（默认"学长"，与角色台词一致）
        user_name = '学长'
        try:
            from auth import load_users
            users_data = load_users()
            users = users_data.get("users", {})
            user_info = users.get(str(user_id), {})
            # 优先使用用户自定义称呼，其次 display_name，最后默认"学长"
            user_name = user_info.get('preferred_name') or user_info.get('display_name') or user_info.get('username', '学长')
        except Exception:
            pass

        # 使用蒸馏角色的系统提示词
        system_prompt = None
        try:
            from characters import get_current_character
            character = get_current_character()
            if character:
                system_prompt = character.get_system_prompt({
                    'user_id': user_id,
                    'user_name': user_name
                })
                logging.info(f"[WebChat] 使用蒸馏角色: {character.config.name}")
        except Exception as e:
            logging.warning(f"[WebChat] 加载蒸馏角色失败，使用默认: {e}")

        if not system_prompt:
            system_prompt = "你是车如云，一个傲娇但内心温柔的角色。用简洁自然的中文回复。"

        # 使用共享的聊天记录
        history = load_chat_history(user_id)

        # 调用 AI
        response = await call_ai(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=history
        )

        # 使用蒸馏角色的格式化方法
        try:
            from characters import get_current_character
            character = get_current_character()
            if character:
                response = character.format_response(response)
        except Exception:
            pass

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

        # 分析对话 - 使用当前用户的 user_id
        analysis = analyze_dialogue_patterns(user_id) if user_id else {}

        # 亲密度
        intimacy = calculate_intimacy(stats)

        # 情绪分布
        emotions = analysis.get("用户情绪分布", {})

        # 建议列表
        advice_str = get_relationship_advice(analysis)
        advice_list = [line.strip() for line in advice_str.split('\n') if line.strip()]

        # 用户特定的照片目录
        user_selfie_dir = get_user_selfie_dir(user_id)
        user_selfie_count = 0
        if os.path.exists(user_selfie_dir):
            user_selfie_count = len([f for f in os.listdir(user_selfie_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])
        
        # 用户照片目录
        user_photos_dir = os.path.join(get_user_dir(user_id), 'photos')
        user_photo_count = 0
        if os.path.exists(user_photos_dir):
            user_photo_count = len([f for f in os.listdir(user_photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])

        return web.json_response({
            'total_messages': stats.get('total_messages', 0),
            'total_days': stats.get('total_days', 0),
            'today_count': stats.get('today_count', 0),
            'memory_count': stats.get('memories_count', 0),
            'caring_count': analysis.get('关心表达次数', 0) if isinstance(analysis.get('关心表达次数', 0), int) else 0,
            'jealous_count': analysis.get('吃醋次数', 0) if isinstance(analysis.get('吃醋次数', 0), int) else 0,
            'warm_count': analysis.get('温暖表达次数', 0) if isinstance(analysis.get('温暖表达次数', 0), int) else 0,
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
            'selfie_count': user_selfie_count,
            'user_photo_count': user_photo_count,
        })
    except Exception as e:
        logging.error(f"仪表盘API错误: {e}")
        return web.json_response({'error': str(e)})
