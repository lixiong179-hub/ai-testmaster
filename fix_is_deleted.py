"""添加 is_deleted 和 deleted_at 字段到 test_cases 表"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT COUNT(*) FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'test_cases' AND COLUMN_NAME = 'is_deleted'
    """))
    exists = result.scalar()
    
    if not exists:
        print('添加 is_deleted 和 deleted_at 字段...')
        conn.execute(text("ALTER TABLE test_cases ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE COMMENT '软删除标记'"))
        conn.execute(text("ALTER TABLE test_cases ADD COLUMN deleted_at DATETIME COMMENT '删除时间'"))
        conn.commit()
        print('✓ 字段添加成功')
    else:
        print('✓ 字段已存在')
