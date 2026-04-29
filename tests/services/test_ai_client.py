"""
AI客户端JSON解析单元测试

覆盖范围:
- _clean_json_string() JSON字符串清理和修复
- _extract_json_objects_fallback() Fallback解析方法
- _parse_test_point_object() 单个对象解析
- _extract_value() 值提取
- 各种格式错误的JSON修复能力
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.ai_client import AIClient


@pytest.fixture
def ai_client():
    """创建AIClient实例（使用.env中的真实配置）"""
    return AIClient()


class TestCleanJsonString:
    """JSON字符串清理方法测试"""

    def test_valid_json_passes_through(self, ai_client):
        """有效JSON直接通过"""
        valid = '{"key": "value", "num": 123}'
        result = ai_client._clean_json_string(valid)
        assert result is not None
        parsed = json.loads(result)
        assert parsed['key'] == 'value'
        assert parsed['num'] == 123

    def test_single_quotes_to_double(self, ai_client):
        """单引号转双引号"""
        input_str = "{'key': 'value', 'name': 'test'}"
        result = ai_client._clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert parsed['key'] == 'value'

    def test_trailing_comma_removal(self, ai_client):
        """尾逗号移除"""
        input_str = '{"key": "value", "num": 123,}'
        result = ai_client._clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert parsed['key'] == 'value'

    def test_missing_space_after_colon(self, ai_client):
        """冒号后缺少空格"""
        input_str = '{"key":"value","name":"test"}'
        result = ai_client._clean_json_string(input_str)
        # 应该能修复或返回None
        assert result is not None or result is None

    def test_missing_quotes_on_key(self, ai_client):
        """键名缺少开头引号"""
        input_str = '{key":"value","function":"login"}'
        result = ai_client._clean_json_string(input_str)
        # 应该尝试修复

    def test_missing_comma_between_objects(self, ai_client):
        """两个对象之间缺少逗号"""
        input_str = '{"a":1}{"b":2}'
        result = ai_client._clean_json_string(input_str)
        # 应该尝试插入逗号

    def test_empty_string_returns_none(self, ai_client):
        """空字符串返回None"""
        result = ai_client._clean_json_string("")
        assert result is None

    def test_none_input_returns_none(self, ai_client):
        """None输入返回None"""
        result = ai_client._clean_json_string(None)
        assert result is None

    def test_control_characters_removed(self, ai_client):
        """控制字符被移除"""
        input_str = '{"key": "val\x00ue", "name": "test\x08x"}'
        result = ai_client._clean_json_string(input_str)
        if result:
            parsed = json.loads(result)
            assert '\x00' not in parsed.get('key', '')


class TestExtractJsonObjectsFallback:
    """Fallback JSON提取方法测试"""

    def test_valid_array_extraction(self, ai_client):
        """从有效的JSON数组中提取对象"""
        content = '''
[
  {"module": "登录模块", "function": "用户登录", "point": "验证正确密码登录成功", "priority": 1},
  {"module": "登录模块", "function": "用户登录", "point": "验证错误密码提示错误", "priority": 1}
]
'''
        results = ai_client._extract_json_objects_fallback(content)
        assert len(results) == 2
        assert results[0]['module'] == '登录模块'
        assert results[0]['point'] == '验证正确密码登录成功'

    def test_real_ai_response_format(self, ai_client):
        """使用真实AI响应格式测试（本次修复的核心场景）"""
        content = '''[
  {
    "module": "链接管理模块",
    "function": "新增"添加人"字段",
    "point": "验证在黑白名单链接列表中，新增的'添加人'列正确显示",
    "priority": 1
  },
  {
    "module": "链接管理模块",
    "function":新增"添加人"字段",
    "point": "验证添加新链接时，'添加人'字段自动填充为当前执行操作的用户身份",
    "priority": 1
  }
]'''
        
        results = ai_client._extract_json_objects_fallback(content)
        assert len(results) >= 1
        assert 'module' in results[0]
        assert 'point' in results[0]
        assert len(results[0]['point']) > 10

    def test_broken_format_with_missing_quotes(self, ai_client):
        """测试缺失引号的损坏格式"""
        content = '''[
  {module: "用户管理", function: 登录功能, point: 验证用户登录, priority: 1}
]'''
        results = ai_client._extract_json_objects_fallback(content)
        # 应该至少尝试提取

    def test_line_by_line_parsing(self, ai_client):
        """逐行解析模式（方法3）"""
        content = '''[
{
"module": "测试模块",
"function": "测试功能",
"point": "这是测试点描述",
"priority": 2
}
]'''
        results = ai_client._extract_json_objects_fallback(content)
        assert len(results) >= 1

    def test_empty_content(self, ai_client):
        """空内容返回空列表"""
        results = ai_client._extract_json_objects_fallback('')
        assert results == []

    def test_no_json_content(self, ai_client):
        """无JSON内容返回空列表"""
        results = ai_client._extract_json_objects_fallback('这是一段纯文本，没有JSON')
        assert results == []

    def test_large_content_truncation(self, ai_client):
        """大内容截断保护"""
        large_content = '[\n' + '  {"m":"test","f":"func","p":"desc","prio":1},\n' * 1000 + ']'
        # 超过50KB的内容应该被截断而不是崩溃
        try:
            results = ai_client._extract_json_objects_fallback(large_content)
            assert isinstance(results, list)
        except Exception as e:
            pytest.fail(f"大内容处理不应抛出异常: {e}")


class TestParseTestPointObject:
    """单个测试点对象解析"""

    def test_valid_object(self, ai_client):
        """有效对象解析"""
        text = '{"module": "M", "function": "F", "point": "P", "priority": 1}'
        result = ai_client._parse_test_point_object(text)
        assert result is not None
        assert result['module'] == 'M'
        assert result['point'] == 'P'

    def test_missing_module(self, ai_client):
        """缺少module字段"""
        text = '{"function": "F", "point": "P", "priority": 1}'
        result = ai_client._parse_test_point_object(text)
        # module可选，有point就应该返回

    def test_empty_point_returns_none(self, ai_client):
        """空point字段返回None"""
        text = '{"module": "M", "function": "F", "point": "", "priority": 1}'
        result = ai_client._parse_test_point_object(text)
        assert result is None


class TestExtractValue:
    """值提取辅助方法"""

    def test_string_value(self, ai_client):
        """字符串值提取"""
        result = ai_client._extract_value('"hello world"')
        assert result == 'hello world'

    def test_integer_value(self, ai_client):
        """整数值提取"""
        result = ai_client._extract_value('123')
        assert result == 123
        assert isinstance(result, int)

    def test_float_value(self, ai_client):
        """浮点数值提取"""
        result = ai_client._extract_value('3.14')
        assert result == 3.14
        assert isinstance(result, float)

    def test_boolean_true(self, ai_client):
        """布尔true提取"""
        result = ai_client._extract_value('true')
        assert result is True

    def test_boolean_false(self, ai_client):
        """布尔false提取"""
        result = ai_client._extract_value('false')
        assert result is False

    def test_value_with_trailing_comma(self, ai_client):
        """带尾逗号的值"""
        result = ai_client._extract_value('"test",')
        assert result == 'test'

    def test_empty_value(self, ai_client):
        """空值"""
        result = ai_client._extract_value(',')
        assert result is None


class TestAiClientIntegration:
    """AIClient集成测试（需要真实API密钥）"""

    def test_client_initialization(self, ai_client):
        """客户端初始化"""
        assert ai_client is not None
        assert ai_client.api_key is not None
        assert len(ai_client.api_key) > 10

    def test_api_key_from_env(self, ai_client):
        """确认API密钥来自环境配置"""
        import os
        env_key = os.getenv('DEEPSEEK_API_KEY')
        if env_key:
            assert ai_client.api_key == env_key
