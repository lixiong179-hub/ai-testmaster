import pytest
from datetime import datetime
from app.models.project import Project, ProjectFile
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="proj_test_user",
        email="proj_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(ProjectFile).filter(ProjectFile.project_id.in_(
        db.query(Project.id).filter(Project.user_id == user.id)
    )).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


class TestProjectModel:
    def test_create_project(self, db, test_user):
        project = Project(
            name="测试项目",
            user_id=test_user.id,
            description="项目描述"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.id is not None
        assert project.name == "测试项目"
        assert project.user_id == test_user.id
        assert project.description == "项目描述"
        assert project.status == 1
        assert project.project_type == "web"
        assert project.create_time is not None
        assert project.update_time is not None
        db.delete(project)
        db.commit()

    def test_project_default_values(self, db, test_user):
        project = Project(
            name="默认项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.status == 1
        assert project.project_type == "web"
        assert project.config is None
        assert project.web_config is None
        assert project.client_config is None
        assert project.test_object_type is None
        assert project.test_object_url is None
        assert project.web_env_configs is None
        assert project.device_config is None
        db.delete(project)
        db.commit()

    def test_project_with_config(self, db, test_user):
        project = Project(
            name="配置项目",
            user_id=test_user.id,
            config={"theme": "dark"},
            web_config={"url": "http://example.com"},
            client_config={"platform": "android"},
            web_env_configs={"test": {"url": "http://test.com"}}
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.config == {"theme": "dark"}
        assert project.web_config == {"url": "http://example.com"}
        assert project.client_config == {"platform": "android"}
        db.delete(project)
        db.commit()

    def test_project_test_object_fields(self, db, test_user):
        project = Project(
            name="测试对象项目",
            user_id=test_user.id,
            test_object_type="web",
            test_object_url="http://test.com",
            test_object_username="admin",
            test_object_app_package="com.example.app",
            test_object_app_activity=".MainActivity"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.test_object_type == "web"
        assert project.test_object_url == "http://test.com"
        assert project.test_object_username == "admin"
        assert project.test_object_app_package == "com.example.app"
        assert project.test_object_app_activity == ".MainActivity"
        db.delete(project)
        db.commit()

    def test_project_password_property(self, db, test_user):
        project = Project(
            name="密码项目",
            user_id=test_user.id
        )
        project.test_object_password = "secret123"
        assert project.test_object_password_encrypted is not None
        decrypted = project.test_object_password
        assert decrypted == "secret123"

    def test_project_password_set_none(self, db, test_user):
        project = Project(
            name="空密码项目",
            user_id=test_user.id
        )
        project.test_object_password = None
        assert project.test_object_password_encrypted is None
        assert project.test_object_password is None

    def test_project_password_set_empty(self, db, test_user):
        project = Project(
            name="空字符串密码项目",
            user_id=test_user.id
        )
        project.test_object_password = ""
        assert project.test_object_password_encrypted is None

    def test_project_password_get_none(self, db, test_user):
        project = Project(
            name="无密码项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        assert project.test_object_password is None
        db.delete(project)
        db.commit()

    def test_project_status_values(self, db, test_user):
        for status_val in [0, 1, 2]:
            project = Project(
                name=f"状态项目{status_val}",
                user_id=test_user.id,
                status=status_val
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            assert project.status == status_val
            db.delete(project)
            db.commit()

    def test_project_type_values(self, db, test_user):
        for ptype in ["web", "app"]:
            project = Project(
                name=f"类型项目{ptype}",
                user_id=test_user.id,
                project_type=ptype
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            assert project.project_type == ptype
            db.delete(project)
            db.commit()

    def test_project_relationships(self, test_user):
        assert hasattr(Project, 'owner')
        assert hasattr(Project, 'files')
        assert hasattr(Project, 'test_cases')
        assert hasattr(Project, 'test_points')
        assert hasattr(Project, 'test_tasks')
        assert hasattr(Project, 'test_reports')
        assert hasattr(Project, 'iterations')


class TestProjectFileModel:
    def test_create_project_file(self, db, test_user):
        project = Project(
            name="文件项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        pf = ProjectFile(
            project_id=project.id,
            file_name="需求文档.docx",
            file_type="docx",
            file_url="/uploads/req.docx"
        )
        db.add(pf)
        db.commit()
        db.refresh(pf)
        assert pf.id is not None
        assert pf.project_id == project.id
        assert pf.file_name == "需求文档.docx"
        assert pf.file_type == "docx"
        assert pf.file_url == "/uploads/req.docx"
        assert pf.file_source == "file"
        assert pf.resource_type == "other"
        assert pf.extract_status == "pending"
        assert pf.is_active is True
        assert pf.sort_order == 0
        assert pf.linked_case_count == 0
        assert pf.upload_time is not None
        db.delete(pf)
        db.delete(project)
        db.commit()

    def test_project_file_default_values(self, db, test_user):
        project = Project(
            name="默认文件项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        pf = ProjectFile(
            project_id=project.id,
            file_name="test.pdf",
            file_type="pdf",
            file_url="/uploads/test.pdf"
        )
        db.add(pf)
        db.commit()
        db.refresh(pf)
        assert pf.size is None
        assert pf.content is None
        assert pf.extract_error is None
        assert pf.extracted_at is None
        assert pf.description is None
        assert pf.iteration_id is None
        db.delete(pf)
        db.delete(project)
        db.commit()

    def test_project_file_resource_types(self, db, test_user):
        project = Project(
            name="资源类型项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        for rtype in ["requirement", "ui_mockup", "api_doc", "test_data", "other"]:
            pf = ProjectFile(
                project_id=project.id,
                file_name=f"file_{rtype}.txt",
                file_type="txt",
                file_url=f"/uploads/{rtype}.txt",
                resource_type=rtype
            )
            db.add(pf)
            db.commit()
            db.refresh(pf)
            assert pf.resource_type == rtype
            db.delete(pf)
            db.commit()
        db.delete(project)
        db.commit()

    def test_project_file_extract_status(self, db, test_user):
        project = Project(
            name="提取状态项目",
            user_id=test_user.id
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        for status in ["pending", "processing", "completed", "failed"]:
            pf = ProjectFile(
                project_id=project.id,
                file_name=f"extract_{status}.txt",
                file_type="txt",
                file_url=f"/uploads/{status}.txt",
                extract_status=status
            )
            db.add(pf)
            db.commit()
            db.refresh(pf)
            assert pf.extract_status == status
            db.delete(pf)
            db.commit()
        db.delete(project)
        db.commit()
