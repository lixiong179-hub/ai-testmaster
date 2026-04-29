import pymysql

conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

print('=== 数据库表 ===')
cursor.execute('SHOW TABLES')
for t in cursor.fetchall():
    print(f'  {t[0]}')

print('\n=== 用户数据 ===')
try:
    cursor.execute('SELECT id, username, email, is_active, is_superuser FROM users LIMIT 10')
    for row in cursor.fetchall():
        print(f'  {row}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目数据 ===')
try:
    cursor.execute('SELECT id, name, project_type, status, description FROM projects LIMIT 10')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, name={row[1]}, type={row[2]}, status={row[3]}, desc={row[4][:50] if row[4] else None}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 测试用例统计 ===')
try:
    cursor.execute('SELECT COUNT(*) FROM test_cases')
    total = cursor.fetchone()[0]
    print(f'  总用例数: {total}')
    cursor.execute('SELECT project_id, COUNT(*) FROM test_cases GROUP BY project_id')
    for row in cursor.fetchall():
        print(f'  项目{row[0]}: {row[1]}个用例')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目文件 ===')
try:
    cursor.execute('SELECT id, project_id, file_name, file_type, resource_type FROM project_files LIMIT 15')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, proj={row[1]}, name={row[2]}, type={row[3]}, resource={row[4]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 测试点 ===')
try:
    cursor.execute('SELECT COUNT(*) FROM test_points')
    print(f'  总测试点数: {cursor.fetchone()[0]}')
    cursor.execute('SELECT id, project_id, module, name FROM test_points LIMIT 10')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, proj={row[1]}, module={row[2]}, name={row[3]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 测试任务 ===')
try:
    cursor.execute('SELECT id, project_id, name, status FROM test_tasks LIMIT 10')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, proj={row[1]}, name={row[2]}, status={row[3]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目环境配置(web_env_configs) ===')
try:
    cursor.execute('SELECT id, name, web_env_configs FROM projects WHERE web_env_configs IS NOT NULL LIMIT 5')
    for row in cursor.fetchall():
        import json
        cfg = json.loads(row[2]) if row[2] else {}
        print(f'  项目{id}: {row[1]}')
        for env, v in cfg.items():
            url = v.get('url', 'N/A') if isinstance(v, dict) else 'N/A'
            user = v.get('username', 'N/A') if isinstance(v, dict) else 'N/A'
            print(f'    [{env}] url={url[:60]}, user={user}')
except Exception as e:
    print(f'  Error: {e}')

conn.close()
