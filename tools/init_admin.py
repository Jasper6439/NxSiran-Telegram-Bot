"""
初始化管理员用户
运行一次创建管理员账号（密码通过命令行输入）
"""
import os
import sys
import json
import getpass
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import USERS_FILE, get_default_tz
from auth import hash_password, save_users

def init_admin():
    """创建管理员账号"""
    username = input("请输入管理员用户名: ").strip()
    if not username:
        print("❌ 用户名不能为空")
        return

    password = getpass.getpass("请输入管理员密码: ").strip()
    if not password or len(password) < 6:
        print("❌ 密码长度至少6位")
        return

    email = input("请输入管理员邮箱: ").strip()

    admin_user = {
        "_version": 2.5,
        "users": {
            "admin001": {
                "email": email,
                "username": username,
                "password_hash": hash_password(password),
                "display_name": username,
                "role": "admin",
                "email_verified": True,
                "created_at": datetime.now(get_default_tz()).isoformat(),
                "last_login": None,
                "login_count": 0,
                "preferences": {"language": "zh-CN", "theme": "auto"},
                "character_bindings": {},
                "reset_code": None,
                "reset_code_expires": None
            }
        }
    }

    save_users(admin_user)
    print("✅ 管理员账号创建成功")
    print(f"   用户名: {username}")
    print(f"   邮箱: {email}")

if __name__ == "__main__":
    init_admin()
