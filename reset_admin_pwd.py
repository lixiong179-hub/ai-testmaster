"""重置admin用户密码为password123"""
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash

# 创建会话
db = PrimarySessionLocal()

# 查找admin用户
admin = db.query(User).filter(User.username == 'admin').first()
if admin:
    # 重置密码为password123
    admin.password_hash = get_password_hash('password123')
    admin.is_active = True
    admin.is_superuser = True
    db.commit()
    print('admin用户密码已重置为: password123')
else:
    print('未找到admin用户')

db.close()

# 验证密码
from app.utils.jwt_utils import verify_password

db = PrimarySessionLocal()
admin = db.query(User).filter(User.username == 'admin').first()
if admin:
    result = verify_password('password123', admin.password_hash)
    print(f'密码验证结果: {result}')
db.close()
