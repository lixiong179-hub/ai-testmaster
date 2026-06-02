"""
AI 调用审计增强 API 测试

测试范围：
    - AICallLog 新增字段写入
    - AIErrorCode 枚举值
    - 成本聚合查询 API
    - 调用记录列表 API
    - record_call 向后兼容性
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
    """AICallLog 新增字段写入测试"""

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


class TestAIInvocationStatsAPI:
    """成本聚合查询 API 测试"""

    def test_stats_no_auth(self, client):
        resp = client.get("/api/v1/ai-invocation/stats", params={"project_id": 1})
        assert resp.status_code in (401, 403)

    def test_stats_empty_result(self, db, client, authHeaders, testProject):
        resp = client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": testProject.id, "group_by": "model"},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 0

    def test_stats_with_data_group_by_model(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-STATS-MODEL",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        log1 = AICallLog(
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
            generation_batch_id=batch.id,
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        )
        log2 = AICallLog(
            model="deepseek-v4",
            prompt_tokens=200,
            completion_tokens=100,
            cost_usd=0.002,
            latency_ms=300,
            generation_batch_id=batch.id,
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        )
        db.add(log1)
        db.add(log2)
        db.flush()

        resp = client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": testProject.id, "group_by": "model"},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1
        model_row = next((r for r in items if r["group_key"] == "deepseek-v4"), None)
        assert model_row is not None
        assert model_row["total_calls"] == 2
        assert model_row["total_prompt_tokens"] == 300
        assert model_row["total_completion_tokens"] == 150

    def test_stats_group_by_strategy(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-STATS-STRAT",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        log = AICallLog(
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
            generation_batch_id=batch.id,
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
        )
        db.add(log)
        db.flush()

        resp = client.get(
            "/api/v1/ai-invocation/stats",
            params={"project_id": testProject.id, "group_by": "strategy"},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1
        strat_row = next(
            (r for r in items if r["group_key"] == "REQUIREMENT_TESTPOINT_STANDARD_GENERATION"),
            None,
        )
        assert strat_row is not None
        assert strat_row["total_calls"] == 1


class TestAIInvocationListAPI:
    """调用记录列表 API 测试"""

    def test_list_no_auth(self, client):
        resp = client.get("/api/v1/ai-invocation/list")
        assert resp.status_code in (401, 403)

    def test_list_no_filter_returns_empty(self, client, authHeaders):
        resp = client.get(
            "/api/v1/ai-invocation/list",
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_by_batch_id(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-LIST-BATCH",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        log = AICallLog(
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
            generation_batch_id=batch.id,
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            prompt_key="test_gen",
            prompt_version=1,
            prompt_hash="sha256abc",
            error_code=AIErrorCode.AI_RATE_LIMIT,
        )
        db.add(log)
        db.flush()

        resp = client.get(
            "/api/v1/ai-invocation/list",
            params={"batch_id": batch.id},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        item = data["items"][0]
        assert item["model"] == "deepseek-v4"
        assert item["generation_batch_id"] == batch.id
        assert item["scenario_type"] == "B1_REQUIREMENT_TESTPOINT"
        assert item["generation_strategy"] == "REQUIREMENT_TESTPOINT_STANDARD_GENERATION"
        assert item["prompt_key"] == "test_gen"
        assert item["prompt_version"] == 1
        assert item["prompt_hash"] == "sha256abc"
        assert item["error_code"] == "AI_RATE_LIMIT"

    def test_list_by_project_id(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-LIST-PROJ",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        log = AICallLog(
            model="deepseek-v4",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            latency_ms=200,
            generation_batch_id=batch.id,
        )
        db.add(log)
        db.flush()

        resp = client.get(
            "/api/v1/ai-invocation/list",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1

    def test_list_pagination(self, db, client, authHeaders, testProject):
        batch = GenerationBatch(
            batch_no="GB-LIST-PAGE",
            project_id=testProject.id,
            user_id=testProject.user_id,
            entry_type="NEW_FEATURE_GENERATION",
            scenario_type="B1_REQUIREMENT_TESTPOINT",
            generation_strategy="REQUIREMENT_TESTPOINT_STANDARD_GENERATION",
            status="saved",
        )
        db.add(batch)
        db.flush()

        for i in range(5):
            log = AICallLog(
                model="deepseek-v4",
                prompt_tokens=100 + i,
                completion_tokens=50,
                cost_usd=0.001,
                latency_ms=200,
                generation_batch_id=batch.id,
            )
            db.add(log)
        db.flush()

        resp = client.get(
            "/api/v1/ai-invocation/list",
            params={"batch_id": batch.id, "page": 1, "page_size": 2},
            headers=authHeaders,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["page"] == 1
        assert data["page_size"] == 2
