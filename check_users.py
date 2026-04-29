import pymysql
import sys
import bcrypt

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
    print("=== Admin user password hash ===")
    cursor.execute("SELECT id, username, password_hash FROM users WHERE username = 'admin'")
    admin = cursor.fetchone()
    if admin:
        print(f"ID: {admin[0]}")
        print(f"Username: {admin[1]}")
        print(f"Password hash: {admin[2]}")

    # 更新密码为 admin123
    print("\n=== Updating admin password ===")
    hashed = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())
    cursor.execute("UPDATE users SET password_hash = %s WHERE username = 'admin'", (hashed.decode('utf-8'),))
    conn.commit()
    print(f"Password set to: admin123")
    print(f"New hash: {hashed.decode('utf-8')}")

    conn.close()
    print("\nDone! You can now login with admin/admin123")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
