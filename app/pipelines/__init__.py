"""
Pipeline 框架模块

本模块提供迭代用例生成与维护流水线的框架层，包括：
    - PipelineStep Protocol : Step 接口定义
    - StepResult : Step 执行结果
    - PipelineContext : 运行时上下文
    - PipelineRunner : 流水线执行引擎
"""
from app.pipelines.base import PipelineStep, StepResult
from app.pipelines.context import PipelineContext
from app.pipelines.runner import PipelineRunner

__all__ = ["PipelineStep", "StepResult", "PipelineContext", "PipelineRunner"]
