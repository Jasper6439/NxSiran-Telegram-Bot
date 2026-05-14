# 农场 API

import logging
import random
from aiohttp import web
from database import get_db
from game_api.auth import authenticate_request

logger = logging.getLogger(__name__)


def _calculate_harvest_rewards(db, user_id, crop_type, crop_info):
    """计算收获时的概率奖励（15%返还种子，5%双倍收获）"""
    rewards = []
    if not crop_info:
        return rewards
    # 15% 概率返还1颗种子
    if random.random() < 0.15:
        db.add_item(user_id, 'seed', crop_type, 1)
        rewards.append({'type': 'seed_return', 'crop': crop_type, 'message': f'获得 1 颗{crop_info["name"]}种子!'})
    # 5% 概率双倍收获
    if random.random() < 0.05:
        db.add_item(user_id, 'crop', crop_type, 1)
        rewards.append({'type': 'double_harvest', 'crop': crop_type, 'message': '🎉 双倍收获!'})
    return rewards


async def api_get_farm(request):
    """获取农场数据"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        db = get_db()

        # 获取农场数据
        farm = db.get_farm(user_id)
        if not farm:
            # 确保用户存在后自动创建农场
            db.get_or_create_user(user_id, f"user_{user_id}")
            farm = db.get_or_create_farm(user_id)

        # 更新作物生长状态
        db.update_crop_growth(farm['id'])

        # 获取作物（生长更新后）
        crops = db.get_crops(farm['id'])

        # 获取背包
        inventory = db.get_inventory(user_id)

        # 获取作物类型
        crop_types = db.get_crop_types()

        return web.json_response({
            'success': True,
            'farm': farm,
            'crops': crops,
            'inventory': inventory,
            'crop_types': crop_types
        })

    except Exception as e:
        logger.error(f"[Game API] 获取农场失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_plant_crop(request):
    """种植作物"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        x = data.get('x', 0)
        y = data.get('y', 0)
        crop_type = data.get('crop_type', 'tomato')

        db = get_db()

        # 获取农场（自动创建）
        farm = db.get_or_create_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '农场创建失败'})

        # 检查背包是否有种子
        if not db.remove_item(user_id, 'seed', crop_type):
            return web.json_response({'success': False, 'error': '背包中没有该种子'})

        # 种植
        success = db.plant_crop(farm['id'], x, y, crop_type)

        if success:
            # 记录事件
            db.log_game_event(user_id, 'plant', {
                'x': x, 'y': y, 'crop_type': crop_type
            }, 'web')

            return web.json_response({
                'success': True,
                'message': f'种下了 {crop_type}'
            })
        else:
            return web.json_response({
                'success': False,
                'error': '这个位置已经有作物了'
            })

    except Exception as e:
        logger.error(f"[Game API] 种植失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_harvest_crop(request):
    """收获作物"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        x = data.get('x', 0)
        y = data.get('y', 0)

        db = get_db()

        # 获取农场
        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})

        # 收获
        crop_type = db.harvest_crop(farm['id'], x, y)

        if crop_type:
            # 添加到背包
            db.add_item(user_id, 'crop', crop_type, 1)

            # 获取作物信息
            crop_info = db.get_crop_type(crop_type)

            # 概率奖励
            rewards = _calculate_harvest_rewards(db, user_id, crop_type, crop_info)

            # 记录事件
            db.log_game_event(user_id, 'harvest', {
                'x': x, 'y': y, 'crop_type': crop_type
            }, 'web')

            return web.json_response({
                'success': True,
                'crop_type': crop_type,
                'crop_name': crop_info['name'] if crop_info else crop_type,
                'emoji': crop_info['emoji'] if crop_info else '🌱',
                'rewards': rewards
            })
        else:
            return web.json_response({
                'success': False,
                'error': '这里没有可收获的作物'
            })

    except Exception as e:
        logger.error(f"[Game API] 收获失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_bulk_harvest(request):
    """一键收获所有成熟作物"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err

        db = get_db()

        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})

        # 先更新生长状态
        db.update_crop_growth(farm['id'])

        # 获取所有作物
        crops = db.get_crops(farm['id'])
        harvested = []
        rewards = []

        for crop in crops:
            if crop.get('is_harvestable'):
                result = db.harvest_crop(farm['id'], crop['tile_x'], crop['tile_y'])
                if result:
                    db.add_item(user_id, 'crop', result, 1)
                    crop_info = db.get_crop_type(result)
                    harvested.append({
                        'type': result,
                        'emoji': crop_info['emoji'] if crop_info else '🌾',
                        'name': crop_info['name'] if crop_info else result
                    })

                    # 概率奖励
                    rewards.extend(_calculate_harvest_rewards(db, user_id, result, crop_info))

        if harvested:
            db.log_game_event(user_id, 'harvest', {'crops': [h['type'] for h in harvested]}, 'web')

        return web.json_response({
            'success': True,
            'harvested': harvested,
            'count': len(harvested),
            'rewards': rewards
        })

    except Exception as e:
        logger.error(f"[Game API] 批量收获失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_sell_crop(request):
    """出售作物"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        crop_type = data.get('crop_type', '')
        quantity = data.get('quantity', 1)

        db = get_db()

        # 检查背包
        if not db.remove_item(user_id, 'crop', crop_type, quantity):
            return web.json_response({
                'success': False,
                'error': '背包里没有这个作物'
            })

        # 获取售价
        crop_info = db.get_crop_type(crop_type)
        price = crop_info['sell_price'] if crop_info else 10
        total = price * quantity

        # 更新金钱
        farm = db.get_farm(user_id)
        db.update_farm(user_id, money=farm['money'] + total)

        # 记录事件
        db.log_game_event(user_id, 'sell', {
            'crop_type': crop_type,
            'quantity': quantity,
            'total': total
        }, 'web')

        return web.json_response({
            'success': True,
            'earned': total,
            'message': f'卖出 {quantity} 个，获得 {total} 金币'
        })

    except Exception as e:
        logger.error(f"[Game API] 出售失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_buy_seed(request):
    """购买种子"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        crop_type = data.get('crop_type', 'tomato')
        quantity = data.get('quantity', 1)

        db = get_db()

        # 获取种子价格
        crop_info = db.get_crop_type(crop_type)
        if not crop_info:
            return web.json_response({'success': False, 'error': '未知的作物类型'})

        price = crop_info['seed_price'] * quantity

        # 检查金钱
        farm = db.get_farm(user_id)
        if not farm or farm['money'] < price:
            return web.json_response({
                'success': False,
                'error': f'金币不足（需要 {price}）'
            })

        # 扣钱
        db.update_farm(user_id, money=farm['money'] - price)

        # 添加种子
        db.add_item(user_id, 'seed', crop_type, quantity)

        # 记录事件
        db.log_game_event(user_id, 'buy_seed', {
            'crop_type': crop_type,
            'quantity': quantity,
            'cost': price
        }, 'web')

        return web.json_response({
            'success': True,
            'cost': price,
            'message': f'购买 {quantity} 个 {crop_info["name"]} 种子'
        })

    except Exception as e:
        logger.error(f"[Game API] 购买失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_water_crop(request):
    """浇水"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        x = data.get('x', 0)
        y = data.get('y', 0)

        db = get_db()
        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})

        success = db.water_crop(farm['id'], x, y)

        if success:
            db.log_game_event(user_id, 'water', {'x': x, 'y': y}, 'web')
            return web.json_response({'success': True, 'message': '浇水完成'})
        else:
            return web.json_response({'success': False, 'error': '这里没有作物'})

    except Exception as e:
        logger.error(f"[Game API] 浇水失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_move_player(request):
    """记录玩家位置"""
    try:
        user_id, err = await authenticate_request(request)
        if err:
            return err


        data = await request.json()
        x = data.get('x', 0)
        y = data.get('y', 0)
        direction = data.get('direction', 'down')

        db = get_db()
        db.save_player_position(user_id, x, y, direction)

        return web.json_response({'success': True})

    except Exception as e:
        logger.error(f"[Game API] 移动失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})
