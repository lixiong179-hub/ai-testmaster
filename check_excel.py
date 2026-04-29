import pandas as pd

df = pd.read_excel("测试用例示例_第三方公司格式.xlsx", sheet_name=0)
print("列名:", df.columns.tolist())
print()

# 查看第4行（可正常绑定设备流程）
row = df.iloc[3]
print("标题:", row['标题'])
print("步骤描述:", repr(row['步骤描述']))
print()

# 测试正则
import re
step_desc = row['步骤描述']
pattern = r'【(\d+)】([^【]*?)(?=【\d+】|$)'
matches = re.findall(pattern, str(step_desc), re.DOTALL)
print("匹配结果:", matches)
