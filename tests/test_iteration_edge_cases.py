"""
迭代管理功能边界场景测试 - P1边界测试

测试范围:
- 并发和竞态条件
- 权限和安全验证
- 数据兼容性和向后兼容

技术要求:
- 使用真实MySQL数据库（禁止Mock）
- 测试并发场景下的数据一致性
- 验证权限控制的有效性

作者: 软件测试工程师
日期: 2026-04-13
"""
import pytest
import asyncio
import os
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models import (
    User, Project, Iteration, ProjectFile,
    UIPrototypeProject, UIPrototypeScreen
)
from app.crud import iteration as iteration_crud
from app.crud import file as file_crud
from app.crud import ui_prototype as ui_prototype_crud


# ==================== Fixtures ====================



@pytest.fixture(scope="function")
def test_user(testUser):
    """使用conftest提供的测试用户"""
    return testUser


@pytest.fixture(scope="function")
def other_user(db):
    """创建另一个测试用户（用于权限测试）"""
    from app.utils.jwt_utils import get_password_hash

    user = User(
        username=f"other_edge_user_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        email=f"other_edge_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com",
        password_hash=get_password_hash("OtherPassword123!")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    yield user


@pytest.fixture(scope="function")
def test_project(db, test_user):
    """创建测试项目"""
    project = Project(
        name=f"边界测试项目_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        description="用于边界场景测试",
        user_id=test_user.id,
        project_type="web"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture(scope="function")
def other_project(db, other_user):
    """创建属于其他用户的项目"""
    project = Project(
        name=f"其他用户项目_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        description="用于权限测试的项目",
        user_id=other_user.id,
        project_type="web"
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    yield project


@pytest.fixture(scope="function")
def test_iteration(db, test_project):
    """创建测试迭代"""
    iteration = Iteration(
        project_id=test_project.id,
        name=f"Sprint Edge_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
        version="v1.0",
        status="draft"
    )
    db.add(iteration)
    db.commit()
    db.refresh(iteration)
    yield iteration


# ==================== 测试6: 并发和竞态条件 ====================

class TestConcurrencyAndRaceConditions:
    """并发操作和竞态条件测试"""

    @pytest.mark.skip(reason="多线程独立引擎与session级testEngine存在锁冲突，需重构测试基础设施")
    def test_concurrent_create_same_name_iteration(self, db, test_project):
        """
        测试同时创建同名迭代的唯一性约束

        场景: 多个线程/协程同时尝试创建同名迭代
        预期: 只有1个成功，其余抛出ValueError或IntegrityError
        """
        iteration_name = f"Concurrent Sprint_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        success_count = 0
        error_count = 0
        errors = []

        def create_iteration_attempt(attempt_id):
            """尝试创建迭代的函数"""
            # 每个线程需要独立的session
            engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                iteration = iteration_crud.create_iteration(
                    db=session,
                    project_id=test_project.id,
                    name=iteration_name,
                    version=f"v{attempt_id}.0"
                )
                session.commit()
                return ("success", iteration.id)
            except (ValueError, IntegrityError) as e:
                session.rollback()
                return ("error", str(e))
            except Exception as e:
                session.rollback()
                return ("error", f"Unexpected: {str(e)}")
            finally:
                session.close()

        # 使用5个并发线程
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(create_iteration_attempt, i)
                for i in range(5)
            ]

            for future in as_completed(futures):
                status, message = future.result()
                if status == "success":
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(message)

        # 验证结果
        assert success_count == 1, f"应该只有1个成功，实际有{success_count}个"
        assert error_count == 4, f"应该有4个失败，实际有{error_count}个"

        # 验证数据库中只有1条记录
        iterations = db.query(Iteration).filter(
            Iteration.project_id == test_project.id,
            Iteration.name == iteration_name
        ).all()
        assert len(iterations) == 1

    def test_rapid_sequential_delete_same_iteration(self, db, test_iteration):
        """
        测试快速连续删除同一迭代

        场景: 第一次删除成功后，后续删除应返回False（已不存在）
        """
        iteration_id = test_iteration.id

        # 第一次删除
        result1 = iteration_crud.delete_iteration(
            db=db,
            iteration_id=iteration_id
        )
        assert result1 is True

        # 第二次删除（应该返回False）
        result2 = iteration_crud.delete_iteration(
            db=db,
            iteration_id=iteration_id
        )
        assert result2 is False

        # 第三次删除（仍然返回False）
        result3 = iteration_crud.delete_iteration(
            db=db,
            iteration_id=iteration_id
        )
        assert result3 is False

    @pytest.mark.skip(reason="多线程独立引擎与session级testEngine存在锁冲突，需重构测试基础设施")
    def test_concurrent_update_same_iteration(self, db, test_iteration):
        """
        测试并发更新同一迭代

        场景: 多个线程同时更新同一迭代的不同字段
        预期: 所有更新都能成功（最后写入的值生效）
        """
        iteration_id = test_iteration.id
        results = []

        def update_iteration_field(field_name, value):
            """更新迭代字段的函数"""
            engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                updated = iteration_crud.update_iteration(
                    db=session,
                    iteration_id=iteration_id,
                    **{field_name: value}
                )
                session.commit()
                return ("success", field_name, value)
            except Exception as e:
                session.rollback()
                return ("error", field_name, str(e))
            finally:
                session.close()

        # 并发更新不同字段
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(update_iteration_field, "name", "Updated Name"),
                executor.submit(update_iteration_field, "version", "v99.0"),
                executor.submit(update_iteration_field, "description", "Concurrent Update Test")
            ]

            for future in as_completed(futures):
                results.append(future.result())

        # 验证所有更新都执行了（至少没有异常）
        successes = [r for r in results if r[0] == "success"]
        assert len(successes) >= 2  # 至少大部分成功

        # 验证最终状态
        final_iteration = db.query(Iteration).filter(
            Iteration.id == iteration_id
        ).first()
        assert final_iteration is not None

    @pytest.mark.skip(reason="多线程独立引擎与session级testEngine存在锁冲突，需重构测试基础设施")
    def test_concurrent_file_uploads_to_same_iteration(self, db, test_project, test_iteration):
        """
        测试并发上传文件到同一迭代

        场景: 多个线程同时向同一迭代上传文件
        预期: 所有文件都正确关联到该迭代
        """
        uploaded_files = []

        def upload_file_to_iteration(file_index):
            """上传文件的函数"""
            engine = create_engine(settings.DATABASE_URL.replace('/ai_testmaster', '/ai_testmaster_test'))
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                file_obj = file_crud.create_project_file(
                    db=session,
                    project_id=test_project.id,
                    file_name=f"concurrent_file_{file_index}.pdf",
                    file_type="pdf",
                    file_url=f"/uploads/test/concurrent_{file_index}.pdf",
                    iteration_id=test_iteration.id
                )
                session.commit()
                return file_obj.id
            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        # 并发上传10个文件
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(upload_file_to_iteration, i)
                for i in range(10)
            ]

            for future in as_completed(futures):
                try:
                    file_id = future.result()
                    uploaded_files.append(file_id)
                except Exception as e:
                    pytest.fail(f"并发上传失败: {e}")

        # 验证所有文件都已上传并正确关联
        assert len(uploaded_files) == 10

        files_in_iteration = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=test_iteration.id
        )
        assert len(files_in_iteration) == 10


