# 恋爱至上主义区域 (Love Supremacy Zone)
"""
NxSiRan Game Database Module
SQLite 数据库操作模块 - 支持农场经营 + 角色互动游戏
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'game.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'game_schema.sql')

# 韩国时区
KR_TZ = timezone(timedelta(hours=9))


class GameDatabase:
    """游戏数据库管理类"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db_dir()
        self._init_db()
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
    
    def _init_db(self):
        """初始化数据库（创建表和初始数据）"""
        if not os.path.exists(self.db_path):
            logger.info(f"[DB] 创建新数据库: {self.db_path}")
        
        with self.get_connection() as conn:
            # 读取并执行 schema
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                logger.info("[DB] Schema 初始化完成")
            else:
                logger.warning(f"[DB] Schema 文件不存在: {SCHEMA_PATH}")
            
            # [v0.3] 自动迁移：为旧数据库添加缺失的列
            self._migrate_db(conn)
    
    def _migrate_db(self, conn):
        """数据库自动迁移 - 添加缺失的列"""
        migrations = {
            'relationships': [
                ('affection', 'INTEGER DEFAULT 0'),
                ('happiness', 'INTEGER DEFAULT 50'),
                ('awakening', 'INTEGER DEFAULT 0'),
                ('current_world_layer', 'TEXT DEFAULT \'stage\''),
            ],
            'characters': [
                ('world_layer', 'TEXT DEFAULT \'stage\''),
                ('is_novel_character', 'INTEGER DEFAULT 1'),
                ('default_affection', 'INTEGER DEFAULT 0'),
                ('default_happiness', 'INTEGER DEFAULT 50'),
                ('default_awakening', 'INTEGER DEFAULT 0'),
                ('world_role', 'TEXT DEFAULT \'\''),
            ],
        }
        
        for table, columns in migrations.items():
            # 获取表已有的列名
            try:
                cursor = conn.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in cursor.fetchall()}
            except Exception:
                continue
            
            for col_name, col_def in columns:
                if col_name not in existing_cols:
                    try:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                        logger.info(f"[DB] 迁移: {table} 添加列 {col_name}")
                    except Exception as e:
                        logger.warning(f"[DB] 迁移失败 {table}.{col_name}: {e}")
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 返回字典格式
        conn.execute("PRAGMA foreign_keys = ON")  # 启用外键约束
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[DB] 数据库错误: {e}")
            raise
        finally:
            conn.close()
    
    # ============================================================
    # 用户管理
    # ============================================================
    
    def get_or_create_user(self, telegram_id: int, username: str = None, password_hash: str = None, is_admin: bool = False) -> int:
        """获取或创建用户，返回 user_id"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM users WHERE telegram_id = ?", 
                (telegram_id,)
            )
            row = cursor.fetchone()
            
            if row:
                # 更新最后活跃时间
                conn.execute(
                    "UPDATE users SET last_active = ?, username = ? WHERE id = ?",
                    (datetime.now(KR_TZ).isoformat(), username, row['id'])
                )
                return row['id']
            
            # 创建新用户
            now = datetime.now(KR_TZ).isoformat()
            cursor = conn.execute(
                """INSERT INTO users (telegram_id, username, password_hash, is_admin, created_at, last_active)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (telegram_id, username, password_hash, 1 if is_admin else 0, now, now)
            )
            user_id = cursor.lastrowid
            
            # 同时创建农场
            conn.execute(
                """INSERT INTO farms (user_id, created_at) VALUES (?, ?)""",
                (user_id, now)
            )
            
            # 创建与车如云的关系（初始化情感值）
            conn.execute(
                """INSERT INTO relationships (user_id, character_id, created_at, 
                                              affection, happiness, awakening, world_layer) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, 'chayewoon', now, 0, 50, 0, 'normal')
            )
            
            logger.info(f"[DB] 创建新用户: telegram_id={telegram_id}, user_id={user_id}")
            return user_id
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """通过 Telegram ID 获取用户"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
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
    
    def get_inventory_item(self, user_id: int, item_type: str, item_id: str) -> Optional[Dict]:
        """获取背包中特定物品"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM inventory WHERE user_id = ? AND item_type = ? AND item_id = ? AND quantity > 0",
                (user_id, item_type, item_id)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ============================================================
    # 每日登录奖励
    # ============================================================
    
    def get_daily_reward(self, user_id: int) -> Optional[Dict]:
        """获取今日奖励状态"""
        today = datetime.now(KR_TZ).strftime('%Y-%m-%d')
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM daily_rewards WHERE user_id = ? AND reward_date = ?",
                (user_id, today)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def claim_daily_reward(self, user_id: int) -> Dict:
        """领取每日登录奖励"""
        today = datetime.now(KR_TZ).strftime('%Y-%m-%d')
        
        # 检查是否已领取
        existing = self.get_daily_reward(user_id)
        if existing and existing['claimed']:
            return {'success': False, 'message': '今天已经领过了'}
        
        # 随机奖励
        import random
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
        now = datetime.now(KR_TZ).isoformat()
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
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取用户"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    # ============================================================
    # 聊天记录管理
    # ============================================================
    
    def save_message(self, user_id: int, character_id: str, role: str, content: str, emotion: str = None) -> int:
        """保存聊天消息"""
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
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
            now = datetime.now(KR_TZ).isoformat()
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
            now = datetime.now(KR_TZ).isoformat()
            conn.execute(
                """UPDATE relationships SET relationship_status = ?, updated_at = ?
                   WHERE user_id = ? AND character_id = ?""",
                (status, now, user_id, character_id)
            )
    
    def record_conversation(self, user_id: int, character_id: str):
        """记录一次对话"""
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
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
    # 农场系统
    # ============================================================
    
    def get_farm(self, user_id: int) -> Optional[Dict]:
        """获取农场数据"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM farms WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_farm(self, user_id: int, **kwargs):
        """更新农场数据"""
        if not kwargs:
            return
        
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
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
            now = datetime.now(KR_TZ).isoformat()
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
            
            now = datetime.now(KR_TZ)
            
            # 获取所有作物
            cursor = conn.execute(
                "SELECT id, crop_type, planted_at, growth_stage FROM crops WHERE farm_id = ? AND is_harvestable = 0",
                (farm_id,)
            )
            crops = cursor.fetchall()
            
            for crop in crops:
                planted = datetime.fromisoformat(crop['planted_at'])
                elapsed_minutes = (now - planted).total_seconds() / 60
                growth_time = growth_times.get(crop['crop_type'], 180)
                
                # 计算生长阶段
                progress = elapsed_minutes / growth_time
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
    
    # ============================================================
    # 背包系统
    # ============================================================
    
    def add_item(self, user_id: int, item_type: str, item_id: str, quantity: int = 1, quality: int = 1):
        """添加物品到背包"""
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
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
    
    # ============================================================
    # 角色日程系统
    # ============================================================
    
    def get_character_location(self, character_id: str, day_of_week: int = None, hour: int = None) -> Optional[Dict]:
        """获取角色当前位置"""
        if day_of_week is None:
            day_of_week = datetime.now(KR_TZ).weekday()
        if hour is None:
            hour = datetime.now(KR_TZ).hour
        
        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT * FROM character_schedules 
                   WHERE character_id = ? AND day_of_week = ? 
                   AND start_hour <= ? AND end_hour > ?""",
                (character_id, day_of_week, hour, hour)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
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
            now = datetime.now(KR_TZ).isoformat()
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
            now = datetime.now(KR_TZ).isoformat()
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
    # 记忆系统
    # ============================================================
    
    def save_memory(self, user_id: int, character_id: str, key: str, value: str, category: str = 'personal'):
        """保存记忆"""
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
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
    
    # ============================================================
    # 作物类型
    # ============================================================
    
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

    # ============================================================
    # 情感值系统（恋爱至上主义区域）
    # ============================================================

    def update_emotion_values(self, user_id: int, character_id: str, 
                              affection_delta: int = 0, happiness_delta: int = 0, 
                              awakening_delta: int = 0) -> Dict:
        """更新角色的情感值（好感度/幸福度/觉醒度）
        
        Args:
            user_id: 用户ID
            character_id: 角色ID
            affection_delta: 好感度变化值
            happiness_delta: 幸福度变化值
            awakening_delta: 觉醒度变化值
            
        Returns:
            更新后的情感值字典
        """
        with self.get_connection() as conn:
            now = datetime.now(KR_TZ).isoformat()
            
            # 获取当前值
            cursor = conn.execute(
                """SELECT affection, happiness, awakening FROM relationships 
                   WHERE user_id = ? AND character_id = ?""",
                (user_id, character_id)
            )
            row = cursor.fetchone()
            
            if not row:
                return {'affection': 0, 'happiness': 50, 'awakening': 0}
            
            # 计算新值（好感度0-100，幸福度0-100，觉醒度0-100）
            new_affection = max(0, min(100, row['affection'] + affection_delta))
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
            now = datetime.now(KR_TZ).isoformat()
            
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
            now = datetime.now(KR_TZ).isoformat()
            
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
    # 玩家位置（DOM-based 游戏引擎用）
    # ============================================================

    def save_player_position(self, user_id: int, x: int, y: int, direction: str = 'down'):
        """保存玩家位置"""
        now = datetime.now(KR_TZ).isoformat()
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

    def water_crop(self, farm_id: int, x: int, y: int) -> bool:
        """浇水"""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE crops SET water_level = MIN(water_level + 1, 3) WHERE farm_id = ? AND tile_x = ? AND tile_y = ?",
                (farm_id, x, y)
            )
            return cursor.rowcount > 0

    # ============================================================
    # 觉醒事件管理 (v0.2)
    # ============================================================

    def get_awakening_events(self, character_id: str) -> List[Dict]:
        """获取角色的觉醒事件列表"""
        with self.get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS awakening_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    character_id TEXT NOT NULL,
                    stage INTEGER NOT NULL,
                    stage_name TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    dialogue_content TEXT,
                    emotion_bonus TEXT,
                    unlocked_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor = conn.execute(
                """SELECT * FROM awakening_events WHERE character_id = ? ORDER BY stage""",
                (character_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def save_awakening_event(self, character_id: str, stage: int, event_id: str,
                              title: str, description: str, dialogue: str,
                              emotion_bonus: Dict = None):
        """保存觉醒事件"""
        now = datetime.now(KR_TZ).isoformat()
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



# 全局实例
db = GameDatabase()


# ============================================================
# 便捷函数（兼容现有代码）
# ============================================================

def get_db() -> GameDatabase:
    """获取数据库实例"""
    return db


def init_game_db():
    """初始化游戏数据库"""
    global db
    db = GameDatabase()
    return db
