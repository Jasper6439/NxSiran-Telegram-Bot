"""背包系统 Mixin"""

from datetime import datetime
from typing import Optional, Dict, List

from system.config import get_default_tz


class InventoryMixin:
    """背包系统相关方法"""

    def add_item(self, user_id: int, item_type: str, item_id: str, quantity: int = 1, quality: int = 1):
        """添加物品到背包"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO inventory (user_id, item_type, item_id, quantity, quality, obtained_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(user_id, item_type, item_id)
                   DO UPDATE SET quantity = quantity + ?""",
                (user_id, item_type, item_id, quantity, quality, now, quantity)
            )

    def remove_item(self, user_id: int, item_type: str, item_id: str, quantity: int = 1) -> bool:
        """从背包移除物品，返回是否成功"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT quantity FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ?",
                (user_id, item_type, item_id)
            )
            row = cursor.fetchone()
            if not row or row['quantity'] < quantity:
                return False

            new_qty = row['quantity'] - quantity
            if new_qty <= 0:
                conn.execute(
                    "DELETE FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ?",
                    (user_id, item_type, item_id)
                )
            else:
                conn.execute(
                    "UPDATE inventory SET quantity = ? WHERE user_id = ? AND item_type = ? AND item_id = ?",
                    (new_qty, user_id, item_type, item_id)
                )
            return True

    def get_inventory(self, user_id: int) -> List[Dict]:
        """获取背包"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM inventory WHERE user_id = ? AND quantity > 0",
                (user_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_inventory_item(self, user_id: int, item_type: str, item_id: str) -> Optional[Dict]:
        """获取背包中特定物品"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ? AND quantity > 0",
                (user_id, item_type, item_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
