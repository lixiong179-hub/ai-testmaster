"""
测试后端直接验证密码
"""
import sys
sys.path.insert(0, '.')

# 不导入 models，只用 jwt_utils
from app.utils.jwt_utils import verify_password

import pymysql
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='test1234',
    database='ai_testmaster',
    charset='utf8mb4'
)
cursor = conn.cursor()
cursor.execute("SELECT password_hash FROM users WHERE username = 'admin'")
stored_hash = cursor.fetchone()[0]
print("Stored hash:", stored_hash)

result = verify_password('password123', stored_hash)
print("verify_password result:", result)

conn.close()
