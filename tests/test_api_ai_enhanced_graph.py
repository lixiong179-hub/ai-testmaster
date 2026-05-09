"""
AI增强端点集成测试 - 流程图模�?

覆盖范围�?
- AIGenerateEnhancedRequest Schema校验（mode/flow_sort_data�?
- 请求体大小限制（nodes�?00, edges�?00�?
- _build_graph_prompt_data 共享函数
- _build_linear_prompt_data 共享函数
- _format_case_response 共享函数
"""
import pytest
from pydantic import ValidationError
from app.api.v1.endpoints.test_case_ai import (
    AIGenerateEnhancedRequest,
    _build_graph_prompt_data,
    _build_linear_prompt_data,
    _format_case_response,
    MAX_FLOW_NODES,
    MAX_FLOW_EDGES,
)
from app.schemas.test_case import FlowSortDataSchema, FlowNodeSchema, FlowEdgeSchema


class TestAIGenerateEnhancedRequest:
    """测试AIGenerateEnhancedRequest请求模型"""

    def test_valid_linear_request(self):
        """测试正常线性模式请�?""
        req = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试登录功能，需要验证用户名和密�?
        )
        assert req.mode == 'linear'
        assert req.flow_sort_data is None

    def test_valid_graph_request(self):
        """测试正常流程图模式请�?""
        flow_data = FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='登录�?)
            ],
            edges=[]
        )
        req = AIGenerateEnhancedRequest(
            project_id=1,
            description="测试登录功能",
            mode='graph',
            flow_sort_data=flow_data
        )
        assert req.mode == 'graph'
        assert req.flow_sort_data is not None

    def test_invalid_mode(self):
        """测试无效mode�?""
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试描述",
                mode='invalid'
            )
        assert 'mode' in str(exc_info.value)

    def test_nodes_exceed_limit(self):
        """测试nodes数量超过限制"""
        nodes = [
            FlowNodeSchema(screen_id=i, screen_order=i, flow_type='main', screen_name=f'页面{i}')
            for i in range(1, MAX_FLOW_NODES + 2)
        ]
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试描述",
                mode='graph',
                flow_sort_data=FlowSortDataSchema(nodes=nodes)
            )
        assert 'nodes' in str(exc_info.value)

    def test_edges_exceed_limit(self):
        """测试edges数量超过限制"""
        nodes = [
            FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='页面1')
        ]
        edges = [
            FlowEdgeSchema(source='1', target='1', edge_type='normal', label=f'连线{i}')
            for i in range(MAX_FLOW_EDGES + 1)
        ]
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试描述",
                mode='graph',
                flow_sort_data=FlowSortDataSchema(nodes=nodes, edges=edges)
            )
        assert 'edges' in str(exc_info.value)

    def test_description_too_short(self):
        """测试描述过短"""
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试"
            )
        assert 'description' in str(exc_info.value)

    def test_invalid_case_type(self):
        """测试无效case_type"""
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试描述",
                case_type='invalid_type'
            )
        assert 'case_type' in str(exc_info.value)

    def test_invalid_exec_mode(self):
        """测试无效exec_mode"""
        with pytest.raises(ValidationError) as exc_info:
            AIGenerateEnhancedRequest(
                project_id=1,
                description="测试描述",
                exec_mode='invalid'
            )
        assert 'exec_mode' in str(exc_info.value)


class TestBuildGraphPromptData:
    """测试_build_graph_prompt_data共享函数"""

    @pytest.fixture
    def flow_sort_data(self):
        return FlowSortDataSchema(
            nodes=[
                FlowNodeSchema(screen_id=1, screen_order=1, flow_type='main', screen_name='登录�?, ocr_text='请输入账�?),
                FlowNodeSchema(screen_id=2, screen_order=2, flow_type='main', screen_name='首页', ocr_text='欢迎回来')
            ],
            edges=[
                FlowEdgeSchema(source='1', target='2', edge_type='normal', label='登录成功')
            ],
            module_info={"name": "用户系统", "description": "用户管理"}
        )

    def test_returns_prompt_data(self, flow_sort_data):
        result = _build_graph_prompt_data(
            flow_sort_data=flow_sort_data,
            context={},
            description="测试登录",
            priority=2
        )
        assert 'graph_prompt' in result
        assert isinstance(result['graph_prompt'], str)
        assert len(result['graph_prompt']) > 0

    def test_includes_requirement_content(self, flow_sort_data):
        result = _build_graph_prompt_data(
            flow_sort_data=flow_sort_data,
            context={"requirement_content": "用户需要登录系�?},
            description="测试登录",
            priority=2
        )
        assert "用户需要登录系�? in result['graph_prompt']

    def test_includes_module_info(self, flow_sort_data):
        result = _build_graph_prompt_data(
            flow_sort_data=flow_sort_data,
            context={},
            description="测试登录",
            priority=2
        )
        assert "用户系统" in result['graph_prompt']


class TestBuildLinearPromptData:
    """测试_build_linear_prompt_data共享函数"""

    def test_returns_prompt_data(self):
        result = _build_linear_prompt_data(
            context={"requirement_content": "测试需�?},
            description="测试描述",
            priority=2,
            case_type='ui_automation',
            exec_mode='all'
        )
        assert 'requirement_content' in result
        assert result['requirement_content'] == "测试需�?

    def test_includes_ui_specs(self):
        ui_specs = [{"screen_name": "测试�?, "ui_spec": {"elements": []}}]
        result = _build_linear_prompt_data(
            context={"ui_specs": ui_specs},
            description="测试",
            priority=2,
            case_type=None,
            exec_mode='all'
        )
        assert 'ui_specs' in result
        assert result['ui_specs'] == ui_specs


class TestFormatCaseResponse:
    """测试_format_case_response共享函数"""

    def test_formats_basic_case(self):
        generated_case = {
            "title": "测试用例",
            "module": "测试模块",
            "precondition": "已登�?,
            "steps": [],
            "expected_result": "成功"
        }
        result = _format_case_response(
            generated_case=generated_case,
            project_id=1,
            description="测试描述",
            priority=2,
            case_type='ui_automation'
        )
        assert result['project_id'] == 1
        assert result['title'] == "测试用例"
        assert result['module'] == "测试模块"
        assert result['priority'] == 2
        assert result['case_type'] == 'ui_automation'
        assert result['generate_status'] == 1

    def test_generates_case_no(self):
        result = _format_case_response(
            generated_case={"title": "测试", "steps": []},
            project_id=1,
            description="测试",
            priority=2,
            case_type=None
        )
        assert result['case_no'].startswith('CASE1-')

    def test_defaults_for_missing_fields(self):
        result = _format_case_response(
            generated_case={"steps": []},
            project_id=1,
            description="测试描述",
            priority=2,
            case_type=None
        )
        assert result['title'] == "测试描述"[:50]
        assert result['module'] == "AI生成"
        assert result['precondition'] == ""
