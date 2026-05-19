import pytest
from unittest.mock import MagicMock
from app.pipelines.context import PipelineContext


class TestPipelineContext:
    def setup_method(self):
        self.db = MagicMock()
        self.ai_client = MagicMock()
        self.run = MagicMock()
        self.run.id = 1
        self.ctx = PipelineContext(
            db=self.db,
            ai_client=self.ai_client,
            run=self.run,
            iteration_id=1,
            user_id=1,
            config={"key1": "value1"},
        )

    def test_get_artifact_none(self):
        assert self.ctx.get_artifact("nonexistent") is None

    def test_set_and_get_artifact(self):
        artifact = MagicMock()
        artifact.payload = {"data": "test"}
        self.ctx.set_artifact("test_kind", artifact)
        result = self.ctx.get_artifact("test_kind")
        assert result == {"data": "test"}

    def test_register_and_get_step_record(self):
        record = MagicMock()
        self.ctx.register_step_record("step1", record)
        assert self.ctx.get_step_record("step1") is record

    def test_get_step_record_none(self):
        assert self.ctx.get_step_record("nonexistent") is None

    def test_get_config_from_context(self):
        assert self.ctx.get_config("key1") == "value1"

    def test_set_confirmation_payload(self):
        self.ctx.set_confirmation_payload({"action": "confirm"})
        assert self.ctx.get_confirmation_payload() == {"action": "confirm"}

    def test_get_confirmation_payload_none(self):
        assert self.ctx.get_confirmation_payload() is None

    def test_set_pause_info(self):
        self.ctx.set_pause_info("等待确认", "review_step")
        info = self.ctx.get_pause_info()
        assert info is not None
        assert info["reason"] == "等待确认"
        assert info["step_name"] == "review_step"
        assert "paused_at" in info

    def test_get_pause_info_none(self):
        assert self.ctx.get_pause_info() is None

    def test_default_config_empty(self):
        ctx = PipelineContext(
            db=self.db, ai_client=self.ai_client,
            run=self.run, iteration_id=1,
        )
        assert ctx.config == {}

    def test_get_ai_client(self):
        client = self.ctx.get_ai_client()
        assert client is not None
