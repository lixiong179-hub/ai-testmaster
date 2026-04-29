"""
验证技术视图API
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.test_case_view_service import TestCaseViewService
from app.models.project import Project
from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator


def test_technical_view_api():
    """测试技术视图API功能"""
    print("=" * 70)
    print("验证技术视图API")
    print("=" * 70)
    
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 查找示例项目
        project = db.query(Project).filter(Project.name == "示例项目").first()
        if not project:
            print("❌ 未找到示例项目")
            return
        
        print(f"✅ 使用项目: {project.name} (ID: {project.id})")
        
        # 查找测试用例
        test_case = db.query(TestCase).filter(
            TestCase.project_id == project.id
        ).order_by(TestCase.id.desc()).first()
        
        if not test_case:
            print("❌ 未找到测试用例")
            return
        
        print(f"✅ 使用测试用例: {test_case.title} (ID: {test_case.id})")
        
        # 创建服务
        service = TestCaseViewService(db)
        
        # 1. 测试获取技术视图
        print("\n1. 测试获取技术视图...")
        technical_view = service.get_technical_view(test_case.id)
        if technical_view:
            print(f"  ✅ 技术视图获取成功")
            print(f"  - 用例编号: {technical_view.get('case_no')}")
            print(f"  - 用例标题: {technical_view.get('title')}")
            print(f"  - 步骤数量: {len(technical_view.get('steps', []))}")
            print(f"  - 定位覆盖率: {technical_view.get('locator_coverage', 0):.1f}%")
        else:
            print("  ❌ 技术视图获取失败")
        
        # 2. 测试获取定位覆盖率
        print("\n2. 测试获取定位覆盖率...")
        coverage = service.get_locator_coverage(test_case.id)
        print(f"  ✅ 覆盖率统计:")
        print(f"  - 总步骤数: {coverage['total_steps']}")
        print(f"  - 已定位: {coverage['located_steps']}")
        print(f"  - 待定位: {coverage['pending_steps']}")
        print(f"  - 覆盖率: {coverage['coverage_percentage']:.1f}%")
        
        # 3. 测试获取视图统计
        print("\n3. 测试获取视图统计...")
        statistics = service.get_view_statistics(test_case.id)
        print(f"  ✅ 视图统计:")
        print(f"  - 总步骤: {statistics['total_steps']}")
        print(f"  - 业务视图步骤: {statistics['business_view_steps']}")
        print(f"  - 技术视图步骤: {statistics['technical_view_steps']}")
        print(f"  - 已定位步骤: {statistics['located_steps']}")
        print(f"  - 定位覆盖率: {statistics['locator_coverage']}")
        
        # 4. 测试导出为JSON
        print("\n4. 测试导出为JSON...")
        json_data = service.export_technical_view_to_json(test_case.id)
        if json_data:
            print(f"  ✅ JSON导出成功")
            print(f"  - 数据大小: {len(str(json_data))} 字符")
        else:
            print("  ❌ JSON导出失败")
        
        # 5. 测试导出为Python脚本
        print("\n5. 测试导出为Python脚本...")
        python_script = service.export_technical_view_to_python(test_case.id)
        if python_script:
            print(f"  ✅ Python脚本导出成功")
            print(f"  - 脚本行数: {len(python_script.split(chr(10)))} 行")
            # 打印前10行
            print("  - 脚本预览:")
            for i, line in enumerate(python_script.split(chr(10))[:10]):
                print(f"    {line}")
            print("    ...")
        else:
            print("  ❌ Python脚本导出失败")
        
        print("\n" + "=" * 70)
        print("技术视图API验证完成！")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_technical_view_api()
