"""初始化默认 Prompt 模板到数据库。

将 6 种硬编码 Prompt 常量注册到 prompt_templates 表，
仅在表为空时执行，避免重复插入。

Prompt 键列表:
    - FULL_CONTEXT_GENERATION
    - REQUIREMENT_TESTPOINT_STANDARD
    - EXCEL_CASE_INCREMENTAL_UPDATE
    - XMIND_TESTPOINT_MERGE
    - XMIND_UI_COMPLETION
    - EXCEL_UI_ADAPTATION

使用方式:
    python -m scripts.seed_prompt_templates
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from app.db.database import PrimarySessionLocal
from app.models.prompt_template import PromptTemplate
from app.services.prompt_registry import PromptRegistry, register_hardcoded_prompt


# 占位 Prompt 内容 — 后续由业务模块填充实际内容
_DEFAULT_PROMPTS: dict[str, str] = {
    "FULL_CONTEXT_GENERATION": (
        "你是AI测试用例生成专家。请根据以下完整上下文（需求+测试点+UI规格）"
        "生成高质量测试用例。输出JSON格式，包含title/module/precondition/steps/"
        "expected_result/priority等字段。"
    ),
    "REQUIREMENT_TESTPOINT_STANDARD": (
        "你是AI测试用例生成专家。请根据需求文档和测试点，按照标准模板生成"
        "测试用例。每个测试点至少生成一条用例，确保覆盖正常流程和异常场景。"
    ),
    "EXCEL_CASE_INCREMENTAL_UPDATE": (
        "你是AI测试用例更新专家。请根据需求变更和已有Excel用例，进行增量更新。"
        "保持未变更部分不变，仅更新与变更相关的字段，输出完整用例而非diff。"
    ),
    "XMIND_TESTPOINT_MERGE": (
        "你是AI测试点合并专家。请将XMind思维导图中的测试点与已有测试点进行"
        "智能合并，去重并补充新测试点，保留已有测试点的用例关联关系。"
    ),
    "XMIND_UI_COMPLETION": (
        "你是AI测试用例补全专家。请根据XMind测试点和UI规格，补全缺失的"
        "测试用例，特别关注UI适配、交互边界和异常流程。"
    ),
    "EXCEL_UI_ADAPTATION": (
        "你是AI UI适配测试专家。请根据Excel用例和目标设备UI规格，"
        "适配生成目标设备的测试用例，调整元素定位器和交互步骤。"
    ),
}


def seed_prompt_templates() -> None:
    """将默认 Prompt 模板注册到数据库，仅在表为空时执行。"""
    db = PrimarySessionLocal()
    try:
        # 检查表是否已有数据
        existing_count = db.query(PromptTemplate).count()
        if existing_count > 0:
            print(f"prompt_templates 表已有 {existing_count} 条记录，跳过 seed")
            return

        # 注册硬编码 fallback
        for key, content in _DEFAULT_PROMPTS.items():
            register_hardcoded_prompt(key, content)

        # 通过 PromptRegistry 注册到数据库
        registry = PromptRegistry(db)
        for key, content in _DEFAULT_PROMPTS.items():
            registry.register_prompt(key=key, content=content, description=f"默认{key} Prompt")

        db.commit()
        print(f"成功 seed {len(_DEFAULT_PROMPTS)} 条 Prompt 模板")
    except Exception as e:
        db.rollback()
        print(f"seed 失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_prompt_templates()
