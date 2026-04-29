"""
检查和修复密码
"""
import pymysql
import bcrypt
import sys

# 密码哈希
hash_str = "$2b$12$ApSBI3YgC.mgXq1IYad6Lu9p3fKZ2SC9.q7EsOuUEiAj5MvTyrBhi"

# 测试密码
passwords = ['admin', 'admin123', 'password', 'password123', 'test1234', 'test123', 'admin888']

print("Testing password hashes...")
for pwd in passwords:
    try:
        # bcrypt 需要 bytes
        hashed = bcrypt.checkpw(pwd.encode('utf-8'), hash_str.encode('utf-8'))
        print(f"'{pwd}': {hashed}")
    except Exception as e:
        print(f"'{pwd}': ERROR - {e}")

# 更新密码为 test1234
print("\n\nUpdating admin password to 'test1234'...")
try:
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='test1234',
        database='ai_testmaster',
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    new_hash = bcrypt.hashpw('test1234'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
    conn.commit()
    print(f"Password updated! New hash: {new_hash[:50]}...")

    conn.close()
    print("\nNow try login with: admin / test1234")

except Exception as e:
    print(f"Error: {e}")
