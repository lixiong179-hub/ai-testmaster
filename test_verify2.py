"""
测试后端密码验证
"""
import sys
sys.path.insert(0, '.')

from app.utils.jwt_utils import verify_password

# 测试数据库中的密码
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

# 测试 verify_password
result = verify_password('password123', stored_hash)
print("verify_password('password123', stored):", result)

conn.close()
