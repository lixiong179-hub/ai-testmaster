import sys
sys.path.insert(0, r'c:\Users\19476\Desktop\ai-testmaster(2)\ai-testmaster')

# 先导入所有模型
from app.models.element_locator import ElementLocator
from app.models.test_case import TestCase, TestStep
from app.db.database import PrimarySessionLocal

db = PrimarySessionLocal()

# 查询最近导入的用例
test_cases = db.query(TestCase).filter(TestCase.title.like('%绑定设备%')).order_by(TestCase.id.desc()).limit(5).all()

for tc in test_cases:
    print(f"用例ID: {tc.id}, 标题: {tc.title}")
    steps = db.query(TestStep).filter(TestStep.test_case_id == tc.id).all()
    print(f"  步骤数: {len(steps)}")
    for step in steps:
        print(f"    步骤{step.step_number}: {step.action[:30]}...")
    print()

db.close()
