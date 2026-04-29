"""查询洪恩早教机项目(ID=3)的完整数据"""
import pymysql
import json

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='test1234',
    database='ai_testmaster',
    charset='utf8mb4'
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

# 1. 查询项目信息
print('=' * 80)
print('【项目信息】')
print('=' * 80)
cursor.execute('SELECT * FROM projects WHERE id = 3')
project = cursor.fetchone()
if project:
    for k, v in project.items():
        if k == 'config' or k == 'web_env_configs' or k == 'device_config':
            print(f'{k}: {json.dumps(v, ensure_ascii=False) if v else None}')
        else:
            print(f'{k}: {v}')

# 2. 查询测试点
print('\n' + '=' * 80)
print(f'【测试点】(共{cursor.execute("SELECT COUNT(*) FROM test_points WHERE project_id = 3")}个)')
print('=' * 80)
cursor.execute('SELECT * FROM test_points WHERE project_id = 3 ORDER BY id')
test_points = cursor.fetchall()
for tp in test_points:
    print(f'ID:{tp["id"]} | 模块:{tp["module"]} | 功能:{tp["function"]} | 测试点:{tp["point"]} | 优先级:{tp["priority"]}')

# 3. 查询已有测试用例
print('\n' + '=' * 80)
case_count = cursor.execute('SELECT COUNT(*) FROM test_cases WHERE project_id = 3')
cursor.execute('SELECT COUNT(*) FROM test_cases WHERE project_id = 3')
total = cursor.fetchone()['COUNT(*)']
print(f'【已有测试用例】(共{total}个)')
print('=' * 80)
cursor.execute('SELECT id, case_no, module, title, priority, case_type, review_status, test_category FROM test_cases WHERE project_id = 3 ORDER BY id')
cases = cursor.fetchall()
for c in cases:
    print(f'ID:{c["id"]} | 编号:{c["case_no"]} | 模块:{c["module"]}')
    print(f'   标题:{c["title"]} | 类型:{c["case_type"]} | 分类:{c["test_category"]} | 优先级:{c["priority"]} | 审核:{c["review_status"]}')

# 4. 查询项目文件
print('\n' + '=' * 80)
cursor.execute('SELECT COUNT(*) FROM project_files WHERE project_id = 3')
file_count = cursor.fetchone()['COUNT(*)']
print(f'【项目文件】(共{file_count}个)')
print('=' * 80)
cursor.execute('SELECT id, file_name, file_type, resource_type, extract_status, size FROM project_files WHERE project_id = 3')
files = cursor.fetchall()
for f in files:
    print(f'ID:{f["id"]} | 文件名:{f["file_name"]} | 类型:{f["file_type"]} | 资源类型:{f["resource_type"]} | 大小:{f["size"]}KB | 提取状态:{f["extract_status"]}')

# 5. 查询用户信息
print('\n' + '=' * 80)
print('【所属用户信息】')
print('=' * 80)
if project:
    cursor.execute('SELECT id, username FROM users WHERE id = %s', (project['user_id'],))
    user = cursor.fetchone()
    if user:
        print(f'ID:{user["id"]} | 用户名:{user["username"]}')

# 6. 查询测试任务
print('\n' + '=' * 80)
cursor.execute('SELECT COUNT(*) FROM test_tasks WHERE project_id = 3')
task_count = cursor.fetchone()['COUNT(*)']
print(f'【测试任务】(共{task_count}个)')
print('=' * 80)
cursor.execute('SELECT id, task_name, status, create_time FROM test_tasks WHERE project_id = 3 ORDER BY id')
tasks = cursor.fetchall()
for t in tasks:
    print(f'ID:{t["id"]} | 任务名:{t["task_name"]} | 状态:{t["status"]} | 创建时间:{t["create_time"]}')

# 7. 查询测试报告
print('\n' + '=' * 80)
cursor.execute('SELECT COUNT(*) FROM test_reports WHERE project_id = 3')
report_count = cursor.fetchone()['COUNT(*)']
print(f'【测试报告】(共{report_count}个)')
print('=' * 80)

conn.close()
print('\n查询完成!')
