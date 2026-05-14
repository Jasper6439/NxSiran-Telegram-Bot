"""玩家位置 Mixin"""

from datetime import datetime
from typing import Optional, Dict

from system.config import get_default_tz


class PlayerMixin:
    """玩家位置相关方法"""

    def save_player_position(self, user_id: int, x: int, y: int, direction: str = 'down'):
        """保存玩家位置"""
        now = datetime.now(get_default_tz()).isoformat()
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO player_positions (user_id, x, y, direction, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET x=?, y=?, direction=?, updated_at=?
            """, (user_id, x, y, direction, now, x, y, direction, now))

    def get_player_position(self, user_id: int) -> Optional[Dict]:
        """获取玩家位置"""
        with self.get_connection() as conn:
            # 创建表（如果不存在）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_positions (
                    user_id INTEGER PRIMARY KEY,
                    x INTEGER DEFAULT 0,
                    y INTEGER DEFAULT 0,
                    direction TEXT DEFAULT 'down',
                    updated_at TEXT
                )
            """)
            cursor = conn.execute("SELECT x, y, direction FROM player_positions WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
