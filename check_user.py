"""检查用户"""
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash, verify_password

db = PrimarySessionLocal()

# 查找admin用户
admin = db.query(User).filter(User.username == 'admin').first()
if admin:
    print(f"用户: {admin.username}")
    print(f"邮箱: {admin.email}")
    print(f"密码哈希: {admin.password_hash[:50]}...")
    print(f"是否激活: {admin.is_active}")

    # 验证密码
    result = verify_password('test1234', admin.password_hash)
    print(f"密码test1234验证: {result}")

    # 如果验证失败，重置
    if not result:
        admin.password_hash = get_password_hash('test1234')
        admin.is_active = True
        db.commit()
        print("密码已重置!")

        # 再次验证
        result = verify_password('test1234', admin.password_hash)
        print(f"重置后验证: {result}")
else:
    print("未找到admin用户!")

db.close()
