"""
聊天 + 统计 API 模块
包含 Web 端聊天和仪表盘数据统计的 API 端点。
"""

import asyncio
import logging
import os

from datetime import datetime

from aiohttp import web

from system.config import (
    CHAT_TOPIC_THREAD_ID,
    get_default_tz, load_config, load_json,
    get_user_memory_file, get_user_selfie_dir, get_user_dir,
)
from system.auth import validate_session_token, validate_api_token
from characters.emotion import calculate_intimacy
from system.prompts import analyze_dialogue_patterns, get_relationship_advice
from characters.stats import load_stats
from characters.image_gen import generate_face_from_user_photos
from characters.chat_history import load_chat_history, save_chat_history

# AI client - use the same alias as bot.py
from characters.ai_client import call_ai as call_ai


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
            if os.environ.get('DEBUG'):
                user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'error': 'Unauthorized'}, status=401)

        # 获取用户显示名（默认"学长"，与角色台词一致）
        user_name = '学长'
        try:
            from system.auth import load_users
            users_data = load_users()
            users = users_data.get("users", {})
            user_info = users.get(str(user_id), {})
            # 优先使用用户自定义称呼，其次 display_name，最后默认"学长"（不用 username）
            user_name = user_info.get('preferred_name') or user_info.get('display_name') or '学长'
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
            from system.config import FALLBACK_SYSTEM_PROMPT
            system_prompt = FALLBACK_SYSTEM_PROMPT

        # 使用共享的聊天记录
        history = load_chat_history(user_id)

        # [AI竞争] 多模型竞争生成最佳回复
        try:
            from characters.ai_compete import compete_reply
            response = await compete_reply(
                system_prompt=system_prompt,
                user_message=user_message,
                chat_history=history
            )
        except Exception as e:
            logging.warning(f"[WebChat] AI竞争失败，fallback 单模型: {e}")
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

        # 过滤由 ai_compete 规则引擎处理，此处不再重复过滤

        # 保存到共享历史（带时间戳）
        timestamp = datetime.now(get_default_tz()).isoformat()
        history.append({"role": "user", "content": user_message, "timestamp": timestamp})
        history.append({"role": "assistant", "content": response, "timestamp": timestamp})
        save_chat_history(user_id, history)

        # [自动发自拍] 检测角色表达是否暗示要发照片
        selfie_keywords = ['自拍', '照片', '拍给你看', '给你看', '这张照片', '我拍的照片']
        selfie_generated = None
        if response and any(kw in response for kw in selfie_keywords):
            try:
                from characters.image_gen import generate_face_from_user_photos
                selfie_result = await generate_face_from_user_photos(str(user_id))
                if selfie_result.get("success"):
                    selfie_generated = selfie_result["image_b64"]
            except Exception as e:
                logging.debug(f"[自动发自拍] 生成失败: {e}")

        # [双向同步 v1.4.12.13] 通过角色绑定的 Bot Token 发送消息到用户的 Telegram
        try:
            from system.auth import get_user_info, get_character_bot_token
            user_info = get_user_info(user_id)
            telegram_chat_id = user_info.get('telegram_chat_id') if user_info else None

            if telegram_chat_id:
                # 获取当前角色的 bot_token（默认 chayewoon）
                character_id = 'chayewoon'  # TODO: 支持多角色时从请求参数获取
                bot_token = get_character_bot_token(user_id, character_id)

                if bot_token:
                    import telegram
                    from telegram.request import HTTPXRequest

                    async def send_to_telegram():
                        try:
                            bot = telegram.Bot(token=bot_token, request=HTTPXRequest())
                            # 发送AI回复
                            await bot.send_message(
                                chat_id=telegram_chat_id,
                                text=response,
                                message_thread_id=CHAT_TOPIC_THREAD_ID
                            )
                            logging.info(f"[双向同步] 消息已通过角色 {character_id} 的 Bot 发送到 Telegram: {telegram_chat_id}")
                        except Exception as e:
                            logging.error(f"[双向同步] 发送到 Telegram 失败: {e}")

                    # 后台发送，不阻塞响应
                    asyncio.create_task(send_to_telegram())
        except Exception as e:
            logging.error(f"[双向同步] 初始化发送失败: {e}")

        result_data = {'response': response}
        if selfie_generated:
            result_data['selfie'] = selfie_generated
        return web.json_response(result_data)
    except Exception as e:
        logging.error(f"[WebChat] 错误: {e}")
        return web.json_response({'error': 'Chat error'})


async def api_stats(request):
    """仪表盘数据API端点"""
    try:
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            if os.environ.get('DEBUG'):
                user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'error': 'Unauthorized'}, status=401)

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
        return web.json_response({'error': 'Chat error'})
