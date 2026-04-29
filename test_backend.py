"""
测试后端登录
"""
import sys
sys.path.insert(0, '.')

from app.utils.jwt_utils import verify_password, create_access_token
from app.db.database import get_db
from app.models.user import User
from app.core.exception import create_response

# 获取数据库会话
db = next(get_db())

# 查询用户
user = db.query(User).filter(User.username == "admin").first()

if user:
    print("User found:", user.username)
    print("Hash:", user.password_hash)

    result = verify_password('password123', user.password_hash)
    print("Password verify:", result)

    if result:
        token = create_access_token(data={"sub": str(user.id)})
        print("\nToken:", token[:50] + "...")
        print("\n=== API Test ===")
        print("Bearer token:", token)
else:
    print("User not found")

db.close()
