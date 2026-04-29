
import re
import sys
from pathlib import Path

# 读取修改文件列表
modified_files = []
with open('modified_python_files.txt', 'r', encoding='utf-8') as f:
    modified_files = [line.strip() for line in f if line.strip()]

print(f"检查 {len(modified_files)} 个文件...")

# 关键文件优先检查
critical_files = [
    r'app\\services\\test_execution_engine\\__init__',
    r'app\\api\\v1\\endpoints\\test_case',
    r'app\\services\\case_',
    r'app\\services\\precondition',
]

print("\n=== 关键文件检查 ===\n")

for file_path in modified_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查基本完整性
        lines = content.split('\n')
        doc_count = content.count('"""')  # 三引号数量应该是偶数
        brackets = content.count('(') - content.count(')')
        braces = content.count('{') - content.count('}')
        
        # 检查是否是关键文件
        is_critical = any(re.search(pat, file_path.replace('/', '\\')) for pat in critical_files)
        
        if is_critical or doc_count % 2 != 0 or brackets != 0 or braces != 0 or len(lines) &lt; 10:
            print(f"⚠️  可能有问题的文件: {file_path}")
            print(f"   行数: {len(lines)}")
            print(f"   三引号对: {'✅' if doc_count%2 ==0 else '❌'}")
            print(f"   括号平衡: {'✅' if brackets ==0 else '❌'} {brackets}")
            print(f"   花括号平衡: {'✅' if braces ==0 else '❌'} {braces}")
            print()
            
    except Exception as e:
        print(f"❌ 读取失败: {file_path} - {e}")
