"""
设置密码为 password123
"""
import pymysql
import bcrypt

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='test1234',
    database='ai_testmaster',
    charset='utf8mb4'
)
cursor = conn.cursor()

# 设置密码为 password123
new_hash = bcrypt.hashpw('password123'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
conn.commit()
print("Password set to: password123")

# 验证
cursor.execute("SELECT password_hash FROM users WHERE username = 'admin'")
stored_hash = cursor.fetchone()[0]
verify = bcrypt.checkpw('password123'.encode('utf-8'), stored_hash.encode('utf-8'))
print("Verification:", verify)

conn.close()
