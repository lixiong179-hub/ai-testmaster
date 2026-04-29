"""
测试将AI生成的测试用例导出为第三方公司功能用例格式
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
print("测试AI生成用例导出为第三方公司功能用例格式")
print("=" * 70)

try:
    # 创建服务实例
    service = TestCaseViewService(db)
    
    # 查找最近导入的功能用例
    test_cases = db.query(TestCase).filter(
        TestCase.title.like('%登录%')
    ).order_by(TestCase.id.desc()).limit(3).all()
    
    if not test_cases:
        print("❌ 未找到测试用例，请先运行 test_functional_excel_import.py 导入用例")
    else:
        print(f"✅ 找到 {len(test_cases)} 条测试用例")
        
        # 导出为功能用例格式
        output_file = "AI生成用例_第三方公司格式.xlsx"
        case_ids = [tc.id for tc in test_cases]
        
        print(f"\n导出到: {output_file}")
        success = service.export_to_functional_excel(case_ids, output_file)
        
        if success:
            print(f"✅ 导出成功！")
            
            # 验证导出的文件
            import pandas as pd
            df = pd.read_excel(output_file, sheet_name=0)
            
            print(f"\n导出的用例信息:")
            print("-" * 70)
            
            for _, row in df.iterrows():
                print(f"\n📋 {row['标题']}")
                print(f"   编号: {row['执行用例ID']}")
                print(f"   模块: {row['所属模块']}")
                print(f"   优先级: {row['用例等级']}")
                print(f"   类型: {row['用例类型']}")
                print(f"   前置条件: {row['前置条件'][:40]}..." if len(str(row['前置条件'])) > 40 else f"   前置条件: {row['前置条件']}")
                
                # 显示步骤
                steps = str(row['步骤描述']).split('\n')[:2]
                print(f"   步骤:")
                for step in steps:
                    print(f"     {step[:45]}..." if len(step) > 45 else f"     {step}")
                if len(str(row['步骤描述']).split('\n')) > 2:
                    print(f"     ... 还有 {len(str(row['步骤描述']).split(chr(10))) - 2} 个步骤")
        else:
            print(f"❌ 导出失败")
    
except Exception as e:
    print(f"❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()

print("\n" + "=" * 70)
print("测试完成")
print("=" * 70)
