# 游戏 API 路由（FastAPI 版本）
# ============================
# 从 aiohttp 迁移至 FastAPI APIRouter 格式。
# 合并自:
#   - game_api/farm_routes.py   (农场操作)
#   - game_api/cooking_routes.py (烹饪 + 每日签到)
#   - game_api/heart_routes.py   (心级事件)
#   - game_api/character_routes.py (角色互动)
#   - game_api/sync_routes.py   (同步 + 全量状态 + SSE)
#   - game_api/map_routes.py    (多地图系统)
#   - game_api/media_routes.py  (多媒体生成)
#   - game_api/learning_routes.py (角色学习进化)
#   - game_api/upload_routes.py (上传处理)

import asyncio
import json
import logging
import os
import random
import shutil
import tempfile
import time
import urllib.parse
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from api.deps import get_current_user
from database import get_db
from api.game_state import (
    notify_state_change, serialize_game_state, get_state_version,
    compute_state_diff, get_snapshot, subscribe_state_changes,
    unsubscribe_state_changes,
)
from system.config import get_default_tz
from characters import get_current_character

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/game", tags=["game"])


# ============================================================
# Pydantic 请求模型
# ============================================================

class PlantCropRequest(BaseModel):
    """种植作物请求体"""
    x: int = 0
    y: int = 0
    crop_type: str = "tomato"


class HarvestCropRequest(BaseModel):
    """收获作物请求体"""
    x: int = 0
    y: int = 0


class SellCropRequest(BaseModel):
    """出售作物请求体"""
    crop_type: str = ""
    quantity: int = 1


class BuySeedRequest(BaseModel):
    """购买种子请求体"""
    crop_type: str = "tomato"
    quantity: int = 1


class WaterCropRequest(BaseModel):
    """浇水请求体"""
    x: int = 0
    y: int = 0


class MovePlayerRequest(BaseModel):
    """记录玩家位置请求体"""
    x: int = 0
    y: int = 0
    direction: str = "down"


class CookRequest(BaseModel):
    """烹饪料理请求体"""
    recipe_id: str = ""


class TriggerHeartEventRequest(BaseModel):
    """触发心级事件请求体"""
    event_id: str = ""


# ============================================================
# 辅助函数
# ============================================================

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


# ============================================================
# 农场路由 (farm_routes.py)
# ============================================================

@router.get("/farm")
async def api_get_farm(user_id: int = Depends(get_current_user)):
    """获取农场数据"""
    try:
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

        return {
            'success': True,
            'farm': farm,
            'crops': crops,
            'inventory': inventory,
            'crop_types': crop_types
        }

    except Exception as e:
        logger.error(f"[Game API] 获取农场失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plant")
async def api_plant_crop(
    body: PlantCropRequest,
    user_id: int = Depends(get_current_user),
):
    """种植作物"""
    try:
        db = get_db()

        # 获取农场（自动创建）
        farm = db.get_or_create_farm(user_id)
        if not farm:
            raise HTTPException(status_code=400, detail='农场创建失败')

        # 检查背包是否有种子
        if not db.remove_item(user_id, 'seed', body.crop_type):
            raise HTTPException(status_code=400, detail='背包中没有该种子')

        # 种植
        success = db.plant_crop(farm['id'], body.x, body.y, body.crop_type)

        if success:
            # 记录事件
            db.log_game_event(user_id, 'plant', {
                'x': body.x, 'y': body.y, 'crop_type': body.crop_type
            }, 'web')

            notify_state_change(user_id, ['crops', 'inventory'])

            return {
                'success': True,
                'message': f'种下了 {body.crop_type}'
            }
        else:
            raise HTTPException(status_code=400, detail='这个位置已经有作物了')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 种植失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/harvest")
async def api_harvest_crop(
    body: HarvestCropRequest,
    user_id: int = Depends(get_current_user),
):
    """收获作物"""
    try:
        db = get_db()

        # 获取农场
        farm = db.get_farm(user_id)
        if not farm:
            raise HTTPException(status_code=400, detail='没有农场')

        # 收获
        crop_type = db.harvest_crop(farm['id'], body.x, body.y)

        if crop_type:
            # 添加到背包
            db.add_item(user_id, 'crop', crop_type, 1)

            # 获取作物信息
            crop_info = db.get_crop_type(crop_type)

            # 概率奖励
            rewards = _calculate_harvest_rewards(db, user_id, crop_type, crop_info)

            # 记录事件
            db.log_game_event(user_id, 'harvest', {
                'x': body.x, 'y': body.y, 'crop_type': crop_type
            }, 'web')

            notify_state_change(user_id, ['crops', 'inventory'])

            return {
                'success': True,
                'crop_type': crop_type,
                'crop_name': crop_info['name'] if crop_info else crop_type,
                'emoji': crop_info['emoji'] if crop_info else '🌱',
                'rewards': rewards
            }
        else:
            raise HTTPException(status_code=400, detail='这里没有可收获的作物')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 收获失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bulk-harvest")
