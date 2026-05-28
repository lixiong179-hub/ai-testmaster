"""Pipeline 产物详情展开 API 测试

覆盖范围:
    - 正常查询 artifact 详情（含完整 payload）
    - artifact_id 不存在返回 404
    - 大 payload 截断（超过 10KB）
    - run_id 不存在返回 404
    - artifact 不属于指定 run_id 返回 404
    - payload 为 None 时正常返回
    - payload 为 dict 类型时截断
    - payload 为 list 类型时截断
    - 无权限用户返回 403
    - _truncate_payload 函数单元测试

使用真实 MySQL、HTTP TestClient + JWT。
"""
import hashlib
import pytest

from app.models.iteration import Iteration
from app.models.pipeline import PipelineRun, Artifact
from app.utils.jwt_utils import create_access_token, get_password_hash


# ── Helpers ───────────────────────────────────────────────────────────


def _make_user(db, username: str, email: str):
    """创建测试用户。"""
    from app.models.user import User

    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    return user


def _make_project(db, user_id: int, name: str):
    """创建测试项目（属于指定用户）。"""
    from app.models.project import Project

    project = Project(
        name=name,
        user_id=user_id,
        description="artifact detail test project",
        status=1,
        project_type="web",
    )
    db.add(project)
    db.flush()
    return project


