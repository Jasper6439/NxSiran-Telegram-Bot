# 同步 + 全量状态 API + SSE 实时推送
# v1.6.3 — 前后端游戏状态同步

import asyncio
import json
import logging
import time

from aiohttp import web
from database import get_db
from characters import get_current_character
from game_api.auth import authenticate_request
from game_api.game_state import (
    serialize_game_state, get_state_version, notify_state_change,
    compute_state_diff, get_snapshot, subscribe_state_changes,
    unsubscribe_state_changes,
)

logger = logging.getLogger(__name__)


async def api_get_game_events(request):
    """获取未同步的游戏事件"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        since = request.query.get('since', None)

        db = get_db()
        events = db.get_unsynced_events(user_id, since)

        return web.json_response({
            'success': True,
            'events': events
        })

    except Exception as e:
        logger.error(f"[Game API] 获取事件失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_mark_synced(request):
    """标记事件已同步"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        event_ids = data.get('event_ids', [])

        db = get_db()
        db.mark_events_synced(event_ids)

        return web.json_response({'success': True})

    except Exception as e:
        logger.error(f"[Game API] 标记同步失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_full_game_state(request):
    """一次性获取全部游戏状态（v1.6.3: 使用 game_state 模块，附带版本号）"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        state = serialize_game_state(user_id)
        version = get_state_version(user_id)

        return web.json_response({
            'success': True,
            'version': version,
            **state
        })

    except Exception as e:
        logger.error(f"[Game API] 获取全量状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_emotion_values(request):
    """获取情感值 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        character_id = request.query.get('character_id')
        if not character_id:
            character = get_current_character()
            character_id = character.config.id if character else 'chayewoon'

        db = get_db()
        emotions = db.get_emotion_values(user_id, character_id)

        return web.json_response({
            'success': True,
            'character_id': character_id,
            'emotions': emotions
        })

    except Exception as e:
        logger.error(f"[Game API] 获取情感值失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_check_awakening(request):
    """检查觉醒条件 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        character_id = request.query.get('character_id')
        if not character_id:
            character = get_current_character()
            character_id = character.config.id if character else 'chayewoon'

        db = get_db()
        check_result = db.check_awakening_conditions(user_id, character_id)

        return web.json_response({
            'success': True,
            'character_id': character_id,
            'can_awaken': check_result['can_awaken'],
            'conditions': check_result['conditions'],
            'current_values': check_result['current_values'],
            'current_hearts': check_result['current_hearts']
        })

    except Exception as e:
        logger.error(f"[Game API] 检查觉醒条件失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_trigger_awakening(request):
    """触发觉醒 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        event_name = data.get('event_name', 'default_awakening')
        character_id = data.get('character_id')
        if not character_id:
            character = get_current_character()
            character_id = character.config.id if character else 'chayewoon'

        db = get_db()
        result = db.trigger_awakening(user_id, character_id, event_name)

        if result:
            return web.json_response({
                'success': True,
                'event': result,
                'message': f'{character.config.name if character else "角色"} 已觉醒！'
            })
        else:
            return web.json_response({
                'success': False,
                'error': '觉醒条件未满足'
            })

    except Exception as e:
        logger.error(f"[Game API] 触发觉醒失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_switch_world_layer(request):
    """切换世界层级 API（向后兼容，同时支持 layer 和 target_layer 字段）"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        # 兼容前端发 target_layer 或 layer
        layer = data.get('target_layer') or data.get('layer', 'normal')

        db = get_db()
        result = db.switch_world_layer(user_id, layer)

        if result['success']:
            return web.json_response({
                'success': True,
                'previous_layer': result['previous_layer'],
                'current_layer': result['current_layer'],
                'layer_name': result['layer_name'],
                'message': f'已切换至 {result["layer_name"]}'
            })
        else:
            return web.json_response({
                'success': False,
                'error': result.get('error', '切换失败')
            })

    except Exception as e:
        logger.error(f"[Game API] 切换世界层级失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_world_state(request):
    """获取世界状态 API"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        db = get_db()
        world_state = db.get_world_layer_state(user_id)

        return web.json_response({
            'success': True,
            'world_state': world_state
        })

    except Exception as e:
        logger.error(f"[Game API] 获取世界状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# v1.6.3 — SSE 实时推送 + 增量同步
# ============================================================

async def api_game_state_sse(request):
    """SSE 端点 — 实时推送游戏状态变更通知

    前端连接后，服务器在有状态变更时推送版本号。
    前端收到通知后调用 /api/game/state/diff 获取增量差异。

    SSE 协议：
    - Content-Type: text/event-stream
    - 每条消息格式: data: {json}\\n\\n
    - 心跳: 每 30 秒发送 ping
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        # 创建 SSE 响应
        response = web.StreamResponse()
        response.content_type = 'text/event-stream'
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        response.headers['X-Accel-Buffering'] = 'no'
        await response.prepare(request)

        # 订阅状态变更
        queue = await subscribe_state_changes(user_id)

        try:
            # 立即发送当前版本号（让前端知道从哪个版本开始）
            current_version = get_state_version(user_id)
            init_msg = json.dumps({
                'type': 'init',
                'version': current_version,
                'timestamp': time.time()
            }, ensure_ascii=False)
            await response.write(f"data: {init_msg}\n\n".encode('utf-8'))

            # 持续监听
            while True:
                try:
                    # 等待状态变更消息，30秒超时用于心跳
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    await response.write(f"data: {msg}\n\n".encode('utf-8'))
                except asyncio.TimeoutError:
                    # 发送心跳
                    await response.write(": ping\n\n".encode('utf-8'))

        except asyncio.CancelledError:
            logger.debug(f"[SSE] 用户 {user_id} 连接断开")
        finally:
            unsubscribe_state_changes(user_id, queue)

        return response

    except Exception as e:
        logger.error(f"[SSE] 连接失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_game_state_diff(request):
    """增量状态差异 API

    前端传入本地版本号，返回该版本之后的所有变更。
    如果版本号过期或不存在，返回 needsFullSync=true 提示前端全量拉取。
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        client_version = int(request.query.get('version', 0))
        current_version = get_state_version(user_id)

        # 版本号一致，无变更
        if client_version == current_version:
            return web.json_response({
                'success': True,
                'version': current_version,
                'hasChanges': False,
                'diff': {}
            })

        # 版本号落后太多（超过10个版本），建议全量同步
        if current_version - client_version > 10:
            return web.json_response({
                'success': True,
                'version': current_version,
                'hasChanges': True,
                'needsFullSync': True
            })

        # 尝试从快照计算差异
        old_snapshot = get_snapshot(user_id)
        new_state = serialize_game_state(user_id)

        if old_snapshot:
            diff = compute_state_diff(old_snapshot, new_state)
        else:
            # 无快照，返回全量
            return web.json_response({
                'success': True,
                'version': current_version,
                'hasChanges': True,
                'needsFullSync': True
            })

        return web.json_response({
            'success': True,
            'version': current_version,
            'hasChanges': True,
            'diff': diff
        })

    except Exception as e:
        logger.error(f"[Game API] 增量同步失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_game_state_version(request):
    """获取当前状态版本号（轻量级，用于前端轮询判断是否需要同步）"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        return web.json_response({
            'success': True,
            'version': get_state_version(user_id)
        })

    except Exception as e:
        logger.error(f"[Game API] 获取版本号失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
