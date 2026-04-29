"""
Update projects table for new schema
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

    cursor.execute("DESCRIBE projects")
    columns = [row[0] for row in cursor.fetchall()]

    print(f"Current columns: {columns}")

    # Add new columns
    new_columns = [
        ("project_type", "VARCHAR(20) NOT NULL DEFAULT 'web'"),
        ("web_env_configs", "JSON"),
        ("device_config", "JSON"),
    ]

    for col_name, col_def in new_columns:
        if col_name not in columns:
            sql = f"ALTER TABLE projects ADD COLUMN {col_name} {col_def}"
            try:
                cursor.execute(sql)
                print(f"Added: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Database update complete!")

except Exception as e:
    print(f"Error: {e}")
