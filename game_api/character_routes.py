# 角色互动 API - 修复版

import logging
from datetime import datetime
from aiohttp import web
from database import get_db
from system.config import get_default_tz
from characters import get_current_character
from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


def _validate_farm_coords(x, y, farm):
    """校验农场坐标是否在合法范围内"""
    return 0 <= x < farm.get('gridWidth', 12) and 0 <= y < farm.get('gridHeight', 8)


async def api_get_character_location(request):
    """获取角色当前位置"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'

        db = get_db()

        # 获取位置
        location = db.get_character_location(character_id)

        if not location:
            # 默认位置
            return web.json_response({
                'success': True,
                'location': {
                    'scene': 'farm',
                    'x': 5,
                    'y': 14,
                    'direction': 'down'
                }
            })

        return web.json_response({
            'success': True,
            'location': location
        })

    except Exception as e:
        logger.error(f"[Game API] 获取角色位置失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_interact_with_character(request):
    """与角色互动"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        interaction_type = data.get('type', 'chat')
        content = data.get('content', '')

        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'

        db = get_db()

        # 记录互动
        # TODO: add_relationship_history 方法不存在于 RelationshipMixin，需要实现或移除
        # db.add_relationship_history(
        #     user_id, character_id,
        #     interaction_type, content,
        #     0  # hearts_delta
        # )

        # 获取更新后的关系
        relationship = db.get_relationship(user_id, character_id)

        return web.json_response({
            'success': True,
            'hearts': relationship['hearts'] if relationship else 0,
            'relationshipStatus': relationship['relationship_status'] if relationship else 'stranger'
        })

    except Exception as e:
        logger.error(f"[Game API] 互动失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_gift_to_character(request):
    """赠送礼物给角色"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        item_id = data.get('itemId')
        quantity = data.get('quantity', 1)

        if not item_id:
            return web.json_response({'success': False, 'error': '未指定物品'})

        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'

        db = get_db()

        # 检查背包
        inventory_item = db.get_inventory_item(user_id, 'crop', item_id)
        if not inventory_item or inventory_item['quantity'] < quantity:
            return web.json_response({'success': False, 'error': '背包中物品不足'})

        # 扣除物品
        if not db.remove_item(user_id, 'crop', item_id, quantity):
            return web.json_response({'success': False, 'error': '扣除物品失败'})

        # 计算好感度变化
        hearts_delta = quantity * 5

        # 更新关系
        db.update_hearts(user_id, character_id, hearts_delta)

        # 记录互动
        # TODO: add_relationship_history 方法不存在于 RelationshipMixin，需要实现或移除
        # db.add_relationship_history(
        #     user_id, character_id,
        #     'gift', f'赠送了 {quantity} 个 {item_id}',
        #     hearts_delta
        # )

        # 获取更新后的关系
        relationship = db.get_relationship(user_id, character_id)

        return web.json_response({
            'success': True,
            'hearts': relationship['hearts'],
            'relationshipStatus': relationship['relationship_status'],
            'heartsDelta': hearts_delta
        })

    except Exception as e:
        logger.error(f"[Game API] 赠送礼物失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_sync_actions(request):
    """增量同步操作 - 服务器端验证版"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        data = await request.json()
        actions = data.get('actions', [])
        client_timestamp = data.get('timestamp', 0)

        # 时间戳校验（防止重放攻击，允许±5分钟误差）
        server_time = datetime.now(get_default_tz()).timestamp()
        if abs(server_time - client_timestamp) > 300:
            return web.json_response({'success': False, 'error': '请求时间戳无效'}, status=400)

        db = get_db()
        processed = 0
        failed = 0
        results = []

        # 获取农场和背包信息（用于验证）
        farm = db.get_or_create_farm(user_id)
        farm_id = farm['id']
        inventory = {f"{item['item_type']}:{item['item_id']}": item['quantity']
                     for item in db.get_inventory(user_id)}

        for action in actions:
            try:
                action_type = action.get('type')
                action_id = action.get('id', '')
                result = {'id': action_id, 'type': action_type, 'success': False}

                if action_type == 'plant':
                    # 验证：1)坐标合法 2)有种子 3)地块为空
                    x, y = action.get('x'), action.get('y')
                    crop_type = action.get('cropType')
                    seed_key = f"seed:{crop_type}"

                    # 坐标范围校验
                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    # 检查是否有种子
                    if inventory.get(seed_key, 0) < 1:
                        result['error'] = '背包中没有该种子'
                        results.append(result)
                        failed += 1
                        continue

                    # 检查地块是否已有作物
                    existing_crops = db.get_crops(farm_id)
                    if any(c['tile_x'] == x and c['tile_y'] == y for c in existing_crops):
                        result['error'] = '该地块已有作物'
                        results.append(result)
                        failed += 1
                        continue

                    # 执行种植：扣除种子，添加作物
                    if db.remove_item(user_id, 'seed', crop_type, 1):
                        db.plant_crop(farm_id, x, y, crop_type)
                        inventory[seed_key] = inventory.get(seed_key, 0) - 1
                        result['success'] = True
                        processed += 1
                    else:
                        result['error'] = '扣除种子失败'
                        failed += 1

                elif action_type == 'harvest':
                    # 验证：1)坐标合法 2)作物可收获
                    x, y = action.get('x'), action.get('y')

                    # 坐标范围校验
                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    # 收获作物（数据库会检查是否可收获）
                    crop_type = db.harvest_crop(farm_id, x, y)
                    if crop_type:
                        # 添加作物到背包
                        db.add_item(user_id, 'crop', crop_type, 1)
                        result['success'] = True
                        result['cropType'] = crop_type
                        processed += 1
                    else:
                        result['error'] = '该作物不可收获或不存在'
                        failed += 1

                elif action_type == 'water':
                    # 验证：1)坐标合法 2)有作物
                    x, y = action.get('x'), action.get('y')

                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    # 浇水
                    if db.water_crop(farm_id, x, y):
                        result['success'] = True
                        processed += 1
                    else:
                        result['error'] = '浇水失败，可能该地块没有作物'
                        failed += 1

                elif action_type == 'buy_seed':
                    # 服务器端验证购买
                    crop_type = action.get('cropType')
                    quantity = action.get('quantity', 1)
                    price = action.get('price', 10) * quantity

                    # 获取作物类型定义验证价格
                    crop_types = {ct['id']: ct for ct in db.get_crop_types()}
                    if crop_type not in crop_types:
                        result['error'] = '无效的作物类型'
                        results.append(result)
                        failed += 1
                        continue

                    expected_price = crop_types[crop_type].get('seed_price', 10) * quantity
                    if price != expected_price:
                        result['error'] = '价格验证失败'
                        results.append(result)
                        failed += 1
                        continue

                    # 检查金币（从农场数据中获取）
                    current_money = farm.get('money', 0)
                    if current_money < price:
                        result['error'] = '金币不足'
                        results.append(result)
                        failed += 1
                        continue

                    # 扣除金币，添加种子
                    db.update_farm(user_id, money=current_money - price)
                    db.add_item(user_id, 'seed', crop_type, quantity)
                    farm['money'] = current_money - price
                    inventory[f"seed:{crop_type}"] = inventory.get(f"seed:{crop_type}", 0) + quantity
                    result['success'] = True
                    result['money'] = farm['money']
                    processed += 1

                elif action_type == 'sell':
                    # 服务器端验证出售
                    item_type = action.get('itemType', 'crop')
                    item_id = action.get('itemId')
                    quantity = action.get('quantity', 1)
                    price = action.get('price', 5) * quantity

                    # 验证背包中有足够物品
                    item_key = f"{item_type}:{item_id}"
                    if inventory.get(item_key, 0) < quantity:
                        result['error'] = '背包中物品数量不足'
                        results.append(result)
                        failed += 1
                        continue

                    # 获取作物类型定义验证价格
                    crop_types = {ct['id']: ct for ct in db.get_crop_types()}
                    expected_price = crop_types.get(item_id, {}).get('sell_price', 5) * quantity
                    if price != expected_price:
                        result['error'] = '价格验证失败'
                        results.append(result)
                        failed += 1
                        continue

                    # 扣除物品，添加金币
                    if db.remove_item(user_id, item_type, item_id, quantity):
                        current_money = farm.get('money', 0)
                        db.update_farm(user_id, money=current_money + price)
                        farm['money'] = current_money + price
                        inventory[item_key] = inventory.get(item_key, 0) - quantity
                        result['success'] = True
                        result['money'] = farm['money']
                        processed += 1
                    else:
                        result['error'] = '扣除物品失败'
                        failed += 1

                elif action_type == 'move':
                    # 移动位置
                    x, y = action.get('x'), action.get('y')
                    direction = action.get('direction', 'down')

                    # 坐标范围校验
                    if not (0 <= x <= 1000 and 0 <= y <= 1000):
                        result['error'] = '坐标超出合理范围'
                        results.append(result)
                        failed += 1
                        continue

                    db.save_player_position(user_id, x, y, direction)
                    result['success'] = True
                    processed += 1

                else:
                    result['error'] = '未知的动作类型'
                    failed += 1

                results.append(result)

            except Exception as e:
                logger.warning(f"[Game API] 同步操作失败: {action_type} - {e}")
                results.append({'id': action_id, 'type': action_type, 'success': False, 'error': str(e)})
                failed += 1

        return web.json_response({
            'success': True,
            'processed': processed,
            'failed': failed,
            'results': results,
            'money': farm.get('money', 0)
        })

    except Exception as e:
        logger.error(f"[Game API] 同步失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
