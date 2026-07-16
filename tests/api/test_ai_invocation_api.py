"""
AI 调用审计增强 API 测试

测试范围：
    - AICallLog 新增字段写入（同步，使用 record_call，不调用端点）
    - AIErrorCode 枚举值（纯枚举测试）
    - 成本聚合查询 API /stats（async endpoint + async client）
    - 调用记录列表 API /list（async endpoint + async client）

迁移说明（任务1 续作 - 端测双迁）:
    endpoint 已迁至 async（AsyncSession + async_get_db），原 sync TestClient
    与 async DB 依赖不兼容，故 TestAIInvocationStatsAPI / TestAIInvocationListAPI
    同步改写为 httpx.AsyncClient 模式，使用 tests/api/conftest.py 提供的
    async_db / async_auth_client / async_test_project fixture。
    TestAIErrorCode / TestAICallLogNewFields 不调用端点，保持同步。
"""
import pytest
from app.ai.call_log import AICallLog, record_call
from app.ai.error_codes import AIErrorCode
from app.models.generation_batch import GenerationBatch


class TestAIErrorCode:
    """AIErrorCode 枚举值测试"""

    def test_all_error_codes_defined(self):
        assert AIErrorCode.AI_TIMEOUT == "AI_TIMEOUT"
        assert AIErrorCode.AI_RATE_LIMIT == "AI_RATE_LIMIT"
        assert AIErrorCode.AI_INVALID_JSON == "AI_INVALID_JSON"
        assert AIErrorCode.AI_EMPTY_RESULT == "AI_EMPTY_RESULT"
        assert AIErrorCode.AI_PROVIDER_UNAVAILABLE == "AI_PROVIDER_UNAVAILABLE"
        assert AIErrorCode.AI_UNKNOWN_ERROR == "AI_UNKNOWN_ERROR"

    def test_error_code_is_string(self):
        for code in AIErrorCode:
            assert isinstance(code.value, str)

    def test_error_code_count(self):
        assert len(AIErrorCode) == 6


