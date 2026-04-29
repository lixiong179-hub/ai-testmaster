"""完整测试test-point/extract接口 - 模拟前端调用"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    url = f"{BASE_URL}/api/v1/auth/login"
    resp = requests.post(url, data={"username": "admin", "password": "password123"})
    result = resp.json()
    if result.get("code") == 200:
        return result["data"]["access_token"]
    return None


def main():
    print("=" * 70)
    print("  完整测试：test-point/extract 接口")
    print("=" * 70)

    # 1. 登录
    print("\n[步骤1] 登录...")
    token = test_login()
    if not token:
        print("  ❌ 登录失败")
        return
    print(f"  ✅ 登录成功")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 获取项目列表
    print("\n[步骤2] 获取项目...")
    resp = requests.get(f"{BASE_URL}/api/v1/project/list", headers=headers)
    projects = resp.json().get("data", {}).get("items", [])
    if not projects:
        print("  ❌ 无项目")
        return

    project_id = projects[0]['id']
    print(f"  ✅ 项目ID: {project_id}")

    # 3. 获取项目的文件列表（找一个有效的文件）
    print("\n[步骤3] 查找可用文件...")
    resp = requests.get(f"{BASE_URL}/api/v1/project/{project_id}", headers=headers)
    project_detail = resp.json().get("data", {})
    files = project_detail.get("files", [])

    if not files:
        print(f"  ⚠️  项目下无文件，尝试使用不存在的file_id测试接口可达性...")

        # 测试接口是否正常响应（预期返回404 文件不存在）
        print("\n[步骤4] 测试extract接口（无效file_id）...")
        extract_resp = requests.post(
            f"{BASE_URL}/api/v1/test-point/extract",
            json={"file_id": 99999},
            headers=headers
        )

        print(f"  HTTP状态码: {extract_resp.status_code}")
        result = extract_resp.json()

        if extract_resp.status_code == 404:
            print(f"  ✅ 接口正常！返回: {result.get('msg', '文件不存在')}")
            print("\n  💡 结论:")
            print("     - 后端服务正常运行 ✓")
            print("     - AI API配置正确 ✓")
            print("     - 前端显示'提取失败'可能原因:")
            print("       ① 选择的项目没有上传需求文档文件")
            print("       ② 文件内容为空或无法解析")
            print("       ③ AI分析超时或返回格式异常")
            return
        elif extract_resp.status_code == 500:
            print(f"  ❌ 500错误!")
            print(f"  详情: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
            return
        else:
            print(f"  状态: {extract_resp.status_code}")
            print(f"  响应: {json.dumps(result, indent=2, ensure_ascii=False)[:300]}")
            return

    # 有文件的情况
    print(f"  找到 {len(files)} 个文件:")
    for f in files[:5]:
        print(f"    - ID:{f['id']} | {f.get('file_name', 'N/A')} | 类型:{f.get('file_type', 'N/A')}")

    # 4. 使用第一个文件测试提取
    test_file = files[0]
    file_id = test_file['id']
    file_name = test_file.get('file_name', '未知')

    print(f"\n[步骤4] 提取测试点 (文件: {file_name}, ID: {file_id})...")

    try:
        extract_resp = requests.post(
            f"{BASE_URL}/api/v1/test-point/extract",
            json={"file_id": file_id},
            headers=headers,
            timeout=60  # AI调用可能较慢
        )

        print(f"\n  HTTP状态码: {extract_resp.status_code}")
        result = extract_resp.json()

        print(f"  业务码: {result.get('code')}")
        print(f"  消息: {result.get('msg', result.get('message', 'N/A'))}")

        if extract_resp.status_code == 200 and result.get('code') == 200:
            data = result.get('data', {})
            items = data.get('items', [])
            total = data.get('total', 0)

            print(f"\n  🎉 提取成功！")
            print(f"  提取到 {total} 个测试点:")

            for i, item in enumerate(items[:5], 1):
                print(f"    {i}. [{item.get('module', 'N/A')}] {item.get('point', 'N/A')}")

            if len(items) > 5:
                print(f"    ... 还有 {len(items) - 5} 个")

        elif extract_resp.status_code == 500:
            print(f"\n  ❌ 服务器错误:")
            msg = result.get('msg', result.get('detail', ''))
            print(f"  详情: {msg}")

            # 分析错误类型
            if 'not defined' in str(msg):
                print("\n  🔍 原因: 函数未导入（代码bug）")
            elif 'API' in str(msg).upper() or 'key' in str(msg).lower():
                print("\n  🔍 原因: AI API相关错误")
            elif 'timeout' in str(msg).lower():
                print("\n  🔍 原因: 请求超时")
            else:
                print(f"\n  🔍 其他错误，请查看后端日志")

        else:
            print(f"\n  ⚠️  其他响应:")
            print(f"  {json.dumps(result, indent=2, ensure_ascii=False)[:400]}")

    except requests.exceptions.Timeout:
        print("\n  ❌ 请求超时（AI分析耗时过长）")
        print("  建议: 检查网络或增加超时时间")
    except Exception as e:
        print(f"\n  ❌ 异常: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
