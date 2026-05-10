"""
数据迁移脚本 - 将现有 JSON 数据迁移到 SQLite
运行一次即可，迁移后可删除旧 JSON 文件
"""

import os
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from database import GameDatabase, DB_PATH

# 韩国时区
KR_TZ = timezone(timedelta(hours=9))

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def migrate_users(db: GameDatabase):
    """迁移用户数据"""
    users_file = os.path.join(DATA_DIR, 'users.json')
    if not os.path.exists(users_file):
        print("[迁移] users.json 不存在，跳过")
        return 0
    
    with open(users_file, 'r', encoding='utf-8') as f:
        users = json.load(f)
    
    count = 0
    for username, user_data in users.items():
        chat_id = user_data.get('chat_id')
        password_hash = user_data.get('password_hash')
        created_at = user_data.get('created_at', datetime.now(KR_TZ).isoformat())
        
        if chat_id:
            # 创建用户
            user_id = db.get_or_create_user(
                telegram_id=int(chat_id),
                username=username,
                password_hash=password_hash
            )
            count += 1
            print(f"[迁移] 用户: {username} (chat_id={chat_id}, user_id={user_id})")
    
    print(f"[迁移] 完成，共迁移 {count} 个用户")
    return count


def migrate_chat_history(db: GameDatabase):
    """迁移聊天记录"""
    count = 0
    
    # 遍历所有用户目录
    if not os.path.exists(DATA_DIR):
        return 0
    
    for entry in os.listdir(DATA_DIR):
        if not entry.startswith('user_'):
            continue
        
        user_dir = os.path.join(DATA_DIR, entry)
        if not os.path.isdir(user_dir):
            continue
        
        # 提取 chat_id
        chat_id = entry.replace('user_', '')
        try:
            chat_id_int = int(chat_id)
        except ValueError:
            continue
        
        # 获取或创建用户
        user = db.get_user_by_telegram_id(chat_id_int)
        if not user:
            user_id = db.get_or_create_user(chat_id_int, f"user_{chat_id}")
        else:
            user_id = user['id']
        
        # 迁移聊天记录
        chat_file = os.path.join(user_dir, 'chat_history.json')
        if os.path.exists(chat_file):
            with open(chat_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            
            for msg in history:
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if content:
                    db.save_message(user_id, 'chayewoon', role, content)
                    count += 1
            
            print(f"[迁移] 聊天记录: {entry} ({len(history)} 条)")
        
        # 迁移语义记忆
        memory_file = os.path.join(user_dir, 'semantic_memory.json')
        if os.path.exists(memory_file):
            with open(memory_file, 'r', encoding='utf-8') as f:
                memories = json.load(f)
            
            for mem in memories:
                key = mem.get('key', '')
                value = mem.get('value', '')
                category = mem.get('category', 'personal')
                if key and value:
                    db.save_memory(user_id, 'chayewoon', key, value, category)
            
            print(f"[迁移] 记忆: {entry} ({len(memories)} 条)")
    
    print(f"[迁移] 完成，共迁移 {count} 条聊天记录")
    return count


def migrate_config(db: GameDatabase):
    """迁移配置（保留 JSON，只提取用户相关数据）"""
    config_file = os.path.join(DATA_DIR, 'config.json')
    if not os.path.exists(config_file):
        print("[迁移] config.json 不存在，跳过")
        return
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 提取管理员信息
    admin_username = config.get('admin_username', 'Ulysses')
    your_chat_id = config.get('your_chat_id', 0)
    
    if your_chat_id and admin_username:
        # 创建管理员用户
        user_id = db.get_or_create_user(
            telegram_id=int(your_chat_id),
            username=admin_username,
            is_admin=True
        )
        print(f"[迁移] 管理员: {admin_username} (chat_id={your_chat_id}, user_id={user_id})")
    
    print("[迁移] 配置文件保留为 JSON（包含敏感 API key）")


def verify_migration(db: GameDatabase):
    """验证迁移结果"""
    print("\n" + "="*50)
    print("迁移验证")
    print("="*50)
    
    with db.get_connection() as conn:
        # 用户数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM users")
        user_count = cursor.fetchone()['cnt']
        print(f"用户数: {user_count}")
        
        # 聊天记录数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM chat_messages")
        msg_count = cursor.fetchone()['cnt']
        print(f"聊天记录: {msg_count} 条")
        
        # 记忆数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM memories")
        mem_count = cursor.fetchone()['cnt']
        print(f"记忆: {mem_count} 条")
        
        # 关系数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM relationships")
        rel_count = cursor.fetchone()['cnt']
        print(f"关系: {rel_count} 条")
        
        # 农场数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM farms")
        farm_count = cursor.fetchone()['cnt']
        print(f"农场: {farm_count} 个")
        
        # 角色数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM characters")
        char_count = cursor.fetchone()['cnt']
        print(f"角色: {char_count} 个")
        
        # 作物类型数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM crop_types")
        crop_count = cursor.fetchone()['cnt']
        print(f"作物类型: {crop_count} 种")
        
        # 心级事件数
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM heart_events")
        event_count = cursor.fetchone()['cnt']
        print(f"心级事件: {event_count} 个")


def main():
    print("="*50)
    print("NxSiRan 数据迁移工具")
    print("="*50)
    print()
    
    # 初始化数据库
    print("[1/4] 初始化数据库...")
    db = GameDatabase()
    
    # 迁移用户
    print("\n[2/4] 迁移用户数据...")
    migrate_users(db)
    
    # 迁移聊天记录和记忆
    print("\n[3/4] 迁移聊天记录和记忆...")
    migrate_chat_history(db)
    
    # 迁移配置
    print("\n[4/4] 迁移配置...")
    migrate_config(db)
    
    # 验证
    verify_migration(db)
    
    print("\n" + "="*50)
    print("迁移完成！")
    print("="*50)
    print("\n注意：")
    print("1. config.json 保留（包含 API key 等敏感信息）")
    print("2. 旧的 chat_history.json 和 semantic_memory.json 可以删除")
    print("3. users.json 可以删除（已迁移到数据库）")


if __name__ == "__main__":
    main()
