"""
初始化管理员用户
运行一次创建 Jasper 管理员账号
"""
import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import USERS_FILE, get_default_tz
from auth import hash_password, save_users

def init_admin():
    """创建管理员 Jasper"""
    admin_user = {
        "_version": 2.5,
        "users": {
            "jasper001": {
                "email": "jasper@admin.com",
                "username": "Jasper",
                "password_hash": hash_password("__REDACTED__"),
                "display_name": "Jasper",
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
    print("   用户名: Jasper")
    print("   密码: __REDACTED__")
    print("   邮箱: jasper@admin.com")

if __name__ == "__main__":
    init_admin()
