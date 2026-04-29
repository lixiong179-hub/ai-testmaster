"""修复 test_cases 表结构"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取数据库连接字符串
DATABASE_URL = os.getenv('DATABASE_URL')
print(f"数据库连接: {DATABASE_URL}\n")

# 创建引擎
engine = create_engine(DATABASE_URL)

# test_cases 表需要的字段
FIELDS = [
    ('case_no', 'VARCHAR(50)'),
    ('title', 'VARCHAR(500)'),
    ('steps_json', 'JSON'),
    ('case_type', 'VARCHAR(50)'),
    ('test_category', 'VARCHAR(50)'),
    ('exec_script', 'TEXT'),
    ('generate_status', 'VARCHAR(50) DEFAULT "pending"'),
    ('review_status', 'VARCHAR(50) DEFAULT "pending"'),
    ('review_comment', 'TEXT'),
    ('reviewed_by', 'INT'),
    ('reviewed_at', 'DATETIME'),
]

with engine.connect() as conn:
    print("检查 test_cases 表...")
    
    # 获取现有字段
    result = conn.execute(text("""
        SELECT COLUMN_NAME 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'test_cases'
    """))
    existing_columns = {row[0] for row in result}
    
    # 检查并添加缺失字段
    for col_name, col_def in FIELDS:
        if col_name not in existing_columns:
            print(f"  ⚠️ 缺失字段: {col_name}")
            try:
                conn.execute(text(f"""
                    ALTER TABLE test_cases 
                    ADD COLUMN {col_name} {col_def}
                """))
                conn.commit()
                print(f"  ✓ 已添加: {col_name}")
            except Exception as e:
                print(f"  ✗ 添加失败: {col_name} - {e}")
        else:
            print(f"  ✓ 字段存在: {col_name}")

print("\ntest_cases 表修复完成！")
