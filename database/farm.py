"""农场系统 Mixin"""

import sqlite3
from datetime import datetime
from typing import Optional, Dict, List

from system.config import get_default_tz


class FarmMixin:
    """农场系统相关方法"""

    def get_farm(self, user_id: int) -> Optional[Dict]:
        """获取农场数据"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM farms WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_or_create_farm(self, user_id: int) -> Dict:
        """获取或自动创建农场，返回农场数据"""
        farm = self.get_farm(user_id)
        if farm:
            return farm

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO farms (user_id, farm_name, created_at, updated_at)
                   VALUES (?, '我的农场', ?, ?)""",
                (user_id, now, now)
            )
            # 同时创建初始关系记录
            conn.execute(
                """INSERT OR IGNORE INTO relationships (user_id, character_id, created_at, updated_at)
                   VALUES (?, 'chayewoon', ?, ?)""",
                (user_id, now, now)
            )

        return self.get_farm(user_id)

    def update_farm(self, user_id: int, **kwargs):
        """更新农场数据"""
        if not kwargs:
            return

        # Whitelist of allowed column names to prevent SQL injection
        _ALLOWED_FARM_COLUMNS = {
            "farm_name", "level", "experience", "coins",
            "last_harvest", "last_watered", "farm_data",
        }

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            invalid = set(kwargs.keys()) - _ALLOWED_FARM_COLUMNS
            if invalid:
                raise ValueError(f"Invalid column names: {invalid}")
            set_clauses = [f"{k} = ?" for k in kwargs.keys()]
            set_clauses.append("updated_at = ?")
            values = list(kwargs.values()) + [now, user_id]

            conn.execute(
                f"UPDATE farms SET {', '.join(set_clauses)} WHERE user_id = ?",
                values
            )

    def plant_crop(self, farm_id: int, x: int, y: int, crop_type: str) -> bool:
        """种植作物"""
        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            try:
                conn.execute(
                    """INSERT INTO crops (farm_id, tile_x, tile_y, crop_type, planted_at, growth_stage)
                       VALUES (?, ?, ?, ?, ?, 0)""",
                    (farm_id, x, y, crop_type, now)
                )
                return True
            except sqlite3.IntegrityError:
                # 该位置已有作物
                return False

    def harvest_crop(self, farm_id: int, x: int, y: int) -> Optional[str]:
        """收获作物，返回作物类型"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT crop_type FROM crops WHERE farm_id = ? AND tile_x = ? AND tile_y = ? AND is_harvestable = 1",
                (farm_id, x, y)
            )
            row = cursor.fetchone()
            if row:
                conn.execute(
                    "DELETE FROM crops WHERE farm_id = ? AND tile_x = ? AND tile_y = ?",
                    (farm_id, x, y)
                )
                return row['crop_type']
            return None

    def get_crops(self, farm_id: int) -> List[Dict]:
        """获取所有作物"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM crops WHERE farm_id = ?",
                (farm_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def update_crop_growth(self, farm_id: int):
        """更新作物生长状态（定时调用）"""
        with self.get_connection() as conn:
            # 获取作物类型定义
            cursor = conn.execute("SELECT id, growth_time FROM crop_types")
            growth_times = {row['id']: row['growth_time'] for row in cursor.fetchall()}

            now = datetime.now(get_default_tz())

            # 获取所有作物
            cursor = conn.execute(
                "SELECT id, crop_type, planted_at, growth_stage, water_level FROM crops WHERE farm_id = ? AND is_harvestable = 0",
                (farm_id,)
            )
            crops = cursor.fetchall()

            for crop in crops:
                planted = datetime.fromisoformat(crop['planted_at'])
                elapsed_minutes = (now - planted).total_seconds() / 60
                growth_time = growth_times.get(crop['crop_type'], 180)

                # 浇水等级减少生长时间（每级=15%减少，最多3级=45%）
                water_bonus = 1.0 - (min(crop.get('water_level', 0) or 0, 3) * 0.15)
                effective_growth_time = growth_time * water_bonus
                progress = elapsed_minutes / effective_growth_time if effective_growth_time > 0 else 1.0
                if progress >= 1.0:
                    new_stage = 3  # 成熟
                    is_harvestable = 1
                elif progress >= 0.66:
                    new_stage = 2  # 生长中
                    is_harvestable = 0
                elif progress >= 0.33:
                    new_stage = 1  # 发芽
                    is_harvestable = 0
                else:
                    new_stage = 0  # 种子
                    is_harvestable = 0

                conn.execute(
                    "UPDATE crops SET growth_stage = ?, is_harvestable = ? WHERE id = ?",
                    (new_stage, is_harvestable, crop['id'])
                )

    def water_crop(self, farm_id: int, x: int, y: int) -> bool:
        """浇水"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE crops SET water_level = MIN(water_level + 1, 3) WHERE farm_id = ? AND tile_x = ? AND tile_y = ?",
                (farm_id, x, y)
            )
            return cursor.rowcount > 0

    def get_crop_types(self) -> List[Dict]:
        """获取所有作物类型"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM crop_types")
            return [dict(row) for row in cursor.fetchall()]

    def get_crop_type(self, crop_id: str) -> Optional[Dict]:
        """获取单个作物类型"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM crop_types WHERE id = ?", (crop_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
