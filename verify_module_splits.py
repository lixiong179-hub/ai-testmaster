"""模块拆分验证测试脚本"""
import sys

print("=" * 60)
print("模块拆分验证测试")
print("=" * 60)

errors = []

# 1. 验证 link_fetcher
print("\n[1] link_fetcher 模块...")
try:
    from app.services.link_fetcher import LinkFetcherService, link_fetcher_service
    service = LinkFetcherService(timeout=10)
    assert service.timeout == 10
    assert link_fetcher_service is not None
    print("  ✅ LinkFetcherService 类和全局实例正常")
except Exception as e:
    errors.append(f"link_fetcher: {e}")
    print(f"  ❌ {e}")

# 2. 验证 test_data
print("\n[2] test_data 模块...")
try:
    from app.services.test_data import TestDataGenerator, create_test_data_generator
    from app.services.test_data.generator_mixin import GeneratorMixin
    from app.services.test_data.constants import DATA_TYPE_STRING, DATA_TYPE_NUMBER
    from app.services.prompt_builder import PromptBuilder
    from app.services.test_data.response_handler import parse_ai_response, validate_generated_data
    
    # 验证常量
    assert DATA_TYPE_STRING == "string"
    assert DATA_TYPE_NUMBER == "number"
    
    # 验证 prompt builder
    prompt = PromptBuilder().for_test_data([{"name": "test", "type": "string", "required": True}], 1, None, "normal")
    assert "test" in prompt
    assert "1条" in prompt
    
    # 验证 response handler
    data = parse_ai_response('{"key": "value"}')
    assert data == {"key": "value"}
    
    validated = validate_generated_data([{"test": "value"}], [{"name": "test", "required": True}])
    assert len(validated) == 1
    
    print("  ✅ TestDataGenerator 和拆分模块正常")
except Exception as e:
    errors.append(f"test_data: {e}")
    print(f"  ❌ {e}")

# 3. 验证 test_data_service
print("\n[3] test_data_service 模块...")
try:
    from app.services.test_data_service import TestDataService, TestDataServiceMixin
    # 验证类存在
    assert TestDataService is not None
    assert TestDataServiceMixin is not None
    print("  ✅ TestDataService 类正常")
except Exception as e:
    errors.append(f"test_data_service: {e}")
    print(f"  ❌ {e}")

# 4. 验证 case_generation
print("\n[4] case_generation 模块...")
try:
    from app.services.case_generation.context_mixin import ContextMixin, MAX_TEST_POINT_PAGE_SIZE, DEFAULT_TEST_POINT_PAGE_SIZE
    from app.services.case_generation.context_loader import load_requirement_content, load_ui_data
    from app.services.case_generation.test_point_loader import load_test_points, get_file_content_helper
    
    assert MAX_TEST_POINT_PAGE_SIZE == 500
    assert DEFAULT_TEST_POINT_PAGE_SIZE == 100
    
    print("  ✅ case_generation 模块和拆分文件正常")
except Exception as e:
    errors.append(f"case_generation: {e}")
    print(f"  ❌ {e}")

# 5. 验证 file_content_extractor
print("\n[5] file_content_extractor 模块...")
try:
    from app.services.file_content_extractor import FileContentExtractor, batch_extract_files, get_file_content
    from app.services.file_extractor.extractors import extract_text_file, extract_docx, extract_pdf, extract_excel, clean_text
    
    # 验证 clean_text
    assert clean_text("  test  ") == "test"
    assert clean_text("") == ""
    
    print("  ✅ file_content_extractor 模块正常")
except Exception as e:
    errors.append(f"file_content_extractor: {e}")
    print(f"  ❌ {e}")

# 6. 验证 test_case_generation
print("\n[6] test_case_generation 模块...")
try:
    from app.services.test_case_generation import TestCaseGenerationService
    from app.services.test_case_generation.ai_mixin import TestCaseGenerationAiMixin
    from app.services.prompt_builder import PromptBuilder, format_ui_spec_for_prompt
    from app.services.test_case_generation.ai_response_parser import parse_ai_response
    
    # 验证 prompt builder
    prompt = PromptBuilder.build_linear_prompt("req", "ui", "mod", "func", "point", 1)
    assert "测试点信息" in prompt
    
    # 验证 response parser
    data = parse_ai_response('{"title": "test"}')
    assert data["title"] == "test"
    
    print("  ✅ test_case_generation 模块正常")
except Exception as e:
    errors.append(f"test_case_generation: {e}")
    print(f"  ❌ {e}")

# 7. 验证 visibility_config
print("\n[7] visibility_config 模块...")
try:
    from app.services.visibility_config import VisibilityConfigService
    from app.services.visibility_config.core_mixin import VisibilityConfigCoreMixin
    from app.services.visibility_config.env_loader import VisibilityEnvLoader
    from app.services.visibility_config.validator import VisibilityConfigValidator
    from app.services.visibility_config.merger import VisibilityConfigMerger
    from app.services.visibility_config.models import VisibilityConfig
    
    # 验证 env loader
    config = VisibilityEnvLoader.load_from_env()
    assert isinstance(config, VisibilityConfig)
    
    # 验证 validator
    valid, msg = VisibilityConfigValidator.validate(config)
    assert valid is True
    
    # 验证 merger
    base = VisibilityConfig()
    override = VisibilityConfig()
    override.headless = False
    merged = VisibilityConfigMerger.merge(base, override)
    assert merged.headless is False
    
    print("  ✅ visibility_config 模块正常")
except Exception as e:
    errors.append(f"visibility_config: {e}")
    print(f"  ❌ {e}")

# 8. 验证 precondition
print("\n[8] precondition 模块...")
try:
    from app.services.precondition import ExecutorMixin, LoginMixin, PreconditionService, create_precondition_service
    from app.services.precondition.models import PreconditionError, PreconditionConfigError, LoginError
    from app.services.precondition.decorator import handle_precondition_errors
    from app.services.precondition.utils import solve_captcha_math, recognize_login_form
    from app.services.precondition.init_mixin import InitMixin
    from app.services.precondition.login_strategy_mixin import LoginStrategyMixin
    
    print("  ✅ precondition 模块正常")
except Exception as e:
    errors.append(f"precondition: {e}")
    print(f"  ❌ {e}")

# 9. 验证 ai_analysis_service
print("\n[9] ai_analysis_service 模块...")
try:
    from app.services.ai_analysis_service import AIAnalysisService, extract_test_points_from_content
    from app.services.ai_analysis_utils import read_file_content, generate_analysis_prompt, parse_ai_response
    
    # 验证 prompt 生成
    prompt = generate_analysis_prompt("test content")
    assert "test content" in prompt
    
    # 验证 response 解析
    result = parse_ai_response([{"module": "test", "function": "func", "point": "point", "priority": 1}])
    assert len(result) == 1
    
    print("  ✅ ai_analysis_service 模块正常")
except Exception as e:
    errors.append(f"ai_analysis_service: {e}")
    print(f"  ❌ {e}")

# 总结
print("\n" + "=" * 60)
if errors:
    print(f"❌ 发现 {len(errors)} 个问题:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
else:
    print("✅ 所有模块拆分验证通过！功能完整保留！")
    sys.exit(0)
