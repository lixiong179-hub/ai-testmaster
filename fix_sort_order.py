"""添加 sort_order 字段到 project_files 表"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    r = conn.execute(text("SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='project_files' AND COLUMN_NAME='sort_order'"))
    exists = r.scalar()
    
    if not exists:
        print("添加 sort_order 字段...")
        conn.execute(text("ALTER TABLE project_files ADD COLUMN sort_order INT DEFAULT 0 COMMENT '排序顺序'"))
        conn.commit()
        print("✓ sort_order 字段添加成功")
    else:
        print("✓ sort_order 已存在")
