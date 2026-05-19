import pytest
from datetime import datetime
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="iter_test_user",
        email="iter_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(Iteration).filter(Iteration.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="迭代测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestIterationModel:
    def test_create_iteration(self, db, test_project):
        iteration = Iteration(
            project_id=test_project.id,
            name="Sprint 1",
            version="v1.0"
        )
        db.add(iteration)
        db.commit()
        db.refresh(iteration)
        assert iteration.id is not None
        assert iteration.project_id == test_project.id
        assert iteration.name == "Sprint 1"
        assert iteration.version == "v1.0"
        assert iteration.status == "draft"
        assert iteration.create_time is not None
        db.delete(iteration)
        db.commit()

    def test_iteration_default_values(self, db, test_project):
        iteration = Iteration(
            project_id=test_project.id,
            name="默认迭代"
        )
        db.add(iteration)
        db.commit()
        db.refresh(iteration)
        assert iteration.version == "v1.0"
        assert iteration.status == "draft"
        assert iteration.description is None
        assert iteration.start_date is None
        assert iteration.end_date is None
        db.delete(iteration)
        db.commit()

    def test_iteration_status_values(self, db, test_project):
        for status in ["draft", "in_pipeline", "in_review", "finalized", "archived"]:
            iteration = Iteration(
                project_id=test_project.id,
                name=f"迭代-{status}",
                status=status
            )
            db.add(iteration)
            db.commit()
            db.refresh(iteration)
            assert iteration.status == status
            db.delete(iteration)
            db.commit()

    def test_iteration_with_dates(self, db, test_project):
        iteration = Iteration(
            project_id=test_project.id,
            name="日期迭代",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31)
        )
        db.add(iteration)
        db.commit()
        db.refresh(iteration)
        assert iteration.start_date == datetime(2024, 1, 1)
        assert iteration.end_date == datetime(2024, 1, 31)
        db.delete(iteration)
        db.commit()

    def test_iteration_unique_name_per_project(self, db, test_project):
        iter1 = Iteration(project_id=test_project.id, name="同名迭代")
        db.add(iter1)
        db.commit()
        nested = db.begin_nested()
        iter2 = Iteration(project_id=test_project.id, name="同名迭代")
        db.add(iter2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_iteration_same_name_different_project(self, db, test_user):
        proj1 = Project(name="项目1", user_id=test_user.id)
        db.add(proj1)
        db.commit()
        db.refresh(proj1)
        proj2 = Project(name="项目2", user_id=test_user.id)
        db.add(proj2)
        db.commit()
        db.refresh(proj2)
        iter1 = Iteration(project_id=proj1.id, name="Sprint A")
        db.add(iter1)
        db.commit()
        iter2 = Iteration(project_id=proj2.id, name="Sprint A")
        db.add(iter2)
        db.commit()
        db.refresh(iter2)
        assert iter2.name == "Sprint A"
        db.delete(iter2)
        db.delete(iter1)
        db.delete(proj2)
        db.delete(proj1)
        db.commit()

    def test_iteration_with_description(self, db, test_project):
        iteration = Iteration(
            project_id=test_project.id,
            name="描述迭代",
            description="第一个冲刺迭代"
        )
        db.add(iteration)
        db.commit()
        db.refresh(iteration)
        assert iteration.description == "第一个冲刺迭代"
        db.delete(iteration)
        db.commit()

    def test_iteration_version_values(self, db, test_project):
        for ver in ["v1.0", "v2.0", "v1.1-beta"]:
            iteration = Iteration(
                project_id=test_project.id,
                name=f"版本迭代-{ver}",
                version=ver
            )
            db.add(iteration)
            db.commit()
            db.refresh(iteration)
            assert iteration.version == ver
            db.delete(iteration)
            db.commit()

    def test_iteration_relationship(self):
        assert hasattr(Iteration, 'project')
