# 同步 + 全量状态 API

import logging
from aiohttp import web
from database import get_db
from characters import get_current_character
from game_api.auth import authenticate_request

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
    """一次性获取全部游戏状态"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()

        # 获取农场
        db.get_or_create_user(user_id, f"game_{user_id}")
        farm = db.get_or_create_farm(user_id)

        # 更新作物生长
        db.update_crop_growth(farm['id'])

        # 获取所有数据
        crops = db.get_crops(farm['id'])
        inventory = db.get_inventory(user_id)
        crop_types = db.get_crop_types()

        # 获取角色关系
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
        relationship = db.get_relationship(user_id, character_id)

        # 获取情感值（恋爱至上主义区域）
        emotion_values = db.get_emotion_values(user_id, character_id)

        # 获取世界层级状态
        world_layer_state = db.get_world_layer_state(user_id)

        # 获取地图系统状态（v1.4.10.2）
        map_state = db.get_map_state(user_id)

        # 获取角色位置
        location = db.get_character_location(character_id)

        # 获取玩家位置
        player_pos = db.get_player_position(user_id)

        # 构建作物字典 (key: "x,y")
        crops_dict = {}
        for crop in crops:
            key = f"{crop['tile_x']},{crop['tile_y']}"
            crops_dict[key] = {
                'type': crop['crop_type'],
                'plantedAt': crop['planted_at'],
                'growthStage': crop['growth_stage'],
                'waterLevel': crop.get('water_level', 0),
                'harvestable': crop.get('is_harvestable', 0) == 1
            }

        # 构建背包字典
        inventory_dict = {}
        for item in inventory:
            item_key = f"{item['item_type']}_{item['item_id']}"
            inventory_dict[item_key] = {
                'type': item['item_type'],
                'name': item.get('name', item['item_id']),
                'quantity': item['quantity'],
                'emoji': item.get('emoji', '')
            }

        # 为种子添加 emoji
        for key, item in inventory_dict.items():
            if item['type'] == 'seed':
                ct = next((ct for ct in crop_types if ct['id'] == item['name']), None)
                if ct:
                    item['name'] = ct['name'] + '种子'
                    item['emoji'] = ct['emoji']
            elif item['type'] == 'crop':
                ct = next((ct for ct in crop_types if ct['id'] == item['name']), None)
                if ct:
                    item['name'] = ct['name']
                    item['emoji'] = ct['emoji']

        # 构建作物类型字典
        crop_types_dict = {}
        for ct in crop_types:
            crop_types_dict[ct['id']] = {
                'name': ct['name'],
                'growthTime': ct['growth_time'],
                'sellPrice': ct['sell_price'],
                'seedPrice': ct['seed_price'],
                'emoji': ct['emoji']
            }

        # NPC 数据
        npc_data = {}
        if location:
            npc_data['chayewoon'] = {
                'id': 'chayewoon',
                'x': location.get('x', 3),
                'y': location.get('y', 2),
                'direction': 'down',
                'name': character.config.name if character else '车如云',
                'location': location['location'],
                'activity': location['activity']
            }

        # 默认建筑和装饰
        buildings = {
            'house': {'x': -6, 'y': 4, 'type': 'house'},
            'barn': {'x': 6, 'y': 4, 'type': 'barn'}
        }
        decorations = {
            'tree1': {'x': -7, 'y': 2, 'type': 'tree'},
            'tree2': {'x': 7, 'y': 1, 'type': 'tree'},
            'tree3': {'x': -5, 'y': -4, 'type': 'tree'},
            'flower1': {'x': -4, 'y': 5, 'type': 'flower_red'},
            'flower2': {'x': 4, 'y': -5, 'type': 'flower_yellow'},
            'rock1': {'x': 8, 'y': 3, 'type': 'rock'}
        }

        return web.json_response({
            'success': True,
            'farm': {
                'id': farm['id'],
                'name': farm['farm_name'],
                'money': farm['money'],
                'level': farm['level'],
                'exp': farm['experience'],
                'gridWidth': farm['grid_width'],
                'gridHeight': farm['grid_height']
            },
            'player': player_pos or {'x': 0, 'y': 0, 'direction': 'down'},
            'crops': crops_dict,
            'inventory': inventory_dict,
            'cropTypes': crop_types_dict,
            'npc': npc_data,
            'hearts': relationship['hearts'] if relationship else 0,
            'relationshipStatus': relationship['relationship_status'] if relationship else 'stranger',
            'emotionValues': emotion_values,
            'worldLayer': world_layer_state,
            'mapSystem': {
                'currentMap': map_state['current_map'],
                'currentMapInfo': map_state['current_map_info'],
                'maps': map_state['maps'],
                'unlockedCount': map_state['unlocked_count'],
                'totalMaps': map_state['total_maps'],
            },
            'buildings': buildings,
            'decorations': decorations,
            'weather': 'sunny',
            'season': 'spring',
            'gameDay': 1
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
