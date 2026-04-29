"""
测试第三方公司功能用例Excel导入功能
"""
import sys
import os

# 添加项目根目录到路径
project_root = r'c:\Users\19476\Desktop\ai-testmaster(2)\ai-testmaster'
sys.path.insert(0, project_root)
os.chdir(project_root)

# 先导入所有模型
from app.models.element_locator import ElementLocator
from app.db.database import PrimarySessionLocal
from app.services.test_case_view_service import TestCaseViewService
from app.models.project import Project
from app.models.test_case import TestCase, TestStep

# 创建数据库会话
db = PrimarySessionLocal()

print("=" * 70)
print("验证第三方公司功能用例Excel文件导入")
print("=" * 70)

try:
    # 创建或获取测试项目
    project = db.query(Project).filter(Project.name == "功能用例导入测试项目").first()
    if not project:
        project = Project(
            name="功能用例导入测试项目",
            description="用于测试功能用例Excel导入",
            status=1,
            user_id=1
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        print(f"✅ 创建测试项目: {project.name} (ID: {project.id})")
    else:
        print(f"✅ 使用现有项目: {project.name} (ID: {project.id})")
    
    # 创建服务实例
    service = TestCaseViewService(db)
    
    # 验证Excel格式
    excel_file = "测试用例示例_第三方公司格式.xlsx"
    print(f"\n验证Excel文件: {excel_file}")
    
    validation = service.validate_functional_excel(excel_file)
    print(f"格式验证结果:")
    print(f"  有效: {validation['valid']}")
    print(f"  用例数: {validation.get('case_count', 0)}")
    print(f"  格式类型: {validation.get('format_type', 'unknown')}")
    
    if validation['errors']:
        print(f"  错误: {validation['errors']}")
    if validation['warnings']:
        print(f"  警告: {validation['warnings']}")
    
    if validation['valid']:
        print(f"\n开始导入...")
        case_ids = service.import_functional_excel(excel_file, project.id)
        
        if case_ids:
            print(f"✅ 导入成功！")
            
            # 查询所有导入的用例
            imported_cases = db.query(TestCase).filter(
                TestCase.project_id == project.id
            ).order_by(TestCase.id.desc()).limit(validation['case_count']).all()
            
            print(f"\n共导入 {len(imported_cases)} 条用例:")
            print("-" * 70)
            
            for tc in reversed(imported_cases):  # 按原始顺序显示
                steps = db.query(TestStep).filter(TestStep.test_case_id == tc.id).all()
                print(f"\n📋 {tc.title}")
                print(f"   编号: {tc.case_no} | 模块: {tc.module} | 优先级: P{tc.priority-1}")
                print(f"   步骤数: {len(steps)}")
                
                for step in steps[:2]:  # 只显示前2步
                    action = step.action[:35] + "..." if len(step.action) > 35 else step.action
                    print(f"     {step.step_number}. {action}")
                if len(steps) > 2:
                    print(f"     ... 还有 {len(steps) - 2} 个步骤")
                    
        else:
            print(f"❌ 导入失败")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
