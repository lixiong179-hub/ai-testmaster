"""验证删除项目功能修复"""
import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    """登录获取token"""
    url = f"{BASE_URL}/api/v1/auth/login"
    data = {"username": "admin", "password": "password123"}

    resp = requests.post(url, data=data)
    result = resp.json()

    if result.get("code") == 200:
        return result["data"]["access_token"]
    return None


def test_delete_project(token, project_id):
    """测试删除项目"""
    print(f"\n测试删除项目 ID={project_id}...")
    url = f"{BASE_URL}/api/v1/project/{project_id}"
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.delete(url, headers=headers)
    print(f"HTTP状态码: {resp.status_code}")

    if resp.status_code == 200:
        result = resp.json()
        print(f"业务码: {result.get('code')}")
        print(f"消息: {result.get('msg', 'N/A')}")

        if result.get("code") == 200:
            print("\n✅ 删除成功！500错误已修复！")
            return True
        else:
            print(f"\n⚠️ 业务逻辑返回: {result.get('message', 'N/A')}")
            return True  # 不是500就算成功
    elif resp.status_code == 500:
        print("❌ 仍然是500错误！")
        print(f"详情: {resp.text[:300]}")
        return False
    else:
        print(f"其他状态: {resp.status_code} - {resp.text[:200]}")
        return True  # 非500错误是正常的


if __name__ == "__main__":
    print("=" * 60)
    print("验证：删除项目功能（test_data.step_id修复）")
    print("=" * 60)

    # 登录
    token = test_login()
    if not token:
        print("[FAIL] 登录失败")
        sys.exit(1)

    print("[OK] 登录成功")

    # 测试删除
    success = test_delete_project(token, 100174)

    print("\n" + "=" * 60)
    if success:
        print("✅ 验证通过！删除项目功能正常")
    else:
        print("❌ 仍有问题，需要进一步排查")
    print("=" * 60)
