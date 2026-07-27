import os
import uuid
import pytest

# pytestmark = pytest.mark.skip(reason="API契约变更，测试需要完全重写")  # 临时移除排查
from tests.helpers import assertResponseSuccess, assertResponseError
from app.models.project import ProjectFile


class TestFileApiUpload:
    def test_upload_file_normal(self, db, client, authHeaders, testProject):
        testContent = b"test file content for integration test"
        response = client.post(
            "/api/v1/file/upload",
            data={
                "project_id": testProject.id,
                "resource_type": "requirement",
                "description": "test upload",
            },
            files={"file": ("test_upload.txt", testContent, "text/plain")},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert "data" in data

    def test_upload_file_no_auth(self, client, testProject):
        testContent = b"no auth upload"
        response = client.post(
            "/api/v1/file/upload",
            data={"project_id": testProject.id},
            files={"file": ("noauth.txt", testContent, "text/plain")},
        )
        assert response.status_code == 401 or response.status_code == 403

    def test_upload_file_wrong_project(self, client, authHeaders):
        testContent = b"wrong project"
        response = client.post(
            "/api/v1/file/upload",
            data={"project_id": 99999},
            files={"file": ("wrong.txt", testContent, "text/plain")},
            headers=authHeaders,
        )
        assert response.status_code == 403

    def test_upload_file_unsupported_format(self, client, authHeaders, testProject):
        testContent = b"executable content"
        response = client.post(
            "/api/v1/file/upload",
            data={"project_id": testProject.id},
            files={"file": ("test.exe", testContent, "application/octet-stream")},
            headers=authHeaders,
        )
        assert response.status_code == 400


class TestFileApiList:
    def test_get_file_list(self, db, client, authHeaders, testProject):
        fileRecord = ProjectFile(
            project_id=testProject.id,
            file_name="list_test.txt",
            file_type="txt",
            file_url="/tmp/test.txt",
            file_source="file",
            size=100,
            resource_type="requirement",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        response = client.get(
            f"/api/v1/file/list/{testProject.id}",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert "items" in data["data"]
        assert "total" in data["data"]

    def test_get_file_list_with_resource_type(self, db, client, authHeaders, testProject):
        fileRecord = ProjectFile(
            project_id=testProject.id,
            file_name="filter_test.txt",
            file_type="txt",
            file_url="/tmp/filter.txt",
            file_source="file",
            size=50,
            resource_type="ui_mockup",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        response = client.get(
            f"/api/v1/file/list/{testProject.id}",
            params={"resource_type": "ui_mockup"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        for item in data["data"]["items"]:
            assert item["resource_type"] == "ui_mockup"

    def test_get_file_list_wrong_project(self, client, authHeaders):
        response = client.get(
            "/api/v1/file/list/99999",
            headers=authHeaders,
        )
        assert response.status_code == 403

    def test_get_all_files(self, db, client, authHeaders, testProject):
        fileRecord = ProjectFile(
            project_id=testProject.id,
            file_name="all_files_test.txt",
            file_type="txt",
            file_url="/tmp/all.txt",
            file_source="file",
            size=200,
            resource_type="other",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        response = client.get(
            "/api/v1/file/list",
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert "items" in data["data"]


class TestFileApiUpdate:
    def test_update_file_description(self, db, client, authHeaders, testProject):
        fileRecord = ProjectFile(
            project_id=testProject.id,
            file_name="update_test.txt",
            file_type="txt",
            file_url="/tmp/update.txt",
            file_source="file",
            size=100,
            resource_type="requirement",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        db.refresh(fileRecord)
        response = client.put(
            f"/api/v1/file/{fileRecord.id}",
            json={"description": "updated description"},
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["description"] == "updated description"

    def test_update_file_nonexistent(self, client, authHeaders):
        response = client.put(
            "/api/v1/file/99999",
            json={"description": "should not update"},
            headers=authHeaders,
        )
        assert response.status_code == 404


class TestFileApiDelete:
    def test_delete_file_normal(self, db, client, authHeaders, testProject):
        fileRecord = ProjectFile(
            project_id=testProject.id,
            file_name="delete_test.txt",
            file_type="txt",
            file_url="/tmp/delete.txt",
            file_source="file",
            size=100,
            resource_type="requirement",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        db.refresh(fileRecord)
        response = client.delete(
            f"/api/v1/file/{fileRecord.id}",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assertResponseSuccess(response)

    def test_delete_file_nonexistent(self, client, authHeaders, testProject):
        response = client.delete(
            "/api/v1/file/99999",
            params={"project_id": testProject.id},
            headers=authHeaders,
        )
        assert response.status_code == 404

    def test_delete_file_wrong_project(self, db, client, authHeaders, testProject, testAdminUser):
        from app.models.project import Project
        adminProject = Project(
            name=f"admin_proj_{uuid.uuid4().hex[:8]}",
            user_id=testAdminUser.id,
            status=1,
            project_type="web",
        )
        db.add(adminProject)
        db.flush()
        fileRecord = ProjectFile(
            project_id=adminProject.id,
            file_name="admin_file.txt",
            file_type="txt",
            file_url="/tmp/admin.txt",
            file_source="file",
            size=100,
            resource_type="other",
            is_active=True,
        )
        db.add(fileRecord)
        db.commit()
        db.refresh(fileRecord)
        response = client.delete(
            f"/api/v1/file/{fileRecord.id}",
            params={"project_id": adminProject.id},
            headers=authHeaders,
        )
        assert response.status_code == 403


class TestFileApiSort:
    def test_update_file_sort(self, db, client, authHeaders, testProject):
        f1 = ProjectFile(
            project_id=testProject.id,
            file_name="sort1.txt",
            file_type="txt",
            file_url="/tmp/sort1.txt",
            file_source="file",
            size=100,
            resource_type="requirement",
            is_active=True,
            sort_order=1,
        )
        f2 = ProjectFile(
            project_id=testProject.id,
            file_name="sort2.txt",
            file_type="txt",
            file_url="/tmp/sort2.txt",
            file_source="file",
            size=200,
            resource_type="requirement",
            is_active=True,
            sort_order=2,
        )
        db.add(f1)
        db.add(f2)
        db.commit()
        db.refresh(f1)
        db.refresh(f2)
        response = client.post(
            "/api/v1/file/update-sort",
            json=[f2.id, f1.id],
            headers=authHeaders,
        )
        data = assertResponseSuccess(response)
        assert data["data"]["updated_count"] >= 1

    def test_update_file_sort_empty_list(self, client, authHeaders):
        response = client.post(
            "/api/v1/file/update-sort",
            json=[],
            headers=authHeaders,
        )
        assert response.status_code == 400
