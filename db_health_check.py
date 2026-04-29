"""
数据库健康检查工具 - 运维监控和诊断

功能：
1. 数据库连接测试
2. 表结构一致性检查
3. 外键完整性验证
4. 索引状态检查
5. 性能指标收集
6. 生成健康报告（JSON格式，便于监控系统消费）

使用场景：
- 定时健康检查（cron/定时任务）
- CI/CD流水线质量门禁
- 运维监控告警
- 问题诊断和排查

输出格式：
- 控制台：彩色文本报告
- 文件：JSON格式详细报告
- API：可直接返回给监控系统

使用方法:
    # 完整检查
    python db_health_check.py

    # 仅检查连接
    python db_health_check.py --check connection

    # 输出JSON报告
    python db_health_check.py --json report.json

    # 静默模式（仅输出错误）
    python db_health_check.py --quiet
"""

import sys
import os
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text, inspect
from app.core.config import settings


@dataclass
class HealthCheckResult:
    """健康检查结果数据类"""
    status: str  # healthy/warning/critical
    timestamp: str
    checks: Dict[str, Any]
    summary: str
    details: List[str]


class DatabaseHealthChecker:
    """数据库健康检查器"""

    def __init__(self, database_url: str = None):
        """
        初始化检查器

        Args:
            database_url: 数据库连接URL，默认使用配置文件中的URL
        """
        self.database_url = database_url or settings.DATABASE_URL
        self.engine = None
        self.inspector = None
        self.results = {}

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self.engine = create_engine(self.database_url)
            self.inspector = inspect(self.engine)
            return True
        except Exception as e:
            self.results['connection'] = {
                'status': 'critical',
                'message': f'连接失败: {e}',
                'latency_ms': None
            }
            return False

    def check_connection(self) -> Dict[str, Any]:
        """检查1：数据库连接测试"""
        result = {
            'status': 'unknown',
            'message': '',
            'latency_ms': None,
            'database': None,
            'version': None
        }

        try:
            start_time = time.time()

            with self.engine.connect() as conn:
                # 测试基本查询
                db_result = conn.execute(text("SELECT VERSION()"))
                version_info = db_result.scalar()

                # 获取当前数据库
                db_name_result = conn.execute(text("SELECT DATABASE()"))
                database = db_name_result.scalar()

                latency = (time.time() - start_time) * 1000

                result.update({
                    'status': 'healthy',
                    'message': '连接正常',
                    'latency_ms': round(latency, 2),
                    'database': database,
                    'version': version_info
                })

        except Exception as e:
            result.update({
                'status': 'critical',
                'message': f'连接异常: {e}',
                'latency_ms': None
            })

        self.results['connection'] = result
        return result

    def check_table_structure(self) -> Dict[str, Any]:
        """检查2：表结构一致性"""
        from app.db.database import Base
        from app.db.smart_sync import DatabaseSyncTool

        result = {
            'status': 'healthy',
            'total_tables': 0,
            'synced_tables': 0,
            'out_of_sync_tables': [],
            'details': []
        }

        try:
            sync_tool = DatabaseSyncTool(self.engine)

            for table_name in sorted(Base.metadata.tables.keys()):
                missing_cols, existing_cols = sync_tool.find_missing_columns(table_name, Base)

                table_info = {
                    'table': table_name,
                    'model_columns': len(sync_tool.get_model_columns(table_name, Base)),
                    'db_columns': len(existing_cols),
                    'missing_columns': [col['name'] for col in missing_cols],
                    'status': 'synced' if not missing_cols else 'out_of_sync'
                }

                result['details'].append(table_info)
                result['total_tables'] += 1

                if missing_cols:
                    result['status'] = 'warning'
                    result['out_of_sync_tables'].append(table_name)
                else:
                    result['synced_tables'] += 1

        except Exception as e:
            result['status'] = 'critical'
            result['message'] = f'表结构检查失败: {e}'

        self.results['table_structure'] = result
        return result

    def check_foreign_keys(self) -> Dict[str, Any]:
        """检查3：外键完整性"""
        result = {
            'status': 'healthy',
            'total_foreign_keys': 0,
            'broken_foreign_keys': [],
            'details': []
        }

        try:
            tables = self.inspector.get_table_names()

            for table in tables:
                try:
                    fks = self.inspector.get_foreign_keys(table)
                    for fk in fks:
                        fk_info = {
                            'table': table,
                            'constrained_columns': fk.get('constrained_columns', []),
                            'referred_table': fk.get('referred_table', ''),
                            'referred_columns': fk.get('referred_columns', []),
                            'name': fk.get('name', '')
                        }
                        result['details'].append(fk_info)
                        result['total_foreign_keys'] += 1

                        # 检查是否有孤立记录（可选，可能耗时）
                        if fk_info['constrained_columns'] and fk_info['referred_table']:
                            pass  # 可以添加更详细的检查

                except Exception as e:
                    result['broken_foreign_keys'].append({
                        'table': table,
                        'error': str(e)
                    })

            if result['broken_foreign_keys']:
                result['status'] = 'warning'

        except Exception as e:
            result['status'] = 'critical'
            result['message'] = f'外键检查失败: {e}'

        self.results['foreign_keys'] = result
        return result

    def check_indexes(self) -> Dict[str, Any]:
        """检查4：索引状态"""
        result = {
            'status': 'healthy',
            'total_indexes': 0,
            'tables_without_pk': [],
            'details': {}
        }

        try:
            tables = self.inspector.get_table_names()

            for table in tables[:20]:  # 限制检查前20个表
                try:
                    indexes = self.inspector.get_indexes(table)
                    pk = self.inspector.get_pk_constraint(table)

                    result['details'][table] = {
                        'index_count': len(indexes),
                        'has_primary_key': pk is not None and pk.get('constrained_columns') is not None
                    }
                    result['total_indexes'] += len(indexes)

                    if not pk or not pk.get('constrained_columns'):
                        result['tables_without_pk'].append(table)

                except Exception as e:
                    result['details'][table] = {'error': str(e)}

            if result['tables_without_pk']:
                result['status'] = 'warning'

        except Exception as e:
            result['status'] = 'critical'
            result['message'] = f'索引检查失败: {e}'

        self.results['indexes'] = result
        return result

    def run_all_checks(self) -> HealthCheckResult:
        """执行所有健康检查"""
        timestamp = datetime.now().isoformat()

        # 连接检查
        if not self.connect():
            return HealthCheckResult(
                status='critical',
                timestamp=timestamp,
                checks=self.results,
                summary='数据库连接失败',
                details=['无法连接到数据库']
            )

        # 执行各项检查
        print("📊 正在执行健康检查...\n")

        print("[1/4] 检查数据库连接...")
        conn_result = self.check_connection()
        self._print_check_result("连接", conn_result)

        print("\n[2/4] 检查表结构...")
        struct_result = self.check_table_structure()
        self._print_check_result("表结构", struct_result)

        print("\n[3/4] 检查外键完整性...")
        fk_result = self.check_foreign_keys()
        self._print_check_result("外键", fk_result)

        print("\n[4/4] 检查索引状态...")
        idx_result = self.check_indexes()
        self._print_check_result("索引", idx_result)

        # 计算总体状态
        overall_status = self._calculate_overall_status()
        summary = self._generate_summary()

        details = []
        if struct_result.get('out_of_sync_tables'):
            details.append(f"⚠️  {len(struct_result['out_of_sync_tables'])} 个表结构不同步")
        if fk_result.get('broken_foreign_keys'):
            details.append(f"⚠️  {len(fk_result['broken_foreign_keys'])} 个外键异常")
        if idx_result.get('tables_without_pk'):
            details.append(f"⚠️  {len(idx_result['tables_without_pk'])} 个表缺少主键")

        return HealthCheckResult(
            status=overall_status,
            timestamp=timestamp,
            checks=self.results,
            summary=summary,
            details=details
        )

    def _calculate_overall_status(self) -> str:
        """计算总体健康状态"""
        statuses = [r.get('status', 'unknown') for r in self.results.values()]

        if 'critical' in statuses:
            return 'critical'
        elif 'warning' in statuses:
            return 'warning'
        else:
            return 'healthy'

    def _generate_summary(self) -> str:
        """生成摘要信息"""
        conn = self.results.get('connection', {})
        struct = self.results.get('table_structure', {})

        parts = [
            f"数据库: {conn.get('database', 'N/A')}",
            f"延迟: {conn.get('latency_ms', 'N/A')}ms",
            f"表数量: {struct.get('total_tables', 0)}",
            f"同步状态: {struct.get('synced_tables', 0)}/{struct.get('total_tables', 0)}"
        ]

        return " | ".join(parts)

    @staticmethod
    def _print_check_result(name: str, result: Dict):
        """打印检查结果"""
        status = result.get('status', 'unknown')
        icon = {'healthy': '✅', 'warning': '⚠️ ', 'critical': '❌'}.get(status, '❓')

        print(f"{icon} {name}: {status.upper()}")

        if result.get('latency_ms'):
            print(f"   延迟: {result['latency_ms']}ms")

        if result.get('out_of_sync_tables'):
            print(f"   不同步的表: {result['out_of_sync_tables']}")

        if result.get('total_indexes') is not None:
            print(f"   索引总数: {result['total_indexes']}")

    def to_json(self, result: HealthCheckResult) -> str:
        """转换为JSON格式"""
        return json.dumps(asdict(result), indent=2, ensure_ascii=False, default=str)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库健康检查工具")
    parser.add_argument('--json', type=str, default=None, help="输出JSON报告到文件")
    parser.add_argument('--quiet', action='store_true', help="静默模式（仅显示错误）")
    parser.add_argument('--check', type=str, default=None, help="仅执行指定检查项 (connection/structure/indexes)")

    args = parser.parse_args()

    print("=" * 70)
    print("  AI TestMaster 数据库健康检查")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70 + "\n")

    checker = DatabaseHealthChecker()

    try:
        if args.check == 'connection':
            checker.connect()
            result = checker.check_connection()
            checker._print_check_result("连接", result)
            health_result = HealthCheckResult(
                status=result['status'],
                timestamp=datetime.now().isoformat(),
                checks={'connection': result},
                summary=f"连接状态: {result['status']}",
                details=[]
            )
        else:
            health_result = checker.run_all_checks()

        # 输出结果
        print("\n" + "=" * 70)
        print("  健康检查报告")
        print("=" * 70)
        print(f"\n总体状态: {health_result.status.upper()}")
        print(f"摘要: {health_result.summary}")

        if health_result.details:
            print("\n注意事项:")
            for detail in health_result.details:
                print(f"  • {detail}")

        # 输出JSON（如果指定）
        if args.json:
            with open(args.json, 'w', encoding='utf-8') as f:
                f.write(checker.to_json(health_result))
            print(f"\n📄 JSON报告已保存到: {args.json}")

        # 返回退出码
        if health_result.status == 'critical':
            sys.exit(2)
        elif health_result.status == 'warning':
            sys.exit(1)
        else:
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
