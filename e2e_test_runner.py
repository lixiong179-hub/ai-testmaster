#!/usr/bin/env python3
"""
AI TestMaster 端到端测试脚本
验证所有核心API接口的真实功能
"""
import requests
import json
import sys
import time
import os

BASE_URL = "http://127.0.0.1:8000/api/v1"
TOKEN = None
PROJECT_ID = None
TEST_POINT_IDS = []
TEST_CASE_ID = None
FILE_ID = None

# 记录所有发现的问题
BUGS = []
PASSED = []
FAILED = []


def log_result(name, passed, request_info=None, response_info=None, bug_detail=None):
    """记录测试结果"""
    status = "PASS" if passed else "FAIL"
    if passed:
        PASSED.append(name)
        print(f"  [{status}] {name}")
    else:
        FAILED.append(name)
        bug = {
            "name": name,
            "detail": bug_detail or ""
        }
        if request_info:
            bug["request"] = request_info
        if response_info:
            bug["response"] = response_info
        BUGS.append(bug)
        print(f"  [{status}] {name} - {bug_detail}")


def get_headers():
    """获取带认证的请求头"""
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ==================== 1. 登录流程测试 ====================
def test_login_flow():
    global TOKEN
    print("\n========== 1. 登录流程测试 ==========")

    # 1.1 获取验证码
    print("\n--- 1.1 验证码生成 ---")
    try:
        resp = requests.get(f"{BASE_URL}/auth/captcha/generate", timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            captcha_id = data["data"]["captcha_id"]
            image = data["data"]["image"]
            log_result("验证码生成", True,
                       response_info={"captcha_id": captcha_id, "image_length": len(image)})
        else:
            log_result("验证码生成", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("验证码生成", False, bug_detail=str(e))

    # 1.2 登录（不使用验证码）
    print("\n--- 1.2 用户登录 ---")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            TOKEN = data["data"]["access_token"]
            refresh_token = data["data"]["refresh_token"]
            token_type = data["data"]["token_type"]
            expires_in = data["data"]["expires_in"]
            log_result("用户登录", True,
                       response_info={"token_type": token_type, "expires_in": expires_in})
        else:
            log_result("用户登录", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("用户登录", False, bug_detail=str(e))

    # 1.3 获取当前用户信息
    print("\n--- 1.3 获取当前用户信息 ---")
    try:
        resp = requests.get(f"{BASE_URL}/auth/me", headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            user_data = data["data"]
            log_result("获取当前用户信息", True,
                       response_info={"username": user_data.get("username"), "id": user_data.get("id")})
        else:
            log_result("获取当前用户信息", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取当前用户信息", False, bug_detail=str(e))

    # 1.4 登录错误密码
    print("\n--- 1.4 登录错误密码 ---")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        }, timeout=10)
        if resp.status_code == 401:
            log_result("登录错误密码返回401", True)
        else:
            log_result("登录错误密码返回401", False,
                       bug_detail=f"预期401, 实际状态码={resp.status_code}")
    except Exception as e:
        log_result("登录错误密码返回401", False, bug_detail=str(e))

    # 1.5 无Token访问受保护接口
    print("\n--- 1.5 无Token访问受保护接口 ---")
    try:
        resp = requests.get(f"{BASE_URL}/auth/me", timeout=10)
        if resp.status_code in [401, 403]:
            log_result("无Token访问受保护接口返回401/403", True)
        else:
            log_result("无Token访问受保护接口返回401/403", False,
                       bug_detail=f"预期401/403, 实际状态码={resp.status_code}")
    except Exception as e:
        log_result("无Token访问受保护接口返回401/403", False, bug_detail=str(e))


# ==================== 2. 项目管理流程测试 ====================
def test_project_flow():
    global PROJECT_ID
    print("\n========== 2. 项目管理流程测试 ==========")

    # 2.1 创建项目
    print("\n--- 2.1 创建项目 ---")
    try:
        resp = requests.post(f"{BASE_URL}/project/", json={
            "name": f"E2E测试项目_{int(time.time())}",
            "description": "端到端测试创建的项目",
            "project_type": "web"
        }, headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            PROJECT_ID = data["data"]["project_id"]
            log_result("创建项目", True, response_info={"project_id": PROJECT_ID})
        else:
            log_result("创建项目", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("创建项目", False, bug_detail=str(e))

    # 2.2 获取项目列表
    print("\n--- 2.2 获取项目列表 ---")
    try:
        resp = requests.get(f"{BASE_URL}/project/list", params={"page": 1, "page_size": 10},
                            headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            total = data["data"]["total"]
            items = data["data"]["items"]
            log_result("获取项目列表", True, response_info={"total": total, "items_count": len(items)})
        else:
            log_result("获取项目列表", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取项目列表", False, bug_detail=str(e))

    # 2.3 获取项目详情
    print("\n--- 2.3 获取项目详情 ---")
    if PROJECT_ID:
        try:
            resp = requests.get(f"{BASE_URL}/project/{PROJECT_ID}",
                                headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                project_data = data["data"]
                log_result("获取项目详情", True,
                           response_info={"name": project_data.get("name"),
                                          "project_type": project_data.get("project_type")})
            else:
                log_result("获取项目详情", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("获取项目详情", False, bug_detail=str(e))
    else:
        log_result("获取项目详情", False, bug_detail="无项目ID，跳过测试")

    # 2.4 获取项目配置
    print("\n--- 2.4 获取项目配置 ---")
    if PROJECT_ID:
        try:
            resp = requests.get(f"{BASE_URL}/project/{PROJECT_ID}/config",
                                headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("获取项目配置", True, response_info=data.get("data"))
            else:
                log_result("获取项目配置", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("获取项目配置", False, bug_detail=str(e))

    # 2.5 更新项目配置
    print("\n--- 2.5 更新项目配置 ---")
    if PROJECT_ID:
        try:
            resp = requests.put(f"{BASE_URL}/project/{PROJECT_ID}/config", json={
                "project_type": "web",
                "web_env_configs": {
                    "test": {
                        "url": "http://test.example.com",
                        "username": "testuser",
                        "password": "testpass"
                    }
                }
            }, headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("更新项目配置", True, response_info=data.get("data"))
            else:
                log_result("更新项目配置", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("更新项目配置", False, bug_detail=str(e))

    # 2.6 创建重名项目
    print("\n--- 2.6 创建重名项目 ---")
    try:
        unique_name = f"dup_test_{int(time.time())}"
        resp = requests.post(f"{BASE_URL}/project/", json={
            "name": unique_name,
            "description": "测试重名",
            "project_type": "web"
        }, headers=get_headers(), timeout=10)
        if resp.status_code == 200:
            # 再创建同名项目
            resp2 = requests.post(f"{BASE_URL}/project/", json={
                "name": unique_name,
                "description": "测试重名",
                "project_type": "web"
            }, headers=get_headers(), timeout=10)
            data2 = resp2.json()
            if resp2.status_code == 400:
                log_result("创建重名项目返回400", True)
            else:
                log_result("创建重名项目返回400", False,
                           bug_detail=f"预期400, 实际状态码={resp2.status_code}, 响应={data2}")
        else:
            log_result("创建重名项目返回400", False, bug_detail=f"首次创建失败: {resp.json()}")
    except Exception as e:
        log_result("创建重名项目返回400", False, bug_detail=str(e))


# ==================== 3. 文件管理流程测试 ====================
def test_file_flow():
    global FILE_ID
    print("\n========== 3. 文件管理流程测试 ==========")

    if not PROJECT_ID:
        log_result("文件管理流程", False, bug_detail="无项目ID，跳过测试")
        return

    # 3.1 上传文件
    print("\n--- 3.1 上传文件 ---")
    try:
        # 创建一个测试文件
        test_content = "这是一个测试需求文档\n\n1. 用户登录功能\n2. 项目管理功能\n3. 测试用例生成功能"
        test_file_path = os.path.join(os.path.dirname(__file__), "test_requirement_upload.txt")
        with open(test_file_path, "w", encoding="utf-8") as f:
            f.write(test_content)

        with open(test_file_path, "rb") as f:
            resp = requests.post(f"{BASE_URL}/file/upload",
                                data={"project_id": str(PROJECT_ID), "resource_type": "requirement", "description": "测试需求文档"},
                                files={"file": ("test_requirement.txt", f, "text/plain")},
                                headers={"Authorization": f"Bearer {TOKEN}"},
                                timeout=30)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            FILE_ID = data["data"]["id"]
            log_result("上传文件", True, response_info={"file_id": FILE_ID, "file_name": data["data"].get("file_name")})
        else:
            log_result("上传文件", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("上传文件", False, bug_detail=str(e))

    # 3.2 获取文件列表
    print("\n--- 3.2 获取文件列表 ---")
    try:
        resp = requests.get(f"{BASE_URL}/file/list/{PROJECT_ID}",
                            headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            total = data["data"]["total"]
            items = data["data"]["items"]
            log_result("获取文件列表", True, response_info={"total": total, "items_count": len(items)})
        else:
            log_result("获取文件列表", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取文件列表", False, bug_detail=str(e))

    # 3.3 提取文件内容
    print("\n--- 3.3 提取文件内容 ---")
    if FILE_ID:
        try:
            resp = requests.post(f"{BASE_URL}/file/extract-content", json={
                "project_id": PROJECT_ID,
                "file_ids": [FILE_ID],
                "force_refresh": False
            }, headers=get_headers(), timeout=30)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("提取文件内容", True, response_info=data.get("data"))
            else:
                log_result("提取文件内容", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("提取文件内容", False, bug_detail=str(e))

    # 3.4 删除文件
    print("\n--- 3.4 删除文件 ---")
    if FILE_ID:
        try:
            resp = requests.delete(f"{BASE_URL}/file/{FILE_ID}",
                                   params={"project_id": PROJECT_ID},
                                   headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("删除文件", True)
            else:
                log_result("删除文件", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("删除文件", False, bug_detail=str(e))


# ==================== 4. 测试点流程测试 ====================
def test_test_point_flow():
    global TEST_POINT_IDS
    print("\n========== 4. 测试点流程测试 ==========")

    if not PROJECT_ID:
        log_result("测试点流程", False, bug_detail="无项目ID，跳过测试")
        return

    # 4.1 批量保存测试点
    print("\n--- 4.1 批量保存测试点 ---")
    try:
        test_points_data = [
            {"module": "登录模块", "function": "用户登录", "point": "验证正确的用户名和密码可以登录", "priority": 1},
            {"module": "登录模块", "function": "用户登录", "point": "验证错误的密码无法登录", "priority": 2},
            {"module": "项目管理", "function": "创建项目", "point": "验证可以创建新项目", "priority": 1},
            {"module": "项目管理", "function": "删除项目", "point": "验证可以删除已有项目", "priority": 2},
            {"module": "测试用例", "function": "生成用例", "point": "验证AI可以基于测试点生成测试用例", "priority": 1},
        ]
        resp = requests.post(f"{BASE_URL}/test-point/batch-save",
                             params={"project_id": PROJECT_ID},
                             json=test_points_data,
                             headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            saved_items = data["data"]["items"]
            TEST_POINT_IDS = [item["id"] for item in saved_items]
            log_result("批量保存测试点", True,
                       response_info={"saved_count": data["data"]["saved_count"],
                                      "ids": TEST_POINT_IDS})
        else:
            log_result("批量保存测试点", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("批量保存测试点", False, bug_detail=str(e))

    # 4.2 获取测试点列表
    print("\n--- 4.2 获取测试点列表 ---")
    try:
        resp = requests.get(f"{BASE_URL}/test-point/list/{PROJECT_ID}",
                            params={"page": 1, "page_size": 10},
                            headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            total = data["data"]["total"]
            items = data["data"]["items"]
            log_result("获取测试点列表", True, response_info={"total": total, "items_count": len(items)})
        else:
            log_result("获取测试点列表", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取测试点列表", False, bug_detail=str(e))

    # 4.3 获取测试点详情
    print("\n--- 4.3 获取测试点详情 ---")
    if TEST_POINT_IDS:
        try:
            resp = requests.get(f"{BASE_URL}/test-point/detail/{TEST_POINT_IDS[0]}",
                                params={"project_id": PROJECT_ID},
                                headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200:
                log_result("获取测试点详情", True, response_info={"id": data.get("id"), "point": data.get("point")})
            else:
                log_result("获取测试点详情", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("获取测试点详情", False, bug_detail=str(e))

    # 4.4 更新测试点
    print("\n--- 4.4 更新测试点 ---")
    if TEST_POINT_IDS:
        try:
            resp = requests.put(f"{BASE_URL}/test-point/{TEST_POINT_IDS[0]}",
                                params={"project_id": PROJECT_ID},
                                json={"module": "登录模块_已修改", "point": "验证修改后的测试点", "priority": 3},
                                headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                updated_point = data["data"]
                log_result("更新测试点", True,
                           response_info={"module": updated_point.get("module"),
                                          "point": updated_point.get("point"),
                                          "priority": updated_point.get("priority")})
            else:
                log_result("更新测试点", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("更新测试点", False, bug_detail=str(e))

    # 4.5 批量删除测试点
    print("\n--- 4.5 批量删除测试点 ---")
    if len(TEST_POINT_IDS) >= 2:
        try:
            ids_to_delete = TEST_POINT_IDS[-2:]  # 删除最后两个
            resp = requests.delete(f"{BASE_URL}/test-point/batch",
                                   params={"project_id": PROJECT_ID},
                                   json=ids_to_delete,
                                   headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("批量删除测试点", True,
                           response_info={"deleted_count": data["data"]["deleted_count"]})
            else:
                log_result("批量删除测试点", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("批量删除测试点", False, bug_detail=str(e))

    # 4.6 删除单个测试点
    print("\n--- 4.6 删除单个测试点 ---")
    if len(TEST_POINT_IDS) >= 3:
        try:
            resp = requests.delete(f"{BASE_URL}/test-point/{TEST_POINT_IDS[2]}",
                                   params={"project_id": PROJECT_ID},
                                   headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("删除单个测试点", True)
            else:
                log_result("删除单个测试点", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("删除单个测试点", False, bug_detail=str(e))

    # 4.7 空数据保存测试点
    print("\n--- 4.7 空数据保存测试点 ---")
    try:
        resp = requests.post(f"{BASE_URL}/test-point/batch-save",
                             params={"project_id": PROJECT_ID},
                             json=[],
                             headers=get_headers(), timeout=10)
        if resp.status_code == 400:
            log_result("空数据保存测试点返回400", True)
        else:
            data = resp.json()
            log_result("空数据保存测试点返回400", False,
                       bug_detail=f"预期400, 实际状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("空数据保存测试点返回400", False, bug_detail=str(e))


# ==================== 5. 测试用例流程测试 ====================
def test_test_case_flow():
    global TEST_CASE_ID
    print("\n========== 5. 测试用例流程测试 ==========")

    if not PROJECT_ID:
        log_result("测试用例流程", False, bug_detail="无项目ID，跳过测试")
        return

    # 5.1 创建测试用例
    print("\n--- 5.1 创建测试用例 ---")
    try:
        resp = requests.post(f"{BASE_URL}/testCase", json={
            "project_id": PROJECT_ID,
            "title": "E2E测试用例-用户登录验证",
            "module": "登录模块",
            "precondition": "用户已注册账号",
            "steps": [
                {"step": 1, "action": "打开登录页面", "param": "预期显示登录表单"},
                {"step": 2, "action": "输入正确的用户名和密码", "param": "预期输入成功"},
                {"step": 3, "action": "点击登录按钮", "param": "预期登录成功跳转首页"}
            ],
            "expected_result": "用户成功登录并跳转到首页",
            "priority": 1,
            "case_type": "functional"
        }, headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            TEST_CASE_ID = data["data"].get("id")
            log_result("创建测试用例", True, response_info={"case_id": TEST_CASE_ID})
        else:
            log_result("创建测试用例", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("创建测试用例", False, bug_detail=str(e))

    # 5.2 获取测试用例列表
    print("\n--- 5.2 获取测试用例列表 ---")
    try:
        resp = requests.get(f"{BASE_URL}/testCase",
                            params={"project_id": PROJECT_ID, "page": 1, "page_size": 10},
                            headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            total = data["data"]["total"]
            items = data["data"]["items"]
            log_result("获取测试用例列表", True, response_info={"total": total, "items_count": len(items)})
        else:
            log_result("获取测试用例列表", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取测试用例列表", False, bug_detail=str(e))

    # 5.3 获取测试用例详情
    print("\n--- 5.3 获取测试用例详情 ---")
    if TEST_CASE_ID:
        try:
            resp = requests.get(f"{BASE_URL}/testCase/{TEST_CASE_ID}",
                                headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                case_data = data["data"]
                log_result("获取测试用例详情", True,
                           response_info={"title": case_data.get("title"),
                                          "module": case_data.get("module")})
            else:
                log_result("获取测试用例详情", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("获取测试用例详情", False, bug_detail=str(e))

    # 5.4 更新测试用例
    print("\n--- 5.4 更新测试用例 ---")
    if TEST_CASE_ID:
        try:
            resp = requests.put(f"{BASE_URL}/testCase/{TEST_CASE_ID}", json={
                "title": "E2E测试用例-用户登录验证(已修改)",
                "priority": 2
            }, headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("更新测试用例", True)
            else:
                log_result("更新测试用例", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("更新测试用例", False, bug_detail=str(e))

    # 5.5 获取生成上下文
    print("\n--- 5.5 获取生成上下文 ---")
    try:
        resp = requests.post(f"{BASE_URL}/testCase/generate-context", json={
            "project_id": PROJECT_ID,
            "test_point_ids": TEST_POINT_IDS[:2] if TEST_POINT_IDS else []
        }, headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            log_result("获取生成上下文", True,
                       response_info={"test_point_count": data["data"].get("test_point_count"),
                                      "requirement_length": data["data"].get("requirement_length")})
        else:
            log_result("获取生成上下文", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取生成上下文", False, bug_detail=str(e))

    # 5.6 删除测试用例
    print("\n--- 5.6 删除测试用例 ---")
    if TEST_CASE_ID:
        try:
            resp = requests.delete(f"{BASE_URL}/testCase/{TEST_CASE_ID}",
                                   headers=get_headers(), timeout=10)
            if resp.status_code == 200:
                log_result("删除测试用例", True)
            else:
                data = resp.json()
                log_result("删除测试用例", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("删除测试用例", False, bug_detail=str(e))


# ==================== 6. 其他接口测试 ====================
def test_other_apis():
    print("\n========== 6. 其他接口测试 ==========")

    # 6.1 健康检查
    print("\n--- 6.1 健康检查 ---")
    try:
        resp = requests.get("http://127.0.0.1:8000/health", timeout=5)
        data = resp.json()
        if resp.status_code == 200 and data.get("status") == "healthy":
            log_result("健康检查", True, response_info=data)
        else:
            log_result("健康检查", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("健康检查", False, bug_detail=str(e))

    # 6.2 根路径
    print("\n--- 6.2 根路径 ---")
    try:
        resp = requests.get("http://127.0.0.1:8000/", timeout=5)
        data = resp.json()
        if resp.status_code == 200 and data.get("message"):
            log_result("根路径", True, response_info=data)
        else:
            log_result("根路径", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("根路径", False, bug_detail=str(e))

    # 6.3 用户注册
    print("\n--- 6.3 用户注册 ---")
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "username": f"test_user_{int(time.time())}",
            "email": f"test_{int(time.time())}@example.com",
            "password": "test123456",
            "confirm_password": "test123456"
        }, timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            log_result("用户注册", True, response_info={"username": data["data"].get("username")})
        else:
            log_result("用户注册", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("用户注册", False, bug_detail=str(e))

    # 6.4 注册密码不一致
    print("\n--- 6.4 注册密码不一致 ---")
    try:
        resp = requests.post(f"{BASE_URL}/auth/register", json={
            "username": "test_pwd_mismatch",
            "email": "mismatch@example.com",
            "password": "test123456",
            "confirm_password": "test654321"
        }, timeout=10)
        if resp.status_code == 400:
            log_result("注册密码不一致返回400", True)
        else:
            log_result("注册密码不一致返回400", False,
                       bug_detail=f"预期400, 实际状态码={resp.status_code}")
    except Exception as e:
        log_result("注册密码不一致返回400", False, bug_detail=str(e))

    # 6.5 获取所有文件列表
    print("\n--- 6.5 获取所有文件列表 ---")
    try:
        resp = requests.get(f"{BASE_URL}/file/list",
                            headers=get_headers(), timeout=10)
        data = resp.json()
        if resp.status_code == 200 and data.get("code") == 200:
            log_result("获取所有文件列表", True, response_info={"total": data["data"]["total"]})
        else:
            log_result("获取所有文件列表", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
    except Exception as e:
        log_result("获取所有文件列表", False, bug_detail=str(e))


# ==================== 7. 清理测试数据 ====================
def cleanup():
    print("\n========== 7. 清理测试数据 ==========")
    if PROJECT_ID:
        try:
            resp = requests.delete(f"{BASE_URL}/project/{PROJECT_ID}",
                                   headers=get_headers(), timeout=10)
            data = resp.json()
            if resp.status_code == 200 and data.get("code") == 200:
                log_result("清理测试项目", True)
            else:
                log_result("清理测试项目", False, bug_detail=f"状态码={resp.status_code}, 响应={data}")
        except Exception as e:
            log_result("清理测试项目", False, bug_detail=str(e))


# ==================== 主函数 ====================
def main():
    print("=" * 60)
    print("  AI TestMaster 端到端测试")
    print("=" * 60)

    # 1. 登录流程
    test_login_flow()

    if not TOKEN:
        print("\n[ERROR] 登录失败，无法继续后续测试")
        print_summary()
        return

    # 2. 项目管理流程
    test_project_flow()

    # 3. 文件管理流程
    test_file_flow()

    # 4. 测试点流程
    test_test_point_flow()

    # 5. 测试用例流程
    test_test_case_flow()

    # 6. 其他接口
    test_other_apis()

    # 7. 清理
    cleanup()

    # 输出汇总
    print_summary()


def print_summary():
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    print(f"  通过: {len(PASSED)}")
    print(f"  失败: {len(FAILED)}")
    print(f"  总计: {len(PASSED) + len(FAILED)}")
    print(f"  通过率: {len(PASSED) / (len(PASSED) + len(FAILED)) * 100:.1f}%" if (len(PASSED) + len(FAILED)) > 0 else "  通过率: N/A")

    if BUGS:
        print("\n  发现的Bug列表:")
        print("-" * 60)
        for i, bug in enumerate(BUGS, 1):
            print(f"  [{i}] {bug['name']}")
            print(f"      详情: {bug['detail']}")
            if "response" in bug:
                resp_str = json.dumps(bug["response"], ensure_ascii=False)
                if len(resp_str) > 200:
                    resp_str = resp_str[:200] + "..."
                print(f"      响应: {resp_str}")
            print()

    print("=" * 60)


if __name__ == "__main__":
    main()
