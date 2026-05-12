"""地图系统 Mixin - 多地图支持

v1.4.10.2 - 借鉴 sunflower-land 的场景设计，实现恋爱模拟多地图系统。
6 个独立地图：home, school, cafe, park, rooftop, beach
每个地图有独立的网格大小、背景色、NPC 位置和活动列表。
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from config import get_default_tz

logger = logging.getLogger(__name__)

# ============================================================
# 地图定义
# ============================================================

MAPS = {
    'home': {
        'name': '家',
        'description': '温馨的小窝，可以休息恢复精力',
        'emoji': '\U0001f3e0',
        'unlocked_by_default': True,
        'unlock_condition': None,
        'unlock_condition_desc': None,
        'grid_size': 20,
        'bg_color': '#FFF8E7',
        'spawn_point': {'x': 10, 'y': 10},
        'npc_locations': {},
        'activities': ['rest', 'diary', 'cook'],
        'buildings': {
            'bed': {'x': 8, 'y': 8, 'type': 'bed'},
            'desk': {'x': 12, 'y': 8, 'type': 'desk'},
            'kitchen': {'x': 14, 'y': 12, 'type': 'kitchen'},
        },
        'decorations': {
            'plant1': {'x': 6, 'y': 6, 'type': 'flower_red'},
            'bookshelf': {'x': 15, 'y': 7, 'type': 'bookshelf'},
        },
    },
    'school': {
        'name': '学校',
        'description': '充满青春回忆的地方，教学楼区域',
        'emoji': '\U0001f3eb',
        'unlocked_by_default': True,
        'unlock_condition': None,
        'unlock_condition_desc': None,
        'grid_size': 30,
        'bg_color': '#F0F4FF',
        'spawn_point': {'x': 15, 'y': 15},
        'npc_locations': {},
        'activities': ['study', 'encounter', 'club'],
        'buildings': {
            'classroom': {'x': 10, 'y': 5, 'type': 'classroom'},
            'library': {'x': 20, 'y': 5, 'type': 'library'},
            'cafeteria': {'x': 5, 'y': 20, 'type': 'cafeteria'},
        },
        'decorations': {
            'tree1': {'x': 2, 'y': 2, 'type': 'tree'},
            'tree2': {'x': 27, 'y': 2, 'type': 'tree'},
            'bench1': {'x': 15, 'y': 25, 'type': 'bench'},
            'fountain': {'x': 15, 'y': 10, 'type': 'fountain'},
        },
    },
    'cafe': {
        'name': '咖啡厅',
        'description': '休闲社交场所，适合约会和对话',
        'emoji': '\u2615',
        'unlocked_by_default': True,
        'unlock_condition': None,
        'unlock_condition_desc': None,
        'grid_size': 20,
        'bg_color': '#F5E6D3',
        'spawn_point': {'x': 10, 'y': 10},
        'npc_locations': {},
        'activities': ['date', 'dialogue', 'part_time'],
        'buildings': {
            'counter': {'x': 10, 'y': 3, 'type': 'counter'},
            'table1': {'x': 5, 'y': 8, 'type': 'table'},
            'table2': {'x': 14, 'y': 8, 'type': 'table'},
            'sofa': {'x': 10, 'y': 15, 'type': 'sofa'},
        },
        'decorations': {
            'flower1': {'x': 3, 'y': 3, 'type': 'flower_yellow'},
            'flower2': {'x': 16, 'y': 3, 'type': 'flower_red'},
            'plant': {'x': 17, 'y': 15, 'type': 'plant'},
        },
    },
    'park': {
        'name': '公园',
        'description': '户外休闲区域，可以散步和参加季节活动',
        'emoji': '\U0001f333',
        'unlocked_by_default': False,
        'unlock_condition': 'affection_20',
        'unlock_condition_desc': '好感度 >= 20',
        'grid_size': 30,
        'bg_color': '#E8F5E9',
        'spawn_point': {'x': 15, 'y': 15},
        'npc_locations': {},
        'activities': ['walk', 'seasonal_event', 'picnic'],
        'buildings': {
            'pavilion': {'x': 15, 'y': 5, 'type': 'pavilion'},
            'pond': {'x': 22, 'y': 20, 'type': 'pond'},
        },
        'decorations': {
            'tree1': {'x': 3, 'y': 3, 'type': 'tree'},
            'tree2': {'x': 8, 'y': 10, 'type': 'tree'},
            'tree3': {'x': 25, 'y': 8, 'type': 'tree'},
            'tree4': {'x': 5, 'y': 22, 'type': 'tree'},
            'tree5': {'x': 20, 'y': 25, 'type': 'tree'},
            'flower1': {'x': 10, 'y': 15, 'type': 'flower_red'},
            'flower2': {'x': 12, 'y': 16, 'type': 'flower_yellow'},
            'bench1': {'x': 15, 'y': 12, 'type': 'bench'},
            'bench2': {'x': 8, 'y': 18, 'type': 'bench'},
            'rock1': {'x': 26, 'y': 15, 'type': 'rock'},
        },
    },
    'rooftop': {
        'name': '天台',
        'description': '秘密场所，可以触发特殊对话和星空事件',
        'emoji': '\U0001f305',
        'unlocked_by_default': False,
        'unlock_condition': 'affection_50',
        'unlock_condition_desc': '好感度 >= 50',
        'grid_size': 20,
        'bg_color': '#1A1A2E',
        'spawn_point': {'x': 10, 'y': 15},
        'npc_locations': {},
        'activities': ['special_dialogue', 'stargazing', 'secret'],
        'buildings': {
            'fence': {'x': 10, 'y': 3, 'type': 'fence'},
            'water_tank': {'x': 3, 'y': 5, 'type': 'water_tank'},
        },
        'decorations': {
            'chair1': {'x': 8, 'y': 10, 'type': 'chair'},
            'chair2': {'x': 12, 'y': 10, 'type': 'chair'},
        },
    },
    'beach': {
        'name': '海边',
        'description': '度假地点，约会专属场景',
        'emoji': '\U0001f3d6',
        'unlocked_by_default': False,
        'unlock_condition': 'affection_80',
        'unlock_condition_desc': '好感度 >= 80',
        'grid_size': 30,
        'bg_color': '#87CEEB',
        'spawn_point': {'x': 15, 'y': 20},
        'npc_locations': {},
        'activities': ['date', 'swim', 'fireworks'],
        'buildings': {
            'umbrella1': {'x': 8, 'y': 18, 'type': 'umbrella'},
            'umbrella2': {'x': 20, 'y': 18, 'type': 'umbrella'},
            'shack': {'x': 25, 'y': 5, 'type': 'shack'},
        },
        'decorations': {
            'shell1': {'x': 5, 'y': 22, 'type': 'shell'},
            'shell2': {'x': 18, 'y': 25, 'type': 'shell'},
            'rock1': {'x': 3, 'y': 15, 'type': 'rock'},
            'rock2': {'x': 27, 'y': 12, 'type': 'rock'},
        },
    },
}

# 默认解锁的地图
DEFAULT_UNLOCKED_MAPS = ['home', 'school', 'cafe']

# 解锁条件检查阈值
UNLOCK_THRESHOLDS = {
    'affection_20': 20,
    'affection_50': 50,
    'affection_80': 80,
}


class MapMixin:
    """地图系统相关方法"""

    def _ensure_player_maps(self, conn, user_id: int):
        """确保 player_maps 记录存在"""
        conn.execute("""
            INSERT OR IGNORE INTO player_maps (user_id, current_map, unlocked_maps, map_discoveries)
            VALUES (?, 'home', ?, '{}')
        """, (user_id, json.dumps(DEFAULT_UNLOCKED_MAPS)))

    def get_current_map(self, user_id: int) -> str:
        """获取玩家当前所在地图

        Args:
            user_id: 用户ID

        Returns:
            当前地图 ID（如 'home', 'school' 等）
        """
        with self.get_connection() as conn:
            self._ensure_player_maps(conn, user_id)
            cursor = conn.execute(
                "SELECT current_map FROM player_maps WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            return row['current_map'] if row else 'home'

    def switch_map(self, user_id: int, map_id: str) -> Dict:
        """切换地图（带解锁检查）

        Args:
            user_id: 用户ID
            map_id: 目标地图 ID

        Returns:
            切换结果字典，包含 success, previous_map, current_map, map_info 等
        """
        # 验证地图 ID
        if map_id not in MAPS:
            return {
                'success': False,
                'error': f'无效的地图: {map_id}',
            }

        # 检查解锁状态
        unlocked = self.get_unlocked_maps(user_id)
        if map_id not in unlocked:
            map_def = MAPS[map_id]
            return {
                'success': False,
                'error': f'地图「{map_def["name"]}」尚未解锁',
                'unlock_condition': map_def.get('unlock_condition_desc'),
            }

        # 获取当前地图
        previous_map = self.get_current_map(user_id)
        if previous_map == map_id:
            return {
                'success': True,
                'previous_map': previous_map,
                'current_map': map_id,
                'message': f'已经在「{MAPS[map_id]["name"]}」了',
            }

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()

            # 更新当前地图
            conn.execute(
                "UPDATE player_maps SET current_map = ?, last_visit = ? WHERE user_id = ?",
                (map_id, now, user_id)
            )

            # 重置玩家位置到新地图的出生点
            spawn = MAPS[map_id].get('spawn_point', {'x': 0, 'y': 0})
            conn.execute("""
                INSERT INTO player_positions (user_id, x, y, direction, updated_at)
                VALUES (?, ?, ?, 'down', ?)
                ON CONFLICT(user_id) DO UPDATE SET x=?, y=?, direction='down', updated_at=?
            """, (user_id, spawn['x'], spawn['y'], now, spawn['x'], spawn['y'], now))

            # 记录地图切换事件
            conn.execute("""
                INSERT INTO game_events (user_id, event_type, event_data, source, created_at)
                VALUES (?, 'map_switch', ?, 'web', ?)
            """, (user_id, json.dumps({
                'from': previous_map,
                'to': map_id,
            }), now))

        logger.info(f"[Map] 玩家 {user_id} 从 {previous_map} 切换到 {map_id}")

        return {
            'success': True,
            'previous_map': previous_map,
            'current_map': map_id,
            'map_info': self._get_map_info(map_id),
            'spawn_point': MAPS[map_id].get('spawn_point', {'x': 0, 'y': 0}),
            'message': f'已移动到「{MAPS[map_id]["name"]}」',
        }

    def get_map_state(self, user_id: int) -> Dict:
        """获取地图完整状态（当前地图、已解锁地图、地图属性）

        Args:
            user_id: 用户ID

        Returns:
            地图状态字典
        """
        current_map = self.get_current_map(user_id)
        unlocked = self.get_unlocked_maps(user_id)

        # 构建地图列表（包含解锁状态）
        maps_list = []
        for map_id, map_def in MAPS.items():
            is_unlocked = map_id in unlocked
            maps_list.append({
                'id': map_id,
                'name': map_def['name'],
                'description': map_def['description'],
                'emoji': map_def['emoji'],
                'unlocked': is_unlocked,
                'unlock_condition': map_def.get('unlock_condition_desc') if not is_unlocked else None,
                'grid_size': map_def['grid_size'],
                'bg_color': map_def['bg_color'],
                'activities': map_def['activities'],
                'is_current': map_id == current_map,
            })

        # 获取当前地图的详细信息
        current_map_info = self._get_map_info(current_map)

        return {
            'current_map': current_map,
            'current_map_info': current_map_info,
            'maps': maps_list,
            'unlocked_count': len(unlocked),
            'total_maps': len(MAPS),
        }

    def get_unlocked_maps(self, user_id: int) -> List[str]:
        """获取已解锁地图列表

        Args:
            user_id: 用户ID

        Returns:
            已解锁地图 ID 列表
        """
        with self.get_connection() as conn:
            self._ensure_player_maps(conn, user_id)
            cursor = conn.execute(
                "SELECT unlocked_maps FROM player_maps WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row['unlocked_maps'])
                except (json.JSONDecodeError, TypeError):
                    return DEFAULT_UNLOCKED_MAPS.copy()
            return DEFAULT_UNLOCKED_MAPS.copy()

    def unlock_map(self, user_id: int, map_id: str) -> Dict:
        """解锁地图

        Args:
            user_id: 用户ID
            map_id: 要解锁的地图 ID

        Returns:
            解锁结果字典
        """
        if map_id not in MAPS:
            return {'success': False, 'error': f'无效的地图: {map_id}'}

        unlocked = self.get_unlocked_maps(user_id)
        if map_id in unlocked:
            return {'success': True, 'message': f'「{MAPS[map_id]["name"]}」已经解锁了'}

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            unlocked.append(map_id)

            conn.execute(
                "UPDATE player_maps SET unlocked_maps = ? WHERE user_id = ?",
                (json.dumps(unlocked), user_id)
            )

            # 记录解锁事件
            conn.execute("""
                INSERT INTO game_events (user_id, event_type, event_data, source, created_at)
                VALUES (?, 'map_unlock', ?, 'system', ?)
            """, (user_id, json.dumps({'map_id': map_id}), now))

        logger.info(f"[Map] 玩家 {user_id} 解锁了地图 {map_id}")

        return {
            'success': True,
            'map_id': map_id,
            'map_name': MAPS[map_id]['name'],
            'message': f'新地图「{MAPS[map_id]["name"]}」已解锁！',
        }

    def check_and_unlock_maps(self, user_id: int, affection: int) -> List[Dict]:
        """根据好感度检查并解锁新地图

        Args:
            user_id: 用户ID
            affection: 当前好感度

        Returns:
            新解锁的地图列表
        """
        newly_unlocked = []
        unlocked = self.get_unlocked_maps(user_id)

        for map_id, map_def in MAPS.items():
            if map_id in unlocked:
                continue

            condition = map_def.get('unlock_condition')
            if not condition:
                continue

            threshold = UNLOCK_THRESHOLDS.get(condition)
            if threshold and affection >= threshold:
                result = self.unlock_map(user_id, map_id)
                if result['success'] and map_id not in [u['map_id'] for u in newly_unlocked]:
                    newly_unlocked.append(result)

        return newly_unlocked

    def discover_map_content(self, user_id: int, discovery_key: str, discovery_data: Dict = None) -> Dict:
        """发现地图上的新内容

        Args:
            user_id: 用户ID
            discovery_key: 发现内容的唯一键
            discovery_data: 发现内容的额外数据

        Returns:
            发现结果字典
        """
        with self.get_connection() as conn:
            self._ensure_player_maps(conn, user_id)

            cursor = conn.execute(
                "SELECT map_discoveries FROM player_maps WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            try:
                discoveries = json.loads(row['map_discoveries']) if row else {}
            except (json.JSONDecodeError, TypeError):
                discoveries = {}

            if discovery_key in discoveries:
                return {
                    'success': True,
                    'new': False,
                    'message': '已经发现过了',
                }

            # 记录新发现
            now = datetime.now(get_default_tz()).isoformat()
            discoveries[discovery_key] = {
                'discovered_at': now,
                'data': discovery_data or {},
            }

            conn.execute(
                "UPDATE player_maps SET map_discoveries = ? WHERE user_id = ?",
                (json.dumps(discoveries, ensure_ascii=False), user_id)
            )

        return {
            'success': True,
            'new': True,
            'discovery_key': discovery_key,
            'message': f'发现了新内容！',
        }

    def get_map_discoveries(self, user_id: int) -> Dict:
        """获取玩家在所有地图上的发现

        Args:
            user_id: 用户ID

        Returns:
            发现内容字典
        """
        with self.get_connection() as conn:
            self._ensure_player_maps(conn, user_id)
            cursor = conn.execute(
                "SELECT map_discoveries FROM player_maps WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            try:
                return json.loads(row['map_discoveries']) if row else {}
            except (json.JSONDecodeError, TypeError):
                return {}

    def _get_map_info(self, map_id: str) -> Dict:
        """获取地图的详细信息（不含解锁状态）

        Args:
            map_id: 地图 ID

        Returns:
            地图信息字典
        """
        map_def = MAPS.get(map_id)
        if not map_def:
            return {}

        return {
            'id': map_id,
            'name': map_def['name'],
            'description': map_def['description'],
            'emoji': map_def['emoji'],
            'grid_size': map_def['grid_size'],
            'bg_color': map_def['bg_color'],
            'spawn_point': map_def.get('spawn_point', {'x': 0, 'y': 0}),
            'activities': map_def['activities'],
            'buildings': map_def.get('buildings', {}),
            'decorations': map_def.get('decorations', {}),
            'npc_locations': map_def.get('npc_locations', {}),
        }
