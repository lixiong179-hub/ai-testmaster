"""全量数据库表结构同步 - 对比所有模型和实际表结构"""
from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取数据库连接字符串
DATABASE_URL = os.getenv('DATABASE_URL')
print(f"数据库连接: {DATABASE_URL}\n")

# 创建引擎
engine = create_engine(DATABASE_URL)

# 定义所有模型字段（根据实际模型文件）
MODELS = {
    'users': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'username': 'VARCHAR(100) NOT NULL UNIQUE',
        'email': 'VARCHAR(100) UNIQUE',
        'phone': 'VARCHAR(20)',
        'password_hash': 'VARCHAR(255) NOT NULL',
        'is_active': 'BOOLEAN DEFAULT TRUE',
        'is_superuser': 'BOOLEAN DEFAULT FALSE',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'projects': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'name': 'VARCHAR(255) NOT NULL',
        'user_id': 'INT NOT NULL',
        'description': 'TEXT',
        'status': 'INT DEFAULT 1',
        'config': 'JSON',
        'project_type': 'VARCHAR(20) DEFAULT "web"',
        'web_env_configs': 'JSON',
        'device_config': 'JSON',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'project_files': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'file_name': 'VARCHAR(500) NOT NULL',
        'file_type': 'VARCHAR(50) NOT NULL',
        'file_url': 'VARCHAR(1000) NOT NULL',
        'file_source': 'VARCHAR(20) DEFAULT "file"',
        'size': 'INT',
        'upload_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'resource_type': 'VARCHAR(50) DEFAULT "other"',
        'content': 'TEXT',
        'extract_status': 'VARCHAR(20) DEFAULT "pending"',
        'extract_error': 'TEXT',
        'extracted_at': 'DATETIME',
        'description': 'TEXT',
        'is_active': 'BOOLEAN DEFAULT TRUE',
        'linked_case_count': 'INT DEFAULT 0',
    },
    'test_cases': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'case_no': 'VARCHAR(50) NOT NULL UNIQUE',
        'project_id': 'INT NOT NULL',
        'module': 'VARCHAR(100) NOT NULL',
        'title': 'VARCHAR(255) NOT NULL',
        'precondition': 'TEXT NOT NULL',
        'steps_json': 'JSON NOT NULL',
        'expected_result': 'TEXT NOT NULL',
        'priority': 'INT NOT NULL',
        'case_type': 'VARCHAR(20) NOT NULL',
        'test_category': 'VARCHAR(100)',
        'exec_script': 'TEXT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
        'generate_status': 'INT DEFAULT 0',
        'review_status': 'VARCHAR(20) DEFAULT "pending"',
        'review_comment': 'TEXT',
        'reviewed_by': 'VARCHAR(100)',
        'reviewed_at': 'DATETIME',
    },
    'test_steps': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'test_case_id': 'INT NOT NULL',
        'step_number': 'INT NOT NULL',
        'action': 'TEXT NOT NULL',
        'expected_result': 'TEXT NOT NULL',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
        'is_business_view': 'INT DEFAULT 1',
        'is_technical_view': 'INT DEFAULT 1',
        'has_locator': 'INT DEFAULT 0',
        'locator_status': 'VARCHAR(20) DEFAULT "pending"',
    },
    'test_case_executions': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'test_case_id': 'INT NOT NULL',
        'test_task_id': 'INT',
        'status': 'VARCHAR(20) DEFAULT "pending"',
        'actual_result': 'TEXT',
        'started_at': 'DATETIME',
        'completed_at': 'DATETIME',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
    },
    'test_points': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'module': 'VARCHAR(255) NOT NULL',
        'function': 'VARCHAR(255) NOT NULL',
        'point': 'TEXT NOT NULL',
        'priority': 'INT DEFAULT 2',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'test_tasks': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'name': 'VARCHAR(255) NOT NULL',
        'description': 'TEXT',
        'status': 'VARCHAR(50) DEFAULT "pending"',
        'test_case_ids': 'JSON',
        'config': 'JSON',
        'result': 'JSON',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'test_reports': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'task_id': 'INT',
        'name': 'VARCHAR(255) NOT NULL',
        'summary': 'JSON',
        'details': 'JSON',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
    },
    'test_results': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'task_id': 'INT NOT NULL',
        'test_case_id': 'INT NOT NULL',
        'status': 'VARCHAR(50)',
        'actual_result': 'TEXT',
        'screenshots': 'JSON',
        'video_url': 'VARCHAR(1000)',
        'execution_time': 'INT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
    },
    'requirement_links': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'url': 'VARCHAR(2000) NOT NULL',
        'title': 'VARCHAR(500)',
        'content': 'TEXT',
        'link_type': 'VARCHAR(50) DEFAULT "requirement"',
        'fetch_status': 'VARCHAR(50) DEFAULT "pending"',
        'fetch_error': 'TEXT',
        'fetched_at': 'DATETIME',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'ui_prototypes': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'name': 'VARCHAR(255) NOT NULL',
        'url': 'VARCHAR(2000)',
        'file_path': 'VARCHAR(1000)',
        'prototype_type': 'VARCHAR(50) DEFAULT "figma"',
        'description': 'TEXT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'element_locators': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'name': 'VARCHAR(255) NOT NULL',
        'locator_type': 'VARCHAR(50) NOT NULL',
        'locator_value': 'VARCHAR(1000) NOT NULL',
        'description': 'TEXT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'test_data': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'project_id': 'INT NOT NULL',
        'name': 'VARCHAR(255) NOT NULL',
        'data_type': 'VARCHAR(50)',
        'content': 'JSON',
        'description': 'TEXT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
        'update_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP',
    },
    'video_records': {
        'id': 'INT AUTO_INCREMENT PRIMARY KEY',
        'task_id': 'INT',
        'test_case_id': 'INT',
        'file_path': 'VARCHAR(1000) NOT NULL',
        'file_name': 'VARCHAR(255)',
        'duration': 'INT',
        'create_time': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
    },
}

