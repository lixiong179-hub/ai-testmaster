"""A/B测试指标端点 async 测试。

覆盖 3 个端点的正常/异常/边界/权限场景：
    - POST /api/v1/ab-test/experiments/{experiment_id}/metrics — 记录指标
    - GET  /api/v1/ab-test/experiments/{experiment_id}/summary  — 实验汇总
    - GET  /api/v1/ab-test/experiments                          — 实验列表

使用 tests/api/conftest.py 的 async_db / async_auth_client fixture。
所有 async fixture 通过 async_db 事务隔离，测试结束 rollback 不落库。
"""
from typing import Any, Dict, List, Optional

from app.models.ab_test_metric import ABTestMetric


async def _create_metric(
    db,
    *,
    experiment_id: str = "exp_test",
    variant: str = "control",
    metric_name: str = "completeness_score",
    metric_value: float = 80.0,
    project_id: Optional[int] = None,
    test_point_id: Optional[int] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> ABTestMetric:
    """直接通过 ORM 创建一条指标记录，绕过端点供查询类测试使用"""
    row = ABTestMetric(
        experiment_id=experiment_id,
        variant=variant,
        project_id=project_id,
        test_point_id=test_point_id,
        metric_name=metric_name,
        metric_value=metric_value,
        detail=detail,
    )
    db.add(row)
    await db.flush()
    return row


class TestRecordMetric:
    """POST /api/v1/ab-test/experiments/{experiment_id}/metrics 记录指标。"""

    async def test_record_metric_success_without_project(
        self, async_auth_client
    ) -> None:
        """无 project_id 时直接记录，不触发归属校验"""
        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp1/metrics",
            json={
                "variant": "control",
                "metric_name": "completeness_score",
                "metric_value": 75.5,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["msg"] == "指标记录成功"
        data = body["data"]
        assert data["experiment_id"] == "exp1"
        assert data["variant"] == "control"
        assert data["metric_name"] == "completeness_score"
        assert data["metric_value"] == 75.5
        assert data["id"] is not None
        assert data["created_at"] is not None

    async def test_record_metric_with_owned_project(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """project_id 属于当前用户时记录成功"""
        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp2/metrics",
            json={
                "variant": "treatment",
                "metric_name": "step_executable_rate",
                "metric_value": 0.92,
                "project_id": async_test_project.id,
                "test_point_id": 42,
                "detail": {"reason": "test"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["variant"] == "treatment"
        assert data["metric_value"] == 0.92

    async def test_record_metric_with_nonexistent_project(
        self, async_auth_client
    ) -> None:
        """project_id 不存在时返回 404"""
        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp3/metrics",
            json={
                "variant": "control",
                "metric_name": "completeness_score",
                "metric_value": 50.0,
                "project_id": 99999,
            },
        )
        assert resp.status_code == 404
        assert resp.json()["msg"] == "项目不存在"

    async def test_record_metric_invalid_metric_name(
        self, async_auth_client
    ) -> None:
        """metric_name 不在白名单时返回 422"""
        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp4/metrics",
            json={
                "variant": "control",
                "metric_name": "invalid_metric_xyz",
                "metric_value": 1.0,
            },
        )
        assert resp.status_code == 422
        assert "非法指标名称" in resp.json()["msg"]

    async def test_record_metric_missing_variant_field(
        self, async_auth_client
    ) -> None:
        """缺少必填字段 variant 时触发 Pydantic 校验错误，全局处理器返回 400"""
        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp5/metrics",
            json={
                "metric_name": "completeness_score",
                "metric_value": 1.0,
            },
        )
        assert resp.status_code == 400


class TestGetExperimentSummary:
    """GET /api/v1/ab-test/experiments/{experiment_id}/summary 实验汇总。"""

    async def test_summary_empty_experiment(self, async_auth_client) -> None:
        """无数据时返回空 variants"""
        resp = await async_auth_client.get(
            "/api/v1/ab-test/experiments/nonexistent_exp/summary"
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["experiment_id"] == "nonexistent_exp"
        assert data["variants"] == {}

    async def test_summary_with_data(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """有数据时按变体分组统计"""
        await _create_metric(
            async_db, experiment_id="exp_s", variant="control",
            metric_name="completeness_score", metric_value=80.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="exp_s", variant="control",
            metric_name="completeness_score", metric_value=90.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="exp_s", variant="treatment",
            metric_name="completeness_score", metric_value=85.0,
            project_id=async_test_project.id,
        )
        resp = await async_auth_client.get(
            "/api/v1/ab-test/experiments/exp_s/summary"
        )
        assert resp.status_code == 200
        variants = resp.json()["data"]["variants"]
        assert "control" in variants
        assert "treatment" in variants
        control_stats = variants["control"]["completeness_score"]
        assert control_stats["sample_count"] == 2
        assert control_stats["mean"] == 85.0
        assert control_stats["std_dev"] == 5.0
        assert variants["treatment"]["completeness_score"]["sample_count"] == 1

    async def test_summary_filters_by_user_project(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """仅返回当前用户项目下的指标"""
        await _create_metric(
            async_db, experiment_id="exp_filter", variant="control",
            metric_name="completeness_score", metric_value=80.0,
            project_id=async_test_project.id,
        )
        # 别人的项目（project_id 故意设为不存在的大数）
        await _create_metric(
            async_db, experiment_id="exp_filter", variant="control",
            metric_name="completeness_score", metric_value=50.0,
            project_id=99999,
        )
        resp = await async_auth_client.get(
            "/api/v1/ab-test/experiments/exp_filter/summary"
        )
        assert resp.status_code == 200
        variants = resp.json()["data"]["variants"]
        # 仅自己的项目数据被聚合（sample_count=1）
        assert variants["control"]["completeness_score"]["sample_count"] == 1
        assert variants["control"]["completeness_score"]["mean"] == 80.0

    async def test_summary_multi_metric_per_variant(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """同一变体下多个指标分别统计"""
        await _create_metric(
            async_db, experiment_id="exp_multi", variant="control",
            metric_name="completeness_score", metric_value=80.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="exp_multi", variant="control",
            metric_name="step_executable_rate", metric_value=0.9,
            project_id=async_test_project.id,
        )
        resp = await async_auth_client.get(
            "/api/v1/ab-test/experiments/exp_multi/summary"
        )
        assert resp.status_code == 200
        control = resp.json()["data"]["variants"]["control"]
        assert "completeness_score" in control
        assert "step_executable_rate" in control


class TestListExperiments:
    """GET /api/v1/ab-test/experiments 实验列表。"""

    async def test_list_empty(self, async_auth_client) -> None:
        """无数据时返回空列表"""
        resp = await async_auth_client.get("/api/v1/ab-test/experiments")
        assert resp.status_code == 200
        data = resp.json()["data"]
        # create_response(data or {}) 把 falsy 的 [] 转为 {}，遵循统一响应约定
        assert data in ([], {})
        assert resp.json()["msg"] == "获取实验列表成功"

    async def test_list_single_experiment(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """单实验记录返回正确 sample_count"""
        await _create_metric(
            async_db, experiment_id="list_exp1", variant="control",
            metric_name="completeness_score", metric_value=80.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="list_exp1", variant="treatment",
            metric_name="completeness_score", metric_value=85.0,
            project_id=async_test_project.id,
        )
        resp = await async_auth_client.get("/api/v1/ab-test/experiments")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["experiment_id"] == "list_exp1"
        assert data[0]["sample_count"] == 2

    async def test_list_multi_experiments_ordered(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """多实验按 experiment_id 升序返回"""
        await _create_metric(
            async_db, experiment_id="zzz_exp", variant="control",
            metric_name="completeness_score", metric_value=1.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="aaa_exp", variant="control",
            metric_name="completeness_score", metric_value=2.0,
            project_id=async_test_project.id,
        )
        await _create_metric(
            async_db, experiment_id="mmm_exp", variant="control",
            metric_name="completeness_score", metric_value=3.0,
            project_id=async_test_project.id,
        )
        resp = await async_auth_client.get("/api/v1/ab-test/experiments")
        assert resp.status_code == 200
        ids = [item["experiment_id"] for item in resp.json()["data"]]
        assert ids == ["aaa_exp", "mmm_exp", "zzz_exp"]

    async def test_list_filters_by_user_project(
        self, async_db, async_auth_client, async_test_project
    ) -> None:
        """仅列出当前用户项目下的实验"""
        await _create_metric(
            async_db, experiment_id="owned_exp", variant="control",
            metric_name="completeness_score", metric_value=1.0,
            project_id=async_test_project.id,
        )
        # 别人项目（不应被列出）
        await _create_metric(
            async_db, experiment_id="others_exp", variant="control",
            metric_name="completeness_score", metric_value=1.0,
            project_id=88888,
        )
        resp = await async_auth_client.get("/api/v1/ab-test/experiments")
        assert resp.status_code == 200
        ids = [item["experiment_id"] for item in resp.json()["data"]]
        assert "owned_exp" in ids
        assert "others_exp" not in ids


class TestAbTestPermissions:
    """A/B 测试端点鉴权场景。"""

    async def test_record_metric_unauthenticated(self, async_client) -> None:
        """未认证请求被 oauth2_scheme 拦截返回 401"""
        resp = await async_client.post(
            "/api/v1/ab-test/experiments/exp_auth/metrics",
            json={
                "variant": "control",
                "metric_name": "completeness_score",
                "metric_value": 1.0,
            },
        )
        assert resp.status_code == 401

    async def test_summary_unauthenticated(self, async_client) -> None:
        resp = await async_client.get(
            "/api/v1/ab-test/experiments/exp_auth/summary"
        )
        assert resp.status_code == 401

    async def test_list_unauthenticated(self, async_client) -> None:
        resp = await async_client.get("/api/v1/ab-test/experiments")
        assert resp.status_code == 401

    async def test_record_metric_other_users_project_forbidden(
        self, async_db, async_auth_client, async_test_user
    ) -> None:
        """project_id 属于其他用户时返回 403"""
        # 创建另一个用户拥有的项目（直接 ORM 插入）
        from app.models.user import User
        from app.utils.jwt_utils import get_password_hash

        other_user = User(
            username="other_user_for_ab_test",
            email="other_ab@test.com",
            password_hash=get_password_hash("Other@123456"),
            is_active=True,
            is_superuser=False,
        )
        async_db.add(other_user)
        await async_db.flush()

        from app.models.project import Project

        other_project = Project(
            name="other_project_ab_test",
            user_id=other_user.id,
            description="other user project",
            status=1,
            project_type="web",
        )
        async_db.add(other_project)
        await async_db.flush()

        resp = await async_auth_client.post(
            "/api/v1/ab-test/experiments/exp_forbidden/metrics",
            json={
                "variant": "control",
                "metric_name": "completeness_score",
                "metric_value": 1.0,
                "project_id": other_project.id,
            },
        )
        assert resp.status_code == 403
        assert resp.json()["msg"] == "无权限操作此项目"
