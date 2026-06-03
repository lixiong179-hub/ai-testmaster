"""
运行时特性开关 API 测试

覆盖场景：CRUD、启用/禁用切换、灰度比例评估、项目级定向投放
"""
import pytest
from app.models.feature_flag import FeatureFlag
from app.services.feature_flag_service import FeatureFlagService


class TestFeatureFlagCRUD:
    """特性开关 CRUD 测试"""

    def test_create_flag(self, db):
        """创建特性开关"""
        service = FeatureFlagService(db)
        flag = service.create_flag(
            key="test_flag",
            name="测试开关",
            description="用于测试的特性开关",
        )
        assert flag.key == "test_flag"
        assert flag.name == "测试开关"
        assert flag.description == "用于测试的特性开关"
        assert flag.enabled is True
        assert flag.rollout_percentage == 100
        assert flag.target_type == "all"
        assert flag.target_project_ids is None

    def test_create_flag_duplicate_key_raises(self, db):
        """重复 key 创建应抛出 ValueError"""
        service = FeatureFlagService(db)
        service.create_flag(key="dup_flag", name="重复开关")
        with pytest.raises(ValueError, match="特性开关已存在"):
            service.create_flag(key="dup_flag", name="另一个开关")

    def test_get_flag(self, db):
        """获取特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="get_flag", name="获取测试")
        flag = service.get_flag("get_flag")
        assert flag is not None
        assert flag.key == "get_flag"

    def test_get_flag_not_found(self, db):
        """获取不存在的开关返回 None"""
        service = FeatureFlagService(db)
        flag = service.get_flag("nonexistent")
        assert flag is None

    def test_list_flags(self, db):
        """列出所有特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="list_a", name="列表A")
        service.create_flag(key="list_b", name="列表B")
        flags = service.list_flags()
        keys = [f.key for f in flags]
        assert "list_a" in keys
        assert "list_b" in keys

    def test_update_flag(self, db):
        """更新特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="update_flag", name="更新前")
        updated = service.update_flag("update_flag", name="更新后", rollout_percentage=50)
        assert updated.name == "更新后"
        assert updated.rollout_percentage == 50

    def test_update_flag_not_found_raises(self, db):
        """更新不存在的开关应抛出 ValueError"""
        service = FeatureFlagService(db)
        with pytest.raises(ValueError, match="特性开关不存在"):
            service.update_flag("nonexistent", name="不存在")

    def test_delete_flag(self, db):
        """删除特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="delete_flag", name="删除测试")
        result = service.delete_flag("delete_flag")
        assert result is True
        assert service.get_flag("delete_flag") is None

    def test_delete_flag_not_found_raises(self, db):
        """删除不存在的开关应抛出 ValueError"""
        service = FeatureFlagService(db)
        with pytest.raises(ValueError, match="特性开关不存在"):
            service.delete_flag("nonexistent")


class TestFeatureFlagToggle:
    """特性开关启用/禁用切换测试"""

    def test_toggle_flag_disable(self, db):
        """禁用特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="toggle_off", name="禁用测试", enabled=True)
        flag = service.toggle_flag("toggle_off", enabled=False)
        assert flag.enabled is False

    def test_toggle_flag_enable(self, db):
        """启用特性开关"""
        service = FeatureFlagService(db)
        service.create_flag(key="toggle_on", name="启用测试", enabled=False)
        flag = service.toggle_flag("toggle_on", enabled=True)
        assert flag.enabled is True

    def test_toggle_flag_not_found_raises(self, db):
        """切换不存在的开关应抛出 ValueError"""
        service = FeatureFlagService(db)
        with pytest.raises(ValueError, match="特性开关不存在"):
            service.toggle_flag("nonexistent", enabled=True)


class TestFeatureFlagEvaluate:
    """特性开关灰度评估测试"""

    def test_evaluate_flag_not_found(self, db):
        """不存在的开关评估为 False"""
        service = FeatureFlagService(db)
        assert service.evaluate("nonexistent") is False

    def test_evaluate_flag_disabled(self, db):
        """disabled 开关评估为 False"""
        service = FeatureFlagService(db)
        service.create_flag(key="disabled_flag", name="禁用", enabled=False)
        assert service.evaluate("disabled_flag") is False

    def test_evaluate_flag_enabled_full_rollout(self, db):
        """enabled + rollout=100 评估为 True"""
        service = FeatureFlagService(db)
        service.create_flag(key="full_rollout", name="全量", enabled=True, rollout_percentage=100)
        assert service.evaluate("full_rollout") is True

    def test_evaluate_flag_zero_rollout(self, db):
        """rollout_percentage=0 评估为 False"""
        service = FeatureFlagService(db)
        service.create_flag(key="zero_rollout", name="零灰度", enabled=True, rollout_percentage=0)
        assert service.evaluate("zero_rollout") is False

    def test_evaluate_flag_specific_target_match(self, db):
        """target_type=specific 且 project_id 在 target_project_ids 中评估为 True"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="specific_match",
            name="定向匹配",
            enabled=True,
            rollout_percentage=100,
            target_type="specific",
            target_project_ids=[1, 2, 3],
        )
        assert service.evaluate("specific_match", project_id=2) is True

    def test_evaluate_flag_specific_target_no_match(self, db):
        """target_type=specific 且 project_id 不在 target_project_ids 中评估为 False"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="specific_no_match",
            name="定向不匹配",
            enabled=True,
            rollout_percentage=100,
            target_type="specific",
            target_project_ids=[1, 2, 3],
        )
        assert service.evaluate("specific_no_match", project_id=99) is False

    def test_evaluate_flag_specific_no_project_id(self, db):
        """target_type=specific 且未传 project_id 评估为 False"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="specific_no_pid",
            name="定向无项目",
            enabled=True,
            rollout_percentage=100,
            target_type="specific",
            target_project_ids=[1, 2, 3],
        )
        assert service.evaluate("specific_no_pid") is False

    def test_evaluate_flag_rollout_deterministic(self, db):
        """灰度比例评估结果确定性：同一 key+project_id 多次调用结果一致"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="rollout_50",
            name="50%灰度",
            enabled=True,
            rollout_percentage=50,
        )
        results = [service.evaluate("rollout_50", project_id=42) for _ in range(10)]
        assert all(r == results[0] for r in results)

    def test_evaluate_flag_rollout_distribution(self, db):
        """灰度比例分布合理性：rollout_percentage=50 时约50%的 project_id 评估为 True"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="rollout_dist",
            name="灰度分布",
            enabled=True,
            rollout_percentage=50,
        )
        true_count = sum(
            1 for pid in range(1, 101)
            if service.evaluate("rollout_dist", project_id=pid)
        )
        assert 20 <= true_count <= 80, f"灰度分布偏差过大: {true_count}/100"

    def test_is_enabled_with_context(self, db):
        """is_enabled 通过 context 传递 project_id"""
        service = FeatureFlagService(db)
        service.create_flag(
            key="ctx_flag",
            name="上下文测试",
            enabled=True,
            rollout_percentage=100,
            target_type="specific",
            target_project_ids=[10],
        )
        assert service.is_enabled("ctx_flag", {"project_id": 10}) is True
        assert service.is_enabled("ctx_flag", {"project_id": 99}) is False
        assert service.is_enabled("ctx_flag") is False


