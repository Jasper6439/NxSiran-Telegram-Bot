"""心级事件 + 游戏事件日志 + 角色日程 Mixin"""

import json
from datetime import datetime
from typing import Optional, Dict, List

from system.config import get_default_tz


class EventsMixin:
    """心级事件、游戏事件日志、角色日程相关方法"""

    # ============================================================
    # 心级事件系统
    # ============================================================

    def get_available_events(self, user_id: int, character_id: str) -> List[Dict]:
        """获取可触发的事件"""
        with self.get_connection() as conn:
            # 获取当前心级
            cursor = conn.execute(
                "SELECT hearts FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )
            row = cursor.fetchone()
            current_hearts = row['hearts'] if row else 0

            # 获取已触发的事件
            cursor = conn.execute(
                "SELECT event_id FROM triggered_events WHERE user_id = ?",
                (user_id,)
            )
            triggered = {row['event_id'] for row in cursor.fetchall()}

            # 获取可触发的事件
            cursor = conn.execute(
                """SELECT * FROM heart_events
                   WHERE character_id = ? AND required_hearts <= ?""",
                (character_id, current_hearts)
            )
            events = []
            for row in cursor.fetchall():
                if row['id'] not in triggered:
                    events.append(dict(row))
            return events

    def trigger_event(self, user_id: int, event_id: str) -> Optional[Dict]:
        """触发事件，返回事件数据"""
        with self.get_connection() as conn:
            # 获取事件
            cursor = conn.execute(
                "SELECT * FROM heart_events WHERE id = ?",
                (event_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            event = dict(row)

            # 记录已触发
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                "INSERT INTO triggered_events (user_id, event_id, triggered_at) VALUES (?, ?, ?)",
                (user_id, event_id, now)
            )

            # 发放奖励
            rewards = json.loads(event.get('rewards', '{}'))
            if 'hearts' in rewards:
                self.update_hearts(user_id, event['character_id'], rewards['hearts'])

            return event

    # ============================================================
    # 游戏事件日志（跨平台同步）
    # ============================================================

    def log_game_event(self, user_id: int, event_type: str, event_data: Dict, source: str):
        """记录游戏事件"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO game_events (user_id, event_type, event_data, source, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, event_type, json.dumps(event_data), source, now)
            )

    def get_unsynced_events(self, user_id: int, since: str = None) -> List[Dict]:
        """获取未同步的事件"""
        with self.get_connection() as conn:
            if since:
                cursor = conn.execute(
                    """SELECT * FROM game_events
                       WHERE user_id = ? AND created_at > ? AND synced = 0
                       ORDER BY created_at ASC""",
                    (user_id, since)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM game_events
                       WHERE user_id = ? AND synced = 0
                       ORDER BY created_at ASC""",
                    (user_id,)
                )
            return [dict(row) for row in cursor.fetchall()]

    def mark_events_synced(self, event_ids: List[int]):
        """标记事件已同步"""
        if not event_ids:
            return
        with self.get_connection() as conn:
            conn.execute(
                f"UPDATE game_events SET synced = 1 WHERE id IN ({','.join('?' * len(event_ids))})",
                event_ids
            )

    # ============================================================
    # 角色日程系统
    # ============================================================

    def get_character_location(self, character_id: str, day_of_week: int = None, hour: int = None) -> Optional[Dict]:
        """获取角色当前位置"""
        if day_of_week is None:
            day_of_week = datetime.now(get_default_tz()).weekday()
        if hour is None:
            hour = datetime.now(get_default_tz()).hour

        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM character_schedules
                   WHERE character_id = ? AND day_of_week = ?
                   AND start_hour <= ? AND end_hour > ?""",
                (character_id, day_of_week, hour, hour)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
