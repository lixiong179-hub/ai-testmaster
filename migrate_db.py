"""
数据库迁移脚本 - 添加视图相关字段
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    """执行数据库迁移"""
    print("开始数据库迁移...")
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'test_steps' 
            AND COLUMN_NAME = 'is_business_view'
        """))
        
        if result.fetchone():
            print("字段已存在，跳过迁移")
            return
        
        # 添加业务视图字段
        conn.execute(text("""
            ALTER TABLE test_steps 
            ADD COLUMN is_business_view INT NOT NULL DEFAULT 1 COMMENT '是否在业务视图显示：0隐藏/1显示'
        """))
        print("✓ 添加 is_business_view 字段")
        
        # 添加技术视图字段
        conn.execute(text("""
            ALTER TABLE test_steps 
            ADD COLUMN is_technical_view INT NOT NULL DEFAULT 1 COMMENT '是否在技术视图显示：0隐藏/1显示'
        """))
        print("✓ 添加 is_technical_view 字段")
        
        # 添加定位状态字段
        conn.execute(text("""
            ALTER TABLE test_steps 
            ADD COLUMN has_locator INT NOT NULL DEFAULT 0 COMMENT '是否已记录元素定位：0否/1是'
        """))
        print("✓ 添加 has_locator 字段")
        
        # 添加定位状态字段
        conn.execute(text("""
            ALTER TABLE test_steps 
            ADD COLUMN locator_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '定位状态：pending/recorded/failed'
        """))
        print("✓ 添加 locator_status 字段")
        
        conn.commit()
    
    print("\n数据库迁移完成！")

if __name__ == "__main__":
    migrate()
