from typing import List, Optional

from app.services.prompt_builder.comparison_examples import (
    get_comparison_examples,
    get_title_spec_rules,
    get_precondition_spec_rules,
    get_automation_friendly_rules,
)


def _append_generation_rules(
    parts: List[str],
    case_type: Optional[str] = None,
    has_history: bool = False,
) -> None:
    parts.append("## 生成要求")
    parts.append("")
    parts.append("### 一、用例结构规范")
    parts.append("1. 每个场景必须生成独立的测试用例，禁止将不同场景的步骤混合在同一条用例中")
    parts.append("2. 主干正向用例只覆盖主干流程步骤，旁路弹窗在对应步骤中增加\"关闭弹窗\"操作即可，不单独生成旁路用例")
    parts.append("3. 分支流程用例：depends_on 必须填写场景1（主干正向用例）的标题，anchor_step 必须填写分支触发点的主干步骤号；前置条件只需写数据准备（如Mock接口返回值）和页面状态（如\"已处于确认订单页\"），执行引擎会自动执行主干用例到 anchor_step 后继续；步骤从触发分支开始，预期结果聚焦分支本身的表现")
    parts.append("4. 异常流程用例：depends_on 必须填写场景1（主干正向用例）的标题，anchor_step 必须填写异常触发点的主干步骤号；前置条件只需写数据准备（如Mock支付接口返回失败）和页面状态（如\"已处于支付页面\"），执行引擎会自动执行主干用例到 anchor_step 后继续；步骤从触发异常开始，预期结果聚焦异常提示和系统容错表现")
    parts.append(
        "5. 若提供了需求文档，结合业务规则验证每个步骤的验收标准；"
        "若未提供，根据UI原型图推断业务逻辑，"
        "但前置条件中必须标注[推断]，预期结果中禁止使用推断性措辞"
    )
    parts.append(
        "6. 若提供了测试点，优先覆盖测试点中的测试维度；"
        "若未提供，根据UI元素生成测试点，"
        "但用例标题中必须标注[推断测试点]"
    )
    parts.append("7. 只输出JSON格式内容，不要添加任何其他文字")
    parts.append(f"8. {get_title_spec_rules(compact=True)}")
    parts.append(f"9. {get_precondition_spec_rules(compact=True)}")
    parts.append("")
    parts.append("### 二、步骤与预期结果规范（核心质量要求）")
    parts.append(
        "10. 操作步骤必须严谨可复现，禁止口语化如\"连续拍摄多张照片\""
    )
    parts.append(
        "11. 预期结果必须按三段式格式书写："
        "\"【元素状态】+【具体文案/数值】+【交互结果】\"；"
        "此规则同时适用于步骤级expected_result和用例级expected_result字段；"
        "三段中至少包含以下一类可客观判定的校验点："
        "元素可见性（如\"弹窗可见\"）、文案内容（如\"提示文案为'网络连接失败'\"）、"
        "状态变化（如\"按钮由置灰变为可点击\"）、数值（如\"正确率显示66.7%\"）、"
        "跳转路径（如\"页面跳转至错词学习页\"）；"
        "禁止\"正常显示\"\"功能正常\"\"交互跳转正确\"\"无崩溃白屏\"\"UI元素完整\"等无法断言的描述"
    )
    parts.append("12. 未区分场景变体时需拆分，如\"无相机权限\"应区分临时拒绝/永久拒绝")
    parts.append(f"13. {get_automation_friendly_rules(compact=True)}")
    parts.append("")
    parts.append("### 三、原子性与确定性规范")
    parts.append(
        "14. 原子性原则：一条用例只验证一个测试场景，"
        "分支/异常用例的步骤从触发点开始，不需要重复主流程到达触发点之前的步骤"
        "（通过前置条件声明如何到达触发点即可）；"
        "如需验证\"正确率100%触发话术旁路\"，必须单独生成一条boundary用例，"
        "不得与主流程正向用例合并"
    )
    parts.append(
        "15. 步骤确定性原则：每个步骤的操作必须唯一确定，"
        "禁止使用\"或\"\"或者\"等不确定措辞（如\"点击关闭按钮或弹窗外区域\""
        "\"导航到X页面的URL（或通过接口模拟）\"）；"
        "如存在多种操作路径，应拆分为多条用例分别覆盖"
    )
    parts.append(
        "16. 自动化可执行原则：case_type为ui_automation时，"
        "禁止步骤中出现\"手动判断\"\"人工确认\"\"目测\"等需要人工介入的描述；"
        "所有验证点必须可通过UI元素状态、文案、属性等客观标准判定"
    )
    if has_history:
        parts.append(
            "17. 评审历史用例时，必须对照流程场景逐一检查："
            "旧用例是否将不同场景混合在同一条用例中（应拆分）、"
            "步骤顺序是否与当前流程一致、"
            "是否遗漏新增的分支/异常场景、预期结果是否与UI原型匹配"
        )
    parts.append("")
    parts.append("### 四、分类与覆盖规范")
    parts.append(
        "18. 变更类用例必须设置 parent_case_id 为原用例ID、"
        "change_type 为 modified；新增用例 change_type 为 added；"
        "建议废弃的原用例 change_type 为 deprecated"
    )
    parts.append(
        "19. 每条用例必须标注 case_category 字段，"
        "取值范围：positive（正向/主流程）、boundary（边界值）、exception（异常场景），"
        "根据用例的实际测试类型选择对应分类"
    )
    parts.append(
        "20. 用例数量 = 1条主干正向(case_category=positive) + "
        "每个分支场景至少1条(case_category=boundary) + "
        "每个异常场景至少1条(case_category=exception)。禁止只生成1条"
    )
    if case_type:
        parts.append(
            f"20. 所有用例的 case_type 字段必须统一为 \"{case_type}\"，"
            "不允许生成其他类型的用例"
        )
        type_guidance = {
            "ui_automation": (
                "步骤必须包含UI元素交互，action_type使用click/input/scroll等UI操作，"
                "预期结果可自动化验证；"
                "前置条件须声明Mock/桩数据准备方式（如\"通过cy.intercept拦截接口返回指定结果\"），"
                "确保自动化脚本可稳定复现预期行为"
            ),
            "manual": (
                "允许包含需要人工判断的步骤，预期结果允许主观描述，"
                "不要求完全可自动化"
            ),
            "api_automation": (
                "用例聚焦接口层面验证，步骤以API请求/响应断言为主，"
                "无需UI元素引用"
            ),
            "performance": (
                "关注响应时间、并发数、吞吐量等性能指标，"
                "预期结果包含数值阈值"
            ),
            "security": (
                "关注XSS注入、SQL注入、权限绕过、"
                "敏感数据泄露等安全验证点"
            ),
        }
        extra = type_guidance.get(case_type, "")
        if extra:
            parts.append(f"   {extra}")
    parts.append("")
    parts.append(get_comparison_examples())

    parts.append("""
## 输出JSON格式（数组，最少3条）：
注意：steps 中 action 字段必须填写完整的业务操作描述（如"点击提交按钮""在用户名输入框中输入admin"），禁止只写操作类型关键词（如"click""input"）。action_type 字段才填写操作类型枚举值。
重要：expected_result 必须按三段式格式书写"【元素状态】+【具体文案/数值】+【交互结果】"，参考下方示例。步骤数量约束：每条用例2-8步；正向用例通常3-8步，边界和异常用例通常2-5步；超过8步说明混合了多个测试场景，必须拆分为多条独立用例。
字段说明：depends_on 为 null（主干用例）或所依赖的主干用例标题（分支/异常用例必填）；anchor_step 为 null（主干用例）或所依赖的主干用例步骤号（分支/异常用例必填，表示从此步骤后继续执行）。

[
  {
    "title": "正向-登录页输入有效账号密码后点击登录验证跳转首页",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名admin/密码Admin123）",
    "test_data": {"normal": {"用户名": "admin", "密码": "Admin123"}, "boundary": {}, "abnormal": {}},
    "steps": [
      {
        "step": "1",
        "description": "访问登录页面",
        "action": "在浏览器地址栏输入登录页URL并回车",
        "action_type": "navigate",
        "input_value": "/login",
        "target_element": "浏览器地址栏",
        "expected_result": "登录页面加载完成（URL包含/login），用户名输入框和密码输入框可见，登录按钮可见但置灰不可点击（按钮为disabled态）",
        "param": ""
      },
      {
        "step": "2",
        "description": "输入用户名和密码",
        "action": "在用户名输入框中输入admin，在密码输入框中输入Admin123",
        "action_type": "input",
        "input_value": "admin/Admin123",
        "target_element": "用户名输入框/密码输入框",
        "expected_result": "用户名输入框显示admin，密码输入框显示掩码字符，登录按钮由置灰变为可点击（按钮从disabled态变为enabled态）",
        "param": ""
      },
      {
        "step": "3",
        "description": "点击登录按钮",
        "action": "点击登录按钮",
        "action_type": "click",
        "input_value": "",
        "target_element": "登录按钮",
        "expected_result": "按钮显示loading状态（文案变为'登录中...'），请求成功后跳转至首页（URL包含/home），顶部导航栏显示用户头像和用户名admin",
        "param": ""
      }
    ],
    "expected_result": "登录成功后跳转至首页，顶部导航栏显示用户头像和用户名admin，localStorage中存储有效token",
    "case_type": "ui_automation",
    "case_category": "positive",
    "priority": 1,
    "change_type": "added",
    "parent_case_id": null,
    "depends_on": null,
    "anchor_step": null
  },
  {
    "title": "边界-密码输入错误5次后账号锁定15分钟",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名locktest/密码Test123）、账号当前未锁定、已处于登录页（可见用户名输入框、密码输入框、登录按钮）",
    "test_data": {"normal": {}, "boundary": {"错误次数": 5}, "abnormal": {}},
    "steps": [
      {
        "step": "1",
        "description": "连续5次输入错误密码点击登录",
        "action": "在用户名输入框输入locktest，在密码输入框输入WrongPwd，点击登录按钮，重复5次",
        "action_type": "input",
        "input_value": "locktest/WrongPwd",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "前4次登录失败后提示'用户名或密码错误'（红色错误文案可见），第5次登录失败后提示'账号已锁定，请15分钟后重试'",
        "param": ""
      },
      {
        "step": "2",
        "description": "锁定期间尝试登录",
        "action": "在用户名输入框输入locktest，在密码输入框输入Test123（正确密码），点击登录按钮",
        "action_type": "input",
        "input_value": "locktest/Test123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "登录失败，提示'账号已锁定，请15分钟后重试'（红色错误文案可见），不跳转首页",
        "param": ""
      },
      {
        "step": "3",
        "description": "锁定到期后用正确密码登录",
        "action": "等待15分钟后在用户名输入框输入locktest，在密码输入框输入Test123，点击登录按钮",
        "action_type": "input",
        "input_value": "locktest/Test123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "登录成功，跳转至首页（URL包含/home），顶部导航栏显示用户名locktest",
        "param": ""
      }
    ],
    "expected_result": "连续5次错误密码后账号锁定15分钟（提示文案为'账号已锁定，请15分钟后重试'），锁定期间即使正确密码也登录失败，锁定到期后用正确密码可成功登录跳转首页",
    "case_type": "ui_automation",
    "case_category": "boundary",
    "priority": 2,
    "change_type": "added",
    "parent_case_id": null,
    "depends_on": "正向-输入有效用户名密码点击登录按钮验证跳转首页成功",
    "anchor_step": 1
  },
  {
    "title": "异常-登录接口超时验证超时提示和重试功能",
    "module": "用户登录",
    "precondition": "浏览器网络正常、测试账号已注册（用户名admin/密码Admin123）、Mock登录接口延迟30秒返回超时、已处于登录页（可见用户名输入框、密码输入框、登录按钮）",
    "test_data": {"normal": {}, "boundary": {}, "abnormal": {"接口响应": "超时"}},
    "steps": [
      {
        "step": "1",
        "description": "输入有效账号密码点击登录",
        "action": "在用户名输入框输入admin，在密码输入框输入Admin123，点击登录按钮",
        "action_type": "input",
        "input_value": "admin/Admin123",
        "target_element": "用户名输入框/密码输入框/登录按钮",
        "expected_result": "按钮显示loading状态（文案变为'登录中...'），等待超时后弹出提示弹窗，弹窗文案为'请求超时，请检查网络后重试'，包含重试按钮和取消按钮",
        "param": ""
      },
      {
        "step": "2",
        "description": "点击重试按钮",
        "action": "点击弹窗中的重试按钮",
        "action_type": "click",
        "input_value": "",
        "target_element": "重试按钮",
        "expected_result": "弹窗关闭，按钮再次显示loading状态，重新发送登录请求",
        "param": ""
      }
    ],
    "expected_result": "接口超时后弹出超时提示弹窗（标题为'请求超时'，文案为'请检查网络后重试'），重试按钮可重新发起请求，取消按钮可关闭弹窗恢复登录页初始状态（输入框保留已输入内容）",
    "case_type": "ui_automation",
    "case_category": "exception",
    "priority": 1,
    "change_type": "added",
    "parent_case_id": null,
    "depends_on": "正向-输入有效用户名密码点击登录按钮验证跳转首页成功",
    "anchor_step": 1
  }
]""")
