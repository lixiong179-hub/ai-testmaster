import pymysql
import json

conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

print('=== 测试点详情 ===')
try:
    cursor.execute('DESCRIBE test_points')
    cols = [row[0] for row in cursor.fetchall()]
    print(f'  列: {cols}')
    cursor.execute('SELECT * FROM test_points LIMIT 10')
    for row in cursor.fetchall():
        d = dict(zip(cols, row))
        print(f'  id={d.get("id")}, proj={d.get("project_id")}, module={d.get("module")}, desc={str(d.get("description", ""))[:60]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 测试任务详情 ===')
try:
    cursor.execute('DESCRIBE test_tasks')
    cols = [row[0] for row in cursor.fetchall()]
    print(f'  列: {cols}')
    cursor.execute('SELECT * FROM test_tasks LIMIT 10')
    for row in cursor.fetchall():
        d = dict(zip(cols, row))
        print(f'  id={d.get("id")}, proj={d.get("project_id")}, title={str(d.get("title", d.get("name", "")))[:50]}, status={d.get("status")}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目3(洪恩早教机)环境配置 ===')
try:
    cursor.execute('SELECT web_env_configs FROM projects WHERE id=3')
    row = cursor.fetchone()
    if row and row[0]:
        cfg = json.loads(row[0])
        print(f'  配置: {json.dumps(cfg, ensure_ascii=False, indent=2)}')
    else:
        print('  无配置')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目3的测试用例详情 ===')
try:
    cursor.execute('SELECT id, case_no, module, title, case_type, priority, review_status FROM test_cases WHERE project_id=3')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, no={row[1]}, module={row[2]}, title={row[3][:40]}, type={row[4]}, pri={row[5]}, review={row[6]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 项目3文件内容提取状态 ===')
try:
    cursor.execute('SELECT id, file_name, file_type, extract_status, content_length FROM project_files WHERE project_id=3')
    for row in cursor.fetchall():
        print(f'  id={row[0]}, name={row[1]}, type={row[2]}, extract_status={row[3]}')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 需求文档内容(前500字符) ===')
try:
    cursor.execute('SELECT content FROM project_files WHERE project_id=3 AND file_type="docx" LIMIT 1')
    row = cursor.fetchone()
    if row and row[0]:
        print(f'  {row[0][:500]}')
    else:
        print('  无内容或未提取')
except Exception as e:
    print(f'  Error: {e}')

print('\n=== 所有项目的环境配置摘要 ===')
try:
    cursor.execute('SELECT id, name, project_type, web_env_configs FROM projects')
    for row in cursor.fetchall():
        cfg_str = row[3]
        if cfg_str:
            try:
                cfg = json.loads(cfg_str)
                if isinstance(cfg, dict):
                    envs = list(cfg.keys())
                    print(f'  项目{row[0]}({row[1]}): type={row[2]}, envs={envs}')
                elif isinstance(cfg, str):
                    print(f'  项目{row[0]}({row[1]}): type={row[2]}, raw_string')
                else:
                    print(f'  项目{row[0]}({row[1]}): type={row[2]}, type={type(cfg)}')
            except:
                print(f'  项目{row[0]}({row[1]}): type={row[2]}, parse_error')
        else:
            print(f'  项目{row[0]}({row[1]}): type={row[2]}, no_env_config')
except Exception as e:
    print(f'  Error: {e}')

conn.close()
