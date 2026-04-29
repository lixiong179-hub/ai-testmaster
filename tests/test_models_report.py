import pytest
from datetime import datetime
from app.models.report import TestReport
from app.models.project import Project
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="rpt_test_user",
        email="rpt_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(TestReport).filter(TestReport.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


@pytest.fixture
def test_project(db, test_user):
    project = Project(name="报告测试项目", user_id=test_user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


class TestTestReportModel:
    def test_create_report(self, db, test_project):
        report = TestReport(
            project_id=test_project.id,
            name="测试报告1"
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.id is not None
        assert report.project_id == test_project.id
        assert report.name == "测试报告1"
        assert report.status == "completed"
        assert report.create_time is not None
        db.delete(report)
        db.commit()

    def test_report_default_values(self, db, test_project):
        report = TestReport(
            project_id=test_project.id,
            name="默认报告"
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.status == "completed"
        assert report.total_cases == 0
        assert report.passed_cases == 0
        assert report.failed_cases == 0
        assert report.skipped_cases == 0
        assert report.description is None
        assert report.start_time is None
        assert report.end_time is None
        assert report.execution_time is None
        assert report.content is None
        assert report.test_task_id is None
        db.delete(report)
        db.commit()

    def test_report_status_values(self, db, test_project):
        for status in ["pending", "running", "completed", "failed"]:
            report = TestReport(
                project_id=test_project.id,
                name=f"状态报告-{status}",
                status=status
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            assert report.status == status
            db.delete(report)
            db.commit()

    def test_report_with_statistics(self, db, test_project):
        report = TestReport(
            project_id=test_project.id,
            name="统计报告",
            total_cases=100,
            passed_cases=80,
            failed_cases=15,
            skipped_cases=5,
            execution_time=3600
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.total_cases == 100
        assert report.passed_cases == 80
        assert report.failed_cases == 15
        assert report.skipped_cases == 5
        assert report.execution_time == 3600
        db.delete(report)
        db.commit()

    def test_report_with_content(self, db, test_project):
        report = TestReport(
            project_id=test_project.id,
            name="内容报告",
            description="测试通过率80%",
            content={"pass_rate": 0.8, "details": []}
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.description == "测试通过率80%"
        assert report.content == {"pass_rate": 0.8, "details": []}
        db.delete(report)
        db.commit()

    def test_report_with_timestamps(self, db, test_project):
        report = TestReport(
            project_id=test_project.id,
            name="时间报告",
            start_time=datetime(2024, 1, 1, 10, 0, 0),
            end_time=datetime(2024, 1, 1, 11, 0, 0)
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        assert report.start_time == datetime(2024, 1, 1, 10, 0, 0)
        assert report.end_time == datetime(2024, 1, 1, 11, 0, 0)
        db.delete(report)
        db.commit()

    def test_report_relationship(self):
        assert hasattr(TestReport, 'project')
