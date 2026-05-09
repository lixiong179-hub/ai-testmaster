import pytest
from app.models.operation_log import OperationLog
from app.models.user import User


@pytest.fixture
def test_user(db):
    user = User(
        username="ol_test_user",
        email="ol_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.query(OperationLog).filter(OperationLog.user_id == user.id).delete(synchronize_session=False)
    db.delete(user)
    db.commit()


class TestOperationLogModel:
    def test_create_operation_log(self, db, test_user):
        log = OperationLog(
            user_id=test_user.id,
            operation_type="create",
            resource_type="project",
            action="创建项目"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.id is not None
        assert log.user_id == test_user.id
        assert log.operation_type == "create"
        assert log.resource_type == "project"
        assert log.action == "创建项目"
        db.delete(log)
        db.commit()

    def test_operation_log_default_values(self, db, test_user):
        log = OperationLog(
            user_id=test_user.id,
            operation_type="login",
            resource_type="system",
            action="用户登录"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.resource_id is None
        assert log.ip_address is None
        assert log.user_agent is None
        assert log.details is None
        db.delete(log)
        db.commit()

    def test_operation_log_operation_types(self, db, test_user):
        for op_type in ["create", "update", "delete", "login", "export", "import"]:
            log = OperationLog(
                user_id=test_user.id,
                operation_type=op_type,
                resource_type="test_case",
                action=f"操作{op_type}"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            assert log.operation_type == op_type
            db.delete(log)
            db.commit()

    def test_operation_log_resource_types(self, db, test_user):
        for res_type in ["project", "test_case", "user", "system"]:
            log = OperationLog(
                user_id=test_user.id,
                operation_type="create",
                resource_type=res_type,
                action=f"创建{res_type}"
            )
            db.add(log)
            db.commit()
            db.refresh(log)
            assert log.resource_type == res_type
            db.delete(log)
            db.commit()

    def test_operation_log_with_details(self, db, test_user):
        log = OperationLog(
            user_id=test_user.id,
            operation_type="update",
            resource_type="test_case",
            resource_id=42,
            action="修改用例",
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            details='{"field": "title", "old": "旧标�?, "new": "新标�?}'
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        assert log.resource_id == 42
        assert log.ip_address == "192.168.1.100"
        assert log.user_agent == "Mozilla/5.0"
        assert log.details == '{"field": "title", "old": "旧标�?, "new": "新标�?}'
        db.delete(log)
        db.commit()

    def test_operation_log_repr(self, db, test_user):
        log = OperationLog(
            user_id=test_user.id,
            operation_type="delete",
            resource_type="project",
            action="删除项目"
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        repr_str = repr(log)
        assert "OperationLog" in repr_str
        db.delete(log)
        db.commit()

    def test_operation_log_relationship(self):
        assert hasattr(OperationLog, 'user')
