"""模块2：Service层 - 最终验证脚本

验证目标:
1. 所有Service文件<300行
2. 无str(e)泄露
3. 所有导入正常
4. 向后兼容
"""
import sys
from pathlib import Path

def check_all():
    """系统性验证模块2"""
    results = []
    
    # 1. 检查所有Service文件<300行
    print("=" * 60)
    print("检查1: 文件大小 (<300行)")
    print("=" * 60)
    service_dir = Path("app/services")
    oversized_files = []
    for py_file in service_dir.rglob("*.py"):
        lines = len(py_file.read_text(encoding='utf-8').splitlines())
        if lines > 300:
            oversized_files.append((str(py_file), lines))
    
    if not oversized_files:
        print("✓ 所有Service文件<300行")
        results.append(True)
    else:
        print(f"✗ 发现{len(oversized_files)}个文件超过300行:")
        for f, lines in oversized_files:
            print(f"  - {f}: {lines}行")
        results.append(False)
    
    # 2. 检查str(e)泄露
    print("\n" + "=" * 60)
    print("检查2: str(e)安全泄露")
    print("=" * 60)
    str_e_issues = []
    for py_file in service_dir.rglob("*.py"):
        content = py_file.read_text(encoding='utf-8')
        if 'str(e)' in content:
            # 检查是否被合理使用
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                if 'str(e)' in line and 'return' in line and 'logger' not in line.lower():
                    str_e_issues.append((str(py_file), i, line.strip()))
    
    if not str_e_issues:
        print("✓ 无str(e)泄露")
        results.append(True)
    else:
        print(f"✗ 发现{len(str_e_issues)}处可能的str(e)泄露:")
        for f, line_no, line in str_e_issues[:5]:
            print(f"  - {f}:{line_no}")
        results.append(False)
    
    # 3. 检查导入
    print("\n" + "=" * 60)
    print("检查3: Service导入验证")
    print("=" * 60)
    try:
        from app.services.case_generation import TestCaseGenerationService
        print("  ✓ case_generation")
        
        from app.services.test_case_generation import TestCaseGenerationService as TC2
        print("  ✓ test_case_generation")
        
        from app.services.test_execution_engine import TestExecutionEngineV2
        print("  ✓ test_execution_engine")
        
        from app.services.precondition import PreconditionService
        print("  ✓ precondition")
        
        from app.services.task_service import TaskService
        print("  ✓ task_service")
        
        from app.services.ui_spec_parser import UISpecParserService
        print("  ✓ ui_spec_parser")
        
        from app.services.link_fetcher import LinkFetcherService
        print("  ✓ link_fetcher")
        
        from app.services.test_data import TestDataGenerator
        print("  ✓ test_data")
        
        from app.services.video import VideoRecordService
        print("  ✓ video")
        
        from app.services.cost_statistics import CostStatisticsService
        print("  ✓ cost_statistics")
        
        from app.services.mobile_ai_executor import MobileAIExecutor
        print("  ✓ mobile_ai_executor")
        
        from app.services.case_quality import CaseQualityAnalyzer
        print("  ✓ case_quality")
        
        from app.services.visibility_config import VisibilityConfigService
        print("  ✓ visibility_config")
        
        from app.services.element_locator import ElementLocatorService
        print("  ✓ element_locator")
        
        from app.services.execution_replay import ExecutionReplayService
        print("  ✓ execution_replay")
        
        results.append(True)
    except ImportError as e:
        print(f"✗ 导入失败: {e}")
        results.append(False)
    
    # 4. 运行测试
    print("\n" + "=" * 60)
    print("检查4: 单元测试")
    print("=" * 60)
    import subprocess
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', 'tests/services/test_service_refactor.py', '-v', '--tb=line'],
        capture_output=True, text=True, cwd=str(Path.cwd())
    )
    if result.returncode == 0:
        # 提取通过的测试数量
        for line in result.stdout.splitlines():
            if 'passed' in line:
                print(f"✓ {line.strip()}")
                break
        results.append(True)
    else:
        print(f"✗ 测试失败")
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        results.append(False)
    
    # 总结
    print("\n" + "=" * 60)
    print("模块2验证总结")
    print("=" * 60)
    checks = ["文件大小<300行", "无str(e)泄露", "导入正常", "单元测试通过"]
    for check, passed in zip(checks, results):
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {check}")
    
    all_passed = all(results)
    print(f"\n总体结果: {'✓ 全部通过' if all_passed else '✗ 部分未通过'}")
    return all_passed


if __name__ == "__main__":
    success = check_all()
    sys.exit(0 if success else 1)
