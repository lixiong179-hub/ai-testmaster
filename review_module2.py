"""全面复盘审查 - 模块拆分验证"""
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).parent
APP_DIR = ROOT / "app" / "services"

def check_file_sizes() -> Tuple[bool, List[Tuple[str, int]]]:
    """检查所有文件是否超过300行"""
    print("\n" + "="*60)
    print("【检查1】文件大小合规性（≤300行）")
    print("="*60)
    
    oversized = []
    for py_file in APP_DIR.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if len(lines) > 300:
                    rel_path = py_file.relative_to(ROOT)
                    oversized.append((str(rel_path), len(lines)))
        except Exception as e:
            print(f"  ✗ 读取失败: {py_file}")
    
    if oversized:
        print(f"✗ 发现 {len(oversized)} 个文件超过300行:")
        for path, lines in oversized:
            print(f"  - {path}: {lines}行")
        return False, oversized
    else:
        print("✓ 所有文件均未超过300行")
        return True, []

def check_str_e_leaks() -> Tuple[bool, List]:
    """检查str(e)安全泄露"""
    import re
    print("\n" + "="*60)
    print("【检查2】str(e)安全泄露检查")
    print("="*60)
    
    leaks = []
    pattern = re.compile(r'["\']error["\'].*str\(e\)|raw_result.*str\(e\)')
    
    for py_file in APP_DIR.rglob("*.py"):
        if '__pycache__' in str(py_file):
            continue
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if pattern.search(line) and not line.strip().startswith('#'):
                        rel_path = py_file.relative_to(ROOT)
                        leaks.append((str(rel_path), line_num, line.strip()[:80]))
        except:
            pass
    
    if leaks:
        print(f"✗ 发现 {len(leaks)} 处str(e)泄露:")
        for path, line_num, line in leaks:
            print(f"  - {path}:{line_num}")
        return False, leaks
    else:
        print("✓ 无str(e)泄露")
        return True, []

def check_imports() -> Tuple[bool, List]:
    """检查关键导入"""
    print("\n" + "="*60)
    print("【检查3】导入兼容性")
    print("="*60)
    
    sys.path.insert(0, str(ROOT.parent))
    
    checks = [
        ("UserService", "app.services.user_service"),
        ("RoleService", "app.services.user_service"),
        ("UserService", "app.services.user_service.user_service"),
        ("RoleService", "app.services.role_service.role_service"),
    ]
    
    failed = []
    for class_name, module_name in checks:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"  ✓ {module_name}.{class_name}")
        except Exception as e:
            print(f"  ✗ {module_name}.{class_name}: {e}")
            failed.append(f"{module_name}.{class_name}")
    
    if failed:
        print(f"✗ {len(failed)} 个导入失败")
        return False, failed
    else:
        print("✓ 所有导入正常")
        return True, []

def check_service_structure() -> bool:
    """检查Service层结构"""
    print("\n" + "="*60)
    print("【检查4】Service层架构完整性")
    print("="*60)
    
    expected_dirs = [
        'task_service', 'user_service', 'role_service',
        'case_generation', 'test_case_generation', 'test_execution_engine',
        'precondition', 'ui_spec_parser', 'link_fetcher',
        'test_data', 'video', 'cost_statistics', 'mobile_ai_executor',
        'case_quality', 'visibility_config', 'element_locator',
        'execution_replay', 'recognizers',
    ]
    
    missing = [d for d in expected_dirs if not (APP_DIR / d).exists()]
    
    if missing:
        print(f"✗ 缺少: {', '.join(missing)}")
        return False
    else:
        print(f"✓ 所有 {len(expected_dirs)} 个子目录存在")
        return True

if __name__ == "__main__":
    results = []
    
    results.append(("文件大小", *check_file_sizes()))
    results.append(("str(e)泄露", *check_str_e_leaks()))
    results.append(("导入兼容", *check_imports()))
    results.append(("架构完整", check_service_structure(), []))
    
    print("\n" + "="*60)
    print("审查总结")
    print("="*60)
    
    for name, passed, issues in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {status}: {name}")
        if issues:
            for issue in issues[:5]:
                print(f"    - {issue}")
    
    all_passed = all(r[1] for r in results)
    print(f"\n总体: {'✓ 全部通过' if all_passed else '✗ 存在问题'}")
    sys.exit(0 if all_passed else 1)
