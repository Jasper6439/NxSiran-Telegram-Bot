#!/usr/bin/env python3
"""
API Token 迁移脚本
将 api_tokens.json 迁移到 SQLite 数据库
v1.9: 实现单一数据源
"""

import os
import sys
import json
import sqlite3
import hashlib
from datetime import datetime, timezone

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from system.config import DATA_DIR, get_default_tz

DB_PATH = os.path.join(project_root, 'database', 'data', 'game.db')
API_TOKENS_FILE = os.path.join(DATA_DIR, 'api_tokens.json')


def parse_timestamp(ts):
    """解析各种格式的时间戳"""
    if ts is None:
        return None

    if isinstance(ts, (int, float)):
        # Unix 时间戳
        try:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return dt.astimezone(get_default_tz()).isoformat()
        except (ValueError, OSError):
            return None

    if isinstance(ts, str):
        # ISO 格式字符串
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            return dt.astimezone(get_default_tz()).isoformat()
        except ValueError:
            return ts  # 返回原字符串

    return None


def migrate_api_tokens():
    """迁移 API Token 从 JSON 到数据库"""

    print("=" * 60)
    print("API Token 迁移工具")
    print("=" * 60)

    # 检查数据库文件
    if not os.path.exists(DB_PATH):
        print(f"[错误] 数据库文件不存在: {DB_PATH}")
        return False

    print(f"[信息] 数据库路径: {DB_PATH}")

    # 检查 JSON 文件
    if not os.path.exists(API_TOKENS_FILE):
        print(f"[警告] API Token 文件不存在: {API_TOKENS_FILE}")
        print("[信息] 没有需要迁移的数据")
        return True

    print(f"[信息] Token 文件路径: {API_TOKENS_FILE}")

    # 读取 JSON 数据
    try:
        with open(API_TOKENS_FILE, 'r', encoding='utf-8') as f:
            tokens_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[错误] JSON 解析失败: {e}")
        return False
    except Exception as e:
        print(f"[错误] 读取文件失败: {e}")
        return False

    if not tokens_data:
        print("[信息] Token 文件为空，无需迁移")
        return True

    print(f"[信息] 发现 {len(tokens_data)} 个 Token 需要迁移")

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查 api_tokens 表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_tokens'")
    if not cursor.fetchone():
        print("[错误] api_tokens 表不存在，请先运行 migration_v19_api_tokens.sql")
        conn.close()
        return False

    # 获取所有现有用户 ID
    cursor.execute("SELECT id, telegram_id FROM users")
    users = {str(row['telegram_id']): row['id'] for row in cursor.fetchall()}
    print(f"[信息] 数据库中有 {len(users)} 个用户")

    migrated_count = 0
    skipped_count = 0
    failed_count = 0

    for token_hash, token_info in tokens_data.items():
        try:
            # 获取用户 ID
            raw_user_id = token_info.get('user_id')
            if not raw_user_id:
                print(f"[跳过] Token {token_hash[:16]}...: 无用户 ID")
                skipped_count += 1
                continue

            # 查找数据库用户 ID
            db_user_id = None
            if str(raw_user_id).isdigit():
                # 尝试通过 telegram_id 查找
                db_user_id = users.get(str(raw_user_id))

            if not db_user_id:
                # 尝试直接作为用户 ID 查找
                cursor.execute("SELECT id FROM users WHERE id = ?", (raw_user_id,))
                row = cursor.fetchone()
                if row:
                    db_user_id = row['id']

            if not db_user_id:
                print(f"[跳过] Token {token_hash[:16]}...: 用户 {raw_user_id} 不存在于数据库")
                skipped_count += 1
                continue

            # 解析时间戳
            created_at = parse_timestamp(token_info.get('created'))
            if not created_at:
                created_at = datetime.now(get_default_tz()).isoformat()

            # 检查 Token 是否已存在
            cursor.execute(
                "SELECT id FROM api_tokens WHERE token_hash = ?",
                (token_hash,)
            )
            if cursor.fetchone():
                print(f"[跳过] Token {token_hash[:16]}...: 已存在于数据库")
                skipped_count += 1
                continue

            # 插入 Token
            cursor.execute(
                """INSERT INTO api_tokens (user_id, token_hash, created_at, expired_at, is_revoked)
                   VALUES (?, ?, ?, ?, ?)""",
                (db_user_id, token_hash, created_at, None, 0)
            )

            print(f"[成功] Token {token_hash[:16]}... -> 用户 {db_user_id}")
            migrated_count += 1

        except Exception as e:
            print(f"[失败] Token {token_hash[:16]}...: {e}")
            failed_count += 1

    # 提交事务
    conn.commit()
    conn.close()

    print("=" * 60)
    print("迁移结果:")
    print(f"  成功: {migrated_count}")
    print(f"  跳过: {skipped_count}")
    print(f"  失败: {failed_count}")
    print("=" * 60)

    if migrated_count > 0:
        print("[提示] 迁移完成后，可以安全删除 api_tokens.json 文件")

    return failed_count == 0


def verify_migration():
    """验证迁移结果"""
    print("\n" + "=" * 60)
    print("验证迁移结果")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 检查表结构
    cursor.execute("PRAGMA table_info(api_tokens)")
    columns = [row['name'] for row in cursor.fetchall()]
    print(f"[信息] api_tokens 表列: {', '.join(columns)}")

    # 统计 Token 数量
    cursor.execute("SELECT COUNT(*) as count FROM api_tokens")
    count = cursor.fetchone()['count']
    print(f"[信息] 数据库中共有 {count} 个 Token")

    # 显示 Token 详情
    cursor.execute("""
        SELECT t.*, u.username, u.telegram_id
        FROM api_tokens t
        JOIN users u ON t.user_id = u.id
        LIMIT 10
    """)
    rows = cursor.fetchall()

    if rows:
        print("\nToken 列表:")
        for row in rows:
            status = "已撤销" if row['is_revoked'] else "有效"
            expired = f"过期: {row['expired_at']}" if row['expired_at'] else "永不过期"
            print(f"  - {row['token_hash'][:16]}... | 用户: {row['username'] or row['telegram_id']} | {status} | {expired}")

    conn.close()
    return True


if __name__ == '__main__':
    success = migrate_api_tokens()
    if success:
        verify_migration()
        print("\n[完成] 迁移成功!")
        sys.exit(0)
    else:
        print("\n[失败] 迁移过程中出现错误")
        sys.exit(1)
