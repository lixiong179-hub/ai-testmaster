"""
检查当前密码哈希并重新验证
"""
import pymysql
import bcrypt
import sys

# 连接数据库
try:
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='test1234',
        database='ai_testmaster',
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    # 查看admin用户的密码哈希
    print("=== Current admin password hash ===")
    cursor.execute("SELECT id, username, password_hash FROM users WHERE username = 'admin'")
    admin = cursor.fetchone()
    if admin:
        print(f"ID: {admin[0]}")
        print(f"Username: {admin[1]}")
        print(f"Hash: {admin[2]}")

        # 重新验证 test1234
        print("\n=== Re-verify test1234 ===")
        result = bcrypt.checkpw('test1234'.encode('utf-8'), admin[2].encode('utf-8'))
        print(f"test1234 is correct: {result}")

        # 强制重置为确认可用的哈希
        print("\n=== Force reset password to test1234 ===")
        # 使用确定有效的哈希（从之前成功的测试来的）
        confirmed_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.A.7tL3qU0YXYGy"
        # 或者生成新哈希
        new_hash = bcrypt.hashpw('test1234'.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
        print(f"New hash: {new_hash}")

        cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (new_hash,))
        conn.commit()
        print("Password reset complete!")

        # 验证
        cursor.execute("SELECT password_hash FROM users WHERE username = 'admin'")
        new_hash_stored = cursor.fetchone()[0]
        verify = bcrypt.checkpw('test1234'.encode('utf-8'), new_hash_stored.encode('utf-8'))
        print(f"Verification: {verify}")

    conn.close()

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
