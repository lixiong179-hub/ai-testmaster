"""M2-T11 Review Undo API 测试

覆盖:
    - POST /review/{id}/undo-decision/{decision_id} 正常撤销
    - POST /review/{id}/undo-decision/{decision_id} 超时403
    - POST /review/{id}/undo-decision/{decision_id} 未finalize 400
    - POST /review/{id}/undo-finalize 正常撤销（admin）
    - POST /review/{id}/undo-finalize 非admin 403
    - POST /review/{id}/undo-finalize 超时403
    - POST /review/{id}/undo-finalize 未finalize 400
"""
import pytest
from datetime import timedelta

from app.models.iteration import Iteration
from app.models.test_case import TestCase, enable_lifecycle_transition, disable_lifecycle_transition
from app.services import review_service
from app.utils.db_time import utcnow
from app.utils.jwt_utils import create_access_token


@pytest.fixture
def auth_headers(testUser):
    token = create_access_token({
        "sub": str(testUser.id),
        "username": testUser.username,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def review_iteration(db, testProject):
    iteration = Iteration(
        project_id=testProject.id,
        name="undo_api_iter",
        status="draft",
    )
    db.add(iteration)
    db.flush()
    return iteration


@pytest.fixture
def undo_review(db, review_iteration):
    return review_service.create_review(
        db=db, iteration_id=review_iteration.id, kind="forward",
    )


@pytest.fixture
def undo_case(db, testProject):
    case = TestCase(
        project_id=testProject.id,
        case_no="REV-API-UNDO-001",
        module="user",
        title="api undo test",
        precondition="",
        steps_json=[],
        expected_result="",
        priority=1,
        case_type="API",
        lifecycle_status="active",
    )
    db.add(case)
    db.flush()
    return case


class TestUndoDecisionApi:
    def test_undo_decision_succeeds(
        self, client, db, undo_review, undo_case, testUser, auth_headers
    ):
        review_service.start_review(db=db, review_id=undo_review.id)

        decision = review_service.add_decision(
            db=db, review_id=undo_review.id,
            target_kind="case", target_id=undo_case.id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=testUser.id,
        )
        review_service.finalize_review(
            db=db, review_id=undo_review.id, finalized_by=testUser.id,
        )
        db.commit()

        response = client.post(
            f"/api/v1/review/{undo_review.id}/undo-decision/{decision.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["human_verdict"] is None

    def test_undo_decision_not_finalized(
        self, client, db, undo_review, undo_case, testUser, auth_headers
    ):
        review_service.start_review(db=db, review_id=undo_review.id)

        decision = review_service.add_decision(
            db=db, review_id=undo_review.id,
            target_kind="case", target_id=undo_case.id,
            ai_verdict="keep", ai_confidence=90,
        )
        db.commit()

        response = client.post(
            f"/api/v1/review/{undo_review.id}/undo-decision/{decision.id}",
            headers=auth_headers,
        )
        assert response.status_code == 400

    def test_undo_decision_window_expired(
        self, client, db, undo_review, undo_case, testUser, auth_headers
    ):
        review_service.start_review(db=db, review_id=undo_review.id)

        decision = review_service.add_decision(
            db=db, review_id=undo_review.id,
            target_kind="case", target_id=undo_case.id,
            ai_verdict="keep", ai_confidence=90,
        )
        review = review_service.finalize_review(
            db=db, review_id=undo_review.id, finalized_by=testUser.id,
        )
        review.finalized_at = utcnow() - timedelta(minutes=61)
        db.commit()

        response = client.post(
            f"/api/v1/review/{undo_review.id}/undo-decision/{decision.id}",
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_undo_decision_review_not_found(self, client, auth_headers):
        response = client.post(
            "/api/v1/review/99999/undo-decision/1",
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_undo_decision_decision_not_found(self, client, undo_review, auth_headers):
        response = client.post(
            f"/api/v1/review/{undo_review.id}/undo-decision/99999",
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestUndoFinalizeApi:
    @pytest.fixture
    def admin_user(self, db):
        from app.models.user import User
        import uuid

        admin = User(
            username=f"undo_admin_{uuid.uuid4().hex[:8]}",
            email=f"undo_admin_{uuid.uuid4().hex[:8]}@test.com",
            password_hash="test",
            is_superuser=True,
        )
        db.add(admin)
        db.flush()
        return admin

    @pytest.fixture
    def admin_project(self, db, admin_user):
        from app.models.project import Project

        project = Project(
            name="admin_undo_project",
            user_id=admin_user.id,
        )
        db.add(project)
        db.flush()
        return project

    @pytest.fixture
    def admin_iteration(self, db, admin_project):
        iteration = Iteration(
            project_id=admin_project.id,
            name="admin_undo_iter",
            status="draft",
        )
        db.add(iteration)
        db.flush()
        return iteration

    @pytest.fixture
    def admin_review(self, db, admin_iteration):
        return review_service.create_review(
            db=db, iteration_id=admin_iteration.id, kind="forward",
        )

    @pytest.fixture
    def admin_case(self, db, admin_project):
        case = TestCase(
            project_id=admin_project.id,
            case_no="REV-ADMIN-CASE-001",
            module="user",
            title="admin undo test case",
            precondition="",
            steps_json=[],
            expected_result="",
            priority=1,
            case_type="API",
            lifecycle_status="active",
        )
        db.add(case)
        db.flush()
        return case

    @pytest.fixture
    def admin_auth_headers(self, admin_user):
        token = create_access_token({
            "sub": str(admin_user.id),
            "username": admin_user.username,
        })
        return {"Authorization": f"Bearer {token}"}

    def test_undo_finalize_succeeds(
        self, client, db, admin_review, admin_case, admin_user, admin_auth_headers
    ):
        review_service.start_review(db=db, review_id=admin_review.id)

        decision = review_service.add_decision(
            db=db, review_id=admin_review.id,
            target_kind="case", target_id=admin_case.id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=admin_user.id,
        )
        review_service.finalize_review(
            db=db, review_id=admin_review.id, finalized_by=admin_user.id,
        )
        db.commit()

        response = client.post(
            f"/api/v1/review/{admin_review.id}/undo-finalize",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["status"] == "in_progress"

    def test_undo_finalize_non_admin_rejected(
        self, client, db, undo_review, undo_case, testUser, auth_headers
    ):
        review_service.start_review(db=db, review_id=undo_review.id)

        decision = review_service.add_decision(
            db=db, review_id=undo_review.id,
            target_kind="case", target_id=undo_case.id,
            ai_verdict="keep", ai_confidence=90,
        )
        review_service.set_human_verdict(
            db=db, decision_id=decision.id,
            human_verdict="keep", human_user_id=testUser.id,
        )
        review_service.finalize_review(
            db=db, review_id=undo_review.id, finalized_by=testUser.id,
        )
        db.commit()

        response = client.post(
            f"/api/v1/review/{undo_review.id}/undo-finalize",
            headers=auth_headers,
        )
        assert response.status_code == 403

    def test_undo_finalize_window_expired(
        self, client, db, admin_review, admin_user, admin_auth_headers
    ):
        review_service.start_review(db=db, review_id=admin_review.id)

        review = review_service.finalize_review(
            db=db, review_id=admin_review.id, finalized_by=admin_user.id,
        )
        review.finalized_at = utcnow() - timedelta(minutes=61)
        db.commit()

        response = client.post(
            f"/api/v1/review/{admin_review.id}/undo-finalize",
            headers=admin_auth_headers,
        )
        assert response.status_code == 403

    def test_undo_finalize_not_finalized(
        self, client, db, admin_review, admin_auth_headers
    ):
        review_service.start_review(db=db, review_id=admin_review.id)
        db.commit()

        response = client.post(
            f"/api/v1/review/{admin_review.id}/undo-finalize",
            headers=admin_auth_headers,
        )
        assert response.status_code == 400

    def test_undo_finalize_review_not_found(self, client, auth_headers):
        response = client.post(
            "/api/v1/review/99999/undo-finalize",
            headers=auth_headers,
        )
        assert response.status_code == 403
