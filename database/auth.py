"""认证与 API Token 管理 Mixin (v1.9)

实现单一数据源：所有 API Token 存储在 SQLite 数据库中
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, List

from system.config import get_default_tz

logger = logging.getLogger(__name__)


class AuthMixin:
    """API Token 认证管理 Mixin"""

    # ============================================================
    # API Token 管理
    # ============================================================

    def create_api_token(self, user_id: int, expires_days: Optional[int] = None) -> str:
        """创建新的 API Token

        Args:
            user_id: 用户数据库 ID
            expires_days: 过期天数（None 表示永不过期）

        Returns:
            生成的原始 Token（仅返回一次，需妥善保存）
        """
        # 生成安全的随机 Token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        now = datetime.now(get_default_tz())
        created_at = now.isoformat()
        expired_at = None

        if expires_days is not None:
            expired_at = (now + timedelta(days=expires_days)).isoformat()

        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO api_tokens (user_id, token_hash, created_at, expired_at, is_revoked)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, token_hash, created_at, expired_at, 0)
            )

        logger.info(f"[Auth] 为用户 {user_id} 创建 API Token")
        return raw_token

    def validate_api_token(self, token: str) -> Optional[Dict]:
        """验证 API Token 是否有效

        Args:
            token: 原始 Token 字符串

        Returns:
            Token 信息字典（含 user_id），无效返回 None
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with self.get_connection() as conn:
            cursor = conn.execute(
                """SELECT t.*, u.username, u.telegram_id, u.is_admin
                   FROM api_tokens t
                   JOIN users u ON t.user_id = u.id
                   WHERE t.token_hash = ? AND t.is_revoked = 0""",
                (token_hash,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # 检查是否过期
            if row['expired_at']:
                try:
                    expired_at = datetime.fromisoformat(row['expired_at'])
                    if datetime.now(get_default_tz()) > expired_at:
                        logger.warning(f"[Auth] Token 已过期: {token_hash[:16]}...")
                        return None
                except ValueError:
                    pass

            # 更新最后使用时间
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                "UPDATE api_tokens SET last_used_at = ? WHERE id = ?",
                (now, row['id'])
            )

            return {
                'id': row['id'],
                'user_id': row['user_id'],
                'username': row['username'],
                'telegram_id': row['telegram_id'],
                'is_admin': bool(row['is_admin']),
                'created_at': row['created_at'],
                'expired_at': row['expired_at'],
            }

    def revoke_api_token(self, token: str) -> bool:
        """撤销 API Token

        Args:
            token: 原始 Token 字符串

        Returns:
            是否成功撤销
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE api_tokens SET is_revoked = 1 WHERE token_hash = ?",
                (token_hash,)
            )
            if cursor.rowcount > 0:
                logger.info(f"[Auth] 撤销 Token: {token_hash[:16]}...")
                return True
            return False

    def revoke_all_user_tokens(self, user_id: int) -> int:
        """撤销用户的所有 API Token

        Args:
            user_id: 用户数据库 ID

        Returns:
            撤销的 Token 数量
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE api_tokens SET is_revoked = 1 WHERE user_id = ? AND is_revoked = 0",
                (user_id,)
            )
            count = cursor.rowcount
            if count > 0:
                logger.info(f"[Auth] 撤销用户 {user_id} 的 {count} 个 Token")
            return count

    def get_user_api_tokens(self, user_id: int, include_revoked: bool = False) -> List[Dict]:
        """获取用户的所有 API Token

        Args:
            user_id: 用户数据库 ID
            include_revoked: 是否包含已撤销的 Token

        Returns:
            Token 信息列表（不含原始 Token，只有 hash）
        """
        with self.get_connection() as conn:
            sql = """SELECT id, token_hash, created_at, expired_at, is_revoked, last_used_at
                     FROM api_tokens WHERE user_id = ?"""
            if not include_revoked:
                sql += " AND is_revoked = 0"
            sql += " ORDER BY created_at DESC"

            cursor = conn.execute(sql, (user_id,))
            rows = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'token_hash_prefix': row['token_hash'][:16] + '...',
                    'created_at': row['created_at'],
                    'expired_at': row['expired_at'],
                    'is_revoked': bool(row['is_revoked']),
                    'last_used_at': row['last_used_at'],
                }
                for row in rows
            ]

    def cleanup_expired_tokens(self) -> int:
        """清理过期的 Token

        Returns:
            清理的 Token 数量
        """
        now = datetime.now(get_default_tz()).isoformat()

        with self.get_connection() as conn:
            cursor = conn.execute(
                """DELETE FROM api_tokens
                   WHERE expired_at IS NOT NULL AND expired_at < ?""",
                (now,)
            )
            count = cursor.rowcount
            if count > 0:
                logger.info(f"[Auth] 清理 {count} 个过期 Token")
            return count

    # ============================================================
    # 用户认证辅助
    # ============================================================

    def get_user_by_api_token(self, token: str) -> Optional[Dict]:
        """通过 API Token 获取用户信息

        Args:
            token: 原始 Token 字符串

        Returns:
            用户信息字典，无效返回 None
        """
        token_info = self.validate_api_token(token)
        if not token_info:
            return None

        return self.get_user_by_id(token_info['user_id'])

    # ============================================================
    # 事务支持的关键操作
    # ============================================================

    def deduct_user_gold(self, user_id: int, amount: int, reason: str = "") -> Dict:
        """扣除用户金币（带事务保护）

        Args:
            user_id: 用户数据库 ID
            amount: 扣除金额
            reason: 扣除原因（用于日志）

        Returns:
            操作结果字典
        """
        if amount <= 0:
            return {'success': False, 'error': '扣除金额必须大于0'}

        with self.get_connection() as conn:
            # 获取当前金币（使用 FOR UPDATE 语义通过事务隔离）
            cursor = conn.execute(
                "SELECT money FROM farms WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户农场不存在'}

            current_money = row['money']

            if current_money < amount:
                return {
                    'success': False,
                    'error': '金币不足',
                    'current': current_money,
                    'required': amount
                }

            # 执行扣除（在同一事务中）
            new_money = current_money - amount
            conn.execute(
                "UPDATE farms SET money = ? WHERE user_id = ?",
                (new_money, user_id)
            )

            # 记录交易日志
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO game_events (user_id, event_type, event_data, source, created_at)
                   VALUES (?, 'gold_deduct', ?, 'system', ?)""",
                (user_id, f'{{"amount": {amount}, "reason": "{reason}", "balance": {new_money}}}', now)
            )

            logger.info(f"[Transaction] 扣除用户 {user_id} {amount} 金币，原因: {reason}")

            return {
                'success': True,
                'previous': current_money,
                'current': new_money,
                'deducted': amount
            }

    def add_user_gold(self, user_id: int, amount: int, reason: str = "") -> Dict:
        """增加用户金币（带事务保护）

        Args:
            user_id: 用户数据库 ID
            amount: 增加金额
            reason: 增加原因（用于日志）

        Returns:
            操作结果字典
        """
        if amount <= 0:
            return {'success': False, 'error': '增加金额必须大于0'}

        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT money FROM farms WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()

            if not row:
                return {'success': False, 'error': '用户农场不存在'}

            current_money = row['money']
            new_money = current_money + amount

            conn.execute(
                "UPDATE farms SET money = ? WHERE user_id = ?",
                (new_money, user_id)
            )

            # 记录交易日志
            now = datetime.now(get_default_tz()).isoformat()
            conn.execute(
                """INSERT INTO game_events (user_id, event_type, event_data, source, created_at)
                   VALUES (?, 'gold_add', ?, 'system', ?)""",
                (user_id, f'{{"amount": {amount}, "reason": "{reason}", "balance": {new_money}}}', now)
            )

            logger.info(f"[Transaction] 增加用户 {user_id} {amount} 金币，原因: {reason}")

            return {
                'success': True,
                'previous': current_money,
                'current': new_money,
                'added': amount
            }
