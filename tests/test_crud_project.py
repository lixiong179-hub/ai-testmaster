import uuid
import pytest
from app.crud.project import create_project, get_projects, get_project_by_id, update_project, delete_project
from app.schemas.project import ProjectCreate, ProjectUpdate
from tests.helpers import createTestProject, createTestUser


class TestCreateProject:
    def test_create_project_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_project_{uuid.uuid4().hex[:8]}",
            description="crud test project",
            project_type="web",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project is not None
        assert project.id is not None
        assert project.name == projectCreate.name
        assert project.user_id == testUser.id
        assert project.status == 1
        assert project.description == "crud test project"

    def test_create_project_app_type(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_app_{uuid.uuid4().hex[:8]}",
            description="app type project",
            project_type="app",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.project_type == "app"

    def test_create_project_minimal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_min_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project is not None
        assert project.description is None

    def test_create_project_default_type(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_default_type_{uuid.uuid4().hex[:8]}",
            description="default type",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.project_type == "web"

    def test_create_project_long_description(self, db, testUser):
        longDesc = "A" * 500
        projectCreate = ProjectCreate(
            name=f"crud_longdesc_{uuid.uuid4().hex[:8]}",
            description=longDesc,
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        assert project.description == longDesc


class TestGetProjects:
    def test_get_projects_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_list_{uuid.uuid4().hex[:8]}",
            description="list test",
        )
        create_project(db=db, project=projectCreate, user_id=testUser.id)
        projects = get_projects(db=db, user_id=testUser.id)
        assert len(projects) >= 1

    def test_get_projects_pagination(self, db, testUser):
        for i in range(3):
            projectCreate = ProjectCreate(
                name=f"crud_page_{i}_{uuid.uuid4().hex[:8]}",
            )
            create_project(db=db, project=projectCreate, user_id=testUser.id)
        first = get_projects(db=db, user_id=testUser.id, skip=0, limit=2)
        assert len(first) <= 2

    def test_get_projects_wrong_user(self, db, testUser):
        projects = get_projects(db=db, user_id=99999)
        found_test_user = [p for p in projects if p.user_id == testUser.id]
        assert len(found_test_user) == 0

    def test_get_projects_empty_result(self, db):
        projects = get_projects(db=db, user_id=-1)
        assert projects == []

    def test_get_projects_skip_beyond_range(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_skip_{uuid.uuid4().hex[:8]}",
        )
        create_project(db=db, project=projectCreate, user_id=testUser.id)
        projects = get_projects(db=db, user_id=testUser.id, skip=10000, limit=10)
        assert projects == []


class TestGetProjectById:
    def test_get_project_by_id_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_get_{uuid.uuid4().hex[:8]}",
            description="get by id test",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        found = get_project_by_id(db=db, project_id=project.id, user_id=testUser.id)
        assert found is not None
        assert found.id == project.id

    def test_get_project_by_id_nonexistent(self, db, testUser):
        found = get_project_by_id(db=db, project_id=99999, user_id=testUser.id)
        assert found is None

    def test_get_project_by_id_wrong_user(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_wrong_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        found = get_project_by_id(db=db, project_id=project.id, user_id=99999)
        assert found is None

    def test_get_project_by_id_zero_id(self, db, testUser):
        found = get_project_by_id(db=db, project_id=0, user_id=testUser.id)
        assert found is None

    def test_get_project_by_id_negative_id(self, db, testUser):
        found = get_project_by_id(db=db, project_id=-1, user_id=testUser.id)
        assert found is None


class TestUpdateProject:
    def test_update_project_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_upd_{uuid.uuid4().hex[:8]}",
            description="original description",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        projectUpdate = ProjectUpdate(
            name=f"updated_{uuid.uuid4().hex[:8]}",
            description="updated description",
        )
        updated = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=testUser.id
        )
        assert updated is not None
        assert updated.description == "updated description"

    def test_update_project_partial(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_partial_{uuid.uuid4().hex[:8]}",
            description="keep this",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        projectUpdate = ProjectUpdate(status=2)
        updated = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=testUser.id
        )
        assert updated is not None
        assert updated.status == 2
        assert updated.description == "keep this"

    def test_update_project_nonexistent(self, db, testUser):
        projectUpdate = ProjectUpdate(description="should not update")
        result = update_project(
            db=db, project_id=99999, project_update=projectUpdate, user_id=testUser.id
        )
        assert result is None

    def test_update_project_wrong_user(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_wrong_upd_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        projectUpdate = ProjectUpdate(description="should not update")
        result = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=99999
        )
        assert result is None

    def test_update_project_status_to_archived(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_archive_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        projectUpdate = ProjectUpdate(status=2)
        updated = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=testUser.id
        )
        assert updated.status == 2

    def test_update_project_status_to_inactive(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_inactive_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        projectUpdate = ProjectUpdate(status=0)
        updated = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=testUser.id
        )
        assert updated.status == 0

    def test_update_project_name_only(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_nameonly_{uuid.uuid4().hex[:8]}",
            description="keep description",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        newName = f"renamed_{uuid.uuid4().hex[:8]}"
        projectUpdate = ProjectUpdate(name=newName)
        updated = update_project(
            db=db, project_id=project.id, project_update=projectUpdate, user_id=testUser.id
        )
        assert updated.name == newName
        assert updated.description == "keep description"


class TestDeleteProject:
    def test_delete_project_normal(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_del_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        result = delete_project(db=db, project_id=project.id, user_id=testUser.id)
        assert result is True
        found = get_project_by_id(db=db, project_id=project.id, user_id=testUser.id)
        assert found is None

    def test_delete_project_nonexistent(self, db, testUser):
        result = delete_project(db=db, project_id=99999, user_id=testUser.id)
        assert result is False

    def test_delete_project_wrong_user(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_wrong_del_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        result = delete_project(db=db, project_id=project.id, user_id=99999)
        assert result is False

    def test_delete_project_twice(self, db, testUser):
        projectCreate = ProjectCreate(
            name=f"crud_twice_{uuid.uuid4().hex[:8]}",
        )
        project = create_project(db=db, project=projectCreate, user_id=testUser.id)
        first = delete_project(db=db, project_id=project.id, user_id=testUser.id)
        assert first is True
        second = delete_project(db=db, project_id=project.id, user_id=testUser.id)
        assert second is False

    def test_delete_project_zero_id(self, db, testUser):
        result = delete_project(db=db, project_id=0, user_id=testUser.id)
        assert result is False
