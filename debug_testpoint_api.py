"""测试测试点API"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    # 模拟后端查询逻辑
    project_id = 100384
    
    # 查询测试点数量
    r = conn.execute(text("""
        SELECT COUNT(*) as total 
        FROM test_points tp 
        JOIN projects p ON tp.project_id = p.id 
        WHERE tp.project_id = :pid AND p.user_id = 1
    """), {"pid": project_id})
    total = r.scalar()
    print(f"总测试点数: {total}")
    
    # 分页查询
    r = conn.execute(text("""
        SELECT tp.id, tp.module, tp.`function`, tp.point, tp.priority 
        FROM test_points tp 
        JOIN projects p ON tp.project_id = p.id 
        WHERE tp.project_id = :pid AND p.user_id = 1 
        LIMIT :limit OFFSET :offset
    """), {"pid": project_id, "limit": 10, "offset": 0})
    
    rows = r.fetchall()
    print(f"\n分页结果 ({len(rows)} 条):")
    for row in rows:
        print(f"  ID={row[0]}, 模块={row[1]}, 功能={row[2]}")
