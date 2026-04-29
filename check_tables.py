"""
Check and fix database tables
"""
import pymysql

host = "localhost"
port = 3306
user = "root"
password = "test1234"
database = "ai_testmaster"

print(f"Connecting to MySQL at {host}:{port}...")

try:
    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    cursor = conn.cursor()

    # Fix test_cases table
    print("\nFixing test_cases table...")
    cursor.execute("DESCRIBE test_cases")
    columns = [row[0] for row in cursor.fetchall()]

    columns_to_add = []
    if "create_time" not in columns and "created_at" not in columns:
        columns_to_add.append("ALTER TABLE test_cases ADD COLUMN create_time DATETIME DEFAULT CURRENT_TIMESTAMP")
    if "updated_at" not in columns and "update_time" not in columns:
        columns_to_add.append("ALTER TABLE test_cases ADD COLUMN update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
    if "updated_at" not in columns and "update_time" in columns:
        pass  # Already has update_time

    # Add missing columns
    for sql in columns_to_add:
        try:
            cursor.execute(sql)
            print(f"Executed: {sql}")
        except Exception as e:
            print(f"Error: {e}")

    # Rename columns if needed
    if "created_at" in columns and "create_time" not in columns:
        cursor.execute("ALTER TABLE test_cases CHANGE COLUMN created_at create_time DATETIME DEFAULT CURRENT_TIMESTAMP")
        print("Renamed created_at to create_time")

    if "updated_at" in columns and "update_time" not in columns:
        cursor.execute("ALTER TABLE test_cases CHANGE COLUMN updated_at update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        print("Renamed updated_at to update_time")

    conn.commit()
    cursor.close()
    conn.close()
    print("\nDone!")

except Exception as e:
    print(f"Database error: {e}")
