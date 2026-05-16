"""
api/routes_chat.py - 统一聊天路由 (v1.7)
=========================================
Web 端聊天 API，支持 SSE 流式和非流式两种模式。
复用 characters/ai_core.py 和 characters/ai_client.py 的核心逻辑。
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.deps import get_current_user
from system.config import get_default_tz

router = APIRouter(tags=["chat"])

logger = logging.getLogger(__name__)


# ============================================================
# Pydantic 请求模型
# ============================================================

class ChatRequest(BaseModel):
    message: str
    character_id: str = "chayewoon"
    stream: bool = False


# ============================================================
# 路由
# ============================================================

@router.post("/api/chat")
async def chat(req: ChatRequest, user_id: int = Depends(get_current_user)):
    """Web 端聊天 API。

    支持 SSE 流式和非流式两种模式。
    复用 characters/ai_core.py 的 call_ai 和 characters/ai_client.py 的 stream_chat_completion。
    """
    if not req.message.strip():
        return {"error": "消息不能为空"}

    if req.stream:
        return StreamingResponse(
            stream_chat_response(req, user_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        return await _handle_non_stream_chat(req, user_id)


async def _handle_non_stream_chat(req: ChatRequest, user_id: int) -> dict:
    """非流式聊天处理，复用 packages/web/chat_routes.py 的逻辑。"""
    user_message = req.message

    # 获取用户显示名
    user_name = '学长'
    try:
        from system.auth import load_users
        users_data = load_users()
        users = users_data.get("users", {})
        user_info = users.get(str(user_id), {})
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
                'user_name': user_name,
            })
            logger.info(f"[WebChat] 使用蒸馏角色: {character.config.name}")
    except Exception as e:
        logger.warning(f"[WebChat] 加载蒸馏角色失败，使用默认: {e}")

    if not system_prompt:
        system_prompt = "你是车如云，一个傲娇但内心温柔的角色。用简洁自然的中文回复。"

    # 使用共享的聊天记录
    from characters.chat_history import load_chat_history, save_chat_history
    history = load_chat_history(user_id)

    # AI 竞争模式，fallback 到单模型
    try:
        from characters.ai_compete import compete_reply
        response = await compete_reply(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=history,
        )
    except Exception as e:
        logger.warning(f"[WebChat] AI竞争失败，fallback 单模型: {e}")
        from characters.ai_client import call_ai as ai_client_call_ai
        response = await ai_client_call_ai(
            system_prompt=system_prompt,
            user_message=user_message,
            chat_history=history,
        )

    # 使用蒸馏角色的格式化方法
    try:
        from characters import get_current_character
        character = get_current_character()
        if character:
            response = character.format_response(response)
    except Exception:
        pass

    # 保存到共享历史
    timestamp = datetime.now(get_default_tz()).isoformat()
    history.append({"role": "user", "content": user_message, "timestamp": timestamp})
    history.append({"role": "assistant", "content": response, "timestamp": timestamp})
    save_chat_history(user_id, history)

    # 自动发自拍检测
    selfie_generated = None
    selfie_keywords = ['自拍', '照片', '拍给你看', '给你看', '这张照片', '我拍的照片']
    if response and any(kw in response for kw in selfie_keywords):
        try:
            from characters.image_gen import generate_face_from_user_photos
            selfie_result = await generate_face_from_user_photos(str(user_id))
            if selfie_result.get("success"):
                selfie_generated = selfie_result["image_b64"]
        except Exception as e:
            logger.debug(f"[自动发自拍] 生成失败: {e}")

    # 双向同步到 Telegram
    try:
        from system.auth import get_user_info, get_character_bot_token
        user_info = get_user_info(user_id)
        telegram_chat_id = user_info.get('telegram_chat_id') if user_info else None

        if telegram_chat_id:
            character_id = req.character_id or 'chayewoon'
            bot_token = get_character_bot_token(user_id, character_id)

            if bot_token:
                async def send_to_telegram():
                    try:
                        import telegram
                        from telegram.request import HTTPXRequest
                        bot = telegram.Bot(token=bot_token, request=HTTPXRequest())
                        await bot.send_message(
                            chat_id=telegram_chat_id,
                            text=response,
                        )
                        logger.info(f"[双向同步] 消息已通过角色 {character_id} 的 Bot 发送到 Telegram: {telegram_chat_id}")
                    except Exception as e:
                        logger.error(f"[双向同步] 发送到 Telegram 失败: {e}")

                asyncio.create_task(send_to_telegram())
    except Exception as e:
        logger.error(f"[双向同步] 初始化发送失败: {e}")

    result_data = {"response": response, "character_id": req.character_id}
    if selfie_generated:
        result_data["selfie"] = selfie_generated
    return result_data


async def stream_chat_response(req: ChatRequest, user_id: int):
    """SSE 流式响应生成器。

    使用 characters/ai_client.py 的 stream_chat_completion_generator 进行真正的逐 token 流式输出。
    包含连接保护：客户端断开时正确清理资源。
    """
    from characters.ai_client import stream_chat_completion_generator
    from starlette.requests import Request

    # 获取用户显示名
    user_name = '学长'
    try:
        from system.auth import load_users
        users_data = load_users()
        users = users_data.get("users", {})
        user_info = users.get(str(user_id), {})
        user_name = user_info.get('preferred_name') or user_info.get('display_name') or '学长'
    except Exception:
        pass

    # 构建系统提示词
    system_prompt = None
    try:
        from characters import get_current_character
        character = get_current_character()
        if character:
            system_prompt = character.get_system_prompt({
                'user_id': user_id,
                'user_name': user_name,
            })
    except Exception as e:
        logger.warning(f"[WebChat Stream] 加载蒸馏角色失败: {e}")

    if not system_prompt:
        system_prompt = "你是车如云，一个傲娇但内心温柔的角色。用简洁自然的中文回复。"

    # 加载聊天历史
    from characters.chat_history import load_chat_history, save_chat_history
    history = load_chat_history(user_id)

    # 连接状态追踪
    is_connected = True
    full_content = ""

    try:
        # 使用真正的生成器逐 token 输出
        async for token in stream_chat_completion_generator(
            system_prompt=system_prompt,
            user_message=req.message,
            chat_history=history,
        ):
            if not is_connected:
                # 客户端已断开，停止生成
                logger.info(f"[WebChat Stream] 客户端断开，停止生成 (user_id={user_id})")
                break

            full_content += token
            # 立即发送每个 token 到前端
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # 流结束标记
        if is_connected:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # 保存到聊天历史（即使客户端断开也保存已生成的内容）
        if full_content:
            timestamp = datetime.now(get_default_tz()).isoformat()
            history.append({"role": "user", "content": req.message, "timestamp": timestamp})
            history.append({"role": "assistant", "content": full_content, "timestamp": timestamp})
            save_chat_history(user_id, history)

        # 双向同步到 Telegram（异步，不阻塞）
        if is_connected and full_content:
            try:
                from system.auth import get_user_info, get_character_bot_token
                user_info = get_user_info(user_id)
                telegram_chat_id = user_info.get('telegram_chat_id') if user_info else None

                if telegram_chat_id:
                    character_id = req.character_id or 'chayewoon'
                    bot_token = get_character_bot_token(user_id, character_id)

                    if bot_token:
                        async def send_to_telegram():
                            try:
                                import telegram
                                from telegram.request import HTTPXRequest
                                bot = telegram.Bot(token=bot_token, request=HTTPXRequest())
                                await bot.send_message(
                                    chat_id=telegram_chat_id,
                                    text=full_content,
                                )
                                logger.info(f"[双向同步] 流式消息已通过角色 {character_id} 的 Bot 发送到 Telegram")
                            except Exception as e:
                                logger.error(f"[双向同步] 发送流式消息到 Telegram 失败: {e}")

                        asyncio.create_task(send_to_telegram())
            except Exception as e:
                logger.error(f"[双向同步] 初始化流式发送失败: {e}")

    except Exception as e:
        logger.error(f"[WebChat Stream] 流式对话错误: {e}")
        if is_connected:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    finally:
        # 清理资源：确保生成器正确关闭
        is_connected = False
        logger.debug(f"[WebChat Stream] 连接清理完成 (user_id={user_id})")


@router.get("/api/stats")
async def get_stats(user_id: int = Depends(get_current_user)):
    """仪表盘数据 API"""
    try:
        from characters.stats import load_stats
        from characters.emotion import analyze_dialogue_patterns, calculate_intimacy, get_relationship_advice
        from system.config import load_json, get_user_memory_file, get_user_selfie_dir, get_user_dir

        stats = load_stats(user_id)
        stats["memories_count"] = len(load_json(get_user_memory_file(user_id), []))

        analysis = analyze_dialogue_patterns(user_id) if user_id else {}
        intimacy = calculate_intimacy(stats)
        emotions = analysis.get("用户情绪分布", {})

        advice_str = get_relationship_advice(analysis)
        advice_list = [line.strip() for line in advice_str.split('\n') if line.strip()]

        import os
        user_selfie_dir = get_user_selfie_dir(user_id)
        user_selfie_count = 0
        if os.path.exists(user_selfie_dir):
            user_selfie_count = len([f for f in os.listdir(user_selfie_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))])

        user_photos_dir = os.path.join(get_user_dir(user_id), 'photos')
        user_photo_count = 0
        if os.path.exists(user_photos_dir):
            user_photo_count = len([f for f in os.listdir(user_photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))])

        return {
            "total_messages": stats.get('total_messages', 0),
            "total_days": stats.get('total_days', 0),
            "today_count": stats.get('today_count', 0),
            "memory_count": stats.get('memories_count', 0),
            "caring_count": analysis.get('关心表达次数', 0) if isinstance(analysis.get('关心表达次数', 0), int) else 0,
            "jealous_count": analysis.get('吃醋次数', 0) if isinstance(analysis.get('吃醋次数', 0), int) else 0,
            "warm_count": analysis.get('温暖表达次数', 0) if isinstance(analysis.get('温暖表达次数', 0), int) else 0,
            "intimacy_score": intimacy['score'],
            "intimacy_level": intimacy['level'],
            "emotions": emotions,
            "user_avg_len": analysis.get('用户平均消息长度', '--'),
            "bot_avg_len": analysis.get('车如云平均回复长度', '--'),
            "user_initiative": analysis.get('用户主动发起比例', '--'),
            "avg_daily": analysis.get('日均消息数', '--'),
            "bot_ellipsis": analysis.get('车如云使用省略号', '--'),
            "bot_inner": analysis.get('车如云内心独白', '--'),
            "advice": advice_list,
            "selfie_count": user_selfie_count,
            "user_photo_count": user_photo_count,
        }
    except Exception as e:
        logger.error(f"仪表盘API错误: {e}")
        return {"error": str(e)}
