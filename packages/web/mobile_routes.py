"""
移动端触控优化 API
v1.6.5 — 为移动端游戏提供触控操作适配端点
"""

import logging
from aiohttp import web
from game_api.auth import authenticate_request
from game_api.game_state import notify_state_change
from database import get_db

logger = logging.getLogger(__name__)


async def api_mobile_dpad_move(request):
    """移动端虚拟方向键移动

    接收方向键输入，转换为玩家坐标移动。
    支持 4 方向移动，每次移动 1 格。
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        direction = data.get('direction', 'down')  # up/down/left/right

        db = get_db()
        current = db.get_player_position(user_id)
        x = (current or {}).get('x', 0)
        y = (current or {}).get('y', 0)

        # 方向映射
        delta_map = {
            'up': (0, -1),
            'down': (0, 1),
            'left': (-1, 0),
            'right': (1, 0),
        }

        dx, dy = delta_map.get(direction, (0, 0))
        new_x = max(0, min(100, x + dx))
        new_y = max(0, min(100, y + dy))

        db.save_player_position(user_id, new_x, new_y, direction)
        notify_state_change(user_id, ['player'])

        return web.json_response({
            'success': True,
            'x': new_x,
            'y': new_y,
            'direction': direction
        })

    except Exception as e:
        logger.error(f"[Mobile] 方向键移动失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_mobile_tap_interact(request):
    """移动端点击交互

    接收屏幕坐标，转换为游戏世界坐标后执行交互。
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        screen_x = data.get('x', 0)
        screen_y = data.get('y', 0)
        action = data.get('action', 'interact')  # interact/plant/harvest/water

        db = get_db()
        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})

        # 将屏幕坐标映射到农场格子坐标（简化版，前端可覆盖此逻辑）
        grid_width = farm.get('grid_width', 12)
        grid_height = farm.get('grid_height', 8)
        tile_x = int(screen_x / 32)  # 假设每格 32px
        tile_y = int(screen_y / 32)

        # 坐标范围校验
        if not (0 <= tile_x < grid_width and 0 <= tile_y < grid_height):
            return web.json_response({'success': False, 'error': '坐标超出范围'})

        result = {'success': True, 'tile_x': tile_x, 'tile_y': tile_y, 'action': action}

        if action == 'harvest':
            crop_type = db.harvest_crop(farm['id'], tile_x, tile_y)
            if crop_type:
                db.add_item(user_id, 'crop', crop_type, 1)
                result['crop_type'] = crop_type
                notify_state_change(user_id, ['crops', 'inventory'])
            else:
                result['success'] = False
                result['error'] = '该位置没有可收获的作物'

        elif action == 'water':
            if db.water_crop(farm['id'], tile_x, tile_y):
                notify_state_change(user_id, ['crops'])
            else:
                result['success'] = False
                result['error'] = '该位置没有作物'

        elif action == 'interact':
            # 检查该位置是否有 NPC
            from characters import get_current_character
            character = get_current_character()
            if character:
                char_id = character.config.id
                location = db.get_character_location(char_id)
                if location and location.get('x') == tile_x and location.get('y') == tile_y:
                    result['npc'] = char_id
                    relationship = db.get_relationship(user_id, char_id)
                    result['hearts'] = relationship['hearts'] if relationship else 0

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Mobile] 点击交互失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_mobile_swipe(request):
    """移动端滑动手势处理

    接收滑动方向和距离，用于地图切换或页面导航。
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        direction = data.get('direction', '')  # up/down/left/right
        distance = data.get('distance', 0)  # 滑动距离（像素）

        # 短滑动忽略（防止误触）
        if distance < 50:
            return web.json_response({'success': True, 'handled': False})

        result = {'success': True, 'handled': True, 'direction': direction}

        # 上下滑动可用于地图切换
        if direction in ('left', 'right'):
            db = get_db()
            map_state = db.get_map_state(user_id)
            maps = map_state.get('maps', [])
            current_map = map_state.get('current_map', 'home')

            if maps:
                current_idx = next((i for i, m in enumerate(maps) if m.get('id') == current_map), 0)
                if direction == 'right':
                    new_idx = min(current_idx + 1, len(maps) - 1)
                else:
                    new_idx = max(current_idx - 1, 0)

                if new_idx != current_idx:
                    new_map = maps[new_idx]['id']
                    db_result = db.switch_map(user_id, new_map)
                    if db_result.get('success'):
                        result['map_switch'] = new_map
                        notify_state_change(user_id, ['mapSystem'])

        return web.json_response(result)

    except Exception as e:
        logger.error(f"[Mobile] 滑动处理失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_mobile_config(request):
    """获取移动端配置

    返回触控灵敏度、UI 缩放等移动端配置参数。
    """
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()
        farm = db.get_farm(user_id)

        return web.json_response({
            'success': True,
            'touch': {
                'minSwipeDistance': 50,
                'maxTapDuration': 300,
                'dpadStep': 1,
            },
            'grid': {
                'tileSize': 32,
                'gridWidth': farm.get('grid_width', 12) if farm else 12,
                'gridHeight': farm.get('grid_height', 8) if farm else 8,
            },
            'ui': {
                'bottomBarHeight': 64,
                'topBarHeight': 44,
                'safeArea': True,
            }
        })

    except Exception as e:
        logger.error(f"[Mobile] 获取配置失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