async def api_bulk_harvest(user_id: int = Depends(get_current_user)):
    """一键收获所有成熟作物"""
    try:
        db = get_db()

        farm = db.get_farm(user_id)
        if not farm:
            raise HTTPException(status_code=400, detail='没有农场')

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
            notify_state_change(user_id, ['crops', 'inventory'])

        return {
            'success': True,
            'harvested': harvested,
            'count': len(harvested),
            'rewards': rewards
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 批量收获失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sell")
async def api_sell_crop(
    body: SellCropRequest,
    user_id: int = Depends(get_current_user),
):
    """出售作物"""
    try:
        db = get_db()

        # 检查背包
        if not db.remove_item(user_id, 'crop', body.crop_type, body.quantity):
            raise HTTPException(status_code=400, detail='背包里没有这个作物')

        # 获取售价
        crop_info = db.get_crop_type(body.crop_type)
        price = crop_info['sell_price'] if crop_info else 10
        total = price * body.quantity

        # 更新金钱
        farm = db.get_farm(user_id)
        db.update_farm(user_id, money=farm['money'] + total)

        # 记录事件
        db.log_game_event(user_id, 'sell', {
            'crop_type': body.crop_type,
            'quantity': body.quantity,
            'total': total
        }, 'web')

        notify_state_change(user_id, ['farm', 'inventory'])

        return {
            'success': True,
            'earned': total,
            'message': f'卖出 {body.quantity} 个，获得 {total} 金币'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 出售失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/buy-seed")
async def api_buy_seed(
    body: BuySeedRequest,
    user_id: int = Depends(get_current_user),
):
    """购买种子"""
    try:
        db = get_db()

        # 获取种子价格
        crop_info = db.get_crop_type(body.crop_type)
        if not crop_info:
            raise HTTPException(status_code=400, detail='未知的作物类型')

        price = crop_info['seed_price'] * body.quantity

        # 检查金钱
        farm = db.get_farm(user_id)
        if not farm or farm['money'] < price:
            raise HTTPException(status_code=400, detail=f'金币不足（需要 {price}）')

        # 扣钱
        db.update_farm(user_id, money=farm['money'] - price)

        # 添加种子
        db.add_item(user_id, 'seed', body.crop_type, body.quantity)

        # 记录事件
        db.log_game_event(user_id, 'buy_seed', {
            'crop_type': body.crop_type,
            'quantity': body.quantity,
            'cost': price
        }, 'web')

        notify_state_change(user_id, ['farm', 'inventory'])

        return {
            'success': True,
            'cost': price,
            'message': f'购买 {body.quantity} 个 {crop_info["name"]} 种子'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 购买失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/water")
async def api_water_crop(
    body: WaterCropRequest,
    user_id: int = Depends(get_current_user),
):
    """浇水"""
    try:
        db = get_db()
        farm = db.get_farm(user_id)
        if not farm:
            raise HTTPException(status_code=400, detail='没有农场')

        success = db.water_crop(farm['id'], body.x, body.y)

        if success:
            db.log_game_event(user_id, 'water', {'x': body.x, 'y': body.y}, 'web')
            notify_state_change(user_id, ['crops'])
            return {'success': True, 'message': '浇水完成'}
        else:
            raise HTTPException(status_code=400, detail='这里没有作物')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 浇水失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/move")
async def api_move_player(
    body: MovePlayerRequest,
    user_id: int = Depends(get_current_user),
):
    """记录玩家位置"""
    try:
        db = get_db()
        db.save_player_position(user_id, body.x, body.y, body.direction)
        return {'success': True}

    except Exception as e:
        logger.error(f"[Game API] 移动失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 烹饪 + 每日签到路由 (cooking_routes.py)
# ============================================================

@router.get("/recipes")
async def api_get_recipes(user_id: int = Depends(get_current_user)):
    """获取所有料理配方"""
    try:
        db = get_db()
        recipes = db.get_recipes()
        inventory = db.get_inventory(user_id)

        # 标记每个配方是否可以烹饪
        for recipe in recipes:
            can, msg = db.can_cook(user_id, recipe['id'])
            recipe['can_cook'] = can
            recipe['cook_message'] = msg

        return {
            'success': True,
            'recipes': recipes,
            'inventory': inventory
        }

    except Exception as e:
        logger.error(f"[Game API] 获取配方失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cook")
async def api_cook(
    body: CookRequest,
    user_id: int = Depends(get_current_user),
):
    """烹饪料理"""
    try:
        db = get_db()
        recipe = db.cook(user_id, body.recipe_id)

        if recipe:
            db.log_game_event(user_id, 'cook', {
                'recipe_id': body.recipe_id,
                'recipe_name': recipe['name']
            }, 'miniapp')

            return {
                'success': True,
                'recipe': recipe,
                'message': f"烹饪成功！{recipe['emoji']} {recipe['name']}"
            }
        else:
            can, msg = db.can_cook(user_id, body.recipe_id)
            raise HTTPException(status_code=400, detail=msg or '材料不足')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 烹饪失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/daily/claim")
async def api_daily_reward(user_id: int = Depends(get_current_user)):
    """领取每日登录奖励"""
    try:
        db = get_db()
        # 确保用户存在
        db.get_or_create_user(user_id, f"web_{user_id}")
        result = db.claim_daily_reward(user_id)

        return result

    except Exception as e:
        logger.error(f"[Game API] 每日签到失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/daily/check")
async def api_check_daily(user_id: int = Depends(get_current_user)):
    """检查今日是否已签到"""
    try:
        db = get_db()
        # 确保用户存在
        db.get_or_create_user(user_id, f"web_{user_id}")
        reward = db.get_daily_reward(user_id)

        return {
            'success': True,
            'claimed': reward['claimed'] == 1 if reward else False
        }

    except Exception as e:
        logger.error(f"[Game API] 检查签到失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 心级事件路由 (heart_routes.py)
# ============================================================

@router.get("/events/heart")
async def api_check_heart_events(user_id: int = Depends(get_current_user)):
    """检查可触发的心级事件"""
    try:
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

        return {
            'success': True,
            'events': triggerable,
            'current_location': location['location'] if location else None,
            'current_hour': current_hour
        }

    except Exception as e:
        logger.error(f"[Game API] 检查事件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/events/trigger")
async def api_trigger_heart_event(
    body: TriggerHeartEventRequest,
    user_id: int = Depends(get_current_user),
):
    """触发心级事件"""
    try:
        if not body.event_id:
            raise HTTPException(status_code=400, detail='缺少事件ID')

        db = get_db()

        # 触发事件
        event = db.trigger_event(user_id, body.event_id)

        if not event:
            raise HTTPException(status_code=400, detail='事件不存在或已触发')

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
            'event_id': body.event_id,
            'title': event.get('title', ''),
            'rewards': rewards
        }, 'miniapp')

        return {
            'success': True,
            'event': {
                'id': event['id'],
                'title': event.get('title', ''),
                'description': event.get('description', ''),
                'dialogue': dialogue,
                'rewards': rewards
            },
            'relationship': relationship
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 触发事件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 角色互动路由 (character_routes.py)
# ============================================================

def _validate_farm_coords(x, y, farm):
    """校验农场坐标是否在合法范围内"""
    return 0 <= x < farm.get('gridWidth', 12) and 0 <= y < farm.get('gridHeight', 8)


def _get_character_id(character_id: Optional[str] = None) -> str:
    """获取 character_id（参数 > 当前角色）"""
    if character_id:
        return character_id
    character = get_current_character()
    return character.config.id if character else 'chayewoon'


class InteractWithCharacterRequest(BaseModel):
    """与角色互动请求体"""
    type: str = "chat"
    content: str = ""
    character_id: Optional[str] = None


class GiftToCharacterRequest(BaseModel):
    """赠送礼物请求体"""
    itemId: str = ""
    quantity: int = 1
    character_id: Optional[str] = None


class SyncActionsRequest(BaseModel):
    """增量同步操作请求体"""
    actions: List[Dict[str, Any]] = []
    timestamp: float = 0


@router.get("/character/location")
async def api_get_character_location(
    character_id: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user),
):
    """获取角色当前位置"""
    try:
        cid = _get_character_id(character_id)
        db = get_db()

        location = db.get_character_location(cid)

        if not location:
            return {
                'success': True,
                'location': {
                    'scene': 'farm',
                    'x': 5,
                    'y': 14,
                    'direction': 'down'
                }
            }

        return {
            'success': True,
            'location': location
        }

    except Exception as e:
        logger.error(f"[Game API] 获取角色位置失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/character/interact")
async def api_interact_with_character(
    body: InteractWithCharacterRequest,
    user_id: int = Depends(get_current_user),
):
    """与角色互动"""
    try:
        interaction_type = body.type
        content = body.content
        character_id = _get_character_id(body.character_id)

        db = get_db()

        # 获取更新后的关系
        relationship = db.get_relationship(user_id, character_id)

        notify_state_change(user_id, ['hearts', 'relationshipStatus'])

        return {
            'success': True,
            'hearts': relationship['hearts'] if relationship else 0,
            'relationshipStatus': relationship['relationship_status'] if relationship else 'stranger'
        }

    except Exception as e:
        logger.error(f"[Game API] 互动失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gift")
async def api_gift_to_character(
    body: GiftToCharacterRequest,
    user_id: int = Depends(get_current_user),
):
    """赠送礼物给角色"""
    try:
        item_id = body.itemId
        quantity = body.quantity
        character_id = _get_character_id(body.character_id)

        db = get_db()

        # 检查背包
        inventory_item = db.get_inventory_item(user_id, 'crop', item_id)
        if not inventory_item or inventory_item['quantity'] < quantity:
            raise HTTPException(status_code=400, detail='背包中物品不足')

        # 扣除物品
        if not db.remove_item(user_id, 'crop', item_id, quantity):
            raise HTTPException(status_code=400, detail='扣除物品失败')

        # 计算好感度变化
        hearts_delta = quantity * 5

        # 更新关系
        db.update_hearts(user_id, character_id, hearts_delta)

        # 获取更新后的关系
        relationship = db.get_relationship(user_id, character_id)

        notify_state_change(user_id, ['hearts', 'relationshipStatus', 'inventory'])

        return {
            'success': True,
            'hearts': relationship['hearts'],
            'relationshipStatus': relationship['relationship_status'],
            'heartsDelta': hearts_delta
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 赠送礼物失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync")
async def api_sync_actions(
    body: SyncActionsRequest,
    user_id: int = Depends(get_current_user),
):
    """增量同步操作 - 服务器端验证版"""
    try:
        actions = body.actions
        client_timestamp = body.timestamp

        # 时间戳校验（防止重放攻击，允许±5分钟误差）
        server_time = datetime.now(get_default_tz()).timestamp()
        if abs(server_time - client_timestamp) > 300:
            raise HTTPException(status_code=400, detail='请求时间戳无效')

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
                    x, y = action.get('x'), action.get('y')
                    crop_type = action.get('cropType')
                    seed_key = f"seed:{crop_type}"

                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    if inventory.get(seed_key, 0) < 1:
                        result['error'] = '背包中没有该种子'
                        results.append(result)
                        failed += 1
                        continue

                    existing_crops = db.get_crops(farm_id)
                    if any(c['tile_x'] == x and c['tile_y'] == y for c in existing_crops):
                        result['error'] = '该地块已有作物'
                        results.append(result)
                        failed += 1
                        continue

                    if db.remove_item(user_id, 'seed', crop_type, 1):
                        db.plant_crop(farm_id, x, y, crop_type)
                        inventory[seed_key] = inventory.get(seed_key, 0) - 1
                        result['success'] = True
                        processed += 1
                    else:
                        result['error'] = '扣除种子失败'
                        failed += 1

                elif action_type == 'harvest':
                    x, y = action.get('x'), action.get('y')

                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    crop_type = db.harvest_crop(farm_id, x, y)
                    if crop_type:
                        db.add_item(user_id, 'crop', crop_type, 1)
                        result['success'] = True
                        result['cropType'] = crop_type
                        processed += 1
                    else:
                        result['error'] = '该作物不可收获或不存在'
                        failed += 1

                elif action_type == 'water':
                    x, y = action.get('x'), action.get('y')

                    if not _validate_farm_coords(x, y, farm):
                        result['error'] = '坐标超出范围'
                        results.append(result)
                        failed += 1
                        continue

                    if db.water_crop(farm_id, x, y):
                        result['success'] = True
                        processed += 1
                    else:
                        result['error'] = '浇水失败，可能该地块没有作物'
                        failed += 1

                elif action_type == 'buy_seed':
                    crop_type = action.get('cropType')
                    quantity = action.get('quantity', 1)
                    price = action.get('price', 10) * quantity

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

                    current_money = farm.get('money', 0)
                    if current_money < price:
                        result['error'] = '金币不足'
                        results.append(result)
                        failed += 1
                        continue

                    db.update_farm(user_id, money=current_money - price)
                    db.add_item(user_id, 'seed', crop_type, quantity)
                    farm['money'] = current_money - price
                    inventory[f"seed:{crop_type}"] = inventory.get(f"seed:{crop_type}", 0) + quantity
                    result['success'] = True
                    result['money'] = farm['money']
                    processed += 1

                elif action_type == 'sell':
                    item_type = action.get('itemType', 'crop')
                    item_id = action.get('itemId')
                    quantity = action.get('quantity', 1)
                    price = action.get('price', 5) * quantity

                    item_key = f"{item_type}:{item_id}"
                    if inventory.get(item_key, 0) < quantity:
                        result['error'] = '背包中物品数量不足'
                        results.append(result)
                        failed += 1
                        continue

                    crop_types = {ct['id']: ct for ct in db.get_crop_types()}
                    expected_price = crop_types.get(item_id, {}).get('sell_price', 5) * quantity
                    if price != expected_price:
                        result['error'] = '价格验证失败'
                        results.append(result)
                        failed += 1
                        continue

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
                    x, y = action.get('x'), action.get('y')
                    direction = action.get('direction', 'down')

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

        return {
            'success': True,
            'processed': processed,
            'failed': failed,
            'results': results,
            'money': farm.get('money', 0)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 同步失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 同步 + 全量状态 + SSE 实时推送路由 (sync_routes.py)
# ============================================================

class MarkSyncedRequest(BaseModel):
    """标记事件已同步请求体"""
    event_ids: List[str] = []


class TriggerAwakeningRequest(BaseModel):
    """触发觉醒请求体"""
    event_name: str = "default_awakening"
    character_id: Optional[str] = None


class SwitchWorldLayerRequest(BaseModel):
    """切换世界层级请求体"""
    target_layer: Optional[str] = None
    layer: Optional[str] = None


@router.get("/state")
async def api_get_full_game_state(user_id: int = Depends(get_current_user)):
    """一次性获取全部游戏状态（附带版本号）"""
    try:
        state = serialize_game_state(user_id)
        version = get_state_version(user_id)

        return {
            'success': True,
            'version': version,
            **state
        }

    except Exception as e:
        logger.error(f"[Game API] 获取全量状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/events")
async def api_get_game_events(
    since: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user),
):
    """获取未同步的游戏事件"""
    try:
        db = get_db()
        events = db.get_unsynced_events(user_id, since)

        return {
            'success': True,
            'events': events
        }

    except Exception as e:
        logger.error(f"[Game API] 获取事件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/events/sync")
async def api_mark_synced(
    body: MarkSyncedRequest,
    user_id: int = Depends(get_current_user),
):
    """标记事件已同步"""
    try:
        db = get_db()
        db.mark_events_synced(body.event_ids)

        return {'success': True}

    except Exception as e:
        logger.error(f"[Game API] 标记同步失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/emotions")
async def api_get_emotion_values(
    character_id: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user),
):
    """获取情感值 API"""
    try:
        if not character_id:
            character = get_current_character()
            character_id = character.config.id if character else 'chayewoon'

        db = get_db()
        emotions = db.get_emotion_values(user_id, character_id)

        return {
            'success': True,
            'character_id': character_id,
            'emotions': emotions
        }

    except Exception as e:
        logger.error(f"[Game API] 获取情感值失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/awakening/check")
async def api_check_awakening(
    character_id: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user),
):
    """检查觉醒条件 API"""
    try:
        if not character_id:
            character = get_current_character()
            character_id = character.config.id if character else 'chayewoon'

        db = get_db()
        check_result = db.check_awakening_conditions(user_id, character_id)

        return {
            'success': True,
            'character_id': character_id,
            'can_awaken': check_result['can_awaken'],
            'conditions': check_result['conditions'],
            'current_values': check_result['current_values'],
            'current_hearts': check_result['current_hearts']
        }

    except Exception as e:
        logger.error(f"[Game API] 检查觉醒条件失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/awakening/trigger")
async def api_trigger_awakening(
    body: TriggerAwakeningRequest,
    user_id: int = Depends(get_current_user),
):
    """触发觉醒 API"""
    try:
        character = get_current_character()
        character_id = body.character_id or (character.config.id if character else 'chayewoon')

        db = get_db()
        result = db.trigger_awakening(user_id, character_id, body.event_name)

        if result:
            return {
                'success': True,
                'event': result,
                'message': f'{character.config.name if character else "角色"} 已觉醒！'
            }
        else:
            raise HTTPException(status_code=400, detail='觉醒条件未满足')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 触发觉醒失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/world/state")
async def api_get_world_state(user_id: int = Depends(get_current_user)):
    """获取世界状态 API"""
    try:
        db = get_db()
        world_state = db.get_world_layer_state(user_id)

        return {
            'success': True,
            'world_state': world_state
        }

    except Exception as e:
        logger.error(f"[Game API] 获取世界状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/world/switch")
async def api_switch_world_layer(
    body: SwitchWorldLayerRequest,
    user_id: int = Depends(get_current_user),
):
    """切换世界层级 API"""
    try:
        layer = body.target_layer or body.layer or 'normal'

        db = get_db()
        result = db.switch_world_layer(user_id, layer)

        if result['success']:
            return {
                'success': True,
                'previous_layer': result['previous_layer'],
                'current_layer': result['current_layer'],
                'layer_name': result['layer_name'],
                'message': f'已切换至 {result["layer_name"]}'
            }
        else:
            raise HTTPException(status_code=400, detail=result.get('error', '切换失败'))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] 切换世界层级失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state/sse")
async def api_game_state_sse(user_id: int = Depends(get_current_user)):
    """SSE 端点 -- 实时推送游戏状态变更通知

    前端连接后，服务器在有状态变更时推送版本号。
    前端收到通知后调用 /api/game/state/diff 获取增量差异。
    """
    async def event_generator():
        queue = await subscribe_state_changes(user_id)
        try:
            current_version = get_state_version(user_id)
            init_msg = json.dumps({
                'type': 'init',
                'version': current_version,
                'timestamp': time.time()
            }, ensure_ascii=False)
            yield f"data: {init_msg}\n\n"

            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            logger.debug(f"[SSE] 用户 {user_id} 连接断开")
        finally:
            unsubscribe_state_changes(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


@router.get("/state/diff")
async def api_game_state_diff(
    version: int = Query(0),
    user_id: int = Depends(get_current_user),
):
    """增量状态差异 API"""
    try:
        client_version = version
        current_version = get_state_version(user_id)

        if client_version == current_version:
            return {
                'success': True,
                'version': current_version,
                'hasChanges': False,
                'diff': {}
            }

        if current_version - client_version > 10:
            return {
                'success': True,
                'version': current_version,
                'hasChanges': True,
                'needsFullSync': True
            }

        old_snapshot = get_snapshot(user_id)
        new_state = serialize_game_state(user_id)

        if old_snapshot:
            diff = compute_state_diff(old_snapshot, new_state)
        else:
            return {
                'success': True,
                'version': current_version,
                'hasChanges': True,
                'needsFullSync': True
            }

        return {
            'success': True,
            'version': current_version,
            'hasChanges': True,
            'diff': diff
        }

    except Exception as e:
        logger.error(f"[Game API] 增量同步失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/state/version")
async def api_game_state_version(user_id: int = Depends(get_current_user)):
    """获取当前状态版本号"""
    try:
        return {
            'success': True,
            'version': get_state_version(user_id)
        }

    except Exception as e:
        logger.error(f"[Game API] 获取版本号失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 多地图系统路由 (map_routes.py)
# ============================================================

class SwitchMapRequest(BaseModel):
    """切换地图请求体"""
    map_id: str = ""


class DiscoverMapRequest(BaseModel):
    """发现地图内容请求体"""
    discovery_key: str = ""
    data: Dict[str, Any] = {}


@router.get("/maps")
async def api_get_maps(
    character_id: str = Query("chayewoon"),
    user_id: int = Depends(get_current_user),
):
    """获取所有地图列表和解锁状态"""
    try:
        db = get_db()

        # 检查好感度自动解锁新地图
        emotions = db.get_emotion_values(user_id, character_id)
        newly_unlocked = db.check_and_unlock_maps(user_id, emotions.get('affection', 0))

        # 获取完整地图状态
        map_state = db.get_map_state(user_id)

        return {
            'success': True,
            'current_map': map_state['current_map'],
            'maps': map_state['maps'],
            'unlocked_count': map_state['unlocked_count'],
            'total_maps': map_state['total_maps'],
            'newly_unlocked': newly_unlocked,
        }

    except Exception as e:
        logger.error(f"[Map API] 获取地图列表失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maps/switch")
async def api_switch_map(
    body: SwitchMapRequest,
    user_id: int = Depends(get_current_user),
):
    """切换当前地图"""
    try:
        if not body.map_id:
            raise HTTPException(status_code=400, detail='缺少 map_id 参数')

        db = get_db()
        result = db.switch_map(user_id, body.map_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Map API] 切换地图失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/maps/state")
async def api_get_map_state(user_id: int = Depends(get_current_user)):
    """获取当前地图详细状态"""
    try:
        db = get_db()
        map_state = db.get_map_state(user_id)

        player_pos = db.get_player_position(user_id)

        return {
            'success': True,
            'current_map': map_state['current_map'],
            'current_map_info': map_state['current_map_info'],
            'maps': map_state['maps'],
            'unlocked_count': map_state['unlocked_count'],
            'total_maps': map_state['total_maps'],
            'player': player_pos or {'x': 0, 'y': 0, 'direction': 'down'},
        }

    except Exception as e:
        logger.error(f"[Map API] 获取地图状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/maps/discover")
async def api_discover_map(
    body: DiscoverMapRequest,
    user_id: int = Depends(get_current_user),
):
    """发现地图上的新内容"""
    try:
        if not body.discovery_key:
            raise HTTPException(status_code=400, detail='缺少 discovery_key 参数')

        db = get_db()
        result = db.discover_map_content(user_id, body.discovery_key, body.data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Map API] 发现地图内容失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/maps/discoveries")
async def api_get_map_discoveries(user_id: int = Depends(get_current_user)):
    """获取玩家在所有地图上的发现"""
    try:
        db = get_db()
        discoveries = db.get_map_discoveries(user_id)

        return {
            'success': True,
            'discoveries': discoveries,
        }

    except Exception as e:
        logger.error(f"[Map API] 获取发现列表失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 多媒体生成路由 (media_routes.py)
# ============================================================

def _generate_image_url(prompt: str, width: int = 768, height: int = 1024) -> str:
    """生成 Pollinations.ai 图片 URL"""
    from system.prompts import SELFIE_PROMPTS, STICKER_PROMPTS, SCENE_PROMPTS
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&safe=true"


class GenerateStickerRequest(BaseModel):
    """生成表情包请求体"""
    mood: str = "默认"


class GenerateSceneRequest(BaseModel):
    """生成场景图请求体"""
    scene: str = "天台"


class TTSRequest(BaseModel):
    """文本转语音请求体"""
    text: str = ""


@router.post("/generate/selfie")
async def api_generate_selfie(user_id: int = Depends(get_current_user)):
    """生成 AI 自拍 API"""
    try:
        from system.prompts import SELFIE_PROMPTS
        prompt = random.choice(SELFIE_PROMPTS)
        url = _generate_image_url(prompt, 768, 1024)

        return {
            'success': True,
            'url': url,
            'type': 'selfie',
            'width': 768,
            'height': 1024
        }

    except Exception as e:
        logger.error(f"[Game API] 生成自拍失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate/sticker")
async def api_generate_sticker(
    body: GenerateStickerRequest,
    user_id: int = Depends(get_current_user),
):
    """生成表情包 API"""
    try:
        from system.prompts import STICKER_PROMPTS
        mood = body.mood

        prompts = STICKER_PROMPTS.get(mood, STICKER_PROMPTS.get('默认', []))
        if not prompts:
            prompts = STICKER_PROMPTS['默认']

        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 512, 512)

        return {
            'success': True,
            'url': url,
            'type': 'sticker',
            'mood': mood,
            'width': 512,
            'height': 512
        }

    except Exception as e:
        logger.error(f"[Game API] 生成表情包失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate/scene")
async def api_generate_scene(
    body: GenerateSceneRequest,
    user_id: int = Depends(get_current_user),
):
    """生成场景图 API"""
    try:
        from system.prompts import SCENE_PROMPTS
        scene = body.scene

        prompts = SCENE_PROMPTS.get(scene, SCENE_PROMPTS.get('天台', []))
        if not prompts:
            prompts = SCENE_PROMPTS['天台']

        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 1024, 768)

        return {
            'success': True,
            'url': url,
            'type': 'scene',
            'scene': scene,
            'width': 1024,
            'height': 768
        }

    except Exception as e:
        logger.error(f"[Game API] 生成场景图失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tts")
async def api_tts(
    body: TTSRequest,
    user_id: int = Depends(get_current_user),
):
    """文本转语音 API"""
    try:
        text = body.text

        if not text or len(text) > 300:
            raise HTTPException(status_code=400, detail='文本为空或超过300字符')

        # 使用 tts_engine 生成语音
        try:
            from characters.tts_engine import TTSEngine
            tts = TTSEngine()
            audio_path = await tts.synthesize(text)

            if audio_path:
                audio_filename = os.path.basename(audio_path)
                return {
                    'success': True,
                    'audio_url': f'/static/tts/{audio_filename}',
                    'duration': len(text) * 0.15
                }
            raise ImportError("TTSEngine synthesize failed")

        except ImportError:
            import edge_tts

            communicate = edge_tts.Communicate(text, "zh-CN-XiaoyiNeural")
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                tmp_path = tmp.name

            await communicate.save(tmp_path)

            tts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'static', 'tts')
            os.makedirs(tts_dir, exist_ok=True)

            audio_filename = f"tts_{user_id}_{int(datetime.now().timestamp())}.ogg"
            final_path = os.path.join(tts_dir, audio_filename)
            shutil.move(tmp_path, final_path)

            return {
                'success': True,
                'audio_url': f'/static/tts/{audio_filename}',
                'duration': len(text) * 0.15
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Game API] TTS 失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 角色学习进化路由 (learning_routes.py) — 前缀 /api/characters
# ============================================================

learning_router = APIRouter(prefix="/api/characters", tags=["characters"])


class CharacterEvolveRequest(BaseModel):
    """角色进化请求体"""
    character_id: str = "chayewoon"


class CharacterLearnNovelRequest(BaseModel):
    """从小说学习请求体"""
    character_id: str = "chayewoon"
    topic: Optional[str] = None


class CharacterLearnChatRequest(BaseModel):
    """从聊天记录学习请求体"""
    character_id: str = "chayewoon"


class CharacterLearnMemoryRequest(BaseModel):
    """从向量记忆学习请求体"""
    character_id: str = "chayewoon"


@learning_router.post("/evolve")
async def api_character_evolve(
    body: CharacterEvolveRequest,
    user_id: int = Depends(get_current_user),
):
    """触发角色完整学习进化流程"""
    try:
        character_id = body.character_id

        logger.info(f"[Learning API] 用户 {user_id} 触发角色 {character_id} 进化")

        from characters.character_learning import evolve_character
        result = await evolve_character(character_id, user_id)

        return {
            'success': True,
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 进化失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@learning_router.post("/learn/novel")
async def api_character_learn_novel(
    body: CharacterLearnNovelRequest,
    user_id: int = Depends(get_current_user),
):
    """从小说知识库学习"""
    try:
        from characters.character_learning import get_learning
        learning = get_learning(body.character_id)
        result = await learning.learn_from_novel(body.topic)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 小说学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@learning_router.post("/learn/chat")
async def api_character_learn_chat(
    body: CharacterLearnChatRequest,
    user_id: int = Depends(get_current_user),
):
    """从聊天记录学习用户偏好"""
    try:
        from characters.character_learning import get_learning
        learning = get_learning(body.character_id)
        result = await learning.learn_from_chat_history(user_id)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 聊天记录学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@learning_router.post("/learn/memory")
async def api_character_learn_memory(
    body: CharacterLearnMemoryRequest,
    user_id: int = Depends(get_current_user),
):
    """从向量记忆库学习"""
    try:
        from characters.character_learning import get_learning
        learning = get_learning(body.character_id)
        result = await learning.learn_from_memories(user_id)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 记忆学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@learning_router.get("/learning/status")
async def api_character_learning_status(
    character_id: str = Query("chayewoon"),
    user_id: int = Depends(get_current_user),
):
    """获取角色学习状态"""
    try:
        from characters.novel_knowledge import is_knowledge_ready
        from characters.memory import get_memory_stats

        novel_ready = is_knowledge_ready(character_id)
        memory_stats = get_memory_stats(character_id)

        return {
            'success': True,
            'character_id': character_id,
            'learning_status': {
                'novel_knowledge': {
                    'ready': novel_ready,
                    'source_file': f'characters/{character_id}/novel.txt'
                },
                'vector_memory': memory_stats,
                'persona_file': f'characters/{character_id}/persona.md',
                'memories_file': f'characters/{character_id}/memories.md',
            }
        }

    except Exception as e:
        logger.error(f"[Learning API] 获取状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 上传处理路由 (upload_routes.py) — 前缀 /api/upload
# ============================================================

upload_router = APIRouter(prefix="/api/upload", tags=["upload"])


class CloneVoiceRequest(BaseModel):
    """声音克隆请求体"""
    character_id: str = "chayewoon"
    sample_id: str = ""
    api_key: str = ""


@upload_router.post("/voice")
async def api_upload_voice(
    voice_file: UploadFile = File(...),
    character_id: str = Form("chayewoon"),
    label: str = Form("用户上传"),
    description: str = Form(""),
    user_id: int = Depends(get_current_user),
):
    """上传角色声音样本"""
    try:
        # 保存临时文件
        ext = voice_file.filename.split('.')[-1] if '.' in voice_file.filename else 'mp3'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            while True:
                chunk = await voice_file.read(8192)
                if not chunk:
                    break
                tmp.write(chunk)
            tmp_path = tmp.name

        # 保存到角色声音库
        from characters.voice_manager import get_voice_manager
        vm = get_voice_manager(character_id)
        result = vm.save_voice_sample(tmp_path, label=label, description=description)

        # 清理临时文件
        os.unlink(tmp_path)

        return result

    except Exception as e:
        logger.error(f"[Upload] 声音上传失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@upload_router.post("/voice/clone")
async def api_clone_voice(
    body: CloneVoiceRequest,
    user_id: int = Depends(get_current_user),
):
    """使用 Fish Speech 克隆声音"""
    try:
        if not body.sample_id or not body.api_key:
            raise HTTPException(status_code=400, detail='缺少 sample_id 或 api_key')

        from characters.voice_manager import get_voice_manager
        vm = get_voice_manager(body.character_id)

        samples = vm.list_samples()
        sample_path = None
        for s in samples:
            if s['id'] == body.sample_id:
                sample_path = s.get('path')
                break

        if not sample_path or not os.path.exists(sample_path):
            raise HTTPException(status_code=400, detail='样本不存在')

        result = await vm.clone_voice_fish(sample_path, body.api_key)
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Upload] 声音克隆失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@upload_router.post("/chatlog")
async def api_upload_chatlog(
    chatlog_file: UploadFile = File(...),
    chat_partner: str = Form(""),
    user_id: int = Depends(get_current_user),
):
    """上传聊天记录生成 soul.md"""
    try:
        # 读取文件内容
        content = b''
        while True:
            chunk = await chatlog_file.read(8192)
            if not chunk:
                break
            content += chunk

        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = content.decode('gbk', errors='ignore')

        # 解析聊天记录
        from packages.analysis.chatlog import parse_wechat_chatlog
        parsed = parse_wechat_chatlog(text_content)

        if not parsed or not parsed.get('messages'):
            raise HTTPException(status_code=400, detail='无法解析聊天记录')

        # 生成 soul.md
        from characters.soul_manager import generate_soul_from_chatlog
        result = await generate_soul_from_chatlog(parsed, chat_partner or "好友")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Upload] 聊天记录上传失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@upload_router.post("/video")
async def api_upload_video(
    video_file: UploadFile = File(...),
    character_id: str = Form("chayewoon"),
    content_type: str = Form("剧集"),
    user_id: int = Depends(get_current_user),
):
    """上传角色视频进行学习"""
    try:
        from system.config import VIDEO_DIR
        os.makedirs(VIDEO_DIR, exist_ok=True)

        ext = video_file.filename.split('.')[-1] if '.' in video_file.filename else 'mp4'
        video_path = os.path.join(VIDEO_DIR, f"upload_{character_id}_{int(os.times().system)}.{ext}")

        with open(video_path, 'wb') as f:
            while True:
                chunk = await video_file.read(8192)
                if not chunk:
                    break
                f.write(chunk)

        # 处理视频
        from packages.importers.video_enhanced import import_video_for_learning
        result = await import_video_for_learning(video_path, character_id, content_type)

        # 清理视频文件（节省空间）
        if os.path.exists(video_path):
            os.remove(video_path)

        return result

    except Exception as e:
        logger.error(f"[Upload] 视频上传失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@upload_router.get("/status")
async def api_upload_status(
    character_id: str = Query("chayewoon"),
    user_id: int = Depends(get_current_user),
):
    """获取上传功能状态"""
    try:
        from characters.voice_manager import get_voice_manager
        from characters.soul_manager import get_soul_manager

        vm = get_voice_manager(character_id)
        sm = get_soul_manager()

        voice_status = vm.get_status()
        soul_exists = os.path.exists(sm.soul_path)

        return {
            'success': True,
            'character_id': character_id,
            'voice': voice_status,
            'soul': {
                'exists': soul_exists,
                'path': sm.soul_path if soul_exists else None
            }
        }

    except Exception as e:
        logger.error(f"[Upload] 获取状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
