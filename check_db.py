# -*- coding: utf-8 -*-
import pymysql
import json

conn = pymysql.connect(host='localhost', user='root', password='test1234', database='ai_testmaster', charset='utf8mb4')
cursor = conn.cursor()

print("=" * 60)
print("【项目详情查询】")
print("=" * 60)

# 查询项目ID:3的详细信息
cursor.execute("SELECT id, name, description, project_type, web_env_configs, status, create_time FROM projects WHERE id=3")
p = cursor.fetchone()
if p:
    print(f"\n项目ID: {p[0]}")
    print(f"名称: {p[1]}")
    print(f"描述: {p[2]}")
    print(f"类型: {p[3]}")
    print(f"Web环境配置: {p[4]}")
    print(f"状态: {p[5]}")
    print(f"创建时间: {p[6]}")
    
    # 解析web_env_configs
    if p[4]:
        try:
            configs = json.loads(p[4])
            print("\n解析后的环境配置:")
            for env, cfg in configs.items():
                print(f"  [{env}]")
                print(f"    URL: {cfg.get('url', 'N/A')}")
                print(f"    用户名: {cfg.get('username', 'N/A')}")
                print(f"    密码: {cfg.get('password', 'N/A')[:4] + '****' if cfg.get('password') else 'N/A'}")
        except:
            print("  配置解析失败")

# 查询项目ID:3的文件
print("\n" + "=" * 60)
print("【项目ID:3的文件】")
print("=" * 60)
cursor.execute("SELECT id, file_name, file_url, file_type, resource_type, content, extract_status FROM project_files WHERE project_id=3")
for f in cursor.fetchall():
    print(f"\n文件ID: {f[0]}")
    print(f"文件名: {f[1]}")
    print(f"存储路径: {f[2]}")
    print(f"类型: {f[3]}")
    print(f"资源类型: {f[4]}")
    print(f"提取状态: {f[6]}")
    content = f[5]
    if content:
        print(f"内容长度: {len(content)} 字符")
        print(f"内容预览: {content[:800]}...")
    else:
        print("内容: 空")

# 查询项目ID:3的测试用例
print("\n" + "=" * 60)
print("【项目ID:3的测试用例】")
print("=" * 60)
cursor.execute("SELECT id, case_no, title, module, priority, case_type, review_status, precondition FROM test_cases WHERE project_id=3")
cases = cursor.fetchall()
print(f"共 {len(cases)} 个测试用例:")
for c in cases:
    print(f"\n用例ID: {c[0]}")
    print(f"编号: {c[1]}")
    print(f"标题: {c[2]}")
    print(f"模块: {c[3]}")
    print(f"优先级: {c[4]}")
    print(f"类型: {c[5]}")
    print(f"审核状态: {c[6]}")
    print(f"前置条件: {c[7][:100] if c[7] else '空'}...")

# 查询项目ID:3的测试点
print("\n" + "=" * 60)
print("【项目ID:3的测试点】")
print("=" * 60)
cursor.execute("SELECT id, module, name, description, priority FROM test_points WHERE project_id=3")
points = cursor.fetchall()
print(f"共 {len(points)} 个测试点:")
for p in points:
    print(f"  [{p[0]}] 模块:{p[1]}, 名称:{p[2]}, 描述:{p[3][:50] if p[3] else '空'}...")

conn.close()
print("\n查询完成!")
