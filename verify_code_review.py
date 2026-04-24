"""代码评审修复验证脚本"""
import sys

errors = []

# 1. 验证 link_fetcher MRO 修复
print("[1] link_fetcher MRO 修复验证...")
try:
    from app.services.link_fetcher import LinkFetcherService
    service = LinkFetcherService(timeout=10)
    mro_names = [c.__name__ for c in LinkFetcherService.__mro__]
    print(f"  MRO: {' -> '.join(mro_names[:5])}")
    assert hasattr(service, 'fetch_content'), 'fetch_content 方法缺失'
    assert hasattr(service, '_process_json'), '_process_json 方法缺失'
    assert hasattr(service, '_process_html'), '_process_html 方法缺失'
    assert hasattr(service, '_process_markdown'), '_process_markdown 方法缺失'
    assert hasattr(service, '_process_auto'), '_process_auto 方法缺失'
    assert hasattr(service, '_detect_auth_failure_in_json'), '_detect_auth_failure_in_json 方法缺失'
    assert hasattr(service, 'fetch_and_parse_ui_mockup'), 'fetch_and_parse_ui_mockup 方法缺失'
    assert hasattr(service, 'validate_link_access'), 'validate_link_access 方法缺失'
    assert hasattr(service, 'extract_auth_config_from_form'), 'extract_auth_config_from_form 方法缺失'
    assert hasattr(service, 'session'), 'session 属性缺失'
    assert hasattr(service, 'timeout'), 'timeout 属性缺失'
    assert service.timeout == 10
    print("  OK MRO 修复验证通过")
except Exception as e:
    errors.append(f"link_fetcher: {e}")
    print(f"  FAIL {e}")

# 2. 验证 file_content_extractor rarfile 修复
print("\n[2] file_content_extractor rarfile 修复验证...")
try:
    from app.services.file_content_extractor import FileContentExtractor
    import inspect
    source = inspect.getsource(FileContentExtractor._extract_archive)
    assert 'import rarfile' in source
    assert 'except ImportError' in source
    print("  OK rarfile 导入逻辑修复验证通过")
except Exception as e:
    errors.append(f"file_content_extractor: {e}")
    print(f"  FAIL {e}")

# 3. 验证所有模块导入
print("\n[3] 所有模块导入验证...")
modules = [
    'app.services.link_fetcher',
    'app.services.test_data',
    'app.services.test_data_service',
    'app.services.case_generation.context_mixin',
    'app.services.file_content_extractor',
    'app.services.test_case_generation',
    'app.services.visibility_config',
    'app.services.ai_analysis_service',
    'app.services.precondition',
    'app.services.user_service.user_service',
    'app.services.role_service.role_service',
    'app.services.test_data_parameterizer',
]
for mod in modules:
    try:
        __import__(mod)
        print(f"  OK {mod}")
    except Exception as e:
        errors.append(f"{mod}: {e}")
        print(f"  FAIL {mod}: {e}")

# 总结
print("\n" + "=" * 60)
if errors:
    print(f"FAIL 发现 {len(errors)} 个问题:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
else:
    print("OK 所有修复验证通过！")
    sys.exit(0)
