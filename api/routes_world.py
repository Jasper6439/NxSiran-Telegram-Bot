"""
api/routes_world.py - 双域世界 API (v1.8)
==========================================
世界切换、双域种植、觉醒烹饪、角色投喂。
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user
from database import get_db
from core.farming_cooking import (
    validate_plant,
    get_available_crops,
    analyze_dish_effect,
    get_feed_feedback,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/world", tags=["world"])


# ============================================================
# Pydantic 请求模型
# ============================================================

class ShiftWorldRequest(BaseModel):
    target_state: str  # 'SCRIPTED' or 'VOID'


class WorldPlantRequest(BaseModel):
    x: int = 0
    y: int = 0
    crop_type: str = "tomato"


class CookRequest(BaseModel):
    recipe_id: str = ""


class FeedRequest(BaseModel):
    recipe_id: str = ""
    character_id: str = "chayewoon"


# ============================================================
# 世界状态
# ============================================================

@router.get("/state")
async def api_get_world_state(user_id: int = Depends(get_current_user)):
    """获取当前世界状态及觉醒度"""
    try:
        db = get_db()
        state = db.get_world_state(user_id)
        return {
            'success': True,
            'current_world': state['current_world_state'],
            'awakening_level': state['awakening_level'],
        }
    except Exception as e:
        logger.error(f"[World API] 获取世界状态失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/shift")
async def api_shift_world(
    body: ShiftWorldRequest,
    user_id: int = Depends(get_current_user),
):
    """切换世界状态（剧本区 <-> 空白区）"""
    try:
        db = get_db()
        result = db.shift_world(user_id, body.target_state.upper())
        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', '切换失败'))

        # 获取更新后的状态
        state = db.get_world_state(user_id)

        return {
            'success': True,
            'previous_state': result['previous_state'],
            'current_state': result['current_state'],
            'awakening_level': state['awakening_level'],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[World API] 切换世界失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 双域种植
# ============================================================

@router.get("/crops")
async def api_get_world_crops(user_id: int = Depends(get_current_user)):
    """获取当前世界可种植的作物"""
    try:
        db = get_db()
        state = db.get_world_state(user_id)
        world_state = state['current_world_state']

        all_crops = db.get_crop_types()
        available = get_available_crops(world_state, all_crops)

        return {
            'success': True,
            'world_state': world_state,
            'crops': available,
        }
    except Exception as e:
        logger.error(f"[World API] 获取作物失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/plant")
async def api_world_plant(
    body: WorldPlantRequest,
    user_id: int = Depends(get_current_user),
):
    """在当前世界中种植作物"""
    try:
        db = get_db()

        # 获取当前世界状态
        state = db.get_world_state(user_id)
        world_state = state['current_world_state']

        # 验证作物是否可在当前世界种植
        all_crops = db.get_crop_types()
        can, reason = validate_plant(world_state, body.crop_type, all_crops)
        if not can:
            raise HTTPException(status_code=400, detail=reason)

        # 获取农场
        farm = db.get_or_create_farm(user_id)
        if not farm:
            raise HTTPException(status_code=400, detail='农场创建失败')

        # 检查种子
        if not db.remove_item(user_id, 'seed', body.crop_type):
            raise HTTPException(status_code=400, detail='背包中没有该种子')

        # 种植
        success = db.plant_crop_in_world(
            farm['id'], body.x, body.y, body.crop_type, world_state
        )

        if success:
            db.log_game_event(user_id, 'world_plant', {
                'x': body.x, 'y': body.y,
                'crop_type': body.crop_type,
                'world_state': world_state,
            }, 'web')

            return {
                'success': True,
                'message': f'在{"空白区" if world_state == "VOID" else "剧本区"}种下了 {body.crop_type}',
                'world_state': world_state,
            }
        else:
            raise HTTPException(status_code=400, detail='这个位置已经有作物了')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[World API] 种植失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 觉醒烹饪
# ============================================================

@router.get("/recipes")
async def api_get_awakening_recipes(user_id: int = Depends(get_current_user)):
    """获取觉醒料理配方"""
    try:
        db = get_db()
        recipes = db.get_awakening_recipes()
        inventory = db.get_inventory(user_id)

        for recipe in recipes:
            can, msg = db.can_cook(user_id, recipe['id'])
            recipe['can_cook'] = can
            recipe['cook_message'] = msg

        return {
            'success': True,
            'recipes': recipes,
            'inventory': inventory,
        }
    except Exception as e:
        logger.error(f"[World API] 获取配方失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/cook")
async def api_world_cook(
    body: CookRequest,
    user_id: int = Depends(get_current_user),
):
    """烹饪觉醒料理"""
    try:
        db = get_db()
        result = db.cook_awakening_dish(user_id, body.recipe_id)

        if result:
            db.log_game_event(user_id, 'awakening_cook', {
                'recipe_id': body.recipe_id,
                'effect_type': result.get('effect_type', 'STABILIZE'),
                'awakening_boost': result.get('awakening_boost', 0),
            }, 'web')

            return {
                'success': True,
                'recipe': result,
                'message': f"烹饪成功！{result.get('emoji', '🍲')} {result.get('name', '')}",
            }
        else:
            can, msg = db.can_cook(user_id, body.recipe_id)
            raise HTTPException(status_code=400, detail=msg or '材料不足')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[World API] 烹饪失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 角色投喂
# ============================================================

@router.post("/feed")
async def api_feed_character(
    body: FeedRequest,
    user_id: int = Depends(get_current_user),
):
    """投喂料理给角色，触发觉醒效果"""
    try:
        db = get_db()
        result = db.feed_character(user_id, body.recipe_id, body.character_id)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('error', '投喂失败'))

        # 生成 AI 情感反馈
        feedback = get_feed_feedback(
            result['feedback_type'],
            result['recipe_name'],
        )

        db.log_game_event(user_id, 'feed_character', {
            'recipe_id': body.recipe_id,
            'character_id': body.character_id,
            'effect_type': result['effect_type'],
            'awakening_boost': result['awakening_boost'],
            'new_awakening_level': result['new_awakening_level'],
        }, 'web')

        return {
            'success': True,
            'feed_result': result,
            'feedback': feedback,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[World API] 投喂失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# 觉醒历史
# ============================================================

@router.get("/history")
async def api_get_world_history(user_id: int = Depends(get_current_user)):
    """获取世界切换历史"""
    try:
        db = get_db()
        history = db.get_world_shift_history(user_id)
        return {
            'success': True,
            'history': history,
        }
    except Exception as e:
        logger.error(f"[World API] 获取历史失败: {e}")
        raise HTTPException(status_code=400, detail=str(e))
