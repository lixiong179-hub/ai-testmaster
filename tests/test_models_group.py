import pytest
from app.models.group import Group, user_group, group_role
from app.models.user import User, Role


@pytest.fixture
def test_user(db):
    user = User(
        username="grp_test_user",
        email="grp_test@example.com",
        password_hash="hash"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user
    db.delete(user)
    db.commit()


class TestGroupModel:
    def test_create_group(self, db):
        group = Group(
            name="test_group_model",
            desc="测试用户组"
        )
        db.add(group)
        db.commit()
        db.refresh(group)
        assert group.id is not None
        assert group.name == "test_group_model"
        assert group.desc == "测试用户组"
        assert group.create_time is not None
        db.delete(group)
        db.commit()

    def test_group_default_values(self, db):
        group = Group(name="default_group_model")
        db.add(group)
        db.commit()
        db.refresh(group)
        assert group.desc is None
        assert group.update_time is not None
        db.delete(group)
        db.commit()

    def test_group_unique_name(self, db):
        g1 = Group(name="unique_group_model")
        db.add(g1)
        db.commit()
        nested = db.begin_nested()
        g2 = Group(name="unique_group_model")
        db.add(g2)
        with pytest.raises(Exception):
            db.commit()
        nested.rollback()

    def test_group_repr(self, db):
        group = Group(name="repr_group_model")
        db.add(group)
        db.commit()
        db.refresh(group)
        repr_str = repr(group)
        assert "Group" in repr_str
        assert "repr_group_model" in repr_str
        db.delete(group)
        db.commit()

    def test_group_relationships(self):
        assert hasattr(Group, 'users')
        assert hasattr(Group, 'roles')

    def test_group_with_users(self, db, test_user):
        group = Group(name="user_group_model", desc="带用户的组")
        db.add(group)
        db.commit()
        db.refresh(group)
        group.users.append(test_user)
        db.commit()
        db.refresh(group)
        assert len(group.users) == 1
        assert group.users[0].id == test_user.id
        db.execute(user_group.delete().where(user_group.c.group_id == group.id))
        db.commit()
        db.delete(group)
        db.commit()

    def test_group_with_roles(self, db):
        role = Role(name="group_test_role", desc="组测试角色")
        db.add(role)
        db.commit()
        db.refresh(role)
        group = Group(name="role_group_model", desc="带角色的组")
        db.add(group)
        db.commit()
        db.refresh(group)
        group.roles.append(role)
        db.commit()
        db.refresh(group)
        assert len(group.roles) == 1
        db.execute(group_role.delete().where(group_role.c.group_id == group.id))
        db.commit()
        db.delete(group)
        db.delete(role)
        db.commit()
