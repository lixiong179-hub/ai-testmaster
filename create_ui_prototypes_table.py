"""创建 ui_prototypes 表"""
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

with engine.connect() as conn:
    # 创建 ui_prototypes 表
    print("创建 ui_prototypes 表...")
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS ui_prototypes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT NOT NULL COMMENT '关联项目ID',
            name VARCHAR(255) NOT NULL COMMENT '原型名称',
            url VARCHAR(2000) COMMENT '原型链接',
            file_path VARCHAR(1000) COMMENT '文件路径',
            prototype_type VARCHAR(50) DEFAULT 'figma' COMMENT '原型类型: figma/axure/sketch等',
            description TEXT COMMENT '描述',
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            INDEX idx_project_id (project_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='UI原型表'
    """))
    conn.commit()
    print("✓ ui_prototypes 表创建成功")

print("\n数据库表创建完成！")
