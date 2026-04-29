#!/usr/bin/env python3
"""
检查并修复admin用户
"""
import sys
sys.path.insert(0, '.')

from app.db.database import get_db
from app.models.user import User
from app.utils.jwt_utils import get_password_hash, verify_password

def check_admin_user():
    db = next(get_db())
    try:
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            print(f"✓ admin用户存在")
            print(f"  - ID: {admin_user.id}")
            print(f"  - Email: {admin_user.email}")
            print(f"  - is_active: {admin_user.is_active}")
            print(f"  - password_hash: {admin_user.password_hash[:50]}...")

            # 验证密码
            test_password = "password123"
            is_valid = verify_password(test_password, admin_user.password_hash)
            print(f"  - 验证密码 '{test_password}': {'✓ 正确' if is_valid else '✗ 错误'}")

            if not is_valid:
                print("\n密码不正确，正在重置为 password123...")
                admin_user.password_hash = get_password_hash("password123")
                db.commit()
                print("✓ 密码已重置")
        else:
            print("✗ admin用户不存在，正在创建...")

            # 创建admin用户
            admin_user = User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("password123"),
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            print(f"✓ admin用户创建成功 (ID: {admin_user.id})")
            print(f"  请使用 admin / password123 登录")

    except Exception as e:
        print(f"✗ 错误: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    check_admin_user()