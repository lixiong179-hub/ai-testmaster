# -*- coding: utf-8 -*-
import pymysql
from app.utils.jwt_utils import verify_password, get_password_hash

conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

# 更新admin密码为admin123
new_hash = get_password_hash('admin123')
print(f"New hash for 'admin123': {new_hash}")

cursor.execute("UPDATE users SET password_hash=%s WHERE username='admin'", (new_hash,))
conn.commit()
print(f"Updated {cursor.rowcount} rows")

# 验证
cursor.execute("SELECT password_hash FROM users WHERE username='admin'")
hash_in_db = cursor.fetchone()[0]
print(f"Verify: {verify_password('admin123', hash_in_db)}")

conn.close()
print("Done!")
