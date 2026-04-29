"""
使用后端直接测试登录
"""
import sys
sys.path.insert(0, '.')

from app.utils.jwt_utils import verify_password, get_password_hash, create_access_token
from app.db.database import get_db
from app.models.user import User

# 获取数据库会话
db = next(get_db())

# 查询用户
user = db.query(User).filter(User.username == "admin").first()

if user:
    print("User found:", user.username)
    print("Hash:", user.password_hash)

    # 验证密码
    result = verify_password("test1234", user.password_hash)
    print("Password verification:", result)

    if result:
        # 生成 token
        user_id = str(user.id)
        token = create_access_token(data={"sub": user_id})
        print("\nToken generated:", token[:50] + "...")
        print("\nUse this token for API calls:")
        print("Bearer", token)
    else:
        print("\nPassword verification failed!")

        # 尝试修复
        print("\nFixing password...")
        new_hash = get_password_hash("test1234")
        user.password_hash = new_hash
        db.commit()
        print("Password fixed! New hash:", new_hash)

        # 再次验证
        result2 = verify_password("test1234", new_hash)
        print("New verification:", result2)

else:
    print("User not found")

db.close()
