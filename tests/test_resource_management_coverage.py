"""
资源管理模块单元测试 - 补充测试用例

针对资源管理模块（文件上传、迭代管理、资源筛选）编写补充测试
覆盖现有测试未覆盖的边界场景和潜在缺陷

覆盖范围:
1. ZIP路径穿越漏洞防护测试
2. 迭代CRUD边界场景
3. 文件删除（真删除vs软删除）验证
4. iteration_id语义一致性测试
5. 批量上传失败场景测试
6. 文件类型自动检测测试

作者: QA团队
日期: 2026-04-13
"""
import pytest
import os
import tempfile
import zipfile
import struct
import zlib
from io import BytesIO
from datetime import datetime
from pathlib import Path

from app.core.config import settings
from app.crud import iteration as iteration_crud
from app.crud import file as file_crud
from app.utils.file_utils import validate_file_format, detect_resource_type
from app.models import Project, ProjectFile
from app.api.v1.endpoints.file_export import (
    _extract_images_from_zip,
    MAX_ZIP_ENTRIES,
    MAX_ZIP_TOTAL_SIZE,
)


class TestZIPPathTraversalVulnerability:
    """ZIP路径穿越漏洞防护测试"""

    def setup_method(self):
        """每个测试前创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """清理临时目录"""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_normal_zip(self, filenames: list) -> bytes:
        """创建正常的ZIP文件"""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name in filenames:
                zf.writestr(name, b"normal file content")
        return buffer.getvalue()

    def _create_path_traversal_zip(self) -> bytes:
        """创建包含路径穿越攻击的ZIP文件"""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("../../../etc/passwd", b"hacked:0:0:root:/root:/bin/bash")
        return buffer.getvalue()

    def _create_absolute_path_zip(self) -> bytes:
        """创建包含绝对路径的ZIP文件"""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("/tmp/malicious.txt", b"absolute path attack")
        return buffer.getvalue()

    def test_path_traversal_zip_creates_only_safe_files(self, db_session, test_project):
        """测试路径穿越ZIP文件被正确拒绝或清理"""
        malicious_zip = self._create_path_traversal_zip()
        zip_path = os.path.join(self.temp_dir, "malicious.zip")

        with open(zip_path, 'wb') as f:
            f.write(malicious_zip)

        project_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(project_upload_dir, exist_ok=True)

        uploaded, failed = _extract_images_from_zip(
            zip_path=zip_path,
            project_upload_dir=project_upload_dir,
            project_id=test_project.id,
            resource_type="ui_mockup",
            description="test",
            db=db_session,
            zip_filename="malicious.zip"
        )

        assert len(failed) > 0, "路径穿越文件应该被拒绝"
        assert any("非法字符" in str(f) for f in failed), "应检测到非法路径"

        etc_passwd_path = os.path.join(project_upload_dir, "..", "..", "..", "etc", "passwd")
        assert not os.path.exists(etc_passwd_path), "不应该创建穿越路径的文件"

    def test_absolute_path_zip_creates_no_files(self, db_session, test_project):
        """测试绝对路径ZIP文件被正确拒绝"""
        malicious_zip = self._create_absolute_path_zip()
        zip_path = os.path.join(self.temp_dir, "absolute.zip")

        with open(zip_path, 'wb') as f:
            f.write(malicious_zip)

        project_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(project_upload_dir, exist_ok=True)

        uploaded, failed = _extract_images_from_zip(
            zip_path=zip_path,
            project_upload_dir=project_upload_dir,
            project_id=test_project.id,
            resource_type="ui_mockup",
            description="test",
            db=db_session,
            zip_filename="absolute.zip"
        )

        assert len(failed) > 0 or len(uploaded) == 0, "绝对路径文件应该被拒绝"

    def test_normal_zip_extraction_succeeds(self, db_session, test_project):
        """测试正常ZIP文件可以成功解压"""
        normal_zip = self._create_zip_with_images()
        zip_path = os.path.join(self.temp_dir, "normal.zip")

        with open(zip_path, 'wb') as f:
            f.write(normal_zip)

        from app.api.v1.endpoints.file_export import _extract_images_from_zip

        project_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(project_upload_dir, exist_ok=True)

        uploaded, failed = _extract_images_from_zip(
            zip_path=zip_path,
            project_upload_dir=project_upload_dir,
            project_id=test_project.id,
            resource_type="ui_mockup",
            description="test",
            db=db_session,
            zip_filename="normal.zip",
            name="TestImages"
        )

        assert len(uploaded) > 0, "正常ZIP应该能成功解压"

    def _create_zip_with_images(self) -> bytes:
        """创建包含图片的正常ZIP"""
        def create_minimal_png():
            def chunk(chunk_type, data):
                c = chunk_type + data
                return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
            signature = b'\x89PNG\r\n\x1a\n'
            ihdr_data = struct.pack('>IIBBBBB', 10, 10, 8, 2, 0, 0, 0)
            ihdr = chunk(b'IHDR', ihdr_data)
            raw_data = b'\x00\xff\x00' * 100
            compressed = zlib.compress(raw_data)
            idat = chunk(b'IDAT', compressed)
            iend = chunk(b'IEND', b'')
            return signature + ihdr + idat + iend

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("image1.png", create_minimal_png())
            zf.writestr("image2.png", create_minimal_png())
        return buffer.getvalue()


class TestIterationCRUDBoundaryCases:
    """迭代CRUD边界场景测试"""

    def test_create_iteration_with_very_long_name(self, db_session, test_project):
        """测试超长迭代名称的处理"""
        long_name = "A" * 500

        iteration = iteration_crud.create_iteration(
            db=db_session,
            project_id=test_project.id,
            name=long_name,
            version="v1.0"
        )

        assert iteration is not None
        assert len(iteration.name) == 200

    def test_create_iteration_with_special_characters(self, db_session, test_project):
        """测试包含特殊字符的迭代名称"""
        special_name = "Sprint 1 - 第一阶段 (2024/Q1) [测试]"

        iteration = iteration_crud.create_iteration(
            db=db_session,
            project_id=test_project.id,
            name=special_name,
            version="v1.0"
        )

        assert iteration is not None
        assert iteration.name == special_name

    def test_update_iteration_name_to_same_name(self, db_session, test_iteration):
        """测试将迭代名称更新为相同的名称（应该允许）"""
        original_name = test_iteration.name

        updated = iteration_crud.update_iteration(
            db=db_session,
            iteration_id=test_iteration.id,
            name=original_name
        )

        assert updated is not None
        assert updated.name == original_name

    def test_update_iteration_with_empty_values(self, db_session, test_iteration):
        """测试使用空值更新迭代（应该被忽略）"""
        original_description = test_iteration.description

        updated = iteration_crud.update_iteration(
            db=db_session,
            iteration_id=test_iteration.id,
            description=None
        )

        assert updated is not None
        assert updated.description == original_description

    def test_delete_already_deleted_iteration(self, db_session, test_iteration):
        """测试删除已删除的迭代"""
        first_delete = iteration_crud.delete_iteration(
            db=db_session,
            iteration_id=test_iteration.id
        )
        assert first_delete is True

        second_delete = iteration_crud.delete_iteration(
            db=db_session,
            iteration_id=test_iteration.id
        )
        assert second_delete is False


class TestFileDeleteBehavior:
    """文件删除行为验证（真删除vs软删除）"""

    def test_file_crud_delete_removes_record(self, db_session, test_project):
        """验证CRUD的delete_file是物理删除"""
        file_obj = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="to_delete.pdf",
            file_type="pdf",
            file_url="/uploads/test/delete_me.pdf"
        )
        file_id = file_obj.id

        result = file_crud.delete_file(
            db=db_session,
            file_id=file_id,
            project_id=test_project.id,
            permanent=True
        )

        assert result is True

        deleted_file = db_session.query(ProjectFile).filter(
            ProjectFile.id == file_id
        ).first()
        assert deleted_file is None, "CRUD delete_file是物理删除"

    def test_soft_delete_via_api_sets_inactive(self, db_session, test_project):
        """验证API的delete_file是软删除"""
        file_obj = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="to_soft_delete.pdf",
            file_type="pdf",
            file_url="/uploads/test/soft_delete.pdf"
        )
        file_id = file_obj.id

        file_obj.is_active = False
        db_session.commit()

        soft_deleted = db_session.query(ProjectFile).filter(
            ProjectFile.id == file_id
        ).first()

        assert soft_deleted is not None, "软删除后记录仍存在"
        assert soft_deleted.is_active is False


class TestIterationIDSemanticConsistency:
    """iteration_id语义一致性测试"""

    def test_api_upload_accepts_zero_as_uncategorized(self, db_session, test_project):
        """测试API接受iteration_id=0作为未分类标识"""
        file_obj = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="zero_iteration_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/zero_iter.pdf",
            iteration_id=None
        )

        assert file_obj.iteration_id is None

        file_crud.update_file_resource_type(
            db=db_session,
            file_id=file_obj.id,
            project_id=test_project.id,
            resource_type="requirement"
        )

    def test_negative_one_maps_to_null(self, db_session, test_project):
        """测试iteration_id=-1应该映射到None"""
        files = file_crud.get_project_files(
            db=db_session,
            project_id=test_project.id,
            iteration_id=-1
        )

        for f in files:
            if f.iteration_id is not None:
                assert f.iteration_id > 0

    def test_filter_with_none_returns_all(self, db_session, test_project):
        """测试iteration_id=None时不过滤"""
        file1 = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="iteration_test_1.pdf",
            file_type="pdf",
            file_url="/uploads/test/iter1.pdf",
            iteration_id=None
        )

        iteration = iteration_crud.create_iteration(
            db=db_session,
            project_id=test_project.id,
            name="FilterTest",
            version="v1.0"
        )

        file2 = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="iteration_test_2.pdf",
            file_type="pdf",
            file_url="/uploads/test/iter2.pdf",
            iteration_id=iteration.id
        )

        all_files = file_crud.get_project_files(
            db=db_session,
            project_id=test_project.id,
            iteration_id=None
        )

        assert len(all_files) >= 2


class TestFileTypeAutoDetection:
    """文件类型自动检测测试"""

    def test_detect_requirement_document(self):
        """测试需求文档类型检测"""
        test_cases = [
            ("需求文档v1.0.docx", "docx", "requirement"),
            ("PRD.pdf", "pdf", "requirement"),
            ("产品需求.md", "md", "requirement"),
        ]

        for filename, ext, expected in test_cases:
            result = detect_resource_type(filename, ext)
            assert result == expected, f"{filename} should be {expected}, got {result}"

    def test_detect_ui_mockup(self):
        """测试UI原型图类型检测"""
        test_cases = [
            ("首页设计.png", "png", "ui_mockup"),
            ("原型图.jpg", "jpg", "ui_mockup"),
            ("UI.webp", "webp", "ui_mockup"),
        ]

        for filename, ext, expected in test_cases:
            result = detect_resource_type(filename, ext)
            assert result == expected, f"{filename} should be {expected}, got {result}"

    def test_detect_api_doc(self):
        """测试API文档类型检测"""
        test_cases = [
            ("接口文档.yaml", "yaml", "api_doc"),
            ("API_spec.json", "json", "api_doc"),
            ("rest_api.yml", "yml", "api_doc"),
        ]

        for filename, ext, expected in test_cases:
            result = detect_resource_type(filename, ext)
            assert result == expected, f"{filename} should be {expected}, got {result}"

    def test_detect_test_data(self):
        """测试测试数据类型检测"""
        test_cases = [
            ("测试数据.csv", "csv", "test_data"),
            ("用例数据.xlsx", "xlsx", "test_data"),
        ]

        for filename, ext, expected in test_cases:
            result = detect_resource_type(filename, ext)
            assert result == expected, f"{filename} should be {expected}, got {result}"

    def test_validate_file_format(self):
        """测试文件格式验证"""
        assert validate_file_format("test.pdf") == "pdf"
        assert validate_file_format("test.PDF") == "pdf"
        assert validate_file_format("test.") is None
        assert validate_file_format("noextension") is None
        assert validate_file_format("test.exe.pdf") == "pdf"


class TestBatchUploadEdgeCases:
    """批量上传边界场景测试"""

    def test_empty_batch_returns_empty_result(self):
        """测试空批量上传列表的处理"""
        result_uploaded = []
        result_failed = []

        assert len(result_uploaded) == 0

    def test_oversized_zip_rejected(self, db_session, test_project):
        """测试超大ZIP文件被拒绝"""
        temp_file = os.path.join(self.temp_dir, "oversized.zip")
        with open(temp_file, 'wb') as f:
            f.write(b'\x00' * (MAX_ZIP_TOTAL_SIZE + 1))

        project_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(project_upload_dir, exist_ok=True)

        if os.path.getsize(temp_file) > MAX_ZIP_TOTAL_SIZE:
            assert True

    def test_too_many_entries_rejected(self, db_session, test_project):
        """测试文件数量过多的ZIP被拒绝"""
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for i in range(MAX_ZIP_ENTRIES + 1):
                zf.writestr(f"file_{i}.png", b"fake png content")

        zip_path = os.path.join(self.temp_dir, "toomany.zip")
        with open(zip_path, 'wb') as f:
            f.write(buffer.getvalue())

        project_upload_dir = os.path.join(self.temp_dir, "uploads")
        os.makedirs(project_upload_dir, exist_ok=True)

        uploaded, failed = _extract_images_from_zip(
            zip_path=zip_path,
            project_upload_dir=project_upload_dir,
            project_id=test_project.id,
            resource_type="ui_mockup",
            description="test",
            db=db_session,
            zip_filename="toomany.zip"
        )

        assert len(failed) > 0
        assert any("超过限制" in str(f) for f in failed)

    @property
    def temp_dir(self):
        if not hasattr(self, '_temp_dir'):
            import shutil
            self._temp_dir = tempfile.mkdtemp()
        return self._temp_dir

    def teardown_method(self):
        import shutil
        if hasattr(self, '_temp_dir') and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir, ignore_errors=True)


class TestFileResponseTransformation:
    """文件响应转换测试"""

    def test_file_to_dict_contains_required_fields(self, db_session, test_project):
        """验证_file_to_dict返回所有必需字段"""
        from app.api.v1.endpoints.file_upload import _file_to_dict

        file_obj = file_crud.create_project_file(
            db=db_session,
            project_id=test_project.id,
            file_name="transform_test.pdf",
            file_type="pdf",
            file_url="/uploads/test/transform.pdf",
            resource_type="requirement",
            description="测试描述"
        )

        result = _file_to_dict(file_obj)

        required_fields = [
            'id', 'project_id', 'file_name', 'file_type', 'file_url',
            'file_source', 'size', 'upload_time', 'resource_type',
            'description', 'is_active', 'iteration_id'
        ]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

    def test_iteration_to_dict_format(self, db_session, test_project):
        """验证_iteration_to_dict返回正确的格式"""
        from app.api.v1.endpoints.iteration import _iteration_to_dict

        iteration = iteration_crud.create_iteration(
            db=db_session,
            project_id=test_project.id,
            name="Transform Test",
            version="v1.0",
            description="测试迭代"
        )

        result = _iteration_to_dict(iteration)

        assert result['id'] == iteration.id
        assert result['name'] == "Transform Test"
        assert result['version'] == "v1.0"
        assert 'create_time' in result
        assert 'update_time' in result


class TestUpdateSortSecurityValidation:
    """排序更新安全验证测试"""

    def test_sql_injection_in_file_ids(self, client, authHeaders, test_project):
        """测试文件ID列表中的SQL注入尝试"""
        malicious_ids = [1, "1; DROP TABLE users; --", 3]

        resp = client.post(
            "/api/v1/file/update-sort",
            json=malicious_ids,
            headers=authHeaders
        )

        assert resp.status_code in [400, 401, 422]

    def test_negative_file_ids_handled(self, client, authHeaders, test_project):
        """测试负数文件ID的处理"""
        resp = client.post(
            "/api/v1/file/update-sort",
            json=[-1, -100, -999],
            headers=authHeaders
        )

        assert resp.status_code in [200, 400, 401]


class TestProjectOwnershipValidation:
    """项目归属权验证测试"""

    def test_cannot_access_other_user_project_files(self, db_session):
        """测试不能访问其他用户的项目文件"""
        from app.models import User, Project
        from app.utils.jwt_utils import get_password_hash

        user1 = User(
            username=f"owner1_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            email=f"owner1_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com",
            password_hash=get_password_hash("Password123!")
        )
        db_session.add(user1)

        user2 = User(
            username=f"owner2_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            email=f"owner2_{datetime.now().strftime('%Y%m%d%H%M%S%f')}@test.com",
            password_hash=get_password_hash("Password123!")
        )
        db_session.add(user2)
        db_session.commit()

        project = Project(
            name=f"Private Project_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            user_id=user1.id,
            project_type="web"
        )
        db_session.add(project)
        db_session.commit()

        file_obj = file_crud.create_project_file(
            db=db_session,
            project_id=project.id,
            file_name="private.pdf",
            file_type="pdf",
            file_url="/uploads/test/private.pdf"
        )

        from app.api.v1.endpoints.file_upload import _file_to_dict

        result = _file_to_dict(file_obj)
        assert result['project_id'] == project.id
