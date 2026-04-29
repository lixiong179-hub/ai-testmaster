"""
AI视觉成本统计服务

统计AI视觉调用次数、缓存命中次数、成本节省率
生成成本优化报表

核心功能：
1. 实时成本统计
2. 缓存命中率分析
3. 成本优化建议
4. 成本趋势分析
5. 成本报表生成
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from loguru import logger

from app.models.test_case import TestCase, TestStep
from app.models.element_locator import ElementLocator
from app.models.test_result import TestResult


@dataclass
class CostStatistics:
    """成本统计数据"""
    total_steps: int  # 总步骤数
    ai_vision_calls: int  # AI视觉调用次数
    cache_hits: int  # 缓存命中次数
    css_selector_used: int  # CSS选择器使用次数
    xpath_used: int  # XPath使用次数
    
    # 成本计算
    estimated_cost: float  # 预估成本
    actual_cost: float  # 实际成本
    cost_savings: float  # 成本节省
    savings_rate: float  # 节省率（百分比）
    
    # 效率指标
    cache_hit_rate: float  # 缓存命中率
    ai_dependency_rate: float  # AI依赖率
    
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CostReport:
    """成本报表"""
    report_id: str
    project_id: int
    start_date: datetime
    end_date: datetime
    
    # 总体统计
    overall_statistics: CostStatistics
    
    # 按用例统计
    case_statistics: List[Dict[str, Any]]
    
    # 按日期统计
    daily_statistics: List[Dict[str, Any]]
    
    # 优化建议
    optimization_suggestions: List[Dict[str, Any]]
    
    # 趋势分析
    trend_data: List[Dict[str, Any]]
    
    generated_at: datetime = field(default_factory=datetime.now)


class CostStatisticsService:
    """
    AI视觉成本统计服务
    
    功能：
    1. 统计AI视觉调用次数和成本
    2. 分析缓存命中率
    3. 生成成本优化建议
    4. 提供成本趋势分析
    5. 生成成本报表
    """
    
    # 成本配置（单位：元/次）
    COST_PER_AI_VISION_CALL = 0.1  # 每次AI视觉调用成本
    COST_PER_CSS_SELECTOR = 0.001  # CSS选择器使用成本（可忽略）
    
    # 优化建议阈值配置
    AI_DEPENDENCY_THRESHOLD = 50.0  # AI依赖率阈值（%）
    BATCH_RECOGNITION_MIN_STEPS = 10  # 批量识别最小步骤数
    CACHE_HIT_RATE_THRESHOLD = 70.0  # 缓存命中率阈值（%）
    
    # 成本节省系数
    LOCATOR_SAVINGS_RATE = 0.8  # 补充定位可节省的成本比例
    BATCH_SAVINGS_RATE = 0.3    # 批量识别可节省的成本比例
    CACHE_SAVINGS_RATE = 0.2    # 优化缓存可节省的成本比例
    
    def __init__(self, db: Session):
        """
        初始化成本统计服务
        
        Args:
            db: 数据库会话
        """

    
    def get_case_cost_statistics(self, case_id: int) -> CostStatistics:
        """
        获取用例成本统计
        
        Args:
            case_id: 测试用例ID
            
        Returns:
            成本统计数据
        """
        # 获取用例信息（预加载步骤和定位信息）
        test_case = self.db.query(TestCase).filter(
            TestCase.id == case_id
        ).options(
            joinedload(TestCase.test_steps).joinedload(TestStep.element_locator)
        ).first()
        
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")
        
        # 获取步骤列表
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        total_steps = len(steps)
        
        if total_steps == 0:
            return CostStatistics(
                total_steps=0,
                ai_vision_calls=0,
                cache_hits=0,
                css_selector_used=0,
                xpath_used=0,
                estimated_cost=0,
                actual_cost=0,
                cost_savings=0,
                savings_rate=0,
                cache_hit_rate=0,
                ai_dependency_rate=0
            )
        
        # 统计定位信息
        ai_vision_calls = 0
        cache_hits = 0
        css_selector_used = 0
        xpath_used = 0
        
        for step in steps:
            locator = step.element_locator if hasattr(step, 'element_locator') else None
            
            if locator:
                # 有定位信息，使用CSS/XPath
                if locator.css_selector:
                    css_selector_used += 1
                    cache_hits += 1
                elif locator.xpath:
                    xpath_used += 1
                    cache_hits += 1
                else:
                    # 只有AI坐标，需要AI视觉
                    ai_vision_calls += 1
            else:
                # 无定位信息，需要AI视觉
                ai_vision_calls += 1
        
        # 计算成本
        estimated_cost = total_steps * self.COST_PER_AI_VISION_CALL
        actual_cost = ai_vision_calls * self.COST_PER_AI_VISION_CALL
        cost_savings = estimated_cost - actual_cost
        savings_rate = (cost_savings / estimated_cost * 100) if estimated_cost > 0 else 0
        
        # 计算效率指标
        cache_hit_rate = (cache_hits / total_steps * 100) if total_steps > 0 else 0
        ai_dependency_rate = (ai_vision_calls / total_steps * 100) if total_steps > 0 else 0
        
        return CostStatistics(
            total_steps=total_steps,
            ai_vision_calls=ai_vision_calls,
            cache_hits=cache_hits,
            css_selector_used=css_selector_used,
            xpath_used=xpath_used,
            estimated_cost=round(estimated_cost, 2),
            actual_cost=round(actual_cost, 2),
            cost_savings=round(cost_savings, 2),
            savings_rate=round(savings_rate, 1),
            cache_hit_rate=round(cache_hit_rate, 1),
            ai_dependency_rate=round(ai_dependency_rate, 1)
        )
    
    def get_project_cost_statistics(self, project_id: int) -> CostStatistics:
        """
        获取项目成本统计
        
        Args:
            project_id: 项目ID
            
        Returns:
            成本统计数据
        """
        # 获取项目所有用例
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        
        if not cases:
            return CostStatistics(
                total_steps=0,
                ai_vision_calls=0,
                cache_hits=0,
                css_selector_used=0,
                xpath_used=0,
                estimated_cost=0,
                actual_cost=0,
                cost_savings=0,
                savings_rate=0,
                cache_hit_rate=0,
                ai_dependency_rate=0
            )
        
        # 汇总所有用例的统计
        total_stats = {
            'total_steps': 0,
            'ai_vision_calls': 0,
            'cache_hits': 0,
            'css_selector_used': 0,
            'xpath_used': 0,
            'estimated_cost': 0,
            'actual_cost': 0
        }
        
        for case in cases:
            try:
                stats = self.get_case_cost_statistics(case.id)
                total_stats['total_steps'] += stats.total_steps
                total_stats['ai_vision_calls'] += stats.ai_vision_calls
                total_stats['cache_hits'] += stats.cache_hits
                total_stats['css_selector_used'] += stats.css_selector_used
                total_stats['xpath_used'] += stats.xpath_used
                total_stats['estimated_cost'] += stats.estimated_cost
                total_stats['actual_cost'] += stats.actual_cost
            except Exception as e:
                logger.error(f"统计用例成本失败 {case.id}: {e}")
        
        # 计算汇总指标
        cost_savings = total_stats['estimated_cost'] - total_stats['actual_cost']
        savings_rate = (cost_savings / total_stats['estimated_cost'] * 100) if total_stats['estimated_cost'] > 0 else 0
        cache_hit_rate = (total_stats['cache_hits'] / total_stats['total_steps'] * 100) if total_stats['total_steps'] > 0 else 0
        ai_dependency_rate = (total_stats['ai_vision_calls'] / total_stats['total_steps'] * 100) if total_stats['total_steps'] > 0 else 0
        
        return CostStatistics(
            total_steps=total_stats['total_steps'],
            ai_vision_calls=total_stats['ai_vision_calls'],
            cache_hits=total_stats['cache_hits'],
            css_selector_used=total_stats['css_selector_used'],
            xpath_used=total_stats['xpath_used'],
            estimated_cost=round(total_stats['estimated_cost'], 2),
            actual_cost=round(total_stats['actual_cost'], 2),
            cost_savings=round(cost_savings, 2),
            savings_rate=round(savings_rate, 1),
            cache_hit_rate=round(cache_hit_rate, 1),
            ai_dependency_rate=round(ai_dependency_rate, 1)
        )
    
    def generate_cost_report(
        self,
        project_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> CostReport:
        """
        生成成本报表
        
        Args:
            project_id: 项目ID
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            成本报表
        """
        # 默认查询最近30天
        if not end_date:
            end_date = datetime.now()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # 获取总体统计
        overall_stats = self.get_project_cost_statistics(project_id)
        
        # 获取用例统计
        case_stats = self._get_case_cost_details(project_id)
        
        # 获取每日统计
        daily_stats = self._get_daily_cost_statistics(project_id, start_date, end_date)
        
        # 生成优化建议
        suggestions = self._generate_cost_optimization_suggestions(project_id, overall_stats)
        
        # 获取趋势数据
        trend_data = self._get_cost_trend(project_id, start_date, end_date)
        
        report = CostReport(
            report_id=f"COST-{project_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            project_id=project_id,
            start_date=start_date,
            end_date=end_date,
            overall_statistics=overall_stats,
            case_statistics=case_stats,
            daily_statistics=daily_stats,
            optimization_suggestions=suggestions,
            trend_data=trend_data
        )
        
        logger.info(f"成本报表生成完成: {report.report_id}")
        return report
    
    def _get_case_cost_details(self, project_id: int) -> List[Dict[str, Any]]:
        """获取用例成本详情"""
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        
        case_stats = []
        for case in cases:
            try:
                stats = self.get_case_cost_statistics(case.id)
                case_stats.append({
                    "case_id": case.id,
                    "case_name": case.title,
                    "total_steps": stats.total_steps,
                    "ai_vision_calls": stats.ai_vision_calls,
                    "cache_hits": stats.cache_hits,
                    "cache_hit_rate": stats.cache_hit_rate,
                    "actual_cost": stats.actual_cost,
                    "cost_savings": stats.cost_savings,
                    "savings_rate": stats.savings_rate
                })
            except Exception as e:
                logger.error(f"获取用例成本详情失败 {case.id}: {e}")
        
        # 按成本节省排序
        case_stats.sort(key=lambda x: x['cost_savings'], reverse=True)
        return case_stats
    
    def _get_daily_cost_statistics(
        self,
        project_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """获取每日成本统计"""
        # 获取项目所有用例
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        
        case_ids = [case.id for case in cases]
        
        if not case_ids:
            return []
        
        # 按日期统计执行结果
        results = self.db.query(
            func.date(TestResult.exec_time).label('date'),
            func.count(TestResult.id).label('execution_count')
        ).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= start_date,
            TestResult.exec_time <= end_date
        ).group_by(
            func.date(TestResult.exec_time)
        ).all()
        
        daily_stats = []
        for result in results:
            daily_stats.append({
                "date": result.date.isoformat() if result.date else None,
                "execution_count": result.execution_count or 0,
                "total_execution_time": 0
            })
        
        return daily_stats
    
    def _generate_cost_optimization_suggestions(
        self,
        project_id: int,
        overall_stats: CostStatistics
    ) -> List[Dict[str, Any]]:
        """生成成本优化建议"""
        suggestions = []
        
        # 建议1：补充元素定位
        if overall_stats.ai_dependency_rate > self.AI_DEPENDENCY_THRESHOLD:
            potential_savings = overall_stats.ai_vision_calls * self.COST_PER_AI_VISION_CALL * self.LOCATOR_SAVINGS_RATE
            suggestions.append({
                "type": "补充元素定位",
                "description": f"AI依赖率较高({overall_stats.ai_dependency_rate}%)，建议为更多步骤补充元素定位信息",
                "potential_savings": round(potential_savings, 2),
                "priority": "high",
                "impact": "可显著降低AI视觉成本"
            })
        
        # 建议2：启用批量识别
        if overall_stats.total_steps >= self.BATCH_RECOGNITION_MIN_STEPS:
            batch_savings = overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.BATCH_SAVINGS_RATE
            suggestions.append({
                "type": "启用批量识别",
                "description": "用例步骤较多，建议使用批量元素识别功能",
                "potential_savings": round(batch_savings, 2),
                "priority": "medium",
                "impact": "减少AI调用次数"
            })
        
        # 建议3：优化缓存策略
        if overall_stats.cache_hit_rate < self.CACHE_HIT_RATE_THRESHOLD:
            cache_savings = overall_stats.total_steps * self.COST_PER_AI_VISION_CALL * self.CACHE_SAVINGS_RATE
            suggestions.append({
                "type": "优化缓存策略",
                "description": f"缓存命中率较低({overall_stats.cache_hit_rate}%)，建议优化定位缓存策略",
                "potential_savings": round(cache_savings, 2),
                "priority": "medium",
                "impact": "提升缓存利用率"
            })
        
        return suggestions
    
    def _get_cost_trend(
        self,
        project_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """获取成本趋势"""
        # 获取项目所有用例
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        
        case_ids = [case.id for case in cases]
        
        if not case_ids:
            return []
        
        # 按周统计
        results = self.db.query(
            func.yearweek(TestResult.exec_time).label('week'),
            func.count(TestResult.id).label('execution_count'),
            func.avg(TestResult.execution_time).label('avg_execution_time')
        ).filter(
            TestResult.case_id.in_(case_ids),
            TestResult.exec_time >= start_date,
            TestResult.exec_time <= end_date
        ).group_by(
            func.yearweek(TestResult.exec_time)
        ).order_by(
            func.yearweek(TestResult.exec_time)
        ).all()
        
        trend = []
        for result in results:
            trend.append({
                "week": result.week,
                "execution_count": result.execution_count or 0,
                "avg_execution_time": round(result.avg_execution_time or 0, 2)
            })
        
        return trend
    
    def get_cost_summary(self, project_id: int) -> Dict[str, Any]:
        """
        获取成本摘要（用于仪表盘）
        
        Args:
            project_id: 项目ID
            
        Returns:
            成本摘要
        """
        stats = self.get_project_cost_statistics(project_id)
        
        return {
            "total_cost": stats.actual_cost,
            "cost_savings": stats.cost_savings,
            "savings_rate": stats.savings_rate,
            "ai_vision_calls": stats.ai_vision_calls,
            "cache_hit_rate": stats.cache_hit_rate,
            "ai_dependency_rate": stats.ai_dependency_rate,
            "optimization_potential": stats.cost_savings > 0
        }

