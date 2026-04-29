"""检查test_points表结构是否有遗留列导致ORM查询异常"""
import pymysql

DB_CONFIG = {
    "host": "localhost", "port": 3306, "user": "root",
    "password": "test1234", "database": "ai_testmaster", "charset": "utf8mb4",
}

conn = pymysql.connect(**DB_CONFIG)
try:
    with conn.cursor() as cursor:
        cursor.execute("DESCRIBE test_points")
        print("=== test_points 表实际结构 ===")
        for col in cursor.fetchall():
            print(f"  {col[0]:20s} {col[1]:25s} Null={col[2]}  Default={col[4]}")
finally:
    conn.close()
