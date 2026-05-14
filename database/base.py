# 恋爱至上主义区域 (Love Supremacy Zone)
"""
NxSiRan Game Database Module
SQLite 数据库操作模块 - 支持农场经营 + 角色互动游戏
"""

import sqlite3
import os
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict
from contextlib import contextmanager

from system.config import get_default_tz

logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'game.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'game_schema.sql')

# 线程本地数据库实例缓存
_local = threading.local()


def _get_thread_db(db_path: str = None) -> 'GameDatabase':
    """获取线程本地的数据库实例"""
    if not hasattr(_local, 'db_instance') or _local.db_instance is None:
        _local.db_instance = GameDatabase(db_path)
    return _local.db_instance


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
            if os.path.exists(SCHEMA_PATH):
                with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
                    conn.executescript(f.read())
                logger.info("[DB] Schema 初始化完成")
            else:
                logger.warning(f"[DB] Schema 文件不存在: {SCHEMA_PATH}")

            self._migrate_db(conn)

    def _migrate_db(self, conn):
        """数据库自动迁移 - 添加缺失的列和表"""
        migrations = {
            'relationships': [
                ('affection', 'INTEGER DEFAULT 0'),
                ('happiness', 'INTEGER DEFAULT 50'),
                ('awakening', 'INTEGER DEFAULT 0'),
                ('current_world_layer', 'TEXT DEFAULT \'stage\''),
                ('world_layer', 'TEXT DEFAULT \'stage\''),
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

        # v1.4.10.2 - 多地图系统：创建 player_maps 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_maps (
                user_id INTEGER PRIMARY KEY,
                current_map TEXT DEFAULT 'home',
                unlocked_maps TEXT DEFAULT '["home","school","cafe"]',
                map_discoveries TEXT DEFAULT '{}',
                last_visit TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

    @contextmanager
    def get_connection(self):
        """获取数据库连接（上下文管理器，已优化 PRAGMA 设置）"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"[DB] 数据库错误: {e}")
            raise
        finally:
            conn.close()

    def close(self):
        """关闭可能存在的连接（清理线程本地缓存）"""
        if hasattr(_local, 'db_instance'):
            _local.db_instance = None

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
                    (datetime.now(get_default_tz()).isoformat(), username, row['id'])
                )
                user_id = row['id']
                # v1.6.4: 为新注册的角色补充关系记录
                self._ensure_relationships(conn, user_id)
                return user_id

            # 创建新用户
            now = datetime.now(get_default_tz()).isoformat()
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

            # v1.6.4: 为所有已注册角色创建关系
            self._ensure_relationships(conn, user_id)

            logger.info(f"[DB] 创建新用户: telegram_id={telegram_id}, user_id={user_id}")
            return user_id

    def _ensure_relationships(self, conn, user_id: int):
        """确保用户与所有已注册角色都有关系记录"""
        try:
            from characters import get_all_character_ids
            character_ids = get_all_character_ids()
        except Exception:
            character_ids = ['chayewoon']

        now = datetime.now(get_default_tz()).isoformat()
        for char_id in character_ids:
            cursor = conn.execute(
                "SELECT 1 FROM relationships WHERE user_id = ? AND character_id = ?",
                (user_id, char_id)
            )
            if not cursor.fetchone():
                conn.execute(
                    """INSERT INTO relationships (user_id, character_id, created_at,
                                                  affection, happiness, awakening, world_layer)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (user_id, char_id, now, 0, 50, 0, 'normal')
                )

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """通过 Telegram ID 获取用户"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """通过数据库用户 ID 获取用户"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """通过用户名获取用户"""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            return dict(row) if row else None


# 全局实例（向后兼容）
_db_global: Optional[GameDatabase] = None


# ============================================================
# 便捷函数（兼容现有代码）
# ============================================================

def get_db() -> GameDatabase:
    """获取数据库实例（优先线程本地，其次全局）"""
    return _get_thread_db()


def init_game_db():
    """初始化游戏数据库"""
    global _db_global
    _db_global = GameDatabase()
    return _db_global
