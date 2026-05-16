"""双域世界系统 + 觉醒料理 Mixin (v1.8 阶段八)"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from system.config import get_default_tz

logger = logging.getLogger(__name__)


class WorldMixin:
    """双域世界系统：剧本区/空白区切换、觉醒度管理、觉醒料理"""

    # ============================================================
    # 世界状态管理
    # ============================================================

    def get_world_state(self, user_id: int, character_id: str = 'chayewoon') -> Dict:
        """获取当前世界状态

        Returns:
            包含 current_world_state, awakening_level 的字典
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT current_world_layer, awakening FROM relationships
                   WHERE user_id = ? AND character_id = ?""",
                (user_id, character_id)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'current_world_state': row['current_world_layer'] or 'SCRIPTED',
                    'awakening_level': row['awakening'] or 0,
                }
            return {
                'current_world_state': 'SCRIPTED',
                'awakening_level': 0,
            }

    def shift_world(self, user_id: int, target_state: str,
                    character_id: str = 'chayewoon') -> Dict:
        """切换世界状态（剧本区 <-> 空白区）

        Args:
            user_id: 用户ID
            target_state: 目标状态 'SCRIPTED' 或 'VOID'
            character_id: 角色ID

        Returns:
            切换结果字典
        """
        valid_states = ('SCRIPTED', 'VOID')
        if target_state not in valid_states:
            return {'success': False, 'error': f'无效的世界状态: {target_state}'}

        current = self.get_world_state(user_id, character_id)
        if current['current_world_state'] == target_state:
            return {'success': False, 'error': '已经在该世界中'}

        now = datetime.now(get_default_tz()).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """UPDATE relationships
                   SET current_world_layer = ?, updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (target_state, now, user_id, character_id)
            )

            # 记录切换历史
            conn.execute(
                """INSERT INTO world_shift_history (user_id, from_state, to_state, shifted_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, current['current_world_state'], target_state, now)
            )

        logger.info(f"[World] 用户 {user_id} 切换世界: {current['current_world_state']} -> {target_state}")
        return {
            'success': True,
            'previous_state': current['current_world_state'],
            'current_state': target_state,
        }

    # ============================================================
    # 觉醒度管理
    # ============================================================

    def get_awakening_level(self, user_id: int,
                            character_id: str = 'chayewoon') -> int:
        """获取觉醒度"""
        state = self.get_world_state(user_id, character_id)
        return state['awakening_level']

    def boost_awakening(self, user_id: int, amount: int,
                        character_id: str = 'chayewoon') -> Dict:
        """增加觉醒度

        Args:
            user_id: 用户ID
            amount: 增加量
            character_id: 角色ID

        Returns:
            更新后的觉醒度信息
        """
        self.update_emotion_values(
            user_id, character_id, awakening_delta=amount
        )
        new_level = self.get_awakening_level(user_id, character_id)
        logger.info(f"[World] 觉醒度提升: user={user_id}, +{amount}, 当前={new_level}")
        return {
            'previous_level': new_level - amount,
            'current_level': new_level,
            'boost': amount,
        }

    # ============================================================
    # 双域种植
    # ============================================================

    def plant_crop_in_world(self, farm_id: int, x: int, y: int,
                            crop_type: str, world_state: str = 'SCRIPTED') -> bool:
        """在世界中种植作物

        Args:
            farm_id: 农场ID
            x, y: 格子坐标
            crop_type: 作物类型
            world_state: 当前世界状态

        Returns:
            是否种植成功
        """
        source_type = 'VOID' if world_state == 'VOID' else 'NORMAL'

        # 确定作物颜色（空白区作物有真实色彩）
        color_hex = None
        if source_type == 'VOID':
            void_colors = {
                'void_pumpkin': '#FF8C42',
                'void_strawberry': '#FF69B4',
                'void_tomato': '#E74C3C',
                'void_corn': '#F4D03F',
                'void_rose': '#E91E63',
                'void_starfruit': '#9B59B6',
            }
            color_hex = void_colors.get(crop_type)

        with self.get_connection() as conn:
            now = datetime.now(get_default_tz()).isoformat()
            try:
                conn.execute(
                    """INSERT INTO crops (farm_id, tile_x, tile_y, crop_type,
                       planted_at, growth_stage, source_type, color_hex)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
                    (farm_id, x, y, crop_type, now, source_type, color_hex)
                )
                return True
            except Exception as e:
                logger.warning(f"[World] 种植失败: {e}")
                return False

    def get_void_crop_types(self) -> List[Dict]:
        """获取空白区专属作物类型"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM crop_types WHERE id LIKE 'void_%'"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_normal_crop_types(self) -> List[Dict]:
        """获取剧本区作物类型"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM crop_types WHERE id NOT LIKE 'void_%'"""
            )
            return [dict(row) for row in cursor.fetchall()]

    # ============================================================
    # 觉醒料理
    # ============================================================

    def get_awakening_recipes(self) -> List[Dict]:
        """获取所有觉醒料理配方"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM recipe_types WHERE effect_type = 'AWAKEN'"""
            )
            return [dict(row) for row in cursor.fetchall()]

    def cook_awakening_dish(self, user_id: int,
                            recipe_id: str) -> Optional[Dict]:
        """烹饪觉醒料理

        Returns:
            料理信息（含 awakening_boost），失败返回 None
        """
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            return None

        can, msg = self.can_cook(user_id, recipe_id)
        if not can:
            return None

        # 执行烹饪
        result = self.cook(user_id, recipe_id)
        if result:
            result['awakening_boost'] = recipe.get('awakening_boost', 0)
            result['effect_type'] = recipe.get('effect_type', 'STABILIZE')
        return result

    def feed_character(self, user_id: int, recipe_id: str,
                       character_id: str = 'chayewoon') -> Dict:
        """投喂料理给角色

        Returns:
            投喂结果，包含觉醒度变化和 AI 情感反馈类型
        """
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            return {'success': False, 'error': '未知料理'}

        # 检查背包是否有该料理
        item = self.get_inventory_item(user_id, 'recipe', recipe_id)
        if not item or item['quantity'] < 1:
            return {'success': False, 'error': '背包中没有该料理'}

        # 扣除料理
        self.remove_item(user_id, 'recipe', recipe_id, 1)

        effect_type = recipe.get('effect_type', 'STABILIZE')
        awakening_boost = recipe.get('awakening_boost', 0)

        # 应用效果
        emotion_result = None
        if effect_type == 'AWAKEN' and awakening_boost > 0:
            emotion_result = self.boost_awakening(
                user_id, awakening_boost, character_id
            )

        # 解析额外效果
        effect = {}
        try:
            effect = json.loads(recipe.get('effect', '{}'))
        except Exception:
            pass

        # 心级变化
        hearts_change = effect.get('hearts', 0)
        if hearts_change:
            new_hearts = self.update_hearts(user_id, character_id, hearts_change)
        else:
            new_hearts = None

        # 确定情感反馈类型
        awakening_level = self.get_awakening_level(user_id, character_id)
        if effect_type == 'AWAKEN':
            if awakening_level > 50:
                feedback_type = 'deep_awakening'
            elif awakening_level > 25:
                feedback_type = 'awakening'
            else:
                feedback_type = 'curious'
        else:
            feedback_type = 'stabilize'

        return {
            'success': True,
            'recipe_name': recipe['name'],
            'recipe_emoji': recipe.get('emoji', '🍲'),
            'effect_type': effect_type,
            'awakening_boost': awakening_boost,
            'new_awakening_level': awakening_level,
            'hearts_change': hearts_change,
            'new_hearts': new_hearts,
            'feedback_type': feedback_type,
        }

    # ============================================================
    # 世界切换历史
    # ============================================================

    def get_world_shift_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """获取世界切换历史"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM world_shift_history
                   WHERE user_id = ? ORDER BY id DESC LIMIT ?""",
                (user_id, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
