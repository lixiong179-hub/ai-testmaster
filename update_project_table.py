"""
更新Project表结构 - 添加被测对象信息字段
"""
import os
import sys

# 设置Python路径
os.environ['PYTHONPATH'] = '.'

from sqlalchemy import create_engine, text, Column, String, Text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.database import Base, primary_engine

def update_project_table():
    """添加被测对象信息字段到projects表"""
    print("开始更新Project表结构...")
    
    # 需要添加的字段
    new_columns = [
        ("test_object_type", "VARCHAR(20)"),
        ("test_object_url", "VARCHAR(1000)"),
        ("test_object_username", "VARCHAR(255)"),
        ("test_object_password", "VARCHAR(255)"),
        ("test_object_device_info", "TEXT"),
        ("test_object_app_package", "VARCHAR(255)"),
        ("test_object_app_activity", "VARCHAR(255)"),
    ]
    
    with primary_engine.connect() as conn:
        # 检查每个字段是否存在，不存在则添加
        for column_name, column_type in new_columns:
            try:
                # 检查字段是否存在
                result = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'projects' 
                    AND COLUMN_NAME = '{column_name}'
                    AND TABLE_SCHEMA = DATABASE()
                """))
                count = result.scalar()
                
                if count == 0:
                    # 字段不存在，添加字段
                    conn.execute(text(f"""
                        ALTER TABLE projects 
                        ADD COLUMN {column_name} {column_type} NULL 
                        COMMENT '被测对象信息字段'
                    """))
                    print(f"✅ 添加字段成功: {column_name}")
                else:
                    print(f"⚠️ 字段已存在: {column_name}")
                    
            except Exception as e:
                print(f"❌ 添加字段失败 {column_name}: {e}")
        
        conn.commit()
    
    print("\nProject表结构更新完成！")
    print("\n新增字段列表:")
    for column_name, _ in new_columns:
        print(f"  - {column_name}")

if __name__ == "__main__":
    update_project_table()
