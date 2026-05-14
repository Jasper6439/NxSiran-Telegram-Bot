"""
游戏状态序列化 + 版本号管理 + 变更通知
v1.6.3 — 前后端游戏状态同步

轻量级状态管理器，基于内存版本号 + SSE 推送，
避免 WebSocket 的内存开销（e2-micro 1GB RAM 约束）。
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Set

from database import get_db
from characters import get_current_character

logger = logging.getLogger(__name__)

# 全局状态版本号（进程级，重启后重置，前端会自动全量拉取）
_state_versions: Dict[int, int] = {}  # user_id -> version
_state_snapshots: Dict[int, dict] = {}  # user_id -> last serialized state
_subscribers: Dict[int, List[asyncio.Queue]] = {}  # user_id -> [Queue]

# 最大订阅者数（内存保护）
_MAX_SUBSCRIBERS_PER_USER = 3
# 快照过期时间（秒）
_SNAPSHOT_TTL = 300


def get_state_version(user_id: int) -> int:
    """获取用户当前状态版本号"""
    return _state_versions.get(user_id, 0)


def _bump_version(user_id: int) -> int:
    """递增版本号并返回新值"""
    current = _state_versions.get(user_id, 0)
    new_version = current + 1
    _state_versions[user_id] = new_version
    return new_version


def serialize_game_state(user_id: int, character_id: str = None) -> dict:
    """序列化完整游戏状态（与 api_get_full_game_state 保持一致的数据结构）

    Args:
        user_id: 用户 ID
        character_id: 角色 ID（可选，默认使用当前角色）
    """
    db = get_db()

    # 确保用户和农场存在
    db.get_or_create_user(user_id, f"game_{user_id}")
    farm = db.get_or_create_farm(user_id)

    # 更新作物生长
    db.update_crop_growth(farm['id'])

    # 获取所有数据
    crops = db.get_crops(farm['id'])
    inventory = db.get_inventory(user_id)
    crop_types = db.get_crop_types()

    # 获取角色关系
    if not character_id:
        character = get_current_character()
        character_id = character.config.id if character else 'chayewoon'
    relationship = db.get_relationship(user_id, character_id)
    emotion_values = db.get_emotion_values(user_id, character_id)

    # 获取世界层级状态
    world_layer_state = db.get_world_layer_state(user_id)

    # 获取地图系统状态
    map_state = db.get_map_state(user_id)

    # 获取角色位置
    location = db.get_character_location(character_id)

    # 获取玩家位置
    player_pos = db.get_player_position(user_id)

    # 构建作物字典
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

    state = {
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
    }

    return state


def compute_state_diff(old_state: dict, new_state: dict) -> dict:
    """计算两个状态之间的差异（仅返回变更的字段）"""
    diff = {}
    _deep_diff(old_state, new_state, '', diff)
    return diff


def _deep_diff(old: any, new: any, path: str, diff: dict):
    """递归比较两个值，记录差异到 diff"""
    if type(old) != type(new):
        diff[path] = {'old': old, 'new': new}
    elif isinstance(new, dict):
        all_keys = set(old.keys()) | set(new.keys())
        for key in all_keys:
            sub_path = f"{path}.{key}" if path else key
            if key not in old:
                diff[sub_path] = {'old': None, 'new': new[key]}
            elif key not in new:
                diff[sub_path] = {'old': old[key], 'new': None}
            else:
                _deep_diff(old[key], new[key], sub_path, diff)
    elif isinstance(new, list):
        if old != new:
            diff[path] = {'old': old, 'new': new}
    elif old != new:
        diff[path] = {'old': old, 'new': new}


def notify_state_change(user_id: int, changed_keys: Optional[List[str]] = None):
    """通知状态变更，向所有订阅者推送"""
    new_version = _bump_version(user_id)

    # 更新快照
    try:
        new_state = serialize_game_state(user_id)
        _state_snapshots[user_id] = {
            'state': new_state,
            'timestamp': time.time()
        }
    except Exception as e:
        logger.error(f"[GameState] 序列化快照失败: {e}")
        return

    # 推送给订阅者
    queues = _subscribers.get(user_id, [])
    if not queues:
        return

    message = json.dumps({
        'version': new_version,
        'changed_keys': changed_keys or [],
        'timestamp': time.time()
    }, ensure_ascii=False)

    dead_queues = []
    for queue in queues:
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead_queues.append(queue)

    # 清理满队列
    for q in dead_queues:
        queues.remove(q)

    logger.debug(f"[GameState] 用户 {user_id} 状态变更 v{new_version}, 推送给 {len(queues)} 个订阅者")


async def subscribe_state_changes(user_id: int) -> asyncio.Queue:
    """订阅状态变更，返回消息队列"""
    if user_id not in _subscribers:
        _subscribers[user_id] = []

    # 内存保护：限制订阅者数量
    if len(_subscribers[user_id]) >= _MAX_SUBSCRIBERS_PER_USER:
        logger.warning(f"[GameState] 用户 {user_id} 订阅者过多，移除最旧的")
        _subscribers[user_id].pop(0)

    queue = asyncio.Queue(maxsize=50)
    _subscribers[user_id].append(queue)
    return queue


def unsubscribe_state_changes(user_id: int, queue: asyncio.Queue):
    """取消订阅"""
    if user_id in _subscribers:
        try:
            _subscribers[user_id].remove(queue)
        except ValueError:
            pass
        if not _subscribers[user_id]:
            del _subscribers[user_id]


def get_snapshot(user_id: int) -> Optional[dict]:
    """获取缓存的状态快照（如果未过期）"""
    snapshot = _state_snapshots.get(user_id)
    if not snapshot:
        return None
    if time.time() - snapshot['timestamp'] > _SNAPSHOT_TTL:
        del _state_snapshots[user_id]
        return None
    return snapshot['state']


def cleanup_stale_subscribers():
    """清理过期订阅者（定期调用）"""
    now = time.time()
    stale_users = []
    for user_id, snapshot in _state_snapshots.items():
        if now - snapshot['timestamp'] > _SNAPSHOT_TTL * 2:
            stale_users.append(user_id)
    for user_id in stale_users:
        _state_snapshots.pop(user_id, None)
        _subscribers.pop(user_id, None)
        logger.debug(f"[GameState] 清理过期用户 {user_id} 的状态数据")
