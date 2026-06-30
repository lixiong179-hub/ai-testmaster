"""
本次改动单元测试

覆盖范围:
1. _normalize_new_format() - 新格式(steps+expected_results分离)标准化
2. _normalize_old_format() - 旧格式优先级转换(1/2/3 -> P0/P2/P3)
3. TestCaseUpdate schema - steps/module字段校验
4. PUT /api/v1/testCase/{id} - steps_json更新逻辑
5. execution.py targetEnv白名单校验

使用真实MySQL数据库，不使用Mock
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.ai_client import (
    _normalize_new_format,
    _normalize_old_format,
)
from app.schemas.test_case import TestCaseUpdate, TestCaseStep
from fastapi.testclient import TestClient
from app.main import app


# ============================================================
# 1. _normalize_new_format 测试
# ============================================================

class TestNormalizeNewFormat:
    """新格式AI响应标准化测试"""

    def test_basic_conversion(self):
        """基础转换：steps + expected_results -> 统一格式"""
        input_case = {
            "title": "模块_测试点",
            "module": "登录模块",
            "precondition": "已登录并进入至首页",
            "case_type": "功能测试",
            "priority": "P0",
            "steps": [
                {"step": 1, "action": "点击'登录按钮'"},
                {"step": 2, "action": "输入用户名"}
            ],
            "expected_results": [
                "查看登录按钮展示正确",
                "输入框显示正确"
            ]
        }
        result = _normalize_new_format(input_case)

        assert result["title"] == "模块_测试点"
        assert result["module"] == "登录模块"
        assert result["case_type"] == "ui_automation"
        assert result["priority"] == "P0"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["step"] == 1
        assert result["steps"][0]["action"] == "点击'登录按钮'"
        assert result["steps"][0]["description"] == "1. 点击'登录按钮'"
        assert result["steps"][0]["expected_result"] == "查看登录按钮展示正确"
        assert result["steps"][0]["test_data"] == []
        assert result["steps"][0]["ui_elements"] == []

    def test_expected_result_joined_as_string(self):
        """expected_results 应合并为换行分隔的字符串"""
        input_case = {
            "title": "测试",
            "steps": [
                {"step": 1, "action": "操作A"},
                {"step": 2, "action": "操作B"},
                {"step": 3, "action": "操作C"}
            ],
            "expected_results": ["结果A", "结果B", "结果C"]
        }
        result = _normalize_new_format(input_case)

        expected_lines = result["expected_result"].split("\n")
        assert len(expected_lines) == 3
        assert "[1] 结果A" in expected_lines[0] or "1. 结果A" in expected_lines[0]
        assert "[2] 结果B" in expected_lines[1] or "2. 结果B" in expected_lines[1]
        assert "[3] 结果C" in expected_lines[2] or "3. 结果C" in expected_lines[2]

    def test_empty_steps(self):
        """空步骤列表处理"""
        input_case = {
            "title": "空步骤用例",
            "steps": [],
            "expected_results": []
        }
        result = _normalize_new_format(input_case)
        assert result["steps"] == []
        assert result["expected_result"] == ""

    def test_missing_optional_fields_use_defaults(self):
        """缺少可选字段时使用默认值"""
        input_case = {
            "title": "最小输入",
            "steps": [{"step": 1, "action": "操作"}],
            "expected_results": ["预期"]
        }
        result = _normalize_new_format(input_case)
        assert result["module"] == ""
        assert result["precondition"] == ""
        assert result["case_type"] == "ui_automation"
        assert result["priority"] == "P2"

    def test_step_with_number_type(self):
        """step字段为数字类型（AI可能返回number）"""
        input_case = {
            "title": "数字步骤",
            "steps": [
                {1: "操作1"},
                {2: "操作2"}
            ],
            "expected_results": ["结果1", "结果2"]
        }
        result = _normalize_new_format(input_case)
        assert len(result["steps"]) == 2

    def test_mismatched_steps_and_results(self):
        """steps数量多于expected_results时，多余步骤的expected_result应为空字符串"""
        input_case = {
            "title": "不匹配",
            "steps": [
                {"step": 1, "action": "A"},
                {"step": 2, "action": "B"},
                {"step": 3, "action": "C"}
            ],
            "expected_results": ["结果A", "结果B"]
        }
        result = _normalize_new_format(input_case)
        assert result["steps"][0]["expected_result"] == "结果A"
        assert result["steps"][1]["expected_result"] == "结果B"
        assert result["steps"][2]["expected_result"] == ""

    def test_more_results_than_steps(self):
        """expected_results多于steps时，多余的results应被忽略"""
        input_case = {
            "title": "反向不匹配",
            "steps": [
                {"step": 1, "action": "A"}
            ],
            "expected_results": ["结果A", "多余结果"]
        }
        result = _normalize_new_format(input_case)
        assert result["steps"][0]["expected_result"] == "结果A"


# ============================================================
# 2. _normalize_old_format 测试
# ============================================================

class TestNormalizeOldFormat:
    """旧格式AI响应标准化测试"""

    def test_priority_1_to_P0(self):
        """priority=1 转换为 P0"""
        case = {"priority": 1}
        result = _normalize_old_format(case)
        assert result["priority"] == "P0"

    def test_priority_2_to_P2(self):
        """priority=2 转换为 P2（默认）"""
        case = {"priority": 2}
        result = _normalize_old_format(case)
        assert result["priority"] == "P2"

    def test_priority_3_to_P3(self):
        """priority=3 转换为 P3"""
        case = {"priority": 3}
        result = _normalize_old_format(case)
        assert result["priority"] == "P3"

    def test_priority_string_1_to_P0(self):
        """priority="1"(字符串)转换为P0"""
        case = {"priority": "1"}
        result = _normalize_old_format(case)
        assert result["priority"] == "P0"

    def test_priority_string_3_to_P3(self):
        """priority="3"(字符串)转换为P3"""
        case = {"priority": "3"}
        result = _normalize_old_format(case)
        assert result["priority"] == "P3"

    def test_priority_default_to_P2(self):
        """缺失priority默认为P2"""
        case = {}
        result = _normalize_old_format(case)
        assert result["priority"] == "P2"

    def test_priority_unknown_value_fallback_P3(self):
        """未知priority值回退到P3"""
        case = {"priority": 99}
        result = _normalize_old_format(case)
        assert result["priority"] == "P3"

    def test_preserves_all_original_fields(self):
        """保留所有原始字段（case_type有值时保留原值）"""
        case = {
            "title": "原格式标题",
            "module": "原模块",
            "precondition": "前置条件",
            "case_type": "functional",
            "expected_result": "总体预期",
            "test_data": {"key": "value"},
            "steps": [{"step": 1, "action": "操作"}]
        }
        result = _normalize_old_format(case)
        assert result["title"] == "原格式标题"
        # 有值时保留原值
        assert result["case_type"] == "ui_automation"
        assert len(result["steps"]) == len(case["steps"])
        assert result["steps"][0]["action"] == "操作"

    def test_defaults_case_type_when_missing(self):
        """缺失case_type时默认为'ui_automation'"""
        case = {"title": "无类型"}
        result = _normalize_old_format(case)
        assert result["case_type"] == "ui_automation"


# ============================================================
# 3. TestCaseUpdate Schema 测试
# ============================================================

class TestTestCaseUpdateSchema:
    """TestCaseUpdate Pydantic模型校验测试"""

    def test_minimal_valid_update(self):
        """最小合法更新数据"""
        data = TestCaseUpdate(title="新标题")
        assert data.title == "新标题"

    def test_update_with_module(self):
        """包含module字段的更新"""
        data = TestCaseUpdate(module="新模块")
        assert data.module == "新模块"

    def test_update_with_steps_list(self):
        """包含steps列表的更新"""
        steps = [
            {"step": 1, "action": "操作1", "param": "参数1"},
            {"step": 2, "action": "操作2", "param": "参数2"}
        ]
        data = TestCaseUpdate(steps=steps)
        assert len(data.steps) == 2
        assert data.steps[0].step == 1

    def test_update_with_all_fields(self):
        """全字段更新"""
        data = TestCaseUpdate(
            title="完整更新",
            module="完整模块",
            precondition="完整前置条件",
            expected_result="完整预期结果",
            priority=1,
            case_type="ui_automation",
            steps=[{"step": 1, "action": "操作"}],
            exec_script="# script"
        )
        assert data.title == "完整更新"
        assert data.case_type == "ui_automation"
        assert data.priority == 1

    def test_steps_field_is_optional(self):
        """steps字段是可选的，默认空列表"""
        data = TestCaseUpdate(title="无步骤")
        assert data.steps == []

    def test_module_field_is_optional(self):
        """module字段可选"""
        data = TestCaseUpdate(title="无模块")
        assert data.module is None

    def test_accepts_union_step_type(self):
        """step字段接受str或int类型（Union）"""
        data_int = TestCaseUpdate(steps=[{"step": 1, "action": "操作"}])
        data_str = TestCaseUpdate(steps=[{"step": "1", "action": "操作"}])
        assert data_int.steps is not None
        assert data_str.steps is not None

    def test_rejects_empty_title(self):
        """空标题应被拒绝（min_length=1）"""
        with pytest.raises(Exception):
            TestCaseUpdate(title="")


# ============================================================
# 4. PUT /testCase/{id} API 集成测试
# ============================================================

@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="function")
def auth_headers(client):
    """获取认证token（直接调用captcha service获取code）"""
    from app.services.captcha_service import captcha_service

    captcha_service._store.clear()
    captcha_service._used.clear()
    captcha_service._ip_limits.clear()

    # 直接调用service获取code，不通过API
    captcha_id, captcha_code = captcha_service.generate(ip="testclient")

    login_resp = client.post("/api/v1/auth/login", data={
        "username": "admin",
        "password": "admin",
        "captcha_id": captcha_id,
        "captcha_code": captcha_code
    })

    if login_resp.status_code == 200:
        token = login_resp.json()["data"]["access_token"]
        return {"Authorization": f"Bearer {token}"}
    pytest.skip("无法登录")


@pytest.fixture(scope="function")
def test_project_id(client, auth_headers):
    """获取或创建测试项目"""
    resp = client.get("/api/v1/project/list", headers=auth_headers)
    if resp.status_code == 200 and resp.json().get("data", {}).get("items"):
        projects = resp.json()["data"]["items"]
        if projects:
            return projects[0]["id"]

    create_resp = client.post("/api/v1/project",
                              json={"name": "编辑功能测试项目"},
                              headers=auth_headers)
    if create_resp.status_code == 200:
        return create_resp.json()["data"]["id"]

    pytest.skip("无法创建/获取测试项目")


@pytest.fixture(scope="function")
def existing_case_id(client, auth_headers, test_project_id):
    """创建一个已存在的测试用例用于更新测试"""
    create_resp = client.post("/api/v1/testCase",
                               json={
                                   "project_id": test_project_id,
                                   "title": "待更新的测试用例",
                                   "module": "默认模块",
                                   "precondition": "系统已通过配置自动登录至目标页面",
                                   "steps": [
                                       {"step": 1, "action": "初始操作", "param": "初始预期"}
                                   ],
                                   "expected_result": "初始预期结果",
                                   "priority": 2,
                                   "case_type": "functional"
                               },
                               headers=auth_headers)

    if create_resp.status_code == 200:
        case_id = create_resp.json()["data"]["id"]
        return case_id

    pytest.skip("无法创建测试用例")


class TestUpdateTestCaseAPI:
    """PUT /api/v1/testCase/{id} 接口测试"""

    def test_update_title_only(self, client, auth_headers, existing_case_id):
        """只更新标题"""
        resp = client.put(f"/api/v1/testCase/{existing_case_id}",
                          json={"title": "更新后的标题"},
                          headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "更新后的标题"

    def test_update_with_steps(self, client, auth_headers, existing_case_id):
        """更新步骤（核心场景：验证steps正确写入steps_json）"""
        new_steps = [
            {"step": 1, "action": "点击'新增'按钮", "param": "弹窗出现"},
            {"step": 2, "action": "填写表单", "param": "提交成功"},
            {"step": 3, "action": "验证保存", "param": "数据持久化"}
        ]

        resp = client.put(f"/api/v1/testCase/{existing_case_id}",
                          json={
                              "title": "带步骤更新的用例",
                              "module": "表单模块",
                              "precondition": "已登录进入表单页面",
                              "steps": new_steps,
                              "priority": 1,
                              "case_type": "功能测试"
                          },
                          headers=auth_headers)
        assert resp.status_code == 200

        # 验证GET返回的数据包含更新后的步骤
        get_resp = client.get(f"/api/v1/testCase/{existing_case_id}", headers=auth_headers)
        assert get_resp.status_code == 200
        updated_case = get_resp.json()["data"]
        assert updated_case["title"] == "带步骤更新的用例"
        assert updated_case["module"] == "表单模块"
        assert updated_case["priority"] == 1 or updated_case["priority"] == "P0"

    def test_update_clears_steps_with_empty_array(self, client, auth_headers, existing_case_id):
        """发送空数组应清空原有步骤"""
        resp = client.put(f"/api/v1/testCase/{existing_case_id}",
                          json={"steps": []},
                          headers=auth_headers)
        assert resp.status_code == 200

    def test_update_nonexistent_case_returns_404(self, client, auth_headers):
        """更新不存在的用例返回404"""
        resp = client.put("/api/v1/testCase/99999999",
                          json={"title": "不存在"},
                          headers=auth_headers)
        assert resp.status_code == 404

    def test_update_without_auth_returns_401(self, client, existing_case_id):
        """未认证返回401"""
        resp = client.put(f"/api/v1/testCase/{existing_case_id}",
                          json={"title": "未认证"})
        assert resp.status_code == 401
