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
        "你是一名资深测试工程师，请根据以下项目需求内容，提取结构化的测试点。\n"
        "\n"
        "项目需求内容：\n"
        "{REQ_CONTENT_PLACEHOLDER}\n"
        "\n"
        "## 测试点提取规则\n"
        "1. 按模块分组，每个模块下的测试点要逻辑清晰、不重复\n"
        "2. 每个测试点必须包含：module（模块名称）、function（功能名称）、point（测试点描述）、priority（1高/2中/3低）\n"
        "3. **禁止重复**：同一模块下不允许出现测试价值重复的测试点（如多条「进入XX模块」），入口校验只需一条\n"
        "4. **必须有验证目标**：测试点必须说明要验证什么结果，不能只描述操作动作\n"
        "5. **覆盖异常和边界**：必须覆盖无网络、无数据、权限异常、重复提交、边界值等场景，不能只有正常流程\n"
        "6. **优先级合理**：核心流程、数据保存、关键交互设为1（高）；一般验证设为2（中）；边缘场景设为3（低）\n"
        "\n"
        "## 测试点描述规范\n"
        "- 格式：「场景/条件」+「操作」+「验证重点」，让人一看就知道要测什么、怎么判断通过\n"
        "- 必须包含可观察的预期结果，如「页面应展示XX」「系统应提示XX」「数据应保存为XX」\n"
        "- 禁止写纯操作步骤（如「进入模块」「点击按钮」），必须附带验证目标\n"
        "- 禁止模糊描述（如「测试XX功能」「验证是否正常」），「正常」不可衡量\n"
        "- 粒度适中：一个测试点对应一个可独立执行的验证场景，不要把整个功能塞进一条\n"
        "\n"
        "## 正反示例\n"
        "❌差劲测试点：\n"
        "1. 进入字词听写模块 — 太泛，只描述操作没有验证目标\n"
        "2. 点击按钮 — 信息缺失，未说明点击哪个按钮、预期什么结果\n"
        "3. 测试字词听写是否正常 — 不可执行，「正常」没有明确定义\n"
        "4. 账号已登录，进入模块 — 不是测试点，是前置条件+操作步骤的组合\n"
        "5. 听写功能测试 — 粒度过大，包含了加载、播放、提交等多个环节\n"
        "\n"
        "✅优秀测试点：\n"
        "1. 已登录用户进入字词听写模块后，页面应正确展示当前教材、单元列表和可听写字词数量 | 优先级：高\n"
        "   优点：明确验证入口加载结果，不只是「进入模块」，覆盖UI与数据渲染校验\n"
        "2. 用户选择一个有字词数据的单元后，系统应展示该单元下的字词列表，并支持开始听写 | 优先级：高\n"
        "   优点：覆盖核心路径：选单元→展示字词→开始听写，流程完整且目标明确\n"
        "3. 用户开始听写后，系统应按顺序播放字词音频，并在播放失败时给出重试提示 | 优先级：高\n"
        "   优点：同时覆盖核心功能和异常处理，能有效发现音频播放、容错逻辑缺陷\n"
        "4. 用户完成听写并提交后，系统应正确展示正确数、错误数、得分，并保存听写记录 | 优先级：高\n"
        "   优点：有明确结果校验，覆盖业务闭环，验证了数据落库与前端展示一致性\n"
        "5. 用户听写错误的字词应自动进入错词记录，并可在错词本中查看 | 优先级：中\n"
        "   优点：覆盖数据流转，验证模块间关联逻辑\n"
        "\n"
        "输出格式必须为JSON，结构如下：\n"
        "[\n"
        "  {\n"
        '    "module": "模块名称",\n'
        '    "function": "功能名称",\n'
        '    "point": "测试点描述（场景/条件+操作+验证重点）",\n'
        '    "priority": 1\n'
        "  }\n"
        "]\n"
        "\n"
        "重要要求：只输出JSON，确保格式正确，测试点必须具体明确有验证目标，禁止重复，优先级合理，必须覆盖异常和边界场景，至少输出5个测试点"
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
                'priority': max(1, min(3, point_data.get('priority', 2))),
                'ai_prompt': json.dumps(point_data)
            }
            if test_point['point']:
                test_points.append(test_point)
    except Exception as e:
        logger.error(f"解析AI响应失败: {e}")
    return test_points
