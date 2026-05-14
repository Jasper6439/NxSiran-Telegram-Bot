"""聊天记录 + 记忆系统 Mixin"""

from datetime import datetime
from typing import Optional, Dict, List

from system.config import get_default_tz


class ChatMixin:
    """聊天记录、记忆系统相关方法"""

    # ============================================================
    # 聊天记录管理
    # ============================================================

    def save_message(self, user_id: int, character_id: str, role: str, content: str, emotion: str = None) -> int:
        """保存聊天消息"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            cursor = conn.execute(
                """INSERT INTO chat_messages (user_id, character_id, role, content, emotion, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, character_id, role, content, emotion, now)
            )
            return cursor.lastrowid

    def get_chat_history(self, user_id: int, character_id: str = 'chayewoon', limit: int = 100) -> List[Dict]:
        """获取聊天历史"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT role, content, emotion, created_at FROM chat_messages
                   WHERE user_id = ? AND character_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, character_id, limit)
            )
            rows = cursor.fetchall()
            # 反转顺序（从旧到新）
            return [dict(row) for row in reversed(rows)]

    def clear_chat_history(self, user_id: int, character_id: str = 'chayewoon'):
        """清空聊天历史"""
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM chat_messages WHERE user_id = ? AND character_id = ?",
                (user_id, character_id)
            )

    # ============================================================
    # 记忆系统
    # ============================================================

    def save_memory(self, user_id: int, character_id: str, key: str, value: str, category: str = 'personal'):
        """保存记忆"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO memories (user_id, character_id, memory_key, memory_value, category, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, character_id, memory_key)
                   DO UPDATE SET memory_value = ?, last_referenced = ?""",
                (user_id, character_id, key, value, category, now, value, now)
            )

    def get_memories(self, user_id: int, character_id: str = 'chayewoon', category: str = None) -> List[Dict]:
        """获取记忆"""
        with self.get_connection() as conn:
            if category:
                cursor = conn.execute(
                    """SELECT * FROM memories
                       WHERE user_id = ? AND character_id = ? AND category = ?
                       ORDER BY importance DESC, last_referenced DESC""",
                    (user_id, character_id, category)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM memories
                       WHERE user_id = ? AND character_id = ?
                       ORDER BY importance DESC, last_referenced DESC""",
                    (user_id, character_id)
                )
            return [dict(row) for row in cursor.fetchall()]

    def delete_memory(self, user_id: int, character_id: str, key: str):
        """删除记忆"""
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM memories WHERE user_id = ? AND character_id = ? AND memory_key = ?",
                (user_id, character_id, key)
            )
