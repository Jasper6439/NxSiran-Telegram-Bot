"""料理系统 + 每日奖励 Mixin"""

import json
import random
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from system.config import get_default_tz


class CookingMixin:
    """料理系统、每日奖励相关方法"""

    # ============================================================
    # 料理系统
    # ============================================================

    def get_recipes(self) -> List[Dict]:
        """获取所有料理配方"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM recipe_types")
            return [dict(row) for row in cursor.fetchall()]

    def get_recipe(self, recipe_id: str) -> Optional[Dict]:
        """获取单个料理配方"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM recipe_types WHERE id = ?", (recipe_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def can_cook(self, user_id: int, recipe_id: str) -> Tuple[bool, str]:
        """检查是否有足够材料烹饪"""
        recipe = self.get_recipe(recipe_id)
        if not recipe:
            return False, "未知配方"

        ingredients = json.loads(recipe['ingredients'])
        for ing in ingredients:
            item = self.get_inventory_item(user_id, 'crop', ing['crop'])
            if not item or item['quantity'] < ing['qty']:
                crop_info = self.get_crop_type(ing['crop'])
                name = crop_info['name'] if crop_info else ing['crop']
                return False, f"缺少 {name} x{ing['qty']}"

        return True, "可以烹饪"

    def cook(self, user_id: int, recipe_id: str) -> Optional[Dict]:
        """烹饪料理"""
        can, msg = self.can_cook(user_id, recipe_id)
        if not can:
            return None

        recipe = self.get_recipe(recipe_id)
        ingredients = json.loads(recipe['ingredients'])

        # 扣除材料
        for ing in ingredients:
            self.remove_item(user_id, 'crop', ing['crop'], ing['qty'])

        # 添加成品到背包
        self.add_item(user_id, 'recipe', recipe_id, 1)

        return recipe

    # ============================================================
    # 每日登录奖励
    # ============================================================

    def get_daily_reward(self, user_id: int) -> Optional[Dict]:
        """获取今日奖励状态"""
        today = datetime.now(get_default_tz()).strftime('%Y-%m-%d')
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM daily_rewards WHERE user_id = ? AND reward_date = ?",
                (user_id, today)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def claim_daily_reward(self, user_id: int) -> Dict:
        """领取每日登录奖励"""
        today = datetime.now(get_default_tz()).strftime('%Y-%m-%d')

        # 检查是否已领取
        existing = self.get_daily_reward(user_id)
        if existing and existing['claimed']:
            return {'success': False, 'message': '今天已经领过了'}

        # 随机奖励
        rewards_pool = [
            {'type': 'seed', 'id': 'tomato', 'qty': 3, 'emoji': '🍅'},
            {'type': 'seed', 'id': 'corn', 'qty': 2, 'emoji': '🌽'},
            {'type': 'seed', 'id': 'strawberry', 'qty': 1, 'emoji': '🍓'},
            {'type': 'money', 'id': 'gold', 'qty': random.randint(50, 200), 'emoji': '💰'},
        ]

        reward = random.choice(rewards_pool)

        # 发放奖励
        if reward['type'] == 'seed':
            self.add_item(user_id, 'seed', reward['id'], reward['qty'])
        elif reward['type'] == 'money':
            farm = self.get_farm(user_id)
            if farm:
                self.update_farm(user_id, money=farm['money'] + reward['qty'])

        # 记录
        with self.get_connection() as conn:
            if existing:
                conn.execute(
                    "UPDATE daily_rewards SET claimed = 1 WHERE user_id = ? AND reward_date = ?",
                    (user_id, today)
                )
            else:
                conn.execute(
                    "INSERT INTO daily_rewards (user_id, reward_date, reward_type, reward_id, reward_qty, claimed) VALUES (?, ?, ?, ?, ?, 1)",
                    (user_id, today, reward['type'], reward['id'], reward['qty'])
                )

        return {
            'success': True,
            'reward': reward,
            'message': f"今日签到：{reward['emoji']} x{reward['qty']}"
        }
