"""
Add missing columns to test_cases table
"""
import pymysql

host = "localhost"
port = 3306
user = "root"
password = "test1234"
database = "ai_testmaster"

try:
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    cursor = conn.cursor()

    cursor.execute("DESCRIBE test_cases")
    columns = [row[0] for row in cursor.fetchall()]

    columns_to_add = [
        ("review_status", "VARCHAR(20) DEFAULT 'pending'"),
        ("review_comment", "TEXT"),
        ("reviewed_by", "VARCHAR(100)"),
        ("reviewed_at", "DATETIME"),
    ]

    for col_name, col_def in columns_to_add:
        if col_name not in columns:
            sql = f"ALTER TABLE test_cases ADD COLUMN {col_name} {col_def}"
            try:
                cursor.execute(sql)
                print(f"Added: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done!")

except Exception as e:
    print(f"Error: {e}")
