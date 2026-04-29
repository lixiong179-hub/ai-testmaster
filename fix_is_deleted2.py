"""添加 is_deleted 字段到 test_cases 表"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    r = conn.execute(text("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='test_cases' AND COLUMN_NAME='is_deleted'"))
    exists = r.scalar()
    
    if not exists:
        print("添加 is_deleted 字段...")
        conn.execute(text("ALTER TABLE test_cases ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE COMMENT '软删除标记'"))
        conn.commit()
        print("✓ 字段添加成功")
    else:
        print("✓ is_deleted 已存在")
