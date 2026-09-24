"""R1-3: `GET /agents/sessions/{session_id}/audits` 端点（list_session_audits）单元测试。

沿用 R1-2 的单元风格（直接 await 端点函数 + mock db），规避 O-13 所述的
「每个 pytest 会话首个 HTTP 测试必失败」的既有问题。

覆盖：
    - 成功：按 id 升序返回审计链，字段映射正确
    - 越权：非本人会话 → 403（由 _check_session_ownership 保证）
    - 空结果：无审计记录 → 空列表
    - 异常映射：服务层抛异常 → 500
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints.agents import list_session_audits
from app.models.agent_audit import AgentAudit

_OWNERSHIP = "app.api.v1.endpoints.agents._check_session_ownership"


def _make_db() -> MagicMock:
    db = MagicMock()
    db.commit = AsyncMock()
    return db


def _make_audit(audit_id=1, session_id=5, iteration=1,
                action_type="tool_call", human_approved=0) -> AgentAudit:
    """构造不落库的 AgentAudit 实例（仅供响应序列化）。"""
    return AgentAudit(
        id=audit_id,
        session_id=session_id,
        iteration=iteration,
        action_type=action_type,
        action_detail={"tool": "get_dom"},
        decision_confidence=None,
        human_approved=human_approved,
    )


@pytest.fixture
def _owned():
    """跳过归属校验（该逻辑由既有 test_agents_endpoints.py 覆盖）。"""
    with patch(_OWNERSHIP, new=AsyncMock(return_value=MagicMock(id=5))) as mock_own:
        yield mock_own


class TestListSessionAudits:
    async def test_returns_audit_chain(self, _owned):
        """返回该会话完整审计链，字段映射正确。"""
        db = _make_db()
        audits = [
            _make_audit(audit_id=1, iteration=1, action_type="tool_call"),
            _make_audit(audit_id=2, iteration=2, action_type="update_locator",
                        human_approved=1),
        ]

        with patch(
            "app.api.v1.endpoints.agents._audit_service.get_session_audit",
            new=AsyncMock(return_value=audits),
        ) as mock_get:
            result = await list_session_audits(
                session_id=5, db=db, current_user=MagicMock(id=7, is_superuser=False)
            )

        assert result["code"] == 200
        data = result["data"]
        assert len(data) == 2
        # 顺序与传入一致（服务层按 id 升序）
        assert [d["id"] for d in data] == [1, 2]
        assert data[0]["action_type"] == "tool_call"
        assert data[0]["session_id"] == 5
        assert data[1]["human_approved"] == 1
        mock_get.assert_awaited_once()

    async def test_empty_chain_returns_empty_payload(self, _owned):
        """无审计记录 → 空载荷，不报错。

        注意：`create_response` 对 falsy 的 data 统一转 `{}`（既有契约，避免前端收到
        null），故空列表在响应中表现为 `{}`，与 messages 端点行为一致。
        """
        db = _make_db()
        with patch(
            "app.api.v1.endpoints.agents._audit_service.get_session_audit",
            new=AsyncMock(return_value=[]),
        ):
            result = await list_session_audits(
                session_id=5, db=db, current_user=MagicMock(id=7, is_superuser=False)
            )

        assert result["code"] == 200
        assert result["data"] in ([], {})

    async def test_ownership_check_enforced(self):
        """归属校验被调用（越权场景由 _check_session_ownership 抛 403）。"""
        db = _make_db()
        with patch(_OWNERSHIP, new=AsyncMock(side_effect=HTTPException(
            status_code=403, detail="无权限操作此会话"
        ))):
            with pytest.raises(HTTPException) as exc:
                await list_session_audits(
                    session_id=5, db=db,
                    current_user=MagicMock(id=7, is_superuser=False),
                )

        assert exc.value.status_code == 403

    async def test_service_exception_maps_to_500(self, _owned):
        """服务层抛异常 → HTTP 500。"""
        db = _make_db()
        with patch(
            "app.api.v1.endpoints.agents._audit_service.get_session_audit",
            new=AsyncMock(side_effect=RuntimeError("db down")),
        ):
            with pytest.raises(HTTPException) as exc:
                await list_session_audits(
                    session_id=5, db=db,
                    current_user=MagicMock(id=7, is_superuser=False),
                )

        assert exc.value.status_code == 500
