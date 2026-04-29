"""
测试Excel导入导出功能
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.services.test_case_view_service import TestCaseViewService
from app.models.test_case import TestCase, TestStep
from app.models.project import Project
from app.db.database import Base


def test_export():
    """测试导出功能"""
    print("=" * 60)
    print("测试Excel导出功能")
    print("=" * 60)
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 查找一个测试用例
        test_case = db.query(TestCase).first()
        if not test_case:
            print("❌ 没有找到测试用例")
            return
        
        print(f"找到测试用例: {test_case.case_no} - {test_case.title}")
        
        # 创建服务
        service = TestCaseViewService(db)
        
        # 导出为Excel
        export_path = "test_case_export.xlsx"
        success = service.export_to_excel(test_case.id, export_path)
        
        if success:
            print(f"✅ 导出成功: {export_path}")
            print(f"文件大小: {os.path.getsize(export_path)} bytes")
        else:
            print("❌ 导出失败")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
    finally:
        db.close()


def test_import():
    """测试导入功能"""
    print("\n" + "=" * 60)
    print("测试Excel导入功能")
    print("=" * 60)
    
    # 创建数据库连接
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # 查找一个项目
        project = db.query(Project).first()
        if not project:
            print("❌ 没有找到项目")
            return
        
        print(f"使用项目: {project.name} (ID: {project.id})")
        
        # 创建服务
        service = TestCaseViewService(db)
        
        # 先创建一个示例Excel文件
        import pandas as pd
        
        # 用例信息
        case_info = pd.DataFrame([{
            "用例编号": "TC002",
            "用例标题": "登录功能测试-导入",
            "所属模块": "登录模块",
            "前置条件": "用户已注册",
            "预期结果": "登录成功",
            "优先级": 1
        }])
        
        # 测试步骤
        steps = pd.DataFrame([
            {
                "步骤编号": 1,
                "操作步骤": "打开登录页面",
                "预期结果": "页面加载成功",
                "业务视图": "是",
                "技术视图": "是",
                "已定位": "否",
                "定位状态": "pending",
                "CSS选择器": "",
                "XPath": "",
                "元素类型": ""
            },
            {
                "步骤编号": 2,
                "操作步骤": "输入用户名 'admin'",
                "预期结果": "用户名显示在输入框",
                "业务视图": "是",
                "技术视图": "是",
                "已定位": "是",
                "定位状态": "recorded",
                "CSS选择器": "input[name=username]",
                "XPath": "//input[@name='username']",
                "元素类型": "input"
            },
            {
                "步骤编号": 3,
                "操作步骤": "点击登录按钮",
                "预期结果": "跳转到首页",
                "业务视图": "是",
                "技术视图": "是",
                "已定位": "是",
                "定位状态": "recorded",
                "CSS选择器": "button[type=submit]",
                "XPath": "//button[@type='submit']",
                "元素类型": "button"
            }
        ])
        
        # 保存Excel文件
        import_file = "test_case_import.xlsx"
        with pd.ExcelWriter(import_file, engine='openpyxl') as writer:
            case_info.to_excel(writer, sheet_name='用例信息', index=False)
            steps.to_excel(writer, sheet_name='测试步骤', index=False)
        
        print(f"✅ 创建示例Excel文件: {import_file}")
        
        # 验证Excel格式
        validation = service.validate_excel_format(import_file)
        print(f"\nExcel格式验证结果:")
        print(f"  有效: {validation['valid']}")
        print(f"  用例数: {validation.get('case_count', 0)}")
        print(f"  步骤数: {validation.get('step_count', 0)}")
        if validation['errors']:
            print(f"  错误: {validation['errors']}")
        
        # 导入Excel
        if validation['valid']:
            case_id = service.import_from_excel(import_file, project.id)
            if case_id:
                print(f"\n✅ 导入成功，测试用例ID: {case_id}")
                
                # 验证导入的数据
                imported_case = db.query(TestCase).filter(TestCase.id == case_id).first()
                if imported_case:
                    print(f"  用例编号: {imported_case.case_no}")
                    print(f"  用例标题: {imported_case.title}")
                    print(f"  步骤数量: {len(imported_case.test_steps)}")
            else:
                print("\n❌ 导入失败")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_export()
    test_import()
    
    print("\n" + "=" * 60)
    print("Excel导入导出测试完成！")
    print("=" * 60)
