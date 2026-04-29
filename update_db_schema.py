"""更新数据库表结构，添加缺失的字段"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取数据库连接字符串
DATABASE_URL = os.getenv('DATABASE_URL')
print(f"数据库连接: {DATABASE_URL}")

# 创建引擎
engine = create_engine(DATABASE_URL)

# 添加 project_type 字段到 projects 表
with engine.connect() as conn:
    # 检查字段是否存在
    result = conn.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'projects' 
        AND COLUMN_NAME = 'project_type'
    """))
    
    exists = result.scalar()
    
    if not exists:
        print("添加 project_type 字段到 projects 表...")
        conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN project_type VARCHAR(20) NOT NULL DEFAULT 'web' 
            COMMENT '项目类型: web=Web端, app=C端'
        """))
        conn.commit()
        print("✓ project_type 字段添加成功")
    else:
        print("✓ project_type 字段已存在")
    
    # 检查 web_env_configs 字段
    result = conn.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'projects' 
        AND COLUMN_NAME = 'web_env_configs'
    """))
    
    exists = result.scalar()
    
    if not exists:
        print("添加 web_env_configs 字段到 projects 表...")
        conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN web_env_configs JSON NULL 
            COMMENT 'Web端多环境配置'
        """))
        conn.commit()
        print("✓ web_env_configs 字段添加成功")
    else:
        print("✓ web_env_configs 字段已存在")
    
    # 检查 device_config 字段
    result = conn.execute(text("""
        SELECT COUNT(*) 
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = 'projects' 
        AND COLUMN_NAME = 'device_config'
    """))
    
    exists = result.scalar()
    
    if not exists:
        print("添加 device_config 字段到 projects 表...")
        conn.execute(text("""
            ALTER TABLE projects 
            ADD COLUMN device_config JSON NULL 
            COMMENT 'C端设备连接信息'
        """))
        conn.commit()
        print("✓ device_config 字段添加成功")
    else:
        print("✓ device_config 字段已存在")

print("\n数据库表结构更新完成！")
