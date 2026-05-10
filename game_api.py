# 恋爱至上主义区域 (Love Supremacy Zone)
"""
游戏 API 模块 - 农场经营 + 角色互动
提供 Web/Mini App 端的游戏数据接口
"""

import json
import logging
import os
import shutil
from datetime import datetime, timezone, timedelta
from aiohttp import web
from database import get_db
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 韩国时区
KR_TZ = timezone(timedelta(hours=9))


# ============================================================
# 农场 API
# ============================================================

async def api_get_farm(request):
    """获取农场数据"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        db = get_db()
        
        # 获取农场数据
        farm = db.get_farm(user_id)
        if not farm:
            # 创建农场
            db.get_or_create_user(user_id, f"user_{user_id}")
            farm = db.get_farm(user_id)
        
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
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        x = data.get('x', 0)
        y = data.get('y', 0)
        crop_type = data.get('crop_type', 'tomato')
        
        db = get_db()
        
        # 获取农场
        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})
        
        # 检查背包是否有种子
        if not db.remove_item(user_id, 'seed', crop_type):
            # 如果没有种子，自动给一个（测试用）
            db.add_item(user_id, 'seed', crop_type, 1)
        
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
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
            
            # 记录事件
            db.log_game_event(user_id, 'harvest', {
                'x': x, 'y': y, 'crop_type': crop_type
            }, 'web')
            
            # 获取作物信息
            crop_info = db.get_crop_type(crop_type)
            
            return web.json_response({
                'success': True,
                'crop_type': crop_type,
                'crop_name': crop_info['name'] if crop_info else crop_type,
                'emoji': crop_info['emoji'] if crop_info else '🌱'
            })
        else:
            return web.json_response({
                'success': False,
                'error': '这里没有可收获的作物'
            })
            
    except Exception as e:
        logger.error(f"[Game API] 收获失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_sell_crop(request):
    """出售作物"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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


# ============================================================
# 角色互动 API
# ============================================================

async def api_get_character_location(request):
    """获取角色当前位置"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        
        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
        
        db = get_db()
        
        # 获取位置
        location = db.get_character_location(character_id)
        
        # 获取关系
        relationship = db.get_relationship(user_id, character_id) if user_id else None
        
        return web.json_response({
            'success': True,
            'character_id': character_id,
            'character_name': character.config.name if character else '车如云',
            'location': location,
            'relationship': relationship
        })
        
    except Exception as e:
        logger.error(f"[Game API] 获取角色位置失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_get_relationship(request):
    """获取玩家与角色的关系"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
        
        db = get_db()
        
        # 获取关系
        relationship = db.get_relationship(user_id, character_id)
        
        # 获取可触发事件
        available_events = db.get_available_events(user_id, character_id)
        
        return web.json_response({
            'success': True,
            'relationship': relationship,
            'available_events': available_events
        })
        
    except Exception as e:
        logger.error(f"[Game API] 获取关系失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_game_chat(request):
    """游戏内与角色对话 (v0.2 - 使用 ChatEngine)"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        message = data.get('message', '')
        character_id = data.get('character_id', 'chayewoon')
        
        if not message:
            return web.json_response({'success': False, 'error': '消息不能为空'})
        
        # 使用 ChatEngine
        from chat_engine import chat_with_character
        from database import get_db
        
        db = get_db()
        location = db.get_character_location(character_id)
        location_text = location['location'] if location else ''
        
        # 获取当前情感值
        emotion_values = db.get_emotion_values(user_id, character_id)
        
        result = await chat_with_character(
            character_id=character_id,
            user_id=user_id,
            user_message=message,
            context={
                'platform': 'web',
                'location': location_text,
                'emotion_values': emotion_values,
            }
        )
        
        # 应用觉醒情感奖励
        if result.get('awakening_triggered') and result['awakening_triggered'].get('emotion_bonus'):
            bonus = result['awakening_triggered']['emotion_bonus']
            for key, value in bonus.items():
                result['emotion_changes'][key] = result['emotion_changes'].get(key, 0) + value
        
        return web.json_response({
            'success': True,
            'response': result['response'],
            'character_name': result['character_name'],
            'character_id': result['character_id'],
            'emotion_changes': result['emotion_changes'],
            'awakening_triggered': result['awakening_triggered'],
            'memory_saved': result['memory_saved'],
        })
        
    except Exception as e:
        logger.error(f"[Game API] 游戏对话失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_chat_history(request):
    """获取对话历史 (v0.2)"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        from database import get_db
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        
        character_id = request.query.get('character_id', 'chayewoon')
        limit = int(request.query.get('limit', 50))
        
        db = get_db()
        history = db.get_chat_history(user_id, character_id, limit)
        
        return web.json_response({'success': True, 'history': history})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_awakening_events(request):
    """获取觉醒事件列表 (v0.2)"""
    try:
        character_id = request.query.get('character_id', 'chayewoon')
        
        from awakening_detector import AwakeningDetector
        detector = AwakeningDetector()
        events = detector.get_all_events(character_id)
        
        return web.json_response({'success': True, 'events': events})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)})


