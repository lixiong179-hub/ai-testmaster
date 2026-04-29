"""
测试数据API端点单元测试

测试范围:
- 测试数据CRUD API
- 测试数据生成API
- 自动推断生成API
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from app.main import app
from app.models.test_data import TestData, DataType, GenerationRule
from app.models.user import User
from app.api.v1.endpoints import auth


# 创建测试客户端
client = TestClient(app)

# 模拟当前用户依赖
def mock_get_current_user():
    user = Mock(spec=User)
    user.id = 1
    user.username = "test_user"
    user.is_active = True
    return user


class TestTestDataAPI:
    """测试数据API测试类"""

    @pytest.fixture
    def mock_current_user(self):
        """创建模拟当前用户"""
        user = Mock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.is_active = True
        return user

    @pytest.fixture
    def sample_test_data_dict(self):
        """创建示例测试数据字典"""
        return {
            "id": 1,
            "step_id": 100,
            "field_name": "username",
            "field_type": "text",
            "data_value": None,
            "generation_rule": "random",
            "rule_config": None,
            "min_length": 6,
            "max_length": 20,
            "min_value": None,
            "max_value": None,
            "enum_values": None,
            "description": "用户名",
            "is_required": True,
            "sort_order": 0
        }

    def test_create_test_data_success(self, mock_current_user, sample_test_data_dict):
        """测试创建测试数据成功"""
        # 准备
        create_data = {
            "step_id": 100,
            "field_name": "email",
            "field_type": "email",
            "generation_rule": "random",
            "is_required": True
        }

        # 执行 - 覆盖认证依赖
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.create_test_data.return_value = Mock(
                to_dict=lambda: {**sample_test_data_dict, "field_name": "email", "field_type": "email"}
            )
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data", json=create_data)
        
        # 清理
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["field_name"] == "email"
        assert result["field_type"] == "email"

    def test_create_test_data_validation_error(self, mock_current_user):
        """测试创建测试数据验证错误"""
        # 准备 - 缺少必填字段
        create_data = {
            "field_name": "email"
            # 缺少 step_id 和 field_type
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.post("/api/v1/test-data", json=create_data)
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 400  # 验证错误(全局异常处理器转换)

    def test_get_test_data_success(self, mock_current_user, sample_test_data_dict):
        """测试获取单个测试数据成功"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.get_test_data.return_value = Mock(to_dict=lambda: sample_test_data_dict)
            mock_service.return_value = mock_service_instance

            response = client.get("/api/v1/test-data/1")
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["id"] == 1
        assert result["field_name"] == "username"

    def test_get_test_data_not_found(self, mock_current_user):
        """测试获取不存在的测试数据"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.get_test_data.return_value = None
            mock_service.return_value = mock_service_instance

            response = client.get("/api/v1/test-data/999")
        
        app.dependency_overrides.clear()

        # 验证 - API使用统一的错误响应格式
        assert response.status_code == 404
        result = response.json()
        assert "message" in result or "msg" in result
        assert "不存在" in (result.get("message") or result.get("msg", ""))

    def test_get_test_data_by_step_success(self, mock_current_user, sample_test_data_dict):
        """测试获取步骤的所有测试数据成功"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.get_test_data_by_step.return_value = [
                Mock(to_dict=lambda: sample_test_data_dict),
                Mock(to_dict=lambda: {**sample_test_data_dict, "id": 2, "field_name": "password", "field_type": "text"})
            ]
            mock_service.return_value = mock_service_instance

            response = client.get("/api/v1/test-data/step/100")
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["step_id"] == 100
        assert len(result["data_list"]) == 2
        assert result["data_list"][0]["field_name"] == "username"
        assert result["data_list"][1]["field_name"] == "password"

    def test_update_test_data_success(self, mock_current_user, sample_test_data_dict):
        """测试更新测试数据成功"""
        # 准备
        update_data = {
            "field_name": "new_username",
            "is_required": False
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.update_test_data.return_value = Mock(
                to_dict=lambda: {**sample_test_data_dict, "field_name": "new_username", "is_required": False}
            )
            mock_service.return_value = mock_service_instance

            response = client.put("/api/v1/test-data/1", json=update_data)
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["field_name"] == "new_username"
        assert result["is_required"] is False

    def test_update_test_data_not_found(self, mock_current_user):
        """测试更新不存在的测试数据"""
        # 准备
        update_data = {"field_name": "new_name"}

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.update_test_data.return_value = None
            mock_service.return_value = mock_service_instance

            response = client.put("/api/v1/test-data/999", json=update_data)
        
        app.dependency_overrides.clear()

        # 验证 - API使用统一的错误响应格式
        assert response.status_code == 404
        result = response.json()
        assert "message" in result or "msg" in result
        assert "不存在" in (result.get("message") or result.get("msg", ""))

    def test_delete_test_data_success(self, mock_current_user):
        """测试删除测试数据成功"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.delete_test_data.return_value = True
            mock_service.return_value = mock_service_instance

            response = client.delete("/api/v1/test-data/1")
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "删除成功" in result["message"]

    def test_delete_test_data_not_found(self, mock_current_user):
        """测试删除不存在的测试数据"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.delete_test_data.return_value = False
            mock_service.return_value = mock_service_instance

            response = client.delete("/api/v1/test-data/999")
        
        app.dependency_overrides.clear()

        # 验证 - API使用统一的错误响应格式
        assert response.status_code == 404
        result = response.json()
        assert "message" in result or "msg" in result
        assert "不存在" in (result.get("message") or result.get("msg", ""))

    def test_generate_step_data_success(self, mock_current_user):
        """测试生成步骤数据成功"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.generate_step_data.return_value = {
                "username": "testuser123",
                "password": "Pass123!"
            }
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data/step/100/generate")
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["step_id"] == 100
        assert "username" in result["generated_data"]
        assert "password" in result["generated_data"]

    def test_generate_step_data_error(self, mock_current_user):
        """测试生成步骤数据失败"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.generate_step_data.side_effect = Exception("生成失败")
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data/step/100/generate")
        
        app.dependency_overrides.clear()

        # 验证 - API使用统一的错误响应格式
        assert response.status_code == 500
        result = response.json()
        assert "message" in result or "msg" in result
        assert "生成失败" in (result.get("message") or result.get("msg", ""))

    def test_auto_generate_test_data_success(self, mock_current_user, sample_test_data_dict):
        """测试自动推断生成测试数据成功"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.auto_generate_for_step.return_value = [
                Mock(to_dict=lambda: sample_test_data_dict),
                Mock(to_dict=lambda: {**sample_test_data_dict, "id": 2, "field_name": "password", "field_type": "text"})
            ]
            mock_service.return_value = mock_service_instance

            response = client.post(
                "/api/v1/test-data/step/100/auto-generate",
                params={"action_description": "输入用户名和密码登录系统"}
            )
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["count"] == 2
        assert len(result["data_list"]) == 2

    def test_auto_generate_test_data_no_match(self, mock_current_user):
        """测试自动推断生成 - 无匹配场景"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.auto_generate_for_step.return_value = []
            mock_service.return_value = mock_service_instance

            response = client.post(
                "/api/v1/test-data/step/100/auto-generate",
                params={"action_description": "点击提交按钮"}
            )
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert result["count"] == 0
        assert len(result["data_list"]) == 0

    def test_auto_generate_test_data_error(self, mock_current_user):
        """测试自动推断生成失败"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.auto_generate_for_step.side_effect = Exception("推断失败")
            mock_service.return_value = mock_service_instance

            response = client.post(
                "/api/v1/test-data/step/100/auto-generate",
                params={"action_description": "输入用户名"}
            )
        
        app.dependency_overrides.clear()

        # 验证 - API使用统一的错误响应格式
        assert response.status_code == 500
        result = response.json()
        assert "message" in result or "msg" in result
        assert "生成失败" in (result.get("message") or result.get("msg", ""))


class TestTestDataAPIAuthentication:
    """测试数据API认证测试类"""

    def test_create_test_data_without_auth(self):
        """测试未认证创建测试数据"""
        # 准备
        create_data = {
            "step_id": 100,
            "field_name": "email",
            "field_type": "email"
        }

        # 执行 - 不覆盖认证依赖
        response = client.post("/api/v1/test-data", json=create_data)

        # 验证 - 应该返回401未认证
        assert response.status_code == 401

    def test_get_test_data_without_auth(self):
        """测试未认证获取测试数据"""
        # 执行
        response = client.get("/api/v1/test-data/1")

        # 验证
        assert response.status_code == 401

    def test_update_test_data_without_auth(self):
        """测试未认证更新测试数据"""
        # 执行
        response = client.put("/api/v1/test-data/1", json={"field_name": "new_name"})

        # 验证
        assert response.status_code == 401

    def test_delete_test_data_without_auth(self):
        """测试未认证删除测试数据"""
        # 执行
        response = client.delete("/api/v1/test-data/1")

        # 验证
        assert response.status_code == 401


class TestTestDataAPIEdgeCases:
    """测试数据API边界情况测试类"""

    @pytest.fixture
    def mock_current_user(self):
        """创建模拟当前用户"""
        user = Mock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.is_active = True
        return user

    def test_create_test_data_with_invalid_data_type(self, mock_current_user):
        """测试创建测试数据 - 无效的数据类型"""
        # 准备
        create_data = {
            "step_id": 100,
            "field_name": "test",
            "field_type": "invalid_type",  # 无效类型
            "generation_rule": "random"
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.post("/api/v1/test-data", json=create_data)
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 400

    def test_create_test_data_with_invalid_generation_rule(self, mock_current_user):
        """测试创建测试数据 - 无效的生成规则"""
        # 准备
        create_data = {
            "step_id": 100,
            "field_name": "test",
            "field_type": "text",
            "generation_rule": "invalid_rule"  # 无效规则
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.post("/api/v1/test-data", json=create_data)
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 400

    def test_create_test_data_with_boundary_values(self, mock_current_user):
        """测试创建测试数据 - 边界值"""
        # 准备 - 完整的响应数据
        response_data = {
            "id": 1,
            "step_id": 100,
            "field_name": "a",
            "field_type": "text",
            "data_value": None,
            "generation_rule": "boundary_min",
            "rule_config": None,
            "min_length": 1,
            "max_length": 1000,
            "min_value": 0,
            "max_value": 999999,
            "enum_values": None,
            "description": None,
            "is_required": True,
            "sort_order": 0
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.create_test_data.return_value = Mock(to_dict=lambda: response_data)
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data", json={
                "step_id": 100,
                "field_name": "a",
                "field_type": "text",
                "generation_rule": "boundary_min",
                "min_length": 1,
                "max_length": 1000,
                "min_value": 0,
                "max_value": 999999
            })
        
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200

    def test_get_test_data_with_invalid_id(self, mock_current_user):
        """测试获取测试数据 - 无效ID"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.get("/api/v1/test-data/invalid_id")
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 400

    def test_update_test_data_with_empty_body(self, mock_current_user):
        """测试更新测试数据 - 空请求体"""
        # 准备 - 模拟返回完整数据
        response_data = {
            "id": 1,
            "step_id": 100,
            "field_name": "test",
            "field_type": "text",
            "data_value": None,
            "generation_rule": "random",
            "rule_config": None,
            "min_length": None,
            "max_length": None,
            "min_value": None,
            "max_value": None,
            "enum_values": None,
            "description": None,
            "is_required": True,
            "sort_order": 0
        }

        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.update_test_data.return_value = Mock(to_dict=lambda: response_data)
            mock_service.return_value = mock_service_instance

            response = client.put("/api/v1/test-data/1", json={})
        
        app.dependency_overrides.clear()

        # 验证 - 空请求体应该返回成功（不更新任何字段）
        assert response.status_code == 200

    def test_generate_step_data_with_invalid_step_id(self, mock_current_user):
        """测试生成步骤数据 - 无效步骤ID"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.post("/api/v1/test-data/step/invalid_id/generate")
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 400

    def test_auto_generate_with_empty_description(self, mock_current_user):
        """测试自动推断生成 - 空描述"""
        # 执行
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        response = client.post(
            "/api/v1/test-data/step/100/auto-generate",
            params={"action_description": ""}
        )
        app.dependency_overrides.clear()

        # 验证
        assert response.status_code == 200  # 空描述应该返回空结果


class TestTestDataAPIResponseStructure:
    """测试数据API响应结构测试类"""

    @pytest.fixture
    def mock_current_user(self):
        """创建模拟当前用户"""
        user = Mock(spec=User)
        user.id = 1
        user.username = "test_user"
        user.is_active = True
        return user

    def test_response_structure_create(self, mock_current_user):
        """测试创建响应结构"""
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.create_test_data.return_value = Mock(
                to_dict=lambda: {
                    "id": 1,
                    "step_id": 100,
                    "field_name": "test",
                    "field_type": "text",
                    "data_value": None,
                    "generation_rule": "random",
                    "rule_config": None,
                    "min_length": None,
                    "max_length": None,
                    "min_value": None,
                    "max_value": None,
                    "enum_values": None,
                    "description": None,
                    "is_required": True,
                    "sort_order": 0
                }
            )
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data", json={
                "step_id": 100,
                "field_name": "test",
                "field_type": "text"
            })
        
        app.dependency_overrides.clear()

        result = response.json()
        # 验证响应包含所有必要字段
        assert "id" in result
        assert "step_id" in result
        assert "field_name" in result
        assert "field_type" in result
        assert "is_required" in result

    def test_response_structure_list(self, mock_current_user):
        """测试列表响应结构"""
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.get_test_data_by_step.return_value = []
            mock_service.return_value = mock_service_instance

            response = client.get("/api/v1/test-data/step/100")
        
        app.dependency_overrides.clear()

        result = response.json()
        # 验证列表响应结构
        assert "step_id" in result
        assert "data_list" in result
        assert isinstance(result["data_list"], list)

    def test_response_structure_generate(self, mock_current_user):
        """测试生成响应结构"""
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.generate_step_data.return_value = {"field1": "value1"}
            mock_service.return_value = mock_service_instance

            response = client.post("/api/v1/test-data/step/100/generate")
        
        app.dependency_overrides.clear()

        result = response.json()
        # 验证生成响应结构
        assert "step_id" in result
        assert "generated_data" in result
        assert isinstance(result["generated_data"], dict)

    def test_response_structure_auto_generate(self, mock_current_user):
        """测试自动生成响应结构"""
        app.dependency_overrides[auth.get_current_user] = lambda: mock_current_user
        with patch('app.api.v1.endpoints.test_data.TestDataService') as mock_service:
            mock_service_instance = Mock()
            mock_service_instance.auto_generate_for_step.return_value = []
            mock_service.return_value = mock_service_instance

            response = client.post(
                "/api/v1/test-data/step/100/auto-generate",
                params={"action_description": "测试"}
            )
        
        app.dependency_overrides.clear()

        result = response.json()
        # 验证自动生成响应结构
        assert "success" in result
        assert "count" in result
        assert "data_list" in result
