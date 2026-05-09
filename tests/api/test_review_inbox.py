"""评审 Inbox API 测试

覆盖范围:
    - GET /review/{id}/decisions �?列表（判决过�?+ 置信度排序）
    - POST /review/{id}/decisions/{did}/decide �?单条人工判定（锁+冲突�?
    - POST /review/{id}/decisions/batch-decide �?批量判定（原子性回滚）
    - POST /review/{id}/finalize �?最终化（锁释放+不可变性）

使用真实 MySQL、HTTP TestClient + JWT�?
"""
import pytest

from app.models.iteration import Iteration
from app.models.review import ReviewLock
from app.services import review_service
from app.utils.jwt_utils import create_access_token


@pytest.fixture
def test_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="inbox_test_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def auth_headers(testUser):
    token = create_access_token({
        "sub": str(testUser.id),
        "username": testUser.username,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other_user_auth_headers(db, testProject):
    from app.models.user import User
    from app.utils.jwt_utils import get_password_hash

    other = User(
        username="inbox_other_user",
        email="inbox_other@test.com",
        password_hash=get_password_hash("Test@123456"),
        is_active=True,
    )
    db.add(other)
    db.flush()
    db.commit()

    token = create_access_token({
        "sub": str(other.id),
        "username": other.username,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_review(db, test_iteration):
    review = review_service.create_review(db, test_iteration.id, "backward")
    db.flush()
    review_service.start_review(db, review.id)
    db.flush()
    db.commit()
    return review


@pytest.fixture
def test_decisions(db, test_review):
    d1 = review_service.add_decision(
        db, test_review.id, "case", 101, "keep", 85, ai_reason="looks good",
    )
    d2 = review_service.add_decision(
        db, test_review.id, "case", 102, "modify", 45,
        ai_reason="needs adjustment", modification_hint="fix precondition",
    )
    d3 = review_service.add_decision(
        db, test_review.id, "testpoint", 201, "deprecate", 90,
        ai_reason="no longer needed", deprecate_reason="outdated",
    )
    d4 = review_service.add_decision(
        db, test_review.id, "case", 103, "keep", 30,
        ai_reason="low confidence keep",
    )
    db.flush()
    db.commit()
    return [d1, d2, d3, d4]


class TestListDecisionsEndpoint:
    def test_list_all_decisions(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 4
        assert len(data["decisions"]) == 4

    def test_list_filtered_by_verdict(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?verdict=keep",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2
        verdicts = {d["final_verdict"] for d in data["decisions"]}
        assert verdicts == {"keep"}

    def test_list_sort_by_confidence_desc(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?sort_by=confidence&order=desc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        decisions = response.json()["data"]["decisions"]
        confidences = [d["ai_confidence"] for d in decisions]
        assert confidences == sorted(confidences, reverse=True)

    def test_list_sort_by_confidence_asc(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?sort_by=confidence&order=asc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        decisions = response.json()["data"]["decisions"]
        confidences = [d["ai_confidence"] for d in decisions]
        assert confidences == sorted(confidences)

    def test_list_sort_by_decided_at_desc(self, client, test_review, test_decisions, auth_headers):
        client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[0].id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[1].id}/decide",
            json={"human_verdict": "modify"},
            headers=auth_headers,
        )

        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?sort_by=decided_at&order=desc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        decisions = response.json()["data"]["decisions"]
        dates = [d["decided_at"] for d in decisions]
        assert dates == sorted(dates, reverse=True)

    def test_list_sort_by_decided_at_asc(self, client, test_review, test_decisions, auth_headers):
        client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[0].id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[1].id}/decide",
            json={"human_verdict": "modify"},
            headers=auth_headers,
        )

        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?sort_by=decided_at&order=asc",
            headers=auth_headers,
        )
        assert response.status_code == 200
        decisions = response.json()["data"]["decisions"]
        dates = [d["decided_at"] for d in decisions]
        assert dates == sorted(dates)

    def test_list_verdict_filter_no_match(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?verdict=nonexistent",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 0
        assert data["decisions"] == []

    def test_list_empty_decisions(self, client, test_review, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 0
        assert data["decisions"] == []

    def test_list_filter_by_target_kind(self, client, test_review, test_decisions, auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions?target_kind=testpoint",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["decisions"][0]["target_kind"] == "testpoint"

    def test_list_nonexistent_review_404(self, client, auth_headers):
        response = client.get(
            "/api/v1/review/99999/decisions",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_list_wrong_user_forbidden(self, client, test_review, other_user_auth_headers):
        response = client.get(
            f"/api/v1/review/{test_review.id}/decisions",
            headers=other_user_auth_headers,
        )
        assert response.status_code == 403


class TestDecideSingleEndpoint:
    def test_decide_sets_human_verdict(self, client, test_review, test_decisions, auth_headers):
        decision = test_decisions[0]
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "modify", "human_reason": "should change"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["human_verdict"] == "modify"
        assert result["human_reason"] == "should change"
        assert result["final_verdict"] == "modify"
        assert result["conflict_marker"] is True

    def test_decide_keep_no_conflict(self, client, test_review, test_decisions, auth_headers):
        decision = test_decisions[0]
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        result = response.json()["data"]
        assert result["final_verdict"] == "keep"
        assert result["conflict_marker"] is False

    def test_decide_invalid_verdict_400(self, client, test_review, test_decisions, auth_headers):
        decision = test_decisions[0]
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "delete"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_decide_lock_conflict_409(self, client, test_review, test_decisions, auth_headers):
        decision = test_decisions[0]
        response1 = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert response1.status_code == 200

        response2 = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "modify"},
            headers=auth_headers,
        )
        assert response2.status_code == 409

    def test_decide_nonexistent_decision_404(self, client, test_review, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/99999/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_decide_finalized_review_rejected(self, client, test_review, test_decisions, auth_headers, db, testUser):
        review_service.finalize_review(db, test_review.id, testUser.id)
        db.commit()

        decision = test_decisions[0]
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{decision.id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "最终化" in response.json()["msg"]

    def test_decide_nonexistent_review_404(self, client, test_decisions, auth_headers):
        decision = test_decisions[0]
        response = client.post(
            f"/api/v1/review/99999/decisions/{decision.id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestBatchDecideEndpoint:
    def test_batch_decide_all_success(self, client, test_review, test_decisions, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "keep"},
                    {"decision_id": test_decisions[1].id, "human_verdict": "modify", "human_reason": "update steps"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2
        assert data["decisions"][0]["human_verdict"] == "keep"
        assert data["decisions"][1]["human_verdict"] == "modify"

    def test_batch_decide_atomic_rollback_on_lock_conflict(self, client, test_review, test_decisions, auth_headers, db):
        first = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[0].id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )
        assert first.status_code == 200

        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "modify"},
                    {"decision_id": test_decisions[1].id, "human_verdict": "keep"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 409

        check = client.get(
            f"/api/v1/review/{test_review.id}/decisions",
            headers=auth_headers,
        )
        d1 = next(d for d in check.json()["data"]["decisions"] if d["id"] == test_decisions[1].id)
        assert d1["human_verdict"] is None

    def test_batch_decide_atomic_rollback_on_invalid_verdict(self, client, test_review, test_decisions, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "keep"},
                    {"decision_id": test_decisions[1].id, "human_verdict": "invalid"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

        check = client.get(
            f"/api/v1/review/{test_review.id}/decisions",
            headers=auth_headers,
        )
        d1 = next(d for d in check.json()["data"]["decisions"] if d["id"] == test_decisions[0].id)
        assert d1["human_verdict"] is None

    def test_batch_decide_finalized_review_rejected(self, client, test_review, test_decisions, auth_headers, db, testUser):
        review_service.finalize_review(db, test_review.id, testUser.id)
        db.commit()

        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "keep"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_batch_decide_nonexistent_decision_404(self, client, test_review, test_decisions, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": 99999, "human_verdict": "keep"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_batch_decide_duplicate_target_lock_conflict(self, client, test_review, test_decisions, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "keep"},
                    {"decision_id": test_decisions[0].id, "human_verdict": "modify"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 409

    def test_batch_decide_empty_list_rejected(self, client, test_review, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/batch-decide",
            json={"decisions": []},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422)

    def test_batch_decide_nonexistent_review_404(self, client, test_decisions, auth_headers):
        response = client.post(
            "/api/v1/review/99999/decisions/batch-decide",
            json={
                "decisions": [
                    {"decision_id": test_decisions[0].id, "human_verdict": "keep"},
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestFinalizeEndpoint:
    def test_finalize_success(self, client, test_review, test_decisions, auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "finalized"
        assert data["review_id"] == test_review.id
        assert data["finalized_at"] is not None

    def test_finalize_releases_locks(self, client, test_review, test_decisions, auth_headers, db):
        client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[0].id}/decide",
            json={"human_verdict": "keep"},
            headers=auth_headers,
        )

        lock_count = db.query(ReviewLock).filter(
            ReviewLock.review_id == test_review.id,
        ).count()
        assert lock_count == 1

        client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            headers=auth_headers,
        )

        lock_count_after = db.query(ReviewLock).filter(
            ReviewLock.review_id == test_review.id,
        ).count()
        assert lock_count_after == 0

    def test_finalize_twice_rejected(self, client, test_review, test_decisions, auth_headers, db):
        first = client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            headers=auth_headers,
        )
        assert first.status_code == 200

        second = client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            headers=auth_headers,
        )
        assert second.status_code == 400

    def test_finalize_decisions_immutable_after(self, client, test_review, test_decisions, auth_headers, db):
        client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            headers=auth_headers,
        )

        response = client.post(
            f"/api/v1/review/{test_review.id}/decisions/{test_decisions[0].id}/decide",
            json={"human_verdict": "modify"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_finalize_nonexistent_review_404(self, client, auth_headers):
        response = client.post(
            "/api/v1/review/99999/finalize",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_finalize_draft_review_fails(self, client, test_iteration, auth_headers, db):
        review = review_service.create_review(db, test_iteration.id, "forward")
        db.flush()
        db.commit()

        response = client.post(
            f"/api/v1/review/{review.id}/finalize",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_finalize_wrong_user_forbidden(self, client, test_review, other_user_auth_headers):
        response = client.post(
            f"/api/v1/review/{test_review.id}/finalize",
            json={},
            headers=other_user_auth_headers,
        )
        assert response.status_code == 403