# ==================== 测试7: 权限和安全 ====================

class TestPermissionsAndSecurity:
    """权限和安全验证测试"""

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_access_iterations(self, client, auth_headers_other_user, test_project, test_iteration):
        """测试无权限用户无法访问他人项目的迭代"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        from app.db.database import get_db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 尝试获取他人项目的迭代列表
            response = await ac.get(
                f"/api/v1/iteration/list/{test_project.id}",
                headers=auth_headers_other_user
            )

            # 应该返回403 Forbidden
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_create_iteration(self, client, auth_headers_other_user, test_project):
        """测试无权限用户无法在他人项目中创建迭代"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                "/api/v1/iteration/",
                json={
                    "project_id": test_project.id,
                    "name": "Unauthorized Sprint",
                    "version": "v1.0"
                },
                headers=auth_headers_other_user
            )

            # 应该返回403 Forbidden
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_update_iteration(self, client, auth_headers_other_user, test_iteration):
        """测试无权限用户无法更新他人项目的迭代"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.put(
                f"/api/v1/iteration/{test_iteration.id}",
                json={
                    "name": "Hacked Name",
                    "version": "v99.0"
                },
                headers=auth_headers_other_user
            )

            # 应该返回403 Forbidden
            assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthorized_user_cannot_delete_iteration(self, client, auth_headers_other_user, test_iteration):
        """测试无权限用户无法删除他人项目的迭代"""
        from httpx import AsyncClient, ASGITransport
        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.delete(
                f"/api/v1/iteration/{test_iteration.id}",
                headers=auth_headers_other_user
            )

            # 应该返回403 Forbidden
            assert response.status_code == 403

    def test_cannot_move_file_to_other_project_iteration(self, db, test_project, other_project, test_iteration):
        """
        测试不能将文件移动到其他项目的迭代

        场景: 尝试将A项目的文件的iteration_id设置为B项目的迭代ID
        预期: before_flush 事件守卫应阻止此操作，抛出 ValueError
        """
        # 在test_project下创建文件
        file_obj = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="security_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/security.pdf"
        )

        # 在other_project下创建迭代
        other_iteration = iteration_crud.create_iteration(
            db=db,
            project_id=other_project.id,
            name="Other Project Sprint",
            version="v1.0"
        )

        # 尝试将文件移动到其他项目的迭代（直接修改DB，绕过API）
        file_obj.iteration_id = other_iteration.id

        # before_flush 守卫应拦截跨项目赋值
        with pytest.raises(ValueError, match="不属于文件所在项目"):
            db.commit()

        # 回滚确保后续测试不受污染
        db.rollback()

    def test_iteration_data_isolation_between_projects(self, db, test_project, other_project):
        """测试不同项目间的迭代数据完全隔离"""
        # 在test_project创建迭代
        iter_in_test = iteration_crud.create_iteration(
            db=db,
            project_id=test_project.id,
            name="Test Project Iteration",
            version="v1.0"
        )

        # 在other_project创建同名迭代
        iter_in_other = iteration_crud.create_iteration(
            db=db,
            project_id=other_project.id,
            name="Test Project Iteration",  # 同名！
            version="v1.0"
        )

        # 验证两个项目都能有同名迭代（因为唯一约束是project_id + name）
        assert iter_in_test.id != iter_in_other.id

        # 查询test_project的迭代不应包含other_project的
        test_iters = iteration_crud.get_iterations_by_project(
            db=db,
            project_id=test_project.id
        )
        assert all(it.project_id == test_project.id for it in test_iters)

        other_iters = iteration_crud.get_iterations_by_project(
            db=db,
            project_id=other_project.id
        )
        assert all(it.project_id == other_project.id for it in other_iters)


# ==================== 测试8: 数据兼容性和向后兼容 ====================

class TestBackwardCompatibility:
    """旧数据兼容性和向后兼容测试"""

    def test_legacy_null_iteration_id_shows_in_uncategorized(self, db, test_project):
        """
        测试旧数据（iteration_id为NULL）在"未分类"视图下的显示

        场景: 模拟旧系统中没有iteration_id的文件
        预期: 这些文件应该在筛选iteration_id=-1时出现
        """
        # 创建没有iteration_id的文件（模拟旧数据）
        legacy_file = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="legacy_document.docx",
            file_type="docx",
            file_url="/uploads/test/legacy.docx",
            iteration_id=None  # 明确设置为None（旧数据特征）
        )

        # 筛选未分类文件（iteration_id=-1）
        uncategorized_files = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=-1
        )

        # 验证旧数据显示在未分类中
        assert len(uncategorized_files) >= 1
        assert any(f.id == legacy_file.id for f in uncategorized_files)
        assert all(f.iteration_id is None for f in uncategorized_files)

    def test_project_without_iterations_basic_operations(self, db, test_project):
        """
        测试没有任何迭代的项目的基本操作

        场景: 项目从未创建过迭代
        预期: 文件上传、查询等基本功能正常工作
        """
        # 创建不带迭代的文件
        file1 = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="no_iter_file1.pdf",
            file_type="pdf",
            file_url="/uploads/test/noiter1.pdf"
        )

        file2 = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="no_iter_file2.png",
            file_type="png",
            file_url="/uploads/test/noiter2.png"
        )

        # 查询所有文件（不传iteration_id）
        all_files = file_crud.get_project_files(
            db=db,
            project_id=test_project.id
        )
        assert len(all_files) == 2

        # 查询未分类文件
        uncategorized = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=-1
        )
        assert len(uncategorized) == 2

        # 查询特定迭代的文件（空结果）
        fake_iteration_id = 99999
        specific_iter_files = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=fake_iteration_id
        )
        assert len(specific_iter_files) == 0

    def test_mixed_old_and_new_data_coexistence(self, db, test_project, test_iteration):
        """
        测试新旧数据共存的情况

        场景: 项目中有部分文件有iteration_id，部分没有
        预期: 各种筛选都能正确工作
        """
        # 创建旧数据（无iteration_id）
        old_files = []
        for i in range(3):
            f = file_crud.create_project_file(
                db=db,
                project_id=test_project.id,
                file_name=f"old_file_{i}.docx",
                file_type="docx",
                file_url=f"/uploads/test/old_{i}.docx",
                iteration_id=None
            )
            old_files.append(f)

        # 创建新数据（有iteration_id）
        new_files = []
        for i in range(3):
            f = file_crud.create_project_file(
                db=db,
                project_id=test_project.id,
                file_name=f"new_file_{i}.pdf",
                file_type="pdf",
                file_url=f"/uploads/test/new_{i}.pdf",
                iteration_id=test_iteration.id
            )
            new_files.append(f)

        # 验证全部文件
        all_files = file_crud.get_project_files(
            db=db,
            project_id=test_project.id
        )
        assert len(all_files) == 6

        # 验证未分类文件（只包含旧的）
        uncategorized = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=-1
        )
        assert len(uncategorized) == 3
        assert all(f.iteration_id is None for f in uncategorized)

        # 验证特定迭代的文件（只包含新的）
        iteration_files = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=test_iteration.id
        )
        assert len(iteration_files) == 3
        assert all(f.iteration_id == test_iteration.id for f in iteration_files)

    def test_ui_prototype_legacy_data_compatibility(self, db, test_project):
        """
        测试UI原型数据的向后兼容性

        场景: 旧版本中的UI原型项目没有iteration_id
        预期: 这些原型项目在筛选未分类时应出现
        """
        # 创建没有iteration_id的UI原型项目（旧数据）
        proto_legacy = ui_prototype_crud.create_ui_prototype_project(
            db=db,
            project_id=test_project.id,
            name="Legacy UI Prototype",
            source="manual",
            iteration_id=None
        )

        # 筛选未分类的原型项目
        uncategorized_protos = ui_prototype_crud.get_ui_prototype_projects_by_project(
            db=db,
            project_id=test_project.id,
            user_id=test_project.user_id,
            iteration_id=-1
        )

        assert len(uncategorized_protos) >= 1
        assert any(p.id == proto_legacy.id for p in uncategorized_protos)

    def test_iteration_id_zero_handling_frontend_compat(self, db, test_project, test_iteration):
        """
        测试前端传递iteration_id=0的处理（前后端参数兼容性）

        场景: 前端在某些情况下传递0表示"未选择迭代"
        预期: 后端正确处理0值，转换为None
        """
        # 创建文件并绑定到迭代
        file_obj = file_crud.create_project_file(
            db=db,
            project_id=test_project.id,
            file_name="zero_compat_test.xlsx",
            file_type="xlsx",
            file_url="/uploads/test/zero_compat.xlsx",
            iteration_id=test_iteration.id
        )

        # 模拟前端传0的情况
        frontend_value = 0
        backend_value = frontend_value if frontend_value > 0 else None

        # 更新文件
        file_obj.iteration_id = backend_value
        db.commit()
        db.refresh(file_obj)

        # 验证已移到未分类
        assert file_obj.iteration_id is None

        uncategorized = file_crud.get_project_files(
            db=db,
            project_id=test_project.id,
            iteration_id=-1
        )
        assert any(f.id == file_obj.id for f in uncategorized)

    def test_large_number_of_iterations_performance(self, db, test_project):
        """
        测试大量迭代的性能

        场景: 项目下有100个迭代
        预期: 分页查询性能可接受（<1秒）
        """
        import time

        # 批量创建100个迭代
        start_time = time.time()
        for i in range(100):
            iteration_crud.create_iteration(
                db=db,
                project_id=test_project.id,
                name=f"Perf Sprint {i+1}",
                version=f"v{i+1}.0"
            )
        create_time = time.time() - start_time
        print(f"\n创建100个迭代耗时: {create_time:.2f}秒")

        # 测试分页查询性能
        start_time = time.time()
        page1 = iteration_crud.get_iterations_by_project(
            db=db,
            project_id=test_project.id,
            skip=0,
            limit=20
        )
        query_time = time.time() - start_time
        print(f"分页查询耗时: {query_time:.2f}秒")

        # 验证结果
        assert len(page1) == 20
        assert query_time < 1.0  # 查询应在1秒内完成

        # 测试总数统计
        start_time = time.time()
        total = iteration_crud.get_iterations_count_by_project(
            db=db,
            project_id=test_project.id
        )
        count_time = time.time() - start_time
        print(f"计数查询耗时: {count_time:.2f}秒")

        assert total >= 100


# ==================== Fixture补充 ====================

@pytest.fixture(scope="function")
def auth_headers(test_user):
    """生成认证token"""
    from app.utils.jwt_utils import create_access_token

    token = create_access_token({"sub": str(test_user.id), "username": test_user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="function")
def auth_headers_other_user(other_user):
    """生成其他用户的认证token"""
    from app.utils.jwt_utils import create_access_token

    token = create_access_token({"sub": str(other_user.id), "username": other_user.username})
    return {"Authorization": f"Bearer {token}"}


# ==================== 运行说明 ====================
"""
运行方式:

1. 运行所有边界测试:
   pytest tests/test_iteration_edge_cases.py -v

2. 只运行并发测试:
   pytest tests/test_iteration_edge_cases.py::TestConcurrencyAndRaceConditions -v

3. 只运行权限测试:
   pytest tests/test_iteration_edge_cases.py::TestPermissionsAndSecurity -v

4. 只运行兼容性测试:
   pytest tests/test_iteration_edge_cases.py::TestBackwardCompatibility -v

5. 运行时显示详细输出:
   pytest tests/test_iteration_edge_cases.py -v -s

预期通过的测试用例数: 约15-20个
特殊标记:
   - xfail: 已知问题（如API层缺少某项验证）
   - skip: 条件不满足时跳过

注意事项:
- 并发测试依赖ThreadPoolExecutor
- 权限测试需要真实的JWT token生成
- 性能测试的结果可能因机器配置而异
"""
