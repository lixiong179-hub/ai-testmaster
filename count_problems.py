#!/usr/bin/env python3
"""精确统计有问题的文件"""
import os

problems = []
oks = []

with open('modified_python_files.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        # 转换路径格式
        line = line.replace('\\', '/')

        try:
            with open(line, 'r', encoding='utf-8', errors='ignore') as f2:
                content = f2.read()

            issues = []
            lines = content.split('\n')
            doc_count = content.count('"""')
            brackets = content.count('(') - content.count(')')

            if doc_count % 2 != 0:
                issues.append(f"三引号不成对:{doc_count}")
            if brackets != 0:
                issues.append(f"括号不平衡:{brackets}")
            if len(lines) < 10:
                issues.append(f"文件太短:{len(lines)}行")

            if issues:
                problems.append((line, issues))
            else:
                oks.append(line)
        except Exception as e:
            problems.append((line, [f"读取失败:{str(e)}"]))

print(f"=== 统计结果 ===")
print(f"正常文件: {len(oks)}")
print(f"有问题文件: {len(problems)}")
print()

if problems:
    print("=== 有问题文件清单 ===")
    for i, (path, issues) in enumerate(problems, 1):
        print(f"{i}. {path}")
        for issue in issues:
            print(f"   - {issue}")
        print()