async def api_gift_character(request):
    """给角色送礼物"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character, call_ai
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        item_type = data.get('item_type', 'crop')
        item_id = data.get('item_id', '')
        
        # 获取当前角色
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
        character_name = character.config.name if character else '车如云'
        
        db = get_db()
        
        # 检查背包
        if not db.remove_item(user_id, item_type, item_id):
            return web.json_response({
                'success': False,
                'error': '背包里没有这个物品'
            })
        
        # 获取物品信息
        item_info = db.get_crop_type(item_id) if item_type == 'crop' else None
        item_name = item_info['name'] if item_info else item_id
        
        # 判断喜好（简化版，实际应该从角色配置读取）
        # 车如云喜欢：红豆相关、甜食
        # 不喜欢：苦的、辣的
        reaction = 'neutral'
        hearts_change = 1
        
        if item_id in ['strawberry', 'watermelon']:
            reaction = 'like'
            hearts_change = 2
        elif 'tomato' in item_id:
            reaction = 'neutral'
            hearts_change = 1
        else:
            reaction = 'neutral'
            hearts_change = 1
        
        # 更新心级
        new_hearts = db.update_hearts(user_id, character_id, hearts_change)
        
        # 记录礼物
        now = datetime.now(KR_TZ).isoformat()
        with db.get_connection() as conn:
            conn.execute(
                """INSERT INTO gift_history (user_id, character_id, item_type, item_id, reaction, hearts_change, gifted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, character_id, item_type, item_id, reaction, hearts_change, now)
            )
        
        # 生成角色反应
        reaction_prompts = {
            'love': f"学长送了我最喜欢的{item_name}，用一句话害羞地回应，不超过15个字",
            'like': f"学长送了我{item_name}，挺喜欢的，用一句话简短回应，不超过15个字",
            'neutral': f"学长送了我{item_name}，用一句话简短回应，不超过15个字",
            'dislike': f"学长送了我{item_name}，不太喜欢，用一句话简短回应，不超过15个字",
        }
        
        response = await call_ai(reaction_prompts.get(reaction, reaction_prompts['neutral']))
        
        # 记录事件
        db.log_game_event(user_id, 'gift', {
            'item_type': item_type,
            'item_id': item_id,
            'reaction': reaction,
            'hearts_change': hearts_change
        }, 'web')
        
        return web.json_response({
            'success': True,
            'reaction': reaction,
            'hearts_change': hearts_change,
            'new_hearts': new_hearts,
            'response': response
        })
        
    except Exception as e:
        logger.error(f"[Game API] 送礼失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 心级事件 API
# ============================================================

async def api_check_heart_events(request):
    """检查可触发的心级事件"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
        
        db = get_db()
        
        # 获取角色当前位置
        location = db.get_character_location(character_id)
        current_hour = datetime.now(KR_TZ).hour if location else 99
        
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
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        import json
        dialogue = []
        try:
            dialogue = json.loads(event.get('dialogue', '[]'))
        except:
            pass
        
        # 解析奖励
        rewards = {}
        try:
            rewards = json.loads(event.get('rewards', '{}'))
        except:
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


# ============================================================
# 烹饪 API
# ============================================================

async def api_get_recipes(request):
    """获取所有料理配方"""
    try:
        from bot import validate_session_token, validate_api_token, load_config

        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        db = get_db()
        recipes = db.get_recipes()
        inventory = db.get_inventory(user_id)
        
        # 标记每个配方是否可以烹饪
        for recipe in recipes:
            can, msg = db.can_cook(user_id, recipe['id'])
            recipe['can_cook'] = can
            recipe['cook_message'] = msg
        
        return web.json_response({
            'success': True,
            'recipes': recipes,
            'inventory': inventory
        })
        
    except Exception as e:
        logger.error(f"[Game API] 获取配方失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_cook(request):
    """烹饪料理"""
    try:
        from bot import validate_session_token, validate_api_token, load_config

        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        recipe_id = data.get('recipe_id', '')
        
        db = get_db()
        recipe = db.cook(user_id, recipe_id)
        
        if recipe:
            db.log_game_event(user_id, 'cook', {
                'recipe_id': recipe_id,
                'recipe_name': recipe['name']
            }, 'miniapp')
            
            return web.json_response({
                'success': True,
                'recipe': recipe,
                'message': f"烹饪成功！{recipe['emoji']} {recipe['name']}"
            })
        else:
            can, msg = db.can_cook(user_id, recipe_id)
            return web.json_response({
                'success': False,
                'error': msg or '材料不足'
            })
            
    except Exception as e:
        logger.error(f"[Game API] 烹饪失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 每日签到 API
# ============================================================

async def api_daily_reward(request):
    """领取每日登录奖励"""
    try:
        from bot import validate_session_token, validate_api_token, load_config

        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        db = get_db()
        # 确保用户存在
        db.get_or_create_user(user_id, f"web_{user_id}")
        result = db.claim_daily_reward(user_id)
        
        return web.json_response(result)
        
    except Exception as e:
        logger.error(f"[Game API] 每日签到失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_check_daily(request):
    """检查今日是否已签到"""
    try:
        from bot import validate_session_token, validate_api_token, load_config

        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        db = get_db()
        # 确保用户存在
        db.get_or_create_user(user_id, f"web_{user_id}")
        reward = db.get_daily_reward(user_id)
        
        return web.json_response({
            'success': True,
            'claimed': reward['claimed'] == 1 if reward else False
        })
        
    except Exception as e:
        logger.error(f"[Game API] 检查签到失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 同步 API
# ============================================================

async def api_get_game_events(request):
    """获取未同步的游戏事件"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        from bot import validate_session_token, validate_api_token
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        event_ids = data.get('event_ids', [])
        
        db = get_db()
        db.mark_events_synced(event_ids)
        
        return web.json_response({'success': True})
        
    except Exception as e:
        logger.error(f"[Game API] 标记同步失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 游戏全量状态 API（DOM-based 游戏引擎用）
# ============================================================

async def api_get_full_game_state(request):
    """一次性获取全部游戏状态"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        db = get_db()
        
        # 确保用户存在
        db.get_or_create_user(user_id, f"game_{user_id}")
        
        # 获取农场
        farm = db.get_farm(user_id)
        if not farm:
            return web.json_response({'success': False, 'error': '没有农场'})
        
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
            'buildings': buildings,
            'decorations': decorations,
            'weather': 'sunny',
            'season': 'spring',
            'gameDay': 1
        })
        
    except Exception as e:
        logger.error(f"[Game API] 获取全量状态失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_water_crop(request):
    """浇水"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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


async def api_sync_actions(request):
    """增量同步操作"""
    try:
        from bot import validate_session_token, validate_api_token
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        actions = data.get('actions', [])
        
        db = get_db()
        processed = 0
        
        for action in actions:
            try:
                action_type = action.get('type')
                if action_type == 'plant':
                    farm = db.get_farm(user_id)
                    if farm:
                        db.plant_crop(farm['id'], action['x'], action['y'], action['cropType'])
                elif action_type == 'harvest':
                    farm = db.get_farm(user_id)
                    if farm:
                        crop_type = db.harvest_crop(farm['id'], action['x'], action['y'])
                        if crop_type:
                            db.add_item(user_id, 'crop', crop_type, 1)
                elif action_type == 'water':
                    farm = db.get_farm(user_id)
                    if farm:
                        db.water_crop(farm['id'], action['x'], action['y'])
                elif action_type == 'buy_seed':
                    # Already processed client-side
                    pass
                elif action_type == 'sell':
                    # Already processed client-side
                    pass
                elif action_type == 'move':
                    db.save_player_position(user_id, action['x'], action['y'], action.get('direction', 'down'))
                processed += 1
            except Exception as e:
                logger.warning(f"[Game API] 同步操作失败: {action_type} - {e}")
        
        return web.json_response({'success': True, 'processed': processed})
        
    except Exception as e:
        logger.error(f"[Game API] 同步失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 情感值与觉醒系统 API（恋爱至上主义区域）
# ============================================================

async def api_get_emotion_values(request):
    """获取情感值 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
        from bot import validate_session_token, validate_api_token, load_config, get_current_character
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
    """切换世界层级 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        layer = data.get('layer', 'normal')
        
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
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
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
# 多媒体生成 API（v0.3）
# ============================================================

import random
import urllib.parse

# 自拍 Prompt（从 bot.py 复制，韩国 BL 美学风格）
SELFIE_PROMPTS = [
    "Young East Asian man slim athletic build, short dark hair clean cut, wearing oversized black jacket over white t-shirt, standing on city street at night, neon signs and street lights in background, cool blue-amber color grading, shallow depth of field, 35mm lens feel, realistic casual photo style, slight film grain, contemplative restrained expression not looking at camera, cinematic 4K",
    "Young East Asian man athletic runner build, short dark messy hair slightly sweaty, wearing track jacket and shorts, leaning against railing on city bridge at night, city lights reflecting on river below, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, realistic documentary style, calm composed expression, cinematic 4K",
    "Young East Asian man slim build, short textured dark hair, wearing loose denim jacket black t-shirt silver chain necklace, mirror selfie in dimly lit room, warm amber indoor lighting, shallow depth of field, realistic casual photo, slight grain texture, restrained half-smile, 35mm lens perspective, cinematic 4K",
    "Young East Asian man 186cm slim athletic, short dark hair with volume on top, wearing oversized olive green jacket white shirt, walking on street with backpack, golden hour sunlight, blue sky with scattered clouds, warm natural color grading, shallow depth of field, 35mm lens documentary feel, relaxed composed expression, realistic casual photography, cinematic 4K",
    "Young East Asian man athletic build, short dark hair, wearing black hoodie and loose jeans, sitting in cafe by window, afternoon sunlight through glass, warm highlights on face, soft natural color grading, shallow depth of field, contemplative calm expression looking away, realistic lifestyle photo, 50mm lens, cinematic 4K",
    "Korean BL drama still frame, young Korean man 18yo 186cm slim athletic, oval face soft contours, large almond eyes, black tousled medium hair with fringe, clear porcelain skin, wearing Korean white school uniform shirt loose tie, leaning against hallway wall, soft warm color grading, shallow depth of field, romantic melancholic youth drama atmosphere, Korean BL cinematography style, photorealistic 8K",
]

# 表情包 Prompt
STICKER_PROMPTS = {
    "害羞": [
        "Korean BL drama close-up emoji sticker, young Korean man 18yo, covering face with one hand peeking through fingers, visible blush on cheeks, black tousled hair, soft warm color grading, simple clean background, cute chibi style, Korean BL aesthetic, flat illustration",
        "Korean BL drama emoji sticker, young Korean man blushing heavily, looking down shyly, hand covering mouth, nose scrunch, warm pink tones, simple background, cute sticker art style, Korean BL aesthetic",
    ],
    "生气": [
        "Korean BL drama emoji sticker, young Korean man 18yo angry expression, furrowed brows, cold glare, arms crossed, slightly pouting, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man looking away annoyed, sharp eyes, slight frown, cold atmosphere, desaturated tones, simple background, cute sticker art style",
    ],
    "开心": [
        "Korean BL drama emoji sticker, young Korean man 18yo rare genuine smile, eyes curved into crescents, soft warm lighting, happy expression, warm golden tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man small shy smile, looking at viewer, gentle eyes, warm atmosphere, soft pastel tones, simple background, cute sticker art style",
    ],
    "难过": [
        "Korean BL drama emoji sticker, young Korean man 18yo sad expression, teary eyes looking down, solitary figure, melancholic atmosphere, cool blue-grey tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man covering eyes with arm, crying silently, lonely atmosphere, muted desaturated tones, simple background, cute sticker art style",
    ],
    "想你": [
        "Korean BL drama emoji sticker, young Korean man 18yo looking at phone screen longingly, lying on bed, dim room, phone glow on face, warm intimate tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man staring out window at night, city lights reflection in eyes, contemplative lonely expression, cool blue-warm tones, simple background, cute sticker art style",
    ],
    "吃醋": [
        "Korean BL drama emoji sticker, young Korean man 18yo jealous expression, sharp side glance, slightly pouting lips, arms crossed, tense atmosphere, warm-cool contrast tones, simple background, cute sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man glaring with narrowed eyes, cold expression but hurt underneath, slight frown, dramatic lighting, simple background, cute sticker art style",
    ],
    "撒娇": [
        "Korean BL drama emoji sticker, young Korean man 18yo puppy eyes expression, slightly pouting, head tilted, cute pleading look, warm pink tones, simple background, cute chibi sticker art style, Korean BL aesthetic",
        "Korean BL drama emoji sticker, young Korean man tugging sleeve shyly, looking up with big eyes, slight blush, soft warm tones, simple background, cute sticker art style",
    ],
    "默认": [
        "Korean BL drama emoji sticker, young Korean man 18yo neutral calm expression, slight contemplative look, simple background, cute sticker art style, Korean BL aesthetic",
    ],
}

# 场景 Prompt
SCENE_PROMPTS = {
    "天台": [
        "Korean high school rooftop at sunset, concrete floor with metal railings, city skyline in background, golden hour lighting, warm orange and pink sky, a backpack and water bottle left on the bench, realistic casual photo style, soft warm color grading, shallow depth of field, 35mm lens, cinematic 4K",
        "Korean school rooftop at night, city lights twinkling below, cool blue moonlight, a single figure's shadow cast on concrete, quiet contemplative atmosphere, high contrast night photography, cool blue-teal color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "房间": [
        "Small cozy Korean student room, single bed with simple white sheets, small desk with textbooks and lamp, morning sunlight through small window, realistic lifestyle photo, soft warm indoor lighting, shallow depth of field, 35mm lens, intimate personal atmosphere, cinematic 4K",
        "Korean student's rooftop room at night, small space with mattress on floor, phone screen glowing, city lights visible through opening, warm amber color grading, shallow depth of field, realistic casual photo, slight film grain, cinematic 4K",
    ],
    "学校": [
        "Korean high school hallway during golden hour, long corridor with lockers, warm sunlight streaming through windows, leading lines composition, realistic documentary style, warm golden color grading, shallow depth of field, 35mm lens, nostalgic youth atmosphere, cinematic 4K",
        "Korean high school classroom, empty desks and chairs, afternoon sunlight through large windows, dust particles in light beams, realistic casual style, soft warm color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "田径场": [
        "Korean high school running track, red rubber surface with white lane markings, green field in center, golden hour sunlight, water bottle on the track, realistic sports photography, warm athletic color grading, shallow depth of field, 50mm lens, cinematic 4K wide angle",
        "Korean school athletic field at dawn, morning mist, dew on grass, track surface glistening, sunrise colors in sky, realistic documentary style, soft cool-warm gradient color grading, shallow depth of field, cinematic 4K",
    ],
    "街道": [
        "Korean city street at dusk, neon signs and shop lights, small shops and convenience store, warm light from windows, quiet residential neighborhood, realistic street photography, warm amber-blue color grading, shallow depth of field, 35mm lens, cinematic blue hour atmosphere, cinematic 4K",
        "Korean city street near high school, afternoon sunlight, small cafes and bakeries, realistic casual street photography, soft warm color grading, shallow depth of field, 35mm lens documentary feel, cinematic 4K",
    ],
    "咖啡厅": [
        "Cozy Korean cafe interior, warm wooden furniture, afternoon sunlight through large windows, latte art on table, realistic lifestyle photography, soft warm indoor color grading, shallow depth of field, 50mm lens, cinematic 4K",
    ],
    "日落": [
        "Korean city skyline at sunset, golden hour, warm orange and pink sky, silhouettes of buildings, romantic atmosphere, realistic photography, cinematic 4K",
    ],
}


def _generate_image_url(prompt: str, width: int = 768, height: int = 1024) -> str:
    """生成 Pollinations.ai 图片 URL"""
    encoded = urllib.parse.quote(prompt)
    seed = random.randint(1, 999999)
    return f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true&safe=true"


async def api_generate_selfie(request):
    """生成 AI 自拍 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        prompt = random.choice(SELFIE_PROMPTS)
        url = _generate_image_url(prompt, 768, 1024)
        
        return web.json_response({
            'success': True,
            'url': url,
            'type': 'selfie',
            'width': 768,
            'height': 1024
        })
        
    except Exception as e:
        logger.error(f"[Game API] 生成自拍失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_generate_sticker(request):
    """生成表情包 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        mood = data.get('mood', '默认')
        
        prompts = STICKER_PROMPTS.get(mood, STICKER_PROMPTS.get('默认', []))
        if not prompts:
            prompts = STICKER_PROMPTS['默认']
        
        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 512, 512)
        
        return web.json_response({
            'success': True,
            'url': url,
            'type': 'sticker',
            'mood': mood,
            'width': 512,
            'height': 512
        })
        
    except Exception as e:
        logger.error(f"[Game API] 生成表情包失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_generate_scene(request):
    """生成场景图 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        scene = data.get('scene', '天台')
        
        prompts = SCENE_PROMPTS.get(scene, SCENE_PROMPTS.get('天台', []))
        if not prompts:
            prompts = SCENE_PROMPTS['天台']
        
        prompt = random.choice(prompts)
        url = _generate_image_url(prompt, 1024, 768)
        
        return web.json_response({
            'success': True,
            'url': url,
            'type': 'scene',
            'scene': scene,
            'width': 1024,
            'height': 768
        })
        
    except Exception as e:
        logger.error(f"[Game API] 生成场景图失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


async def api_tts(request):
    """文本转语音 API"""
    try:
        from bot import validate_session_token, validate_api_token, load_config
        
        user_id = validate_session_token(request)
        if not user_id:
            user_id = validate_api_token(request)
        if not user_id:
            user_id = load_config().get('your_chat_id', 0)
        if not user_id:
            return web.json_response({'success': False, 'error': '未登录'})
        
        data = await request.json()
        text = data.get('text', '')
        
        if not text or len(text) > 300:
            return web.json_response({'success': False, 'error': '文本为空或超过300字符'})
        
        # 使用 tts_engine 生成语音
        try:
            from tts_engine import TTSEngine
            tts = TTSEngine()
            audio_path = await tts.synthesize(text)
            
            if audio_path:
                # 返回音频文件路径（相对于 static）
                audio_filename = os.path.basename(audio_path)
                return web.json_response({
                    'success': True,
                    'audio_url': f'/static/tts/{audio_filename}',
                    'duration': len(text) * 0.15  # 估算时长
                })
            # synthesize 返回 None，走 edge_tts fallback
            raise ImportError("TTSEngine synthesize failed")
                
        except ImportError:
            # tts_engine 不可用或失败，直接使用 Edge TTS
            import edge_tts
            import tempfile
            
            communicate = edge_tts.Communicate(text, "zh-CN-XiaoyiNeural")
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                tmp_path = tmp.name
            
            await communicate.save(tmp_path)
            
            # 移动到 static/tts 目录
            tts_dir = os.path.join(os.path.dirname(__file__), 'static', 'tts')
            os.makedirs(tts_dir, exist_ok=True)
            
            audio_filename = f"tts_{user_id}_{int(datetime.now().timestamp())}.ogg"
            final_path = os.path.join(tts_dir, audio_filename)
            shutil.move(tmp_path, final_path)
            
            return web.json_response({
                'success': True,
                'audio_url': f'/static/tts/{audio_filename}',
                'duration': len(text) * 0.15
            })
        
    except Exception as e:
        logger.error(f"[Game API] TTS 失败: {e}")
        return web.json_response({'success': False, 'error': str(e)})


# ============================================================
# 注册路由
# ============================================================

def register_game_routes(app):
    """注册游戏 API 路由"""
    # DOM-based 游戏引擎
    app.router.add_get("/api/game/state", api_get_full_game_state)
    app.router.add_post("/api/game/water", api_water_crop)
    app.router.add_post("/api/game/move", api_move_player)
    app.router.add_post("/api/game/sync", api_sync_actions)
    
    # 农场
    app.router.add_get("/api/game/farm", api_get_farm)
    app.router.add_post("/api/game/plant", api_plant_crop)
    app.router.add_post("/api/game/harvest", api_harvest_crop)
    app.router.add_post("/api/game/sell", api_sell_crop)
    app.router.add_post("/api/game/buy-seed", api_buy_seed)
    
    # 角色互动
    app.router.add_get("/api/game/character/location", api_get_character_location)
    app.router.add_get("/api/game/relationship", api_get_relationship)
    app.router.add_post("/api/game/chat", api_game_chat)
    app.router.add_get("/api/game/chat/history", api_chat_history)
    app.router.add_get("/api/game/awakening/events", api_awakening_events)
    app.router.add_post("/api/game/gift", api_gift_character)
    
    # 心级事件
    app.router.add_get("/api/game/events/heart", api_check_heart_events)
    app.router.add_post("/api/game/events/trigger", api_trigger_heart_event)
    
    # 烹饪
    app.router.add_get("/api/game/recipes", api_get_recipes)
    app.router.add_post("/api/game/cook", api_cook)
    
    # 每日签到
    app.router.add_get("/api/game/daily/check", api_check_daily)
    app.router.add_post("/api/game/daily/claim", api_daily_reward)
    
    # 同步
    app.router.add_get("/api/game/events", api_get_game_events)
    app.router.add_post("/api/game/sync", api_mark_synced)
    
    # 情感值与觉醒系统（恋爱至上主义区域）
    app.router.add_get("/api/game/emotions", api_get_emotion_values)
    app.router.add_get("/api/game/awakening/check", api_check_awakening)
    app.router.add_post("/api/game/awakening/trigger", api_trigger_awakening)
    app.router.add_get("/api/game/world/state", api_get_world_state)
    app.router.add_post("/api/game/world/switch", api_switch_world_layer)
    
    # 多媒体生成 API（v0.3）
    app.router.add_post("/api/game/generate/selfie", api_generate_selfie)
    app.router.add_post("/api/game/generate/sticker", api_generate_sticker)
    app.router.add_post("/api/game/generate/scene", api_generate_scene)
    app.router.add_post("/api/game/tts", api_tts)
