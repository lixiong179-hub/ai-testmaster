"""AI分析服务 - 工具函数模块
包含文件读取、Prompt生成、响应解析等工具函数
"""
import json
from typing import List, Dict, Any
from loguru import logger


def read_file_content(file_path: str) -> str:
    """读取本地文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"读取文件失败: {file_path}, 错误: {e}")
        return "文件读取失败"


def generate_analysis_prompt(content: str) -> str:
    """生成AI需求分析的Prompt"""
    prompt = (
        "你是一名专业的测试工程师，请根据以下项目需求内容，提取结构化的测试点。\n"
        "\n"
        "项目需求内容：\n"
        "{REQ_CONTENT_PLACEHOLDER}\n"
        "\n"
        "请按照以下格式提取测试点：\n"
        "1. 按模块分组\n"
        "2. 每个测试点包含：模块名称、功能名称、测试点描述、优先级（1高/2中/3低）\n"
        "3. 测试点必须具体、可执行\n"
        "4. 覆盖正常场景和异常场景\n"
        "\n"
        "输出格式必须为JSON，结构如下：\n"
        "[\n"
        "  {\n"
        '    "module": "模块名称",\n'
        '    "function": "功能名称",\n'
        '    "point": "测试点描述",\n'
        '    "priority": 1\n'
        "  }\n"
        "]\n"
        "\n"
        "请确保输出的JSON格式正确，并且测试点描述清晰、具体、可执行。"
    ).replace("{REQ_CONTENT_PLACEHOLDER}", content)
    return prompt


def parse_ai_response(test_points_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """解析AI响应，提取并标准化测试点数据"""
    test_points = []
    try:
        for point_data in test_points_data:
            test_point = {
                'module': point_data.get('module', '未命名模块'),
                'function': point_data.get('function', '未命名功能'),
                'point': point_data.get('point', ''),
                'priority': point_data.get('priority', 2),
                'ai_prompt': json.dumps(point_data)
            }
            if test_point['point']:
                test_points.append(test_point)
    except Exception as e:
        logger.error(f"解析AI响应失败: {e}")
    return test_points
