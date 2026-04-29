"""
Add missing columns to projects table
"""
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Database connection
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

    # Check if columns exist
    cursor.execute("DESCRIBE projects")
    columns = [row[0] for row in cursor.fetchall()]

    # Modify columns to have default values
    columns_to_modify = [
        ("project_type", "VARCHAR(50) DEFAULT 'web'"),
    ]

    for col_name, col_def in columns_to_modify:
        try:
            sql = f"ALTER TABLE projects MODIFY COLUMN {col_name} {col_def}"
            cursor.execute(sql)
            print(f"Modified column: {col_name}")
        except Exception as e:
            print(f"Error modifying {col_name}: {e}")

    conn.commit()
    cursor.close()
    conn.close()
    print("Done!")

except Exception as e:
    print(f"Database error: {e}")