def sync_database():
    """同步数据库表结构"""
    with engine.connect() as conn:
        # 获取所有现有表
        result = conn.execute(text("""
            SELECT TABLE_NAME 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE()
        """))
        existing_tables = {row[0] for row in result}
        
        print(f"数据库中现有表: {len(existing_tables)} 个")
        print(f"模型定义表: {len(MODELS)} 个\n")
        
        total_added = 0
        
        for table_name, columns in MODELS.items():
            print(f"\n检查表: {table_name}")
            
            if table_name not in existing_tables:
                print(f"  ⚠️ 表不存在，需要创建")
                # 创建表
                try:
                    cols_def = ", ".join([f"{col} {def_}" for col, def_ in columns.items()])
                    conn.execute(text(f"CREATE TABLE {table_name} ({cols_def})"))
                    conn.commit()
                    print(f"  ✓ 表创建成功")
                    total_added += len(columns)
                except Exception as e:
                    print(f"  ✗ 创建失败: {e}")
                continue
            
            # 获取表的现有字段
            result = conn.execute(text(f"""
                SELECT COLUMN_NAME 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE() 
                AND TABLE_NAME = '{table_name}'
            """))
            existing_columns = {row[0] for row in result}
            
            # 检查每个字段
            for col_name, col_def in columns.items():
                if col_name not in existing_columns:
                    print(f"  ⚠️ 缺失字段: {col_name}")
                    try:
                        # 添加字段
                        conn.execute(text(f"""
                            ALTER TABLE {table_name} 
                            ADD COLUMN {col_name} {col_def}
                        """))
                        conn.commit()
                        print(f"  ✓ 已添加: {col_name}")
                        total_added += 1
                    except Exception as e:
                        print(f"  ✗ 添加失败: {col_name} - {e}")
                # else:
                #     print(f"  ✓ 字段存在: {col_name}")
        
        print("\n" + "="*50)
        print(f"数据库表结构同步完成！共添加 {total_added} 个字段/表")
        print("="*50)

if __name__ == "__main__":
    sync_database()
