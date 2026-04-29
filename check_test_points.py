"""检查数据库中的测试点数据"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    # 检查测试点表的数据量
    r = conn.execute(text("SELECT COUNT(*) FROM test_points"))
    count = r.scalar()
    print(f"test_points 表中共有 {count} 条记录")
    
    if count > 0:
        # 显示前5条数据（用反引号包裹保留字）
        r = conn.execute(text("SELECT id, project_id, module, `function`, point FROM test_points LIMIT 5"))
        rows = r.fetchall()
        print("\n前5条测试点数据:")
        for row in rows:
            print(f"  ID={row[0]}, 项目ID={row[1]}, 模块={row[2]}, 功能={row[3]}")
    
    # 检查项目表
    r = conn.execute(text("SELECT COUNT(*) FROM projects"))
    p_count = r.scalar()
    print(f"\nprojects 表中共有 {p_count} 条记录")
    
    if p_count > 0:
        r = conn.execute(text("SELECT id, name FROM projects LIMIT 10"))
        rows = r.fetchall()
        print("\n项目列表:")
        for row in rows:
            print(f"  ID={row[0]}, 名称={row[1]}")
