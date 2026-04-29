#!/usr/bin/env python3
"""文件完整性检查脚本 - 检查所有被修改文件的内容完整性"""
import re
import os

def check_file_integrity(file_path):
    """检查单个文件的内容完整性"""
    issues = []

    try:
        # 转换Windows路径
        file_path = file_path.replace('/', os.sep).replace('\\', os.sep)

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        lines = content.split('\n')

        # 1. 检查三引号配对
        doc_count = content.count('"""')
        if doc_count % 2 != 0:
            issues.append(f"三引号不成对: {doc_count}个")

        # 2. 检查括号平衡
        brackets = content.count('(') - content.count(')')
        if brackets != 0:
            issues.append(f"圆括号不平衡: {brackets}")

        # 3. 检查花括号平衡
        braces = content.count('{') - content.count('}')
        if braces != 0:
            issues.append(f"花括号不平衡: {braces}")

        # 4. 检查方括号平衡
        squares = content.count('[') - content.count(']')
        if squares != 0:
            issues.append(f"方括号不平衡: {squares}")

        # 5. 检查文件是否太短（可能内容被删除）
        if len(lines) < 10:
            issues.append(f"文件只有{len(lines)}行，可能内容缺失")

        # 6. 检查是否只有文档字符串没有实际代码
        non_doc_lines = [l for l in lines if l.strip() and not l.strip().startswith('#') and l.strip() != '"""']
        if len(non_doc_lines) < 3 and doc_count >= 2:
            issues.append(f"可能只有文档字符串，缺少实际代码")

        return issues, len(lines), doc_count

    except FileNotFoundError:
        return [f"文件不存在"], 0, 0
    except Exception as e:
        return [f"读取失败: {str(e)}"], 0, 0

def main():
    # 读取修改文件列表
    modified_files = []
    try:
        with open('modified_python_files.txt', 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stripped = line.strip()
                if stripped and stripped.endswith('.py'):
                    modified_files.append(stripped)
    except Exception as e:
        print(f"读取文件列表失败: {e}")
        return

    print(f"检查 {len(modified_files)} 个文件...\n")

    problematic_files = []
    ok_files = []

    for file_path in modified_files:
        issues, line_count, doc_count = check_file_integrity(file_path)

        if issues:
            print(f"\n{'='*60}")
            print(f"[PROBLEM] {file_path}")
            print(f"  行数: {line_count}, 三引号: {doc_count}个")
            for issue in issues:
                print(f"  - {issue}")
            problematic_files.append((file_path, issues))
        else:
            ok_files.append(file_path)

    print(f"\n\n{'='*60}")
    print(f"检查完成！")
    print(f"[OK] 正常文件: {len(ok_files)}个")
    print(f"[PROBLEM] 有问题文件: {len(problematic_files)}个")

    if problematic_files:
        print(f"\n有问题文件列表:")
        for i, (f, issues) in enumerate(problematic_files, 1):
            print(f"  {i}. {f}")
            for issue in issues:
                print(f"     - {issue}")

    # 保存结果到文件
    with open('integrity_check_results.txt', 'w', encoding='utf-8') as f:
        f.write("=== 有问题的文件 ===\n\n")
        for pf, issues in problematic_files:
            f.write(f"{pf}\n")
            for issue in issues:
                f.write(f"  - {issue}\n")
            f.write("\n")
        f.write(f"\n=== 正常文件 ({len(ok_files)}个) ===\n")
        for of in ok_files:
            f.write(f"{of}\n")

    print(f"\n结果已保存到 integrity_check_results.txt")

if __name__ == '__main__':
    main()
