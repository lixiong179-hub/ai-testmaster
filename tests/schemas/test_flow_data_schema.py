"""
FlowDataSaveRequest / FlowDataResponse Schema 校验测试

覆盖范围:
    - FlowDataSaveRequest: 正常 flow_data、空 nodes+edges 拒绝、仅有 nodes/仅有 edges 通过
    - FlowDataResponse: from_attributes 配置校验
"""
import pytest
from pydantic import ValidationError

from app.schemas.ui_prototype import FlowDataSaveRequest, FlowDataResponse


class TestFlowDataSaveRequest:
    """FlowDataSaveRequest 请求体校验"""

    def test_valid_with_nodes_and_edges(self):
        request = FlowDataSaveRequest(
            flow_data={
                "nodes": [{"id": "1", "name": "登录"}],
                "edges": [{"from": "1", "to": "2"}],
            }
        )
        assert request.flow_data["nodes"] == [{"id": "1", "name": "登录"}]
        assert request.flow_data["edges"] == [{"from": "1", "to": "2"}]

    def test_empty_nodes_and_empty_edges_raises_validation_error(self):
        with pytest.raises(ValidationError) as exc_info:
            FlowDataSaveRequest(
                flow_data={"nodes": [], "edges": []}
            )
        assert "不能同时为空" in str(exc_info.value)

    def test_only_nodes_passes(self):
        request = FlowDataSaveRequest(
            flow_data={
                "nodes": [{"id": "1"}],
                "edges": [],
            }
        )
        assert request.flow_data["nodes"] == [{"id": "1"}]

    def test_only_edges_passes(self):
        request = FlowDataSaveRequest(
            flow_data={
                "nodes": [],
                "edges": [{"from": "1", "to": "2"}],
            }
        )
        assert request.flow_data["edges"] == [{"from": "1", "to": "2"}]

    def test_flow_data_missing_raises_validation_error(self):
        with pytest.raises(ValidationError):
            FlowDataSaveRequest()


class TestFlowDataResponse:
    """FlowDataResponse 响应体配置校验"""

    def test_from_attributes_config(self):
        assert FlowDataResponse.model_config.get("from_attributes") is True
