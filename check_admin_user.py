"""检查和修复admin用户密码"""
import sys
sys.path.insert(0, ".")

from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash, verify_password

def check_admin_user():
    db = PrimarySessionLocal()
    try:
        # 查询admin用户
        admin = db.query(User).filter(User.username == "admin").first()
        
        if admin:
            print(f"找到admin用户:")
            print(f"  ID: {admin.id}")
            print(f"  用户名: {admin.username}")
            print(f"  邮箱: {admin.email}")
            print(f"  是否激活: {admin.is_active}")
            print(f"  是否超级用户: {admin.is_superuser}")
            print(f"  密码哈希: {admin.password_hash[:50]}...")
            
            # 测试密码
            test_password = "password123"
            is_valid = verify_password(test_password, admin.password_hash)
            print(f"\n测试密码 '{test_password}': {'正确' if is_valid else '错误'}")
            
            if not is_valid:
                print("\n需要重置密码...")
                admin.password_hash = get_password_hash(test_password)
                db.commit()
                print(f"密码已重置为: {test_password}")
                
                # 再次验证
                is_valid = verify_password(test_password, admin.password_hash)
                print(f"验证新密码: {'成功' if is_valid else '失败'}")
        else:
            print("未找到admin用户，创建新用户...")
            new_admin = User(
                username="admin",
                email="admin@example.com",
                password_hash=get_password_hash("password123"),
                is_active=True,
                is_superuser=True
            )
            db.add(new_admin)
            db.commit()
            print("admin用户已创建，密码为: password123")
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_admin_user()
