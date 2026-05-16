#!/usr/bin/env python3
"""
tools/reset_and_init.py - 清理所有用户数据并创建管理员
========================================================
用法: python3 tools/reset_and_init.py [--admin-username ADMIN] [--admin-password PASS]
"""

import os
import sys
import shutil
import argparse
import logging

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def reset_all_data(admin_username: str = "admin", admin_password: str = "admin123456"):
    """清理所有用户数据并创建管理员"""

    # 1. 删除 users.json
    users_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'data', 'users.json')
    if os.path.exists(users_file):
        os.remove(users_file)
        logger.info(f"✓ 已删除 {users_file}")

    # 2. 删除 sessions.json
    sessions_file = os.path.join(os.path.dirname(users_file), 'sessions.json')
    if os.path.exists(sessions_file):
        os.remove(sessions_file)
        logger.info(f"✓ 已删除 {sessions_file}")

    # 3. 删除 auto_login.json
    auto_login_file = os.path.join(os.path.dirname(users_file), 'auto_login.json')
    if os.path.exists(auto_login_file):
        os.remove(auto_login_file)
        logger.info(f"✓ 已删除 {auto_login_file}")

    # 4. 删除用户数据目录
    data_dir = os.path.dirname(users_file)
    if os.path.isdir(data_dir):
        for entry in os.listdir(data_dir):
            entry_path = os.path.join(data_dir, entry)
            if entry.startswith('user_') and os.path.isdir(entry_path):
                shutil.rmtree(entry_path)
                logger.info(f"✓ 已删除用户目录 {entry_path}")
    else:
        logger.info(f"! data 目录不存在，跳过用户目录清理: {data_dir}")

    # 5. 删除 SQLite 数据库
    db_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'database', 'data', 'game.db')
    if os.path.exists(db_file):
        os.remove(db_file)
        logger.info(f"✓ 已删除 {db_file}")
    # 也删除 WAL 和 SHM 文件
    for suffix in ['-wal', '-shm']:
        f = db_file + suffix
        if os.path.exists(f):
            os.remove(f)
            logger.info(f"✓ 已删除 {f}")

    # 6. 清除 Redis 缓存
    try:
        import redis
        r = redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'))
        keys = r.keys('chat:memory:*')
        if keys:
            r.delete(*keys)
            logger.info(f"✓ 已清除 {len(keys)} 个 Redis 记忆键")
        else:
            logger.info("✓ Redis 无记忆数据需要清除")
    except Exception as e:
        logger.warning(f"! Redis 清除失败（可能未启动）: {e}")

    # 7. 重新初始化数据库（创建表和初始数据）
    logger.info("重新初始化数据库...")
    from database import init_game_db
    init_game_db()
    logger.info("✓ 数据库初始化完成")

    # 8. 创建管理员账号
    logger.info(f"创建管理员账号: {admin_username}")
    from system.auth import register_user
    success, msg = register_user(admin_username, admin_password, "10001")
    if success:
        logger.info(f"✓ 管理员创建成功: {admin_username} (chat_id: 10001)")
    else:
        logger.warning(f"! 管理员创建失败: {msg}")
        # 可能已存在，尝试登录验证
        from system.auth import validate_user
        ok, _ = validate_user(admin_username, admin_password)
        if ok:
            logger.info(f"✓ 管理员已存在，密码验证通过")

    # 9. 生成 API Token（持久化到文件）
    from system.auth import generate_api_token, API_TOKENS
    api_token = generate_api_token("10001")

    # 持久化 API Token 到文件
    import json as _json
    api_tokens_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    'data', 'api_tokens.json')
    os.makedirs(os.path.dirname(api_tokens_file), exist_ok=True)
    with open(api_tokens_file, 'w', encoding='utf-8') as f:
        _json.dump(dict(API_TOKENS), f, indent=2, ensure_ascii=False)
    logger.info(f"✓ API Token 已持久化到 {api_tokens_file}")
    logger.info(f"")
    logger.info(f"{'='*50}")
    logger.info(f"  管理员 API Token (请保存):")
    logger.info(f"  {api_token}")
    logger.info(f"{'='*50}")
    logger.info(f"")
    logger.info(f"使用方法:")
    logger.info(f"  curl -H 'Authorization: Bearer {api_token}' http://localhost:8080/api/world/state")
    logger.info(f"")

    # 10. 确保数据库中也有管理员记录
    from database import get_db
    db = get_db()
    db_user_id = db.get_or_create_user(10001, admin_username)
    logger.info(f"✓ 数据库用户记录已创建 (db_user_id: {db_user_id})")

    return api_token


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='清理用户数据并创建管理员')
    parser.add_argument('--admin-username', default='admin', help='管理员用户名')
    parser.add_argument('--admin-password', default='admin123456', help='管理员密码')
    args = parser.parse_args()

    print("=" * 50)
    print("  LoveSupremacy Bot - 数据重置工具")
    print("=" * 50)
    print()

    token = reset_all_data(args.admin_username, args.admin_password)

    print()
    print("✅ 所有用户数据已清理，管理员账号已创建")