class TestFeatureFlagAPI:
    """特性开关 API 端点测试"""

    def test_list_flags_empty(self, client, authHeaders):
        """空列表"""
        resp = client.get("/api/v1/feature-flags/", headers=authHeaders)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_flag_via_api(self, client, adminAuthHeaders):
        """通过 API 创建特性开关"""
        resp = client.post(
            "/api/v1/feature-flags/",
            json={
                "key": "api_flag",
                "name": "API创建开关",
                "description": "通过API创建",
                "enabled": True,
                "rollout_percentage": 80,
                "target_type": "all",
            },
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["key"] == "api_flag"
        assert data["name"] == "API创建开关"
        assert data["rollout_percentage"] == 80

    def test_create_flag_duplicate_via_api(self, client, adminAuthHeaders):
        """通过 API 重复创建返回 409"""
        payload = {"key": "dup_api", "name": "重复"}
        client.post("/api/v1/feature-flags/", json=payload, headers=adminAuthHeaders)
        resp = client.post("/api/v1/feature-flags/", json=payload, headers=adminAuthHeaders)
        assert resp.status_code == 409

    def test_update_flag_via_api(self, client, adminAuthHeaders):
        """通过 API 更新特性开关"""
        client.post(
            "/api/v1/feature-flags/",
            json={"key": "upd_api", "name": "更新前"},
            headers=adminAuthHeaders,
        )
        resp = client.put(
            "/api/v1/feature-flags/upd_api",
            json={"name": "更新后", "rollout_percentage": 30},
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "更新后"
        assert data["rollout_percentage"] == 30

    def test_update_flag_not_found_via_api(self, client, adminAuthHeaders):
        """通过 API 更新不存在的开关返回 404"""
        resp = client.put(
            "/api/v1/feature-flags/nonexistent",
            json={"name": "不存在"},
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 404

    def test_toggle_flag_via_api(self, client, adminAuthHeaders):
        """通过 API 切换特性开关"""
        client.post(
            "/api/v1/feature-flags/",
            json={"key": "toggle_api", "name": "切换测试", "enabled": True},
            headers=adminAuthHeaders,
        )
        resp = client.post(
            "/api/v1/feature-flags/toggle_api/toggle?enabled=false",
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is False

    def test_toggle_flag_not_found_via_api(self, client, adminAuthHeaders):
        """通过 API 切换不存在的开关返回 404"""
        resp = client.post(
            "/api/v1/feature-flags/nonexistent/toggle?enabled=true",
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 404

    def test_delete_flag_via_api(self, client, adminAuthHeaders):
        """通过 API 删除特性开关"""
        client.post(
            "/api/v1/feature-flags/",
            json={"key": "del_api", "name": "删除测试"},
            headers=adminAuthHeaders,
        )
        resp = client.delete("/api/v1/feature-flags/del_api", headers=adminAuthHeaders)
        assert resp.status_code == 200

    def test_delete_flag_not_found_via_api(self, client, adminAuthHeaders):
        """通过 API 删除不存在的开关返回 404"""
        resp = client.delete("/api/v1/feature-flags/nonexistent", headers=adminAuthHeaders)
        assert resp.status_code == 404

    def test_create_flag_with_specific_target(self, client, adminAuthHeaders):
        """通过 API 创建项目级定向开关"""
        resp = client.post(
            "/api/v1/feature-flags/",
            json={
                "key": "specific_api",
                "name": "项目级开关",
                "target_type": "specific",
                "target_project_ids": [1, 2, 3],
                "rollout_percentage": 100,
            },
            headers=adminAuthHeaders,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["target_type"] == "specific"
        assert data["target_project_ids"] == [1, 2, 3]

    def test_unauthenticated_access(self, client):
        """未认证访问返回错误"""
        resp = client.get("/api/v1/feature-flags/")
        assert resp.status_code in (401, 403)
