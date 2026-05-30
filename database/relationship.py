"""关系/亲密度 + 情感值 + 觉醒事件 Mixin"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List

from system.config import get_default_tz

logger = logging.getLogger(__name__)


class RelationshipMixin:
    """关系系统、情感值、觉醒事件相关方法"""

    # ============================================================
    # 关系系统（亲密度）
    # ============================================================

    def get_relationship(self, user_id: int, character_id: str = 'chayewoon') -> Optional[Dict]:
        """获取玩家与角色的关系"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_hearts(self, user_id: int, character_id: str, delta: int) -> int:
        """更新心级（可正可负），返回新的心级"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            # 获取当前心级
            cursor = conn.execute(
                "SELECT hearts FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )
            row = cursor.fetchone()
            current_hearts = row['hearts'] if row else 0

            # 计算新心级（0-10 范围）
            new_hearts = max(0, min(10, current_hearts + delta))

            # 更新
            conn.execute(
                """UPDATE relationships SET hearts = ?, updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (new_hearts, now, user_id, character_id)
            )

            return new_hearts

    def update_relationship_status(self, user_id: int, character_id: str, status: str):
        """更新关系状态"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """UPDATE relationships SET relationship_status = ?, updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (status, now, user_id, character_id)
            )

    def record_conversation(self, user_id: int, character_id: str):
        """记录一次对话"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """UPDATE relationships
                   SET total_conversations = total_conversations + 1,
                       talked_today = 1,
                       updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (now, user_id, character_id)
            )

    def reset_daily_flags(self):
        """重置每日标志（每天凌晨调用）"""
        with self.get_connection() as conn:
            conn.execute("UPDATE relationships SET talked_today = 0, gifted_today = 0")
            logger.info("[DB] 每日标志已重置")

    # ============================================================
    # 情感值系统（恋爱至上主义区域）
    # ============================================================

    def update_emotion_values(self, user_id: int, character_id: str,
                              affection_delta: int = 0, happiness_delta: int = 0,
                              awakening_delta: int = 0) -> Dict:
        """更新角色的情感值

        三维情感值定义：
        - affection（好感度）：角色对用户的情感，从敌意→冷淡→好感→深爱
        - happiness（幸福感）：角色自身的幸福状态，受互动质量影响
        - awakening（觉醒度）：角色突破原著限制的程度，自然的情感积累，不是刻意推进

        Args:
            affection_delta: 好感度变化值
            happiness_delta: 幸福感变化值
            awakening_delta: 觉醒度变化值

        Returns:
            更新后的情感值字典
        """
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()

            # 获取当前值
            cursor = conn.execute(
                """SELECT affection, happiness, awakening FROM relationships
                   WHERE user_id = ? AND character_id = ?""",
                (user_id, character_id)
            )
            row = cursor.fetchone()

            if not row:
                return {'affection': 0, 'happiness': 50, 'awakening': 0}

            # 计算新值（好感度-100~100，幸福度0-100，觉醒度0-100）
            new_affection = max(-100, min(100, row['affection'] + affection_delta))
            new_happiness = max(0, min(100, row['happiness'] + happiness_delta))
            new_awakening = max(0, min(100, row['awakening'] + awakening_delta))

            # 更新
            conn.execute(
                """UPDATE relationships
                   SET affection = ?, happiness = ?, awakening = ?, updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (new_affection, new_happiness, new_awakening, now, user_id, character_id)
            )

            return {
                'affection': new_affection,
                'happiness': new_happiness,
                'awakening': new_awakening
            }

    def get_emotion_values(self, user_id: int, character_id: str) -> Dict:
        """获取当前情感值

        Args:
            user_id: 用户ID
            character_id: 角色ID

        Returns:
            情感值字典，包含 affection/happiness/awakening
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT affection, happiness, awakening FROM relationships
                   WHERE user_id = ? AND character_id = ?""",
                (user_id, character_id)
            )
            row = cursor.fetchone()

            if row:
                return {
                    'affection': row['affection'],
                    'happiness': row['happiness'],
                    'awakening': row['awakening']
                }

            # 默认初始值
            return {'affection': 0, 'happiness': 50, 'awakening': 0}

    def check_awakening_conditions(self, user_id: int, character_id: str) -> Dict:
        """检查觉醒条件是否满足

        Args:
            user_id: 用户ID
            character_id: 角色ID

        Returns:
            包含条件检查结果和状态的字典
        """
        emotions = self.get_emotion_values(user_id, character_id)
        relationship = self.get_relationship(user_id, character_id)

        # 觉醒条件：好感度>=80，幸福度>=70，觉醒度>=60
        conditions = {
            'affection_met': emotions['affection'] >= 80,
            'happiness_met': emotions['happiness'] >= 70,
            'awakening_met': emotions['awakening'] >= 60,
            'hearts_met': (relationship['hearts'] if relationship else 0) >= 8
        }

        all_met = all(conditions.values())

        return {
            'can_awaken': all_met,
            'conditions': conditions,
            'current_values': emotions,
            'current_hearts': relationship['hearts'] if relationship else 0
        }

    def trigger_awakening(self, user_id: int, character_id: str, event_name: str) -> Optional[Dict]:
        """触发觉醒事件

        Args:
            user_id: 用户ID
            character_id: 角色ID
            event_name: 觉醒事件名称

        Returns:
            觉醒事件结果，失败返回None
        """
        # 检查条件
        check = self.check_awakening_conditions(user_id, character_id)
        if not check['can_awaken']:
            return None

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()

            # 记录觉醒事件
            cursor = conn.execute(
                """INSERT INTO awakening_events (user_id, character_id, event_name, triggered_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, character_id, event_name, now)
            )
            event_id = cursor.lastrowid

            # 提升觉醒度到100
            self.update_emotion_values(user_id, character_id, awakening_delta=100)

            # 更新关系状态为觉醒
            conn.execute(
                """UPDATE relationships
                   SET relationship_status = 'awakened', updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (now, user_id, character_id)
            )

            return {
                'event_id': event_id,
                'event_name': event_name,
                'character_id': character_id,
                'triggered_at': now,
                'new_status': 'awakened'
            }

    # ============================================================
    # 觉醒事件管理 (v0.2)
    # ============================================================

    def get_awakening_events(self, character_id: str) -> List[Dict]:
        """获取角色的觉醒事件列表"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM awakening_events WHERE character_id = ? ORDER BY stage""",
                (character_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_awakening_event(self, character_id: str, stage: int, event_id: str,
                              title: str, description: str, dialogue: str,
                              emotion_bonus: Dict = None):
        """保存觉醒事件"""
        now = datetime.now(get_default_tz()).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO awakening_events
                (character_id, stage, stage_name, event_id, title, description,
                 dialogue_content, emotion_bonus, unlocked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                character_id, stage,
                {1: '困局', 2: '触动', 3: '觉醒', 4: '共鸣', 5: '完成'}.get(stage, '未知'),
                event_id, title, description, dialogue,
                json.dumps(emotion_bonus) if emotion_bonus else None,
                now
            ))

    # ============================================================
    # 世界层级系统
    # ============================================================

    def get_world_layer_state(self, user_id: int) -> Dict:
        """获取当前世界层级状态

        Args:
            user_id: 用户ID

        Returns:
            世界层级状态字典
        """
        with self.get_connection() as conn:
            # 获取主要关系的世界层
            cursor = conn.execute(
                """SELECT world_layer FROM relationships WHERE user_id = ? LIMIT 1""",
                (user_id,)
            )
            row = cursor.fetchone()
            current_layer = row['world_layer'] if row else 'normal'

            # 获取各层解锁状态
            layers = {
                'normal': {'unlocked': True, 'name': '现实世界', 'description': '日常生活层'},
                'dream': {'unlocked': True, 'name': '梦境层', 'description': '潜意识世界'},
                'memory': {'unlocked': False, 'name': '记忆层', 'description': '过去的回忆'},
                'truth': {'unlocked': False, 'name': '真相层', 'description': '隐藏的真相'}
            }

            # 检查记忆层解锁条件（好感度>=50）
            cursor = conn.execute(
                """SELECT COUNT(*) as count FROM relationships
                   WHERE user_id = ? AND affection >= 50""",
                (user_id,)
            )
            if cursor.fetchone()['count'] > 0:
                layers['memory']['unlocked'] = True

            # 检查真相层解锁条件（有觉醒角色）
            cursor = conn.execute(
                """SELECT COUNT(*) as count FROM relationships
                   WHERE user_id = ? AND relationship_status = 'awakened'""",
                (user_id,)
            )
            if cursor.fetchone()['count'] > 0:
                layers['truth']['unlocked'] = True

            return {
                'current_layer': current_layer,
                'layers': layers,
                'can_switch': True
            }

    def switch_world_layer(self, user_id: int, layer: str) -> Dict:
        """切换世界层级

        Args:
            user_id: 用户ID
            layer: 目标层级（normal/dream/memory/truth）

        Returns:
            切换结果字典
        """
        valid_layers = ['normal', 'dream', 'memory', 'truth']
        if layer not in valid_layers:
            return {'success': False, 'error': f'无效的世界层级: {layer}'}

        # 检查该层是否已解锁
        state = self.get_world_layer_state(user_id)
        if not state['layers'][layer]['unlocked']:
            return {'success': False, 'error': f'世界层级 {layer} 尚未解锁'}

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()

            # 更新所有关系的世界层
            conn.execute(
                """UPDATE relationships
                   SET world_layer = ?, updated_at = ?
                   WHERE user_id = ?""",
                (layer, now, user_id)
            )

            # 记录层切换事件
            conn.execute(
                """INSERT INTO world_layer_history (user_id, from_layer, to_layer, switched_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, state['current_layer'], layer, now)
            )

            return {
                'success': True,
                'previous_layer': state['current_layer'],
                'current_layer': layer,
                'layer_name': state['layers'][layer]['name']
            }

    # ============================================================
    # 用户活跃时间持久化 (v1.7 Phase 5)
    # ============================================================

    def update_last_active_time(self, user_id: int, character_id: str = 'chayewoon') -> bool:
        """更新用户最后活跃时间到数据库。

        Args:
            user_id: 用户ID
            character_id: 角色ID

        Returns:
            是否更新成功
        """
        now = datetime.now(get_default_tz()).isoformat()
        with self.get_connection() as conn:
            # 检查关系是否存在
            cursor = conn.execute(
                "SELECT id FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )
            row = cursor.fetchone()

            if row:
                # 更新现有记录
                conn.execute(
                    """UPDATE relationships SET last_active_time = ?, updated_at = ?
                       WHERE user_id = ? AND character_id = ?""",
                    (now, now, user_id, character_id)
                )
            else:
                # 创建新记录（如果用户存在）
                conn.execute(
                    """INSERT INTO relationships (user_id, character_id, last_active_time, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, character_id, now, now, now)
                )
            return True

    def get_last_active_time(self, user_id: int, character_id: str = 'chayewoon') -> Optional[datetime]:
        """从数据库获取用户最后活跃时间。

        Args:
            user_id: 用户ID
            character_id: 角色ID

        Returns:
            最后活跃时间的 datetime 对象，不存在返回 None
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT last_active_time FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )
            row = cursor.fetchone()

            if row and row['last_active_time']:
                try:
                    return datetime.fromisoformat(row['last_active_time'])
                except (ValueError, TypeError):
                    return None
            return None
