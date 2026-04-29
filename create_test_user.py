"""创建测试用户"""
from app.db.database import PrimarySessionLocal
from app.models.user import User
from app.utils.jwt_utils import get_password_hash

# 创建会话
db = PrimarySessionLocal()

# 检查用户
users = db.query(User).all()
print(f'数据库中用户数量: {len(users)}')
for u in users:
    print(f'  - {u.username} (id={u.id})')

# 如果没有admin用户，创建一个
admin = db.query(User).filter(User.username == 'admin').first()
if not admin:
    admin = User(
        username='admin',
        email='admin@example.com',
        password_hash=get_password_hash('test1234'),
        is_active=True,
        is_superuser=True
    )
    db.add(admin)
    db.commit()
    print('已创建admin用户，密码: test1234')
else:
    print('admin用户已存在')

db.close()