class TestAICallLogNewFields:
    """AICallLog 新增字段写入测试

    说明：不调用 endpoint，使用同步 db fixture + record_call。
    record_call 内部使用 sync Session，与本测试同步，无需改写为 async。
    """

    def test_record_call_with_new_fields(self, db, testProject):
        batch = GenerationBatch(
            batch_no="GB-RECORD-NEW",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        log = record_call(
            db,
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=500,
            generation_batch_id=batch.id,
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            prompt_key="test_case_generation",
            prompt_version=2,
            prompt_hash="abc123def456",
            error_code=AIErrorCode.AI_TIMEOUT,
        )
        db.flush()
        assert log.generation_batch_id == batch.id
        assert log.scenario_type == "B1_REQUIREMENT_TESTPOINT"
        assert log.generation_strategy == "REQUIREMENT_TESTPOINT_STANDARD_GENERATION"
        assert log.prompt_key == "test_case_generation"
        assert log.prompt_version == 2
        assert log.prompt_hash == "abc123def456"
        assert log.error_code == "AI_TIMEOUT"

    def test_record_call_new_fields_default_none(self, db):
        log = record_call(
            db,
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
        )
        db.flush()
        assert log.generation_batch_id is None
        assert log.scenario_type is None
        assert log.generation_strategy is None
        assert log.prompt_key is None
        assert log.prompt_version is None
        assert log.prompt_hash is None
        assert log.error_code is None

    def test_record_call_backward_compatible(self, db):
        """旧调用方式（不含新字段）仍可正常写入"""
        log = record_call(
            db,
            model="deepseek-v4",
            prompt_tokens=200,
            completion_tokens=100,
            cost_usd=0.002,
            latency_ms=300,
            step_name="generate",
            status="success",
        )
        db.flush()
        assert log.model == "deepseek-v4"
        assert log.step_name == "generate"
        assert log.status == "success"

    def test_record_call_failed_with_error_code(self, db):
        log = record_call(
            db,
            model="deepseek-v4",
            status="failed",
            error_message="request timeout",
            error_code=AIErrorCode.AI_TIMEOUT,
        )
        db.flush()
        assert log.status == "failed"
        assert log.error_code == "AI_TIMEOUT"
        assert log.error_message == "request timeout"

    def test_record_call_without_db(self):
        """db=None 时不写入数据库，仅返回实例"""
        log = record_call(
            model="deepseek-v4",
            prompt_tokens=50,
            generation_batch_id=2,
            scenario_type="A1_REQUIREMENT_TESTPOINT_UI",
        )
        assert log.model == "deepseek-v4"
        assert log.generation_batch_id == 2
        assert log.scenario_type == "A1_REQUIREMENT_TESTPOINT_UI"


async def _create_batch(
    db,
    *,
    project_id: int,
    user_id: int,
    batch_no: str,
    scenario_type: str = "B1_REQUIREMENT_TESTPOINT",
    generation_strategy: str = "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
) -> GenerationBatch:
    """辅助：在 async_db 中创建一条 GenerationBatch 记录。"""
    batch = GenerationBatch(
        batch_no=batch_no,
        project_id=project_id,
        user_id=user_id,
        entry_type="NEW_FEATURE_GENERATION",
        scenario_type=scenario_type,
        generation_strategy=generation_strategy,
        status="saved",
    )
    db.add(batch)
    await db.flush()
    return batch


async def _create_call_log(
    db,
    *,
    batch_id: int,
    model: str = "deepseek-v4",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    cost_usd: float = 0.001,
    latency_ms: int = 200,
    scenario_type: str | None = "B1_REQUIREMENT_TESTPOINT",
    generation_strategy: str = "REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
    prompt_key: str | None = None,
    prompt_version: int | None = None,
    prompt_hash: str | None = None,
    error_code: str | None = None,
) -> AICallLog:
    """辅助：在 async_db 中创建一条 AICallLog 记录。"""
    log = AICallLog(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        generation_batch_id=batch_id,
        scenario_type=scenario_type,
        generation_strategy=generation_strategy,
        prompt_key=prompt_key,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        error_code=error_code,
    )
    db.add(log)
    await db.flush()
    return log


class TestAIInvocationStatsAPI:
    """成本聚合查询 API 测试（async endpoint）"""

    async def test_stats_no_auth(self, async_client):
        """未认证返回 401"""
        resp = await async_client.get(
            "/api/v1/ai-invocation/stats", params={"project_id": 1}
        )
        assert resp.status_code in (401, 403)

    async def test_stats_empty_result(
        self, async_auth_client, async_test_project
    ):
        """无数据时返回空 items 列表"""
        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": async_test_project.id, "group_by": "model"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 0

    async def test_stats_with_data_group_by_model(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 model 聚合，验证 total_calls 与 tokens 求和"""
        batch = await _create_batch(
            async_db,
            project_id=async_test_project.id,
            user_id=async_test_user.id,
            batch_no="GB-STATS-MODEL",
        )
        await _create_call_log(
            async_db,
            batch_id=batch.id,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
        )
        await _create_call_log(
            async_db,
            batch_id=batch.id,
            prompt_tokens=200,
            completion_tokens=100,
            cost_usd=0.002,
            latency_ms=300,
        )

        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": async_test_project.id, "group_by": "model"},
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1
        model_row = next((r for r in items if r["group_key"] == "deepseek-v4"), None)
        assert model_row is not None
        assert model_row["total_calls"] == 2
        assert model_row["total_prompt_tokens"] == 300
        assert model_row["total_completion_tokens"] == 150

    async def test_stats_group_by_strategy(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 strategy 聚合"""
        batch = await _create_batch(
            async_db,
            project_id=async_test_project.id,
            user_id=async_test_user.id,
            batch_no="GB-STATS-STRAT",
        )
        await _create_call_log(
            async_db,
            batch_id=batch.id,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
        )

        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": async_test_project.id, "group_by": "strategy"},
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1
        strat_row = next(
            (
                r
                for r in items
                if r["group_key"] == "REQUIREMENT_TESTPOINT_STANDARD_GENERATION"
            ),
            None,
        )
        assert strat_row is not None
        assert strat_row["total_calls"] == 1


class TestAIInvocationListAPI:
    """调用记录列表 API 测试（async endpoint）"""

    async def test_list_no_auth(self, async_client):
        """未认证返回 401"""
        resp = await async_client.get("/api/v1/ai-invocation/list")
        assert resp.status_code in (401, 403)

    async def test_list_no_filter_returns_empty(self, async_auth_client):
        """无筛选条件返回空列表，避免全表扫描"""
        resp = await async_auth_client.get("/api/v1/ai-invocation/list")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_by_batch_id(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 batch_id 筛选，验证新字段透传"""
        batch = await _create_batch(
            async_db,
            project_id=async_test_project.id,
            user_id=async_test_user.id,
            batch_no="GB-LIST-BATCH",
        )
        await _create_call_log(
            async_db,
            batch_id=batch.id,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
            prompt_key="test_gen",
            prompt_version=1,
            prompt_hash="sha256abc",
            error_code=AIErrorCode.AI_RATE_LIMIT,
        )

        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/list",
            params={"batch_id": batch.id},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        item = data["items"][0]
        assert item["model"] == "deepseek-v4"
        assert item["generation_batch_id"] == batch.id
        assert item["scenario_type"] == "B1_REQUIREMENT_TESTPOINT"
        assert (
            item["generation_strategy"] == "REQUIREMENT_TESTPOINT_STANDARD_GENERATION"
        )
        assert item["prompt_key"] == "test_gen"
        assert item["prompt_version"] == 1
        assert item["prompt_hash"] == "sha256abc"
        assert item["error_code"] == "AI_RATE_LIMIT"

    async def test_list_by_project_id(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """按 project_id 筛选（通过 generation_batch 间接关联）"""
        batch = await _create_batch(
            async_db,
            project_id=async_test_project.id,
            user_id=async_test_user.id,
            batch_no="GB-LIST-PROJ",
        )
        await _create_call_log(
            async_db,
            batch_id=batch.id,
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
        )

        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/list",
            params={"project_id": async_test_project.id},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1

    async def test_list_pagination(
        self, async_auth_client, async_db, async_test_project, async_test_user
    ):
        """分页查询，page=1, page_size=2 返回 2 条且 total>=5"""
        batch = await _create_batch(
            async_db,
            project_id=async_test_project.id,
            user_id=async_test_user.id,
            batch_no="GB-LIST-PAGE",
        )
        for i in range(5):
            await _create_call_log(
                async_db,
                batch_id=batch.id,
                prompt_tokens=100 + i,
                completion_tokens=50,
                cost_usd=0.001,
                latency_ms=200,
            )

        resp = await async_auth_client.get(
            "/api/v1/ai-invocation/list",
            params={"batch_id": batch.id, "page": 1, "page_size": 2},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["page"] == 1
        assert data["page_size"] == 2
