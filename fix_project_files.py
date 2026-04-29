"""修复 project_files 表缺失的字段"""
import pymysql

# 数据库连接配置
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'test1234',
    'database': 'ai_testmaster',
    'charset': 'utf8mb4'
}

# 需要添加的字段及其定义
COLUMNS_TO_ADD = [
    ("content", "TEXT COMMENT '从文件提取的文本内容'"),
]

def fix_project_files_table():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # 检查表是否存在
        cursor.execute("SHOW TABLES LIKE 'project_files'")
        if not cursor.fetchone():
            print("表 project_files 不存在，跳过")
            return

        # 检查每个字段是否存在，不存在则添加
        cursor.execute("DESCRIBE project_files")
        existing_columns = {row[0] for row in cursor.fetchall()}

        for col_name, col_def in COLUMNS_TO_ADD:
            if col_name not in existing_columns:
                sql = f"ALTER TABLE project_files ADD COLUMN {col_name} {col_def}"
                cursor.execute(sql)
                print(f"添加字段成功: {col_name}")
            else:
                print(f"字段已存在，跳过: {col_name}")

        conn.commit()
        print("所有字段修复完成！")

    except Exception as e:
        print(f"修复失败: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    fix_project_files_table()
