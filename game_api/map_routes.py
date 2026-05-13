# 多地图系统 API (v1.4.10.2)

import logging
from aiohttp import web
from database.base import get_db
from database.maps import MAPS
from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


async def api_get_maps(request):
    """获取所有地图列表和解锁状态

    GET /api/game/maps
    Response: {
        success: true,
        maps: [...],
        current_map: "home",
        unlocked_count: 3,
        total_maps: 6
    }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()

        # 检查好感度自动解锁新地图
        character_id = request.query.get('character_id', 'chayewoon')
        emotions = db.get_emotion_values(user_id, character_id)
        newly_unlocked = db.check_and_unlock_maps(user_id, emotions.get('affection', 0))

        # 获取完整地图状态
        map_state = db.get_map_state(user_id)

        return web.json_response({
            'success': True,
            'current_map': map_state['current_map'],
            'maps': map_state['maps'],
            'unlocked_count': map_state['unlocked_count'],
            'total_maps': map_state['total_maps'],
            'newly_unlocked': newly_unlocked,
        })

    except Exception as e:
        logger.error(f"[Map API] 获取地图列表失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_switch_map(request):
    """切换当前地图

    POST /api/game/maps/switch
    Body: { "map_id": "cafe" }
    Response: {
        success: true,
        previous_map: "home",
        current_map: "cafe",
        map_info: {...},
        spawn_point: {x, y},
        message: "已移动到「咖啡厅」"
    }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        map_id = data.get('map_id', '')

        if not map_id:
            return web.json_response({'success': False, 'error': '缺少 map_id 参数'})

        db = get_db()
        result = db.switch_map(user_id, map_id)

        if result['success']:
            return web.json_response(result)
        else:
            return web.json_response(result)

    except Exception as e:
        logger.error(f"[Map API] 切换地图失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_map_state(request):
    """获取当前地图详细状态

    GET /api/game/maps/state
    Response: {
        success: true,
        current_map: "home",
        current_map_info: {
            id, name, description, emoji, grid_size, bg_color,
            spawn_point, activities, buildings, decorations, npc_locations
        },
        maps: [...],
        unlocked_count: 3,
        total_maps: 6
    }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()
        map_state = db.get_map_state(user_id)

        # 获取玩家当前位置
        player_pos = db.get_player_position(user_id)

        return web.json_response({
            'success': True,
            'current_map': map_state['current_map'],
            'current_map_info': map_state['current_map_info'],
            'maps': map_state['maps'],
            'unlocked_count': map_state['unlocked_count'],
            'total_maps': map_state['total_maps'],
            'player': player_pos or {'x': 0, 'y': 0, 'direction': 'down'},
        })

    except Exception as e:
        logger.error(f"[Map API] 获取地图状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_discover_map(request):
    """发现地图上的新内容

    POST /api/game/maps/discover
    Body: { "discovery_key": "park_hidden_spot", "data": {...} }
    Response: {
        success: true,
        new: true,
        discovery_key: "park_hidden_spot",
        message: "发现了新内容！"
    }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        discovery_key = data.get('discovery_key', '')

        if not discovery_key:
            return web.json_response({'success': False, 'error': '缺少 discovery_key 参数'})

        discovery_data = data.get('data', {})

        db = get_db()
        result = db.discover_map_content(user_id, discovery_key, discovery_data)

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Map API] 发现地图内容失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_map_discoveries(request):
    """获取玩家在所有地图上的发现

    GET /api/game/maps/discoveries
    Response: {
        success: true,
        discoveries: {...}
    }
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()
        discoveries = db.get_map_discoveries(user_id)

        return web.json_response({
            'success': True,
            'discoveries': discoveries,
        })

    except Exception as e:
        logger.error(f"[Map API] 获取发现列表失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
