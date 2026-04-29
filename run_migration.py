"""
数据库迁移自动化脚本 - 一键式迁移管理

功能：
1. 自动检测模型变更
2. 生成迁移脚本
3. 执行迁移
4. 回滚操作

使用方法：
    # 完整流程：检测 -> 生成 -> 执行
    python run_migration.py

    # 仅生成迁移脚本（不执行）
    python run_migration.py --generate-only

    # 仅执行已有迁移
    python run_migration.py --upgrade-only

    # 回滚到上一版本
    python run_migration.py --rollback

    # 查看当前版本状态
    python run_migration.py --status

示例输出：
    $ python run_migration.py --status
    当前版本: 004_add_view_fields (head)
    待执行迁移: 0个

    $ python run_migration.py
    [1/4] 检测模型变更...
    [2/4] 生成迁移脚本...
    [3/4] 执行迁移...
    [4/4] 验证结果...
    ✅ 迁移完成！新增 1 个字段
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime


def run_command(cmd: str, description: str = "") -> bool:
    """
    执行shell命令

    Args:
        cmd: 要执行的命令
        description: 命令描述（用于日志）

    Returns:
        是否成功
    """
    if description:
        print(f"\n{description}")

    print(f"执行: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr and "WARNING" not in result.stderr:
        print(f"错误: {result.stderr}", file=sys.stderr)

    return result.returncode == 0


def check_alembic_status():
    """检查Alembic迁移状态"""
    return run_command(
        "alembic current",
        "📊 检查当前数据库版本..."
    )


def generate_migration(message: str = None):
    """自动生成迁移脚本"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    msg = message or f"auto_migration_{timestamp}"

    success = run_command(
        f'alembic revision --autogenerate -m "{msg}"',
        "🔍 检测模型变更并生成迁移脚本..."
    )

    if success:
        print("✅ 迁移脚本已生成")

    return success


def upgrade_database():
    """执行数据库升级"""
    success = run_command(
        "alembic upgrade head",
        "⬆️  执行数据库迁移..."
    )

    if success:
        print("✅ 数据库升级完成")

    return success


def rollback_database(steps: int = 1):
    """回滚数据库"""
    success = run_command(
        f"alembic downgrade -{steps}",
        f"⬇️  回滚 {steps} 个版本..."
    )

    if success:
        print("✅ 回滚完成")

    return success


def show_history():
    """显示迁移历史"""
    return run_command(
        "alembic history",
        "📜 显示迁移历史..."
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="AI TestMaster 数据库迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s                    # 完整流程：检测->生成->执行
  %(prog)s --status           # 查看当前版本状态
  %(prog)s --generate-only    # 仅生成迁移脚本
  %(prog)s --upgrade-only     # 仅执行已有迁移
  %(prog)s --rollback         # 回滚到上一版本
  %(prog)s --history          # 查看迁移历史
        """
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="查看当前数据库版本状态"
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="仅生成迁移脚本，不执行"
    )
    parser.add_argument(
        "--upgrade-only",
        action="store_true",
        help="仅执行已有迁移，不生成新脚本"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="回滚到上一个版本"
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="查看迁移历史"
    )
    parser.add_argument(
        "-m", "--message",
        type=str,
        default=None,
        help="迁移描述信息"
    )
    parser.add_argument(
        "-s", "--steps",
        type=int,
        default=1,
        help="回滚步数（默认1）"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  AI TestMaster 数据库迁移工具")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 切换到项目根目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    try:
        if args.status:
            check_alembic_status()
        elif args.history:
            show_history()
        elif args.rollback:
            rollback_database(args.steps)
        elif args.generate_only:
            generate_migration(args.message)
        elif args.upgrade_only:
            upgrade_database()
        else:
            # 默认完整流程
            print("\n🚀 开始完整迁移流程...\n")

            print("[1/4] 检查当前状态...")
            check_alembic_status()

            print("\n[2/4] 生成迁移脚本...")
            generate_success = generate_migration(args.message)

            if generate_success:
                print("\n[3/4] 执行迁移...")
                upgrade_success = upgrade_database()

                if upgrade_success:
                    print("\n[4/4] 验证结果...")
                    check_alembic_status()

                    print("\n" + "=" * 70)
                    print("  ✅ 迁移完成！")
                    print("=" * 70)
                else:
                    print("\n❌ 迁移执行失败，请检查错误信息")
            else:
                print("\nℹ️  无需迁移或生成失败（可能是无模型变更）")

    except KeyboardInterrupt:
        print("\n\n❌ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
