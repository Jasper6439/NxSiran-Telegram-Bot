# 心级事件 API

import json
import logging
from datetime import datetime
from aiohttp import web
from database import get_db
from system.config import get_default_tz
from characters import get_current_character
from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


async def api_check_heart_events(request):
    """检查可触发的心级事件"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'

        db = get_db()

        # 获取角色当前位置
        location = db.get_character_location(character_id)
        current_hour = datetime.now(get_default_tz()).hour if location else 99

        # 获取可触发事件
        available = db.get_available_events(user_id, character_id)

        # 检查是否有符合当前场景的事件
        triggerable = []
        for event in available:
            # 检查位置
            if event.get('trigger_location') and location:
                if event['trigger_location'] != location['location']:
                    continue

            # 检查时间
            if event.get('trigger_time_start') is not None:
                if current_hour < event['trigger_time_start'] or current_hour >= event.get('trigger_time_end', 24):
                    continue

            triggerable.append(event)

        return web.json_response({
            'success': True,
            'events': triggerable,
            'current_location': location['location'] if location else None,
            'current_hour': current_hour
        })

    except Exception as e:
        logger.error(f"[Game API] 检查事件失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_trigger_heart_event(request):
    """触发心级事件"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        event_id = data.get('event_id', '')

        if not event_id:
            return web.json_response({'success': False, 'error': '缺少事件ID'})

        db = get_db()

        # 触发事件
        event = db.trigger_event(user_id, event_id)

        if not event:
            return web.json_response({'success': False, 'error': '事件不存在或已触发'})

        # 解析对话
        dialogue = []
        try:
            dialogue = json.loads(event.get('dialogue', '[]'))
        except Exception:
            pass

        # 解析奖励
        rewards = {}
        try:
            rewards = json.loads(event.get('rewards', '{}'))
        except Exception:
            pass

        # 获取新的关系状态
        relationship = db.get_relationship(user_id, event['character_id'])

        # 记录游戏事件
        db.log_game_event(user_id, 'heart_event', {
            'event_id': event_id,
            'title': event.get('title', ''),
            'rewards': rewards
        }, 'miniapp')

        return web.json_response({
            'success': True,
            'event': {
                'id': event['id'],
                'title': event.get('title', ''),
                'description': event.get('description', ''),
                'dialogue': dialogue,
                'rewards': rewards
            },
            'relationship': relationship
        })

    except Exception as e:
        logger.error(f"[Game API] 触发事件失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
