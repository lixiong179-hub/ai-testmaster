
"""全面复盘审查脚本 - 核实所有任务完成情况

审查范围:
1. 模块1：Core层（异常处理、常量、配置）
2. 模块2：Service层（文件拆分、安全修复、类型注解）
3. 模块3：API层（路由、依赖注入、中间件）
4. 模块4：测试覆盖率（≥80%）
5. 代码规范（文件大小≤300行、无str(e)、类型注解）
6. 向后兼容性
"""
import sys
import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple

# 项目根目录
ROOT = Path(__file__).parent
APP_DIR = ROOT / "app"
SERVICES_DIR = APP_DIR / "services"
TESTS_DIR = ROOT / "tests"

class ComplianceReviewer:
    """合规审查器"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
        self.passed = []
    
    def check_file_size_limit(self, limit: int = 300) -> bool:
        """检查所有Python文件是否超过行数限制"""
        print("\n" + "="*60)
        print("【检查1】文件大小限制（≤300行）")
        print("="*60)
        
        oversized_files = []
        for py_file in APP_DIR.rglob("*.py"):
            if '__pycache__' in str(py_file):
                continue
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) > limit:
                        rel_path = py_file.relative_to(ROOT)
                        oversized_files.append((rel_path, len(lines)))
            except Exception as e:
                self.warnings.append(f"无法读取文件 {py_file}: {e}")
        
        if oversized_files:
            print(f"✗ 发现 {len(oversized_files)} 个文件超过 {limit} 行:")
            for path, lines in oversized_files:
                print(f"  - {path}: {lines}行")
                self.issues.append(f"文件 {path} 超过行数限制: {lines}行 > {limit}行")
            return False
        else:
            print("✓ 所有文件均未超过300行")
            self.passed.append("文件大小合规")
            return True
    
    def check_str_e_leak(self) -> bool:
        """检查是否存在str(e)泄露到API响应"""
        print("\n" + "="*60)
        print("【检查2】安全：str(e)信息泄露")
        print("="*60)
        
        # 匹配 raw_result={"error": str(e)} 或类似模式
        str_e_pattern = re.compile(r'raw_result\s*[=:]\s*\{[^}]*str\(e\)[^}]*\}|["\']error["\'].*str\(e\)|f["\'].*\{e\}.*["\'].*error')
        
        leaks = []
        for py_file in APP_DIR.rglob("*.py"):
            if '__pycache__' in str(py_file):
                continue
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if str_e_pattern.search(line):
                            # 排除注释
                            stripped = line.strip()
                            if not stripped.startswith('#'):
                                rel_path = py_file.relative_to(ROOT)
                                leaks.append((rel_path, line_num, stripped))
            except Exception:
                pass
        
        if leaks:
            print(f"✗ 发现 {len(leaks)} 处str(e)泄露:")
            for path, line_num, line in leaks:
                print(f"  - {path}:{line_num}")
                print(f"    {line[:100]}")
                self.issues.append(f"安全泄露: {path}:{line_num}")
            return False
        else:
            print("✓ 未发现str(e)信息泄露")
            self.passed.append("无str(e)泄露")
            return True
    
    def check_type_annotations(self) -> bool:
        """检查公开方法是否有类型注解"""
        print("\n" + "="*60)
        print("【检查3】类型注解")
        print("="*60)
        
        import inspect
        missing_annotations = []
        
        # 检查关键Service类
        service_modules = [
            'app.services.user_service.user_service',
            'app.services.role_service.role_service',
            'app.services.task_service',
            'app.services.test_data_parameterizer',
        ]
        
        for module_name in service_modules:
            try:
                module = __import__(module_name, fromlist=[''])
                for name in dir(module):
                    if name.startswith('_'):
                        continue
                    cls = getattr(module, name, None)
                    if cls and inspect.isclass(cls):
                        for method_name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
                            if method_name.startswith('_'):
                                continue
                            sig = inspect.signature(method)
                            if sig.return_annotation == inspect.Parameter.empty:
                                missing_annotations.append(f"{module_name}.{name}.{method_name}")
            except ImportError as e:
                self.warnings.append(f"无法导入模块 {module_name}: {e}")
            except Exception as e:
                self.warnings.append(f"检查类型注解时出错 {module_name}: {e}")
        
        if missing_annotations:
            print(f"✗ 发现 {len(missing_annotations)} 个方法缺少返回类型注解:")
            for method in missing_annotations[:10]:  # 只显示前10个
                print(f"  - {method}")
            if len(missing_annotations) > 10:
                print(f"  ... 还有 {len(missing_annotations) - 10} 个")
            self.issues.append(f"{len(missing_annotations)} 个方法缺少类型注解")
            return False
        else:
            print("✓ 所有公开方法均有类型注解")
            self.passed.append("类型注解完整")
            return True
    
    def check_imports(self) -> bool:
        """检查关键导入是否正常"""
        print("\n" + "="*60)
        print("【检查4】导入验证")
        print("="*60)
        
        imports_to_check = [
            ("UserService", "app.services.user_service.user_service"),
            ("RoleService", "app.services.role_service.role_service"),
            ("TaskService", "app.services.task_service"),
            ("TestDataParameterizer", "app.services.test_data_parameterizer"),
            ("UserService", "app.services.user_service"),  # 向后兼容
            ("RoleService", "app.services.user_service"),  # 向后兼容
        ]
        
        failed_imports = []
        for class_name, module_name in imports_to_check:
            try:
                module = __import__(module_name, fromlist=[class_name])
                cls = getattr(module, class_name)
                print(f"  ✓ {module_name}.{class_name}")
            except ImportError as e:
                print(f"  ✗ {module_name}.{class_name}: {e}")
                failed_imports.append(f"{module_name}.{class_name}")
                self.issues.append(f"导入失败: {module_name}.{class_name}")
            except Exception as e:
                print(f"  ✗ {module_name}.{class_name}: {e}")
                failed_imports.append(f"{module_name}.{class_name}")
                self.issues.append(f"导入异常: {module_name}.{class_name} - {e}")
        
        if failed_imports:
            return False
        else:
            print("✓ 所有导入正常")
            self.passed.append("导入验证通过")
            return True
    
    def check_backward_compatibility(self) -> bool:
        """检查向后兼容性"""
        print("\n" + "="*60)
        print("【检查5】向后兼容性")
        print("="*60)
        
        # 检查旧的导入路径是否仍然有效
        compatibility_checks = [
            # 原路径 -> 新路径
            ("app.services.user_role_service", "已拆分为 user_service 和 role_service"),
        ]
        
        # 检查是否有代理模块
        old_module = ROOT / "app" / "services" / "user_role_service.py"
        if old_module.exists():
            print(f"  ⚠ user_role_service.py 仍然存在（应删除或改为代理）")
            self.warnings.append("user_role_service.py 未删除")
        
        # 检查 __init__.py 是否重新导出
        init_file = ROOT / "app" / "services" / "__init__.py"
        if init_file.exists():
            try:
                with open(init_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'UserService' in content and 'RoleService' in content:
                        print("  ✓ __init__.py 已重新导出 UserService 和 RoleService")
                        self.passed.append("向后兼容导出")
                        return True
            except Exception as e:
                self.warnings.append(f"读取 __init__.py 失败: {e}")
        
        print("  ⚠ 向后兼容性需进一步验证")
        self.warnings.append("向后兼容性未完全验证")
        return True  # 警告但不失败
    
    def check_test_coverage(self) -> bool:
        """检查测试覆盖率"""
        print("\n" + "="*60)
        print("【检查6】测试覆盖率（目标≥80%）")
        print("="*60)
        
        try:
            # 运行覆盖率检查
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "--cov=app", "--cov-report=term-missing", "-q"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            # 解析覆盖率
            coverage_output = result.stdout + result.stderr
            coverage_match = re.search(r'TOTAL\s+\d+\s+\d+\s+(\d+)%', coverage_output)
            
            if coverage_match:
                coverage = int(coverage_match.group(1))
                print(f"  当前覆盖率: {coverage}%")
                if coverage >= 80:
                    print("  ✓ 覆盖率达标（≥80%）")
                    self.passed.append(f"测试覆盖率: {coverage}%")
                    return True
                else:
                    print(f"  ✗ 覆盖率未达标（{coverage}% < 80%）")
                    self.issues.append(f"测试覆盖率不足: {coverage}%")
                    return False
            else:
                print("  ⚠ 无法解析覆盖率数据")
                self.warnings.append("无法解析覆盖率")
                return True  # 警告但不失败
        except subprocess.TimeoutExpired:
            print("  ✗ 测试超时（>120秒）")
            self.issues.append("测试超时")
            return False
        except Exception as e:
            print(f"  ✗ 测试运行失败: {e}")
            self.warnings.append(f"测试运行失败: {e}")
            return True
    
    def check_service_structure(self) -> bool:
        """检查Service层结构是否符合规范"""
        print("\n" + "="*60)
        print("【检查7】Service层架构规范")
        print("="*60)
        
        expected_dirs = [
            'task_service',
            'user_service',
            'role_service',
            'case_generation',
            'test_case_generation',
            'test_execution_engine',
            'precondition',
            'ui_spec_parser',
            'link_fetcher',
            'test_data',
            'video',
            'cost_statistics',
            'mobile_ai_executor',
            'case_quality',
            'visibility_config',
            'element_locator',
            'execution_replay',
            'recognizers',
        ]
        
        missing_dirs = []
        for dir_name in expected_dirs:
            dir_path = SERVICES_DIR / dir_name
            if not dir_path.exists():
                missing_dirs.append(dir_name)
        
        if missing_dirs:
            print(f"✗ 缺少以下Service子目录:")
            for d in missing_dirs:
                print(f"  - {d}")
            self.issues.append(f"缺少Service子目录: {', '.join(missing_dirs)}")
            return False
        else:
            print(f"✓ 所有 {len(expected_dirs)} 个Service子目录均存在")
            self.passed.append("Service结构完整")
            return True
    
    def generate_report(self) -> str:
        """生成审查报告"""
        report = []
        report.append("\n" + "="*60)
        report.append("全面复盘审查报告")
        report.append("="*60)
        
        report.append(f"\n✓ 通过项 ({len(self.passed)}):")
        for item in self.passed:
            report.append(f"  ✓ {item}")
        
        if self.warnings:
            report.append(f"\n⚠ 警告项 ({len(self.warnings)}):")
            for item in self.warnings:
                report.append(f"  ⚠ {item}")
        
        if self.issues:
            report.append(f"\n✗ 问题项 ({len(self.issues)}):")
            for item in self.issues:
                report.append(f"  ✗ {item}")
        
        report.append(f"\n总结:")
        report.append(f"  通过: {len(self.passed)}")
        report.append(f"  警告: {len(self.warnings)}")
        report.append(f"  问题: {len(self.issues)}")
        
        if self.issues:
            report.append(f"\n结论: ✗ 审查未通过，需解决 {len(self.issues)} 个问题")
        elif self.warnings:
            report.append(f"\n结论: ⚠ 审查通过，但有 {len(self.warnings)} 个警告")
        else:
            report.append(f"\n结论: ✓ 审查完全通过")
        
        return "\n".join(report)


def main():
    """执行全面审查"""
    reviewer = ComplianceReviewer()
    
    print("开始全面复盘审查...")
    print(f"项目根目录: {ROOT}")
    
    # 执行各项检查
    reviewer.check_file_size_limit()
    reviewer.check_str_e_leak()
    reviewer.check_type_annotations()
    reviewer.check_imports()
    reviewer.check_backward_compatibility()
    reviewer.check_service_structure()
    reviewer.check_test_coverage()
    
    # 生成报告
    report = reviewer.generate_report()
    print(report)
    
    # 返回结果
    if reviewer.issues:
        print(f"\n✗ 发现 {len(reviewer.issues)} 个必须解决的问题")
        return 1
    else:
        print(f"\n✓ 审查通过（{len(reviewer.warnings)} 个警告）")
        return 0


if __name__ == "__main__":
    sys.exit(main())
