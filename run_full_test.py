# -*- coding: utf-8 -*-
"""
AI测试平台 - 完整测试执行入口
整合API测试和UI测试
"""
import json
from datetime import datetime
from comprehensive_test import ComprehensiveTester
from ui_test import run_ui_tests
import os

def save_report(api_results, ui_results):
    """保存测试报告"""
    report = {
        "title": "AI测试平台 - 智慧园区项目测试报告",
        "generated_at": datetime.now().isoformat(),
        "api_test": {
            "total": api_results.get("total", 0),
            "passed": api_results.get("passed", 0),
            "failed": api_results.get("failed", 0),
            "warned": api_results.get("warned", 0),
            "pass_rate": f"{100*api_results.get('passed',0)/max(api_results.get('total',1),1):.1f}%"
        },
        "ui_test": {
            "total": len(ui_results),
            "passed": len([r for r in ui_results if r["status"] == "PASS"]),
            "failed": len([r for r in ui_results if r["status"] == "FAIL"])
        },
        "details": api_results.get("results", [])
    }
    
    # 添加UI测试详情
    if ui_results:
        report["ui_details"] = ui_results
    
    with open("TEST_REPORT_FULL.md", "w", encoding="utf-8") as f:
        f.write("# AI测试平台 - 智慧园区项目测试报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        
        f.write("## 测试结果汇总\n\n")
        f.write(f"| 类型 | 总数 | 通过 | 失败 | 通过率 |\n")
        f.write(f"|------|------|------|------|--------|\n")
        f.write(f"| API测试 | {report['api_test']['total']} | {report['api_test']['passed']} | {report['api_test']['failed']} | {report['api_test']['pass_rate']} |\n")
        f.write(f"| UI测试 | {report['ui_test']['total']} | {report['ui_test']['passed']} | {report['ui_test']['failed']} | {100*report['ui_test']['passed']/max(report['ui_test']['total'],1):.1f}% |\n\n")
        
        f.write("---\n\n")
        f.write("## API测试详情\n\n")
        for r in report["details"]:
            status_icon = "[PASS]" if r["status"] == "PASS" else "[FAIL]" if r["status"] == "FAIL" else "[WARN]"
            f.write(f"- {status_icon} **{r['module']}** / {r['test_name']}: {r['details']}\n")
        
        if ui_results:
            f.write("\n---\n\n")
            f.write("## UI测试详情\n\n")
            for r in ui_results:
                status_icon = "[PASS]" if r["status"] == "PASS" else "[FAIL]"
                f.write(f"- {status_icon} **{r['module']}** / {r['name']}: {r['details']}\n")
        
        f.write("\n---\n\n")
        f.write("## 发现的Bug\n\n")
        f.write("| Bug ID | 描述 | 严重程度 | 状态 |\n")
        f.write("|--------|------|----------|------|\n")
        f.write("| BUG-001 | admin用户初始密码不正确 | 高 | 已修复 |\n\n")
        
        f.write("---\n\n")
        f.write(f"*报告生成时间: {datetime.now().isoformat()}*\n")
    
    # 同时保存JSON格式
    with open("TEST_REPORT_FULL.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n报告已保存到 TEST_REPORT_FULL.md 和 TEST_REPORT_FULL.json")
    
    return report

def main():
    print("=" * 60)
    print("  AI测试平台 - 完整测试执行")
    print("  项目: 智慧园区 (ID:3)")
    print("=" * 60)
    
    # 1. 执行API测试
    print("\n>>> 步骤1: 执行API和数据库测试...")
    api_tester = ComprehensiveTester()
    api_results = api_tester.run_all()
    
    # 2. 执行UI测试（如果可用）
    print("\n>>> 步骤2: 执行UI自动化测试...")
    ui_results = run_ui_tests()
    
    # 3. 生成报告
    print("\n>>> 步骤3: 生成测试报告...")
    report = save_report(api_results, ui_results)
    
    # 4. 打印汇总
    print("\n" + "=" * 60)
    print("  测试执行完成!")
    print("=" * 60)
    print(f"\nAPI测试: {api_results.get('passed', 0)}/{api_results.get('total', 0)} 通过")
    print(f"UI测试: {len([r for r in ui_results if r['status']=='PASS'])}/{len(ui_results)} 通过")
    print(f"\n详细报告已保存!")

if __name__ == "__main__":
    main()
