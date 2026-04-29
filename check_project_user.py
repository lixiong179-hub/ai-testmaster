"""检查项目和用户的关联关系"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    # 检查项目100384的user_id
    r = conn.execute(text("SELECT id, name, user_id FROM projects WHERE id = 100384"))
    row = r.fetchone()
    if row:
        print(f"项目信息: ID={row[0]}, 名称={row[1]}, 创建者user_id={row[2]}")
    
    # 检查admin用户的id
    r = conn.execute(text("SELECT id, username FROM users WHERE username='admin'"))
    row = r.fetchone()
    if row:
        print(f"Admin用户: ID={row[0]}, 用户名={row[1]}")
    
    # 检查测试点的project_id分布
    r = conn.execute(text("SELECT project_id, COUNT(*) as cnt FROM test_points GROUP BY project_id"))
    rows = r.fetchall()
    print("\n测试点按项目分组:")
    for row in rows:
        print(f"  项目ID={row[0]}, 数量={row[1]}")
