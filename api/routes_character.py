"""
角色相关 API 路由模块

将原 aiohttp 路由（character_routes, map_routes, learning_routes）迁移为 FastAPI APIRouter 格式。
包含角色互动、多地图系统、角色学习进化共 13 条路由。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.deps import get_current_user
from database import get_db
from system.config import get_default_tz
from characters import get_current_character
from api.game_state import notify_state_change
from characters.character_learning import evolve_character, get_learning

logger = logging.getLogger(__name__)

router = APIRouter(tags=["character"])


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _validate_farm_coords(x: int, y: int, farm: dict) -> bool:
    """校验农场坐标是否在合法范围内"""
    return 0 <= x < farm.get('gridWidth', 12) and 0 <= y < farm.get('gridHeight', 8)


def _get_default_character_id() -> str:
    """获取默认角色 ID（当前角色或回退值）"""
    character = get_current_character()
    return character.config.id if character else 'chayewoon'


# ---------------------------------------------------------------------------
# Pydantic 请求模型
# ---------------------------------------------------------------------------

class InteractRequest(BaseModel):
    """与角色互动请求体"""
    type: str = 'chat'
    content: str = ''
    character_id: Optional[str] = None


class GiftRequest(BaseModel):
    """赠送礼物请求体"""
    itemId: str
    quantity: int = 1
    character_id: Optional[str] = None


class SyncActionItem(BaseModel):
    """增量同步中的单条操作"""
    type: str
    id: Optional[str] = ''
    x: Optional[int] = None
    y: Optional[int] = None
    direction: Optional[str] = 'down'
    cropType: Optional[str] = None
    itemType: Optional[str] = 'crop'
    itemId: Optional[str] = None
    quantity: Optional[int] = 1
    price: Optional[int] = None


class SyncActionsRequest(BaseModel):
    """增量同步操作请求体"""
    actions: List[SyncActionItem] = []
    timestamp: float = 0


class SwitchMapRequest(BaseModel):
    """切换地图请求体"""
    map_id: str


class DiscoverMapRequest(BaseModel):
    """发现地图内容请求体"""
    discovery_key: str
    data: Optional[Dict[str, Any]] = None


class EvolveRequest(BaseModel):
    """角色进化请求体"""
    character_id: str = 'chayewoon'


class LearnNovelRequest(BaseModel):
    """从小说学习请求体"""
    character_id: str = 'chayewoon'
    topic: Optional[str] = None


class LearnChatRequest(BaseModel):
    """从聊天记录学习请求体"""
    character_id: str = 'chayewoon'


class LearnMemoryRequest(BaseModel):
    """从向量记忆库学习请求体"""
    character_id: str = 'chayewoon'


# ===========================================================================
# 一、角色互动路由（原 character_routes.py）
# ===========================================================================

@router.get("/api/game/character/location")
async def api_get_character_location(
    character_id: Optional[str] = Query(None),
    user_id: int = Depends(get_current_user),
):
    """获取角色当前位置"""
    try:
        if not character_id:
            character_id = _get_default_character_id()

        db = get_db()

        # 获取位置
        location = db.get_character_location(character_id)

        if not location:
            # 默认位置
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


@router.post("/api/game/character/interact")
async def api_interact_with_character(
    body: InteractRequest,
    user_id: int = Depends(get_current_user),
):
    """与角色互动"""
    try:
        interaction_type = body.type
        content = body.content
        character_id = body.character_id or _get_default_character_id()

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

        notify_state_change(user_id, ['hearts', 'relationshipStatus'])

        return {
            'success': True,
            'hearts': relationship['hearts'] if relationship else 0,
            'relationshipStatus': relationship['relationship_status'] if relationship else 'stranger'
        }

    except Exception as e:
        logger.error(f"[Game API] 互动失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/game/character/gift")
async def api_gift_to_character(
    body: GiftRequest,
    user_id: int = Depends(get_current_user),
):
    """赠送礼物给角色"""
    try:
        item_id = body.itemId
        quantity = body.quantity
        character_id = body.character_id or _get_default_character_id()

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

        # 记录互动
        # TODO: add_relationship_history 方法不存在于 RelationshipMixin，需要实现或移除
        # db.add_relationship_history(
        #     user_id, character_id,
        #     'gift', f'赠送了 {quantity} 个 {item_id}',
        #     hearts_delta
        # )

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


@router.post("/api/game/character/sync")
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
                action_type = action.type
                action_id = action.id or ''
                result: Dict[str, Any] = {'id': action_id, 'type': action_type, 'success': False}

                if action_type == 'plant':
                    # 验证：1)坐标合法 2)有种子 3)地块为空
                    x, y = action.x, action.y
                    crop_type = action.cropType
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
                    x, y = action.x, action.y

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
                    x, y = action.x, action.y

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
                    crop_type = action.cropType
                    quantity = action.quantity or 1
                    price = (action.price or 10) * quantity

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
                    item_type = action.itemType or 'crop'
                    item_id = action.itemId
                    quantity = action.quantity or 1
                    price = (action.price or 5) * quantity

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
                    x, y = action.x, action.y
                    direction = action.direction or 'down'

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


# ===========================================================================
# 二、多地图系统路由（原 map_routes.py）
# ===========================================================================

@router.get("/api/game/maps")
async def api_get_maps(
    character_id: str = Query('chayewoon'),
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


@router.post("/api/game/maps/switch")
async def api_switch_map(
    body: SwitchMapRequest,
    user_id: int = Depends(get_current_user),
):
    """切换当前地图"""
    try:
        map_id = body.map_id

        if not map_id:
            raise HTTPException(status_code=400, detail='缺少 map_id 参数')

        db = get_db()
        result = db.switch_map(user_id, map_id)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Map API] 切换地图失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/game/maps/state")
async def api_get_map_state(
    user_id: int = Depends(get_current_user),
):
    """获取当前地图详细状态"""
    try:
        db = get_db()
        map_state = db.get_map_state(user_id)

        # 获取玩家当前位置
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


@router.post("/api/game/maps/discover")
async def api_discover_map(
    body: DiscoverMapRequest,
    user_id: int = Depends(get_current_user),
):
    """发现地图上的新内容"""
    try:
        discovery_key = body.discovery_key

        if not discovery_key:
            raise HTTPException(status_code=400, detail='缺少 discovery_key 参数')

        discovery_data = body.data or {}

        db = get_db()
        result = db.discover_map_content(user_id, discovery_key, discovery_data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Map API] 发现地图内容失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/game/maps/discoveries")
async def api_get_map_discoveries(
    user_id: int = Depends(get_current_user),
):
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


# ===========================================================================
# 三、角色学习进化路由（原 learning_routes.py）
# ===========================================================================

@router.post("/api/characters/evolve")
async def api_character_evolve(
    body: EvolveRequest,
    user_id: int = Depends(get_current_user),
):
    """触发角色完整学习进化流程

    执行：
    1. 从 novel.txt 学习 → 更新 persona.md
    2. 从聊天记录学习 → 更新 memories.md（用户画像）
    3. 从向量记忆学习 → 更新 memories.md（关键记忆）
    """
    try:
        character_id = body.character_id

        logger.info(f"[Learning API] 用户 {user_id} 触发角色 {character_id} 进化")

        result = await evolve_character(character_id, user_id)

        return {
            'success': True,
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 进化失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/characters/learn/novel")
async def api_character_learn_novel(
    body: LearnNovelRequest,
    user_id: int = Depends(get_current_user),
):
    """从小说知识库学习"""
    try:
        character_id = body.character_id
        topic = body.topic

        learning = get_learning(character_id)
        result = await learning.learn_from_novel(topic)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 小说学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/characters/learn/chat")
async def api_character_learn_chat(
    body: LearnChatRequest,
    user_id: int = Depends(get_current_user),
):
    """从聊天记录学习用户偏好"""
    try:
        character_id = body.character_id

        learning = get_learning(character_id)
        result = await learning.learn_from_chat_history(user_id)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 聊天记录学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/characters/learn/memory")
async def api_character_learn_memory(
    body: LearnMemoryRequest,
    user_id: int = Depends(get_current_user),
):
    """从向量记忆库学习"""
    try:
        character_id = body.character_id

        learning = get_learning(character_id)
        result = await learning.learn_from_memories(user_id)

        return {
            'success': result.get('success', False),
            'result': result
        }

    except Exception as e:
        logger.error(f"[Learning API] 记忆学习失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/characters/learning/status")
async def api_character_learning_status(
    character_id: str = Query('chayewoon'),
    user_id: int = Depends(get_current_user),
):
    """获取角色学习状态"""
    try:
        # 检查各学习源状态
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