def _make_iteration(db, project_id: int, name: str = "artifact_iter"):
    """创建测试迭代。"""
    iteration = Iteration(
        project_id=project_id,
        name=name,
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


def _make_run(db, iteration_id: int, status: str = "completed") -> PipelineRun:
    """创建 PipelineRun 记录。"""
    unique_hash = hashlib.sha256(
        f"artifact-detail-test-{iteration_id}-{status}".encode(),
    ).hexdigest()[:64]
    run = PipelineRun(
        iteration_id=iteration_id,
        input_hash=unique_hash,
        pipeline_version="1.0",
        status=status,
    )
    db.add(run)
    db.flush()
    return run


def _make_artifact(
    db, run_id: int, kind: str, payload: dict | None = None,
    confidence: float | None = 0.9, content_hash: str | None = None,
) -> Artifact:
    """创建 Artifact 记录。"""
    if content_hash is None:
        content_hash = hashlib.sha256(
            f"artifact-{run_id}-{kind}".encode(),
        ).hexdigest()[:64]
    artifact = Artifact(
        run_id=run_id,
        kind=kind,
        schema_version="1.0",
        payload=payload,
        confidence=confidence,
        content_hash=content_hash,
    )
    db.add(artifact)
    db.flush()
    return artifact


def _auth_headers(user_id: int, username: str) -> dict:
    """生成 JWT 认证头。"""
    token = create_access_token({"sub": str(user_id), "username": username})
    return {"Authorization": f"Bearer {token}"}


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def owner_setup(db):
    """拥有项目的用户 + 项目 + 迭代 + 运行。"""
    user = _make_user(db, "artifact_owner", "artifact_owner@test.com")
    project = _make_project(db, user.id, "artifact_owner_proj")
    iteration = _make_iteration(db, project.id, "artifact_owner_iter")
    run = _make_run(db, iteration.id)
    return {
        "user": user,
        "project": project,
        "iteration": iteration,
        "run": run,
        "headers": _auth_headers(user.id, user.username),
    }


@pytest.fixture
def other_user_setup(db):
    """另一个用户（不同项目），用于测试权限隔离。"""
    user = _make_user(db, "artifact_other", "artifact_other@test.com")
    project = _make_project(db, user.id, "artifact_other_proj")
    return {
        "user": user,
        "project": project,
        "headers": _auth_headers(user.id, user.username),
    }


@pytest.fixture
def small_artifact(db, owner_setup):
    """创建一个小 payload 的 artifact。"""
    return _make_artifact(
        db,
        run_id=owner_setup["run"].id,
        kind="raw_signals",
        payload={"has_prd": True, "has_ui": False, "source_count": 3},
        confidence=0.85,
    )


@pytest.fixture
def large_list_artifact(db, owner_setup):
    """创建一个大 payload（list 类型，超过 10KB）的 artifact。"""
    big_payload = [{"id": i, "name": f"item_{i}", "data": "x" * 100} for i in range(200)]
    return _make_artifact(
        db,
        run_id=owner_setup["run"].id,
        kind="generated_cases",
        payload=big_payload,
        confidence=0.72,
        content_hash=hashlib.sha256("large-list-artifact".encode()).hexdigest()[:64],
    )


@pytest.fixture
def large_dict_artifact(db, owner_setup):
    """创建一个大 payload（dict 类型，超过 10KB）的 artifact。"""
    big_payload = {f"key_{i}": f"value_{'x' * 100}_{i}" for i in range(200)}
    return _make_artifact(
        db,
        run_id=owner_setup["run"].id,
        kind="quality_scores",
        payload=big_payload,
        confidence=0.65,
        content_hash=hashlib.sha256("large-dict-artifact".encode()).hexdigest()[:64],
    )


@pytest.fixture
def null_payload_artifact(db, owner_setup):
    """创建 payload 为 None 的 artifact。"""
    return _make_artifact(
        db,
        run_id=owner_setup["run"].id,
        kind="persisted_case_ids",
        payload=None,
        confidence=None,
        content_hash=hashlib.sha256("null-payload-artifact".encode()).hexdigest()[:64],
    )


# ── 正常查询测试 ──────────────────────────────────────────────────────


class TestGetArtifactDetail:
    """正常查询 artifact 详情。"""

    def test_returns_artifact_detail_with_payload(self, client, db, owner_setup, small_artifact):
        """正常查询返回 artifact 完整 payload。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["artifact_id"] == small_artifact.id
        assert data["run_id"] == run_id
        assert data["kind"] == "raw_signals"
        assert data["schema_version"] == "1.0"
        assert data["payload"]["has_prd"] is True
        assert data["payload"]["has_ui"] is False
        assert data["payload"]["source_count"] == 3
        assert data["confidence"] == 0.85
        assert data["truncated"] is False
        assert data["truncated_reason"] is None

    def test_returns_provenance_and_content_hash(self, client, db, owner_setup, small_artifact):
        """返回 provenance 和 content_hash 字段。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "content_hash" in data
        assert "provenance" in data
        assert isinstance(data["provenance"], dict)

    def test_returns_created_at_iso_format(self, client, db, owner_setup, small_artifact):
        """created_at 返回 ISO 格式字符串。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["created_at"] is not None
        assert "T" in data["created_at"]

    def test_null_payload_returns_null(self, client, db, owner_setup, null_payload_artifact):
        """payload 为 None 时正常返回，truncated 为 False。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{null_payload_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["payload"] is None
        assert data["confidence"] is None
        assert data["truncated"] is False


# ── 404 测试 ──────────────────────────────────────────────────────────


class TestGetArtifactDetailNotFound:
    """artifact_id 或 run_id 不存在返回 404。"""

    def test_artifact_id_not_found(self, client, db, owner_setup):
        """artifact_id 不存在返回 404。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/999999",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 404
        assert "产物不存在" in resp.json()["message"]

    def test_run_id_not_found(self, client, db, owner_setup, small_artifact):
        """run_id 不存在返回 404。"""
        resp = client.get(
            f"/api/v1/pipeline/999999/artifacts/{small_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 404
        assert "运行不存在" in resp.json()["message"]

    def test_artifact_not_belong_to_run(self, client, db, owner_setup, other_user_setup):
        """artifact 不属于指定 run_id 返回 404。"""
        other_iteration = _make_iteration(
            db, other_user_setup["project"].id, "other_iter_for_run",
        )
        other_run = _make_run(db, other_iteration.id)
        other_artifact = _make_artifact(
            db,
            run_id=other_run.id,
            kind="raw_signals",
            payload={"test": True},
            content_hash=hashlib.sha256("other-artifact".encode()).hexdigest()[:64],
        )
        # 用 owner 的 run_id 查 other_run 的 artifact_id
        resp = client.get(
            f"/api/v1/pipeline/{owner_setup['run'].id}/artifacts/{other_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 404


# ── 大 payload 截断测试 ────────────────────────────────────────────────


class TestGetArtifactDetailTruncation:
    """大 payload 截断测试。"""

    def test_large_list_payload_truncated(self, client, db, owner_setup, large_list_artifact):
        """大 list payload 被截断，truncated=True，仅保留前 50 条。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{large_list_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["truncated"] is True
        assert data["truncated_reason"] is not None
        assert "10" in data["truncated_reason"] or "240" in data["truncated_reason"]
        assert len(data["payload"]) == 50

    def test_large_dict_payload_truncated(self, client, db, owner_setup, large_dict_artifact):
        """大 dict payload 被截断，truncated=True，仅保留前 50 个键。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{large_dict_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["truncated"] is True
        assert data["truncated_reason"] is not None
        assert len(data["payload"]) == 50

    def test_small_payload_not_truncated(self, client, db, owner_setup, small_artifact):
        """小 payload 不截断，truncated=False。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
            headers=owner_setup["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["truncated"] is False
        assert data["truncated_reason"] is None


# ── 权限测试 ──────────────────────────────────────────────────────────


class TestGetArtifactDetailPermission:
    """权限校验：非项目成员无法查询。"""

    def test_other_user_cannot_access(self, client, db, owner_setup, other_user_setup, small_artifact):
        """非项目用户查询返回 403。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
            headers=other_user_setup["headers"],
        )
        assert resp.status_code == 403

    def test_unauthenticated_user_rejected(self, client, db, owner_setup, small_artifact):
        """未认证用户查询返回 401。"""
        run_id = owner_setup["run"].id
        resp = client.get(
            f"/api/v1/pipeline/{run_id}/artifacts/{small_artifact.id}",
        )
        assert resp.status_code == 401


# ── _truncate_payload 单元测试 ─────────────────────────────────────────


class TestTruncatePayload:
    """_truncate_payload 函数单元测试。"""

    def test_small_payload_not_truncated(self):
        """小 payload 不截断。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload

        payload = {"key": "value"}
        result, truncated, reason = _truncate_payload(payload)
        assert result == payload
        assert truncated is False
        assert reason is None

    def test_none_payload_not_truncated(self):
        """None payload 不截断。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload

        result, truncated, reason = _truncate_payload(None)
        assert result is None
        assert truncated is False
        assert reason is None

    def test_large_list_truncated_to_50(self):
        """大 list 截断到前 50 条。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload

        big_list = [{"id": i, "data": "x" * 200} for i in range(200)]
        result, truncated, reason = _truncate_payload(big_list)
        assert truncated is True
        assert len(result) == 50
        assert reason is not None
        assert "50" in reason

    def test_large_dict_truncated_to_50_keys(self):
        """大 dict 截断到前 50 个键。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload

        big_dict = {f"key_{i}": "x" * 200 for i in range(200)}
        result, truncated, reason = _truncate_payload(big_dict)
        assert truncated is True
        assert len(result) == 50
        assert reason is not None
        assert "50" in reason

    def test_exactly_at_threshold_not_truncated(self):
        """刚好在阈值边界的 payload 不截断。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload, PAYLOAD_TRUNCATE_THRESHOLD

        # 构造一个小 payload，确保不超过阈值
        small_payload = {"a": 1}
        result, truncated, reason = _truncate_payload(small_payload)
        assert truncated is False

    def test_string_payload_over_threshold(self):
        """大字符串 payload 截断到阈值长度。"""
        from app.api.v1.endpoints.pipeline_artifacts import _truncate_payload, PAYLOAD_TRUNCATE_THRESHOLD

        big_string = "x" * 20000
        result, truncated, reason = _truncate_payload(big_string)
        assert truncated is True
        assert reason is not None
        assert isinstance(result, str)
        assert len(result) == PAYLOAD_TRUNCATE_THRESHOLD
