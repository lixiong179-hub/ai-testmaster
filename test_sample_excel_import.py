"""
验证示例Excel文件可以正确导入
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.test_case_view_service import TestCaseViewService
from app.models.project import Project


def test_import_sample():
    """测试导入示例Excel文件"""
    print("=" * 70)
    print("验证示例Excel文件导入")
    print("=" * 70)
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 创建或查找项目
        project = db.query(Project).filter(Project.name == "示例项目").first()
        if not project:
            project = Project(
                name="示例项目",
                description="用于测试示例Excel导入",
                user_id=1,
                test_object_type="web",
                test_object_url="https://example.com",
                status=1
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            print(f"✅ 创建项目: {project.name} (ID: {project.id})")
        else:
            print(f"✅ 使用现有项目: {project.name} (ID: {project.id})")
        
        # 创建服务
        service = TestCaseViewService(db)
        
        # 验证Excel格式
        excel_file = "测试用例示例_用户登录功能.xlsx"
        print(f"\n验证Excel文件: {excel_file}")
        
        validation = service.validate_excel_format(excel_file)
        print(f"格式验证结果:")
        print(f"  有效: {validation['valid']}")
        print(f"  用例数: {validation.get('case_count', 0)}")
        print(f"  步骤数: {validation.get('step_count', 0)}")
        
        if validation['errors']:
            print(f"  错误: {validation['errors']}")
            return
        
        if validation['warnings']:
            print(f"  警告: {validation['warnings']}")
        
        # 导入Excel
        print(f"\n开始导入...")
        case_id = service.import_from_excel(excel_file, project.id)
        
        if case_id:
            print(f"✅ 导入成功！")
            print(f"  测试用例ID: {case_id}")
            
            # 查询导入的数据
            from app.models.test_case import TestCase, TestStep
            test_case = db.query(TestCase).filter(TestCase.id == case_id).first()
            
            if test_case:
                print(f"\n导入的测试用例信息:")
                print(f"  用例编号: {test_case.case_no}")
                print(f"  用例标题: {test_case.title}")
                print(f"  所属模块: {test_case.module}")
                print(f"  前置条件: {test_case.precondition}")
                print(f"  预期结果: {test_case.expected_result}")
                print(f"  优先级: {test_case.priority}")
                print(f"  步骤数量: {len(test_case.test_steps)}")
                
                print(f"\n测试步骤详情:")
                for step in test_case.test_steps:
                    print(f"  步骤 {step.step_number}:")
                    print(f"    操作: {step.action}")
                    print(f"    预期: {step.expected_result}")
                    print(f"    业务视图: {'是' if step.is_business_view else '否'}")
                    print(f"    技术视图: {'是' if step.is_technical_view else '否'}")
                    print(f"    已定位: {'是' if step.has_locator else '否'}")
                    if step.element_locator:
                        print(f"    CSS选择器: {step.element_locator.css_selector}")
                        print(f"    XPath: {step.element_locator.xpath}")
                    print()
        else:
            print("❌ 导入失败")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_import_sample()
