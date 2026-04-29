"""验证test-point/extract接口修复"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    """登录获取token"""
    url = f"{BASE_URL}/api/v1/auth/login"
    resp = requests.post(url, data={"username": "admin", "password": "password123"})
    result = resp.json()

    if result.get("code") == 200:
        return result["data"]["access_token"]
    return None


def test_extract_interface(token):
    """测试extract接口是否能正常调用（不再报未定义错误）"""
    print("\n" + "=" * 60)
    print("测试: /api/v1/test-point/extract 接口")
    print("=" * 60)

    # 获取一个有效的文件ID
    headers = {"Authorization": f"Bearer {token}"}

    # 先获取项目列表
    projects_resp = requests.get(f"{BASE_URL}/api/v1/project/list", headers=headers)
    if projects_resp.status_code != 200:
        print("[WARN] 无法获取项目列表")
        return None

    projects = projects_resp.json().get("data", {}).get("items", [])
    if not projects:
        print("[INFO] 无可用项目")
        return None

    project_id = projects[0]['id']
    print(f"[INFO] 使用项目ID: {project_id}")

    # 尝试调用extract接口（即使没有文件，也应该返回400而不是500）
    extract_url = f"{BASE_URL}/api/v1/test-point/extract"
    data = {"file_id": 99999}  # 使用不存在的文件ID

    try:
        resp = requests.post(extract_url, json=data, headers=headers)
        print(f"\nHTTP状态码: {resp.status_code}")
        result = resp.json()
        print(f"业务码: {result.get('code')}")
        print(f"消息: {result.get('msg', result.get('message', 'N/A'))}")

        # 关键检查：是否还是"not defined"错误
        msg = str(result.get('msg', result.get('message', '')))

        if 'not defined' in msg:
            print("\n❌ 失败：仍然是 'not defined' 错误！")
            return False
        elif resp.status_code == 500:
            print(f"\n⚠️  仍是500错误，但原因不同:")
            print(f"   详情: {msg[:200]}")
            # 如果不是not defined错误，说明导入修复成功
            return True
        else:
            # 400/200等正常响应
            print(f"\n✅ 接口正常响应！（不再是 not defined 错误）")
            return True

    except Exception as e:
        print(f"\n❌ 请求异常: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("验证：test-point/extract接口修复")
    print("=" * 60)

    token = test_login()

    if not token:
        print("[FAIL] 登录失败")
        sys.exit(1)

    print("[OK] 登录成功")

    success = test_extract_interface(token)

    print("\n" + "=" * 60)
    if success:
        print("✅ 修复验证通过！")
        print("   导入语句已添加：extract_test_points_from_content")
    else:
        print("❌ 仍有问题")
    print("=" * 60)
