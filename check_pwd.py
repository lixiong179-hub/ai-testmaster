# -*- coding: utf-8 -*-
import pymysql
from app.utils.jwt_utils import verify_password, get_password_hash

conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

cursor.execute("SELECT id, username, password_hash FROM users WHERE username='admin'")
u = cursor.fetchone()
print(f"User ID: {u[0]}, Username: {u[1]}")
print(f"Password Hash: {u[2]}")

test_pwds = ['admin123', 'admin', 'password', 'test1234', 'Test@123456', 'test', 'admin@123', 'admin123456']
print("\nTesting passwords:")
for p in test_pwds:
    result = verify_password(p, u[2])
    print(f"  '{p}': {result}")
    if result:
        print(f"  *** FOUND: '{p}' ***")

conn.close()
