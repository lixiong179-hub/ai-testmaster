import uuid

from app.crud.test_point import create_test_point
from app.models.requirement import Requirement
from tests.helpers import createTestTestCase
from app.utils.jwt_utils import create_access_token


class TestTestPointManagementEndpoints:
    def test_list_endpoint_returns_stats(self, client, db, testProject, testUser):
        auth_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(testUser.id), 'username': testUser.username})}"
        }
        point = create_test_point(
            db=db,
            project_id=testProject.id,
            module="api_stats_module",
            point="api point",
            priority=1,
            created_by=testUser.username,
        )
        createTestTestCase(
            db=db,
            projectId=testProject.id,
            case_no=f"CASE-{uuid.uuid4().hex[:8]}",
            module="api_stats_module",
            precondition="",
            steps_json=[],
            expected_result="ok",
            priority=1,
            case_type="manual",
            test_point_id=point.id,
        )

        response = client.get(
            f"/api/v1/test-point/list/{testProject.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert "stats" in payload
        assert payload["stats"]["total"] >= 1
        assert payload["stats"]["high_priority_count"] >= 1
        assert payload["stats"]["generated_case_count"] >= 1

    def test_requirement_options_endpoint_returns_project_requirements(self, client, db, testProject, testUser):
        auth_headers = {
            "Authorization": f"Bearer {create_access_token({'sub': str(testUser.id), 'username': testUser.username})}"
        }
        requirement = Requirement(
            project_id=testProject.id,
            req_no=f"REQ-{uuid.uuid4().hex[:8]}",
            title="Test point requirement",
            description="used for filter options",
            priority=1,
            status="draft",
        )
        db.add(requirement)
        db.flush()

        response = client.get(
            f"/api/v1/test-point/requirements/{testProject.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["id"] == requirement.id
        assert items[0]["req_no"] == requirement.req_no
