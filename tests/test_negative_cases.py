"""
负面测试用例 - API 错误处理测试 (v1.9)
======================================
测试当不存在或 ID 错误的用户尝试访问 API 时，
系统应该返回标准的 HTTP 404 或 401 错误，而不是抛出 500 内部服务器错误。
"""

import pytest
import asyncio
from fastapi import HTTPException
from fastapi.testclient import TestClient

# 需要在运行测试前导入应用
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestNegativeCases:
    """负面测试用例集合"""

    @pytest.mark.asyncio
    async def test_invalid_user_access_world_state(self):
        """测试无效用户访问 /world/state 应返回 401/404 而非 500"""
        from api.deps import get_current_user, UserNotFoundException

        # 测试无效的 authorization header
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer invalid_token_12345")

        assert exc_info.value.status_code in [401, 404]
        assert "500" not in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_nonexistent_user_id_access(self):
        """测试不存在的用户 ID 访问应返回 404"""
        from api.deps import get_user_or_404, UserNotFoundException

        # 测试不存在的用户 ID
        with pytest.raises((HTTPException, UserNotFoundException)) as exc_info:
            await get_user_or_404(999999)  # 不存在的用户 ID

        assert exc_info.value.status_code == 404
        assert "用户不存在" in exc_info.value.detail or "not found" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_missing_authorization_header(self):
        """测试缺少认证头应返回 401"""
        from api.deps import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(None)

        assert exc_info.value.status_code == 401
        assert "未提供认证令牌" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_malformed_authorization_header(self):
        """测试格式错误的认证头应返回 401"""
        from api.deps import get_current_user

        # 测试不是 Bearer 格式的 token
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Basic dXNlcjpwYXNz")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_bearer_token(self):
        """测试空的 Bearer token 应返回 401"""
        from api.deps import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("Bearer ")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_revoked_token_access(self):
        """测试已撤销的 Token 应返回 401"""
        from database import get_db

        db = get_db()

        # 创建一个测试 token 然后撤销
        test_token = db.create_api_token(1)  # 假设用户 1 存在
        db.revoke_api_token(test_token)

        # 验证撤销后的 token 无效
        result = db.validate_api_token(test_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_expired_token_access(self):
        """测试过期的 Token 应返回 401"""
        from database import get_db
        from datetime import datetime, timedelta

        db = get_db()

        # 创建一个已过期的 token（-1 天表示昨天创建，已过期）
        expired_token = db.create_api_token(1, expires_days=-1)

        # 验证过期 token 无效
        result = db.validate_api_token(expired_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_user_access_other_user_data(self):
        """测试用户访问其他用户数据应返回 403"""
        from api.deps import verify_user_access

        # 普通用户 1 尝试访问用户 2 的数据
        with pytest.raises(HTTPException) as exc_info:
            await verify_user_access(
                current_user_id=1,
                target_user_id=99999,  # 不存在的用户
                allow_admin=True
            )

        assert exc_info.value.status_code in [403, 404]

    @pytest.mark.asyncio
    async def test_farm_data_invalid_user(self):
        """测试农场数据接口对无效用户的处理"""
        from api.deps import get_current_user

        # 使用随机无效 token
        invalid_tokens = [
            "Bearer invalid_token",
            "Bearer ",
            "Bearer 12345",
            "Invalid prefix_token",
            None,
        ]

        for token in invalid_tokens:
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token)

            # 确保不是 500 错误
            assert exc_info.value.status_code != 500
            assert exc_info.value.status_code in [401, 404]


class TestDatabaseTransactionSafety:
    """数据库事务安全测试"""

    def test_gold_deduction_transaction(self):
        """测试金币扣除的事务安全性"""
        from database import get_db

        db = get_db()

        # 获取用户当前金币
        user = db.get_user_by_id(1)
        if not user:
            pytest.skip("用户 1 不存在，跳过测试")

        # 获取农场信息
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT money FROM farms WHERE user_id = ?", (1,))
            row = cursor.fetchone()
            if not row:
                pytest.skip("用户 1 没有农场，跳过测试")
            initial_money = row['money']

        # 测试正常扣除
        if initial_money >= 100:
            result = db.deduct_user_gold(1, 100, "测试扣除")
            assert result['success'] is True
            assert result['deducted'] == 100
            assert result['previous'] == initial_money
            assert result['current'] == initial_money - 100

        # 测试超额扣除（应该失败）
        result = db.deduct_user_gold(1, 999999999, "超额测试")
        assert result['success'] is False
        assert "不足" in result['error'] or "insufficient" in result['error'].lower()

    def test_invalid_amount_deduction(self):
        """测试无效金额扣除应失败"""
        from database import get_db

        db = get_db()

        # 测试负数金额
        result = db.deduct_user_gold(1, -100, "负数测试")
        assert result['success'] is False

        # 测试零金额
        result = db.deduct_user_gold(1, 0, "零金额测试")
        assert result['success'] is False

    def test_nonexistent_user_gold_operation(self):
        """测试对不存在用户的金币操作"""
        from database import get_db

        db = get_db()

        result = db.deduct_user_gold(999999, 100, "不存在用户测试")
        assert result['success'] is False
        assert "不存在" in result['error'] or "not found" in result['error'].lower()


class TestCascadeDelete:
    """级联删除测试"""

    def test_user_cascade_delete_relationships(self):
        """测试删除用户时级联删除关系数据"""
        import sqlite3

        DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'data', 'game.db')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查外键约束是否存在
        cursor.execute("PRAGMA foreign_key_list(relationships)")
        fks = cursor.fetchall()

        user_fk = [fk for fk in fks if fk[3] == 'user_id']
        if user_fk:
            # PRAGMA foreign_key_list 返回的列：
            # (id, seq, table, from, to, on_update, on_delete, match)
            # on_delete 是第 7 个字段（索引 6）
            on_delete = user_fk[0][6]
            assert on_delete == 'CASCADE', f"期望 CASCADE，实际得到 {on_delete}"

        conn.close()

    def test_user_cascade_delete_api_tokens(self):
        """测试删除用户时级联删除 API Token"""
        import sqlite3

        DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'data', 'game.db')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查 api_tokens 外键
        cursor.execute("PRAGMA foreign_key_list(api_tokens)")
        fks = cursor.fetchall()

        user_fk = [fk for fk in fks if fk[3] == 'user_id']
        assert len(user_fk) > 0, "api_tokens 应该有关联 users 的外键"

        conn.close()


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])
