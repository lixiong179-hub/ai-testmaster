"""
用例质量分析服务

分析测试用例质量，提供评分和优化建议

核心功能：
1. 用例复杂度评分
2. 用例冗余度分析
3. 定位覆盖率评估
4. 优化建议生成
"""
from typing import Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from loguru import logger

from app.models.test_case import TestCase
from app.models.element_locator import ElementLocator
from app.models.test_result import TestResult


@dataclass
class ComplexityScore:
    """复杂度评分"""
    step_count_score: float  # 步骤数量评分
    action_variety_score: float  # 操作类型多样性评分
    data_dependency_score: float  # 数据依赖复杂度评分
    total_score: float  # 总复杂度评分
    level: str  # 复杂度等级：low, medium, high


@dataclass
class RedundancyScore:
    """冗余度评分"""
    duplicate_steps_score: float  # 重复步骤评分
    similar_cases_score: float  # 相似用例评分
    unnecessary_steps_score: float  # 不必要步骤评分
    total_score: float  # 总冗余度评分
    redundant_step_indices: List[int] = field(default_factory=list)  # 冗余步骤索引


@dataclass
class CoverageScore:
    """覆盖率评分"""
    locator_coverage: float  # 元素定位覆盖率
    execution_coverage: float  # 执行历史覆盖率
    assertion_coverage: float  # 断言覆盖率
    total_score: float  # 总覆盖率评分


@dataclass
class QualityReport:
    """质量分析报告"""
    case_id: int
    case_name: str
    overall_score: float  # 综合质量评分（0-100）
    complexity: ComplexityScore
    redundancy: RedundancyScore
    coverage: CoverageScore
    optimization_suggestions: List[Dict[str, Any]]
    created_at: datetime = field(default_factory=datetime.now)


class CaseQualityAnalyzer:
    """
    用例质量分析器
    
    功能：
    1. 分析用例复杂度（步骤数、操作类型、数据依赖）
    2. 检测用例冗余（重复步骤、相似用例）
    3. 评估定位覆盖率
    4. 生成优化建议
    """
    
    # 评分权重配置
    WEIGHTS = {
        "complexity": 0.30,  # 复杂度权重
        "redundancy": 0.30,  # 冗余度权重
        "coverage": 0.40,    # 覆盖率权重
    }
    
    # 复杂度阈值
    COMPLEXITY_THRESHOLDS = {
        "low": 30,      # 低复杂度阈值
        "medium": 60,   # 中复杂度阈值
        "high": 100,    # 高复杂度阈值
    }
    
    # 操作类型定义
    ACTION_TYPES = {
        "click": ["点击", "单击", "按下", "选择"],
        "input": ["输入", "填写", "键入", "录入"],
        "verify": ["验证", "检查", "确认", "断言"],
        "wait": ["等待", "暂停", "延迟"],
        "navigate": ["跳转", "打开", "进入", "访问"],
        "scroll": ["滚动", "滑动"],
        "upload": ["上传", "选择文件"],
        "download": ["下载"],
    }
    
    def __init__(self, db: Session):
        """
        初始化用例质量分析器
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    async def analyze_case_quality(self, case_id: int) -> QualityReport:
        """
        分析用例质量
        
        Args:
            case_id: 测试用例ID
            
        Returns:
            质量分析报告
        """
        # 获取测试用例
        test_case = self.db.query(TestCase).filter(TestCase.id == case_id).first()
        if not test_case:
            raise ValueError(f"测试用例不存在: {case_id}")
        
        logger.info(f"开始分析用例质量: {test_case.title} (ID: {case_id})")
        
        # 分析各项评分
        complexity = self._analyze_complexity(test_case)
        redundancy = self._analyze_redundancy(test_case)
        coverage = self._analyze_coverage(test_case)
        
        # 生成优化建议
        suggestions = self._generate_optimization_suggestions(
            test_case, complexity, redundancy, coverage
        )
        
        # 计算综合评分
        overall_score = self._calculate_overall_score(
            complexity, redundancy, coverage
        )
        
        report = QualityReport(
            case_id=case_id,
            case_name=test_case.title,
            overall_score=overall_score,
            complexity=complexity,
            redundancy=redundancy,
            coverage=coverage,
            optimization_suggestions=suggestions
        )
        
        logger.info(f"用例质量分析完成: {test_case.title}, 综合评分: {overall_score:.1f}")
        return report
    
    def _analyze_complexity(self, test_case: TestCase) -> ComplexityScore:
        """
        分析用例复杂度
        
        评估维度：
        1. 步骤数量（步骤越多越复杂）
        2. 操作类型多样性（类型越多越复杂）
        3. 数据依赖（依赖越多越复杂）
        """
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        step_count = len(steps)
        
        # 1. 步骤数量评分（满分30分）
        if step_count <= 5:
            step_count_score = 30
        elif step_count <= 10:
            step_count_score = 20
        elif step_count <= 20:
            step_count_score = 10
        else:
            step_count_score = 5
        
        # 2. 操作类型多样性评分（满分40分）
        action_types_found = set()
        for step in steps:
            action = step.action if hasattr(step, 'action') else str(step)
            for action_type, keywords in self.ACTION_TYPES.items():
                if any(keyword in action for keyword in keywords):
                    action_types_found.add(action_type)
                    break
        
        action_variety_score = min(40, len(action_types_found) * 10)
        
        # 3. 数据依赖复杂度评分（满分30分）
        data_dependencies = 0
        for step in steps:
            # 检查是否有数据依赖标记
            if hasattr(step, 'data') and step.data:
                data_dependencies += 1
            # 检查是否有参数化标记
            if hasattr(step, 'params') and step.params:
                data_dependencies += 1
        
        if data_dependencies == 0:
            data_dependency_score = 30
        elif data_dependencies <= 3:
            data_dependency_score = 20
        elif data_dependencies <= 6:
            data_dependency_score = 10
        else:
            data_dependency_score = 5
        
        # 计算总复杂度评分
        total_score = step_count_score + action_variety_score + data_dependency_score
        
        # 确定复杂度等级
        if total_score >= 80:
            level = "low"
        elif total_score >= 50:
            level = "medium"
        else:
            level = "high"
        
        return ComplexityScore(
            step_count_score=step_count_score,
            action_variety_score=action_variety_score,
            data_dependency_score=data_dependency_score,
            total_score=total_score,
            level=level
        )
    
    def _analyze_redundancy(self, test_case: TestCase) -> RedundancyScore:
        """
        分析用例冗余度
        
        检测维度：
        1. 重复步骤（相同操作和目标的步骤）
        2. 相似用例（与其他用例相似度）
        3. 不必要步骤（可以合并或删除的步骤）
        """
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        
        # 1. 检测重复步骤（满分40分）
        duplicate_indices = []
        step_signatures = []
        
        for i, step in enumerate(steps):
            # 生成步骤签名
            action = step.action if hasattr(step, 'action') else str(step)
            target = step.target if hasattr(step, 'target') else ""
            signature = f"{action}:{target}"
            
            if signature in step_signatures:
                duplicate_indices.append(i)
            else:
                step_signatures.append(signature)
        
        duplicate_ratio = len(duplicate_indices) / len(steps) if steps else 0
        duplicate_steps_score = max(0, 40 - duplicate_ratio * 40)
        
        # 2. 检测相似用例（满分30分）
        similar_cases = self._find_similar_cases(test_case)
        similar_cases_score = max(0, 30 - len(similar_cases) * 10)
        
        # 3. 检测不必要步骤（满分30分）
        unnecessary_indices = []
        for i, step in enumerate(steps):
            action = step.action if hasattr(step, 'action') else str(step)
            # 检测连续等待、重复验证等不必要操作
            if i > 0:
                prev_action = steps[i-1].action if hasattr(steps[i-1], 'action') else str(steps[i-1])
                # 连续等待
                if "等待" in action and "等待" in prev_action:
                    unnecessary_indices.append(i)
                # 重复验证同一元素
                if "验证" in action and "验证" in prev_action:
                    target = step.target if hasattr(step, 'target') else ""
                    prev_target = steps[i-1].target if hasattr(steps[i-1], 'target') else ""
                    if target == prev_target:
                        unnecessary_indices.append(i)
        
        unnecessary_ratio = len(unnecessary_indices) / len(steps) if steps else 0
        unnecessary_steps_score = max(0, 30 - unnecessary_ratio * 30)
        
        # 计算总冗余度评分
        total_score = duplicate_steps_score + similar_cases_score + unnecessary_steps_score
        
        return RedundancyScore(
            duplicate_steps_score=duplicate_steps_score,
            similar_cases_score=similar_cases_score,
            unnecessary_steps_score=unnecessary_steps_score,
            total_score=total_score,
            redundant_step_indices=list(set(duplicate_indices + unnecessary_indices))
        )
    
    def _find_similar_cases(self, test_case: TestCase) -> List[Dict[str, Any]]:
        """查找相似用例"""
        similar_cases = []
        
        # 获取所有同项目的用例
        all_cases = self.db.query(TestCase).filter(
            TestCase.project_id == test_case.project_id,
            TestCase.id != test_case.id
        ).all()
        
        # 计算相似度
        case_steps = [step.action if hasattr(step, 'action') else str(step) 
                      for step in (test_case.test_steps or [])]
        
        for other_case in all_cases:
            other_steps = [step.action if hasattr(step, 'action') else str(step) 
                          for step in (other_case.test_steps or [])]
            
            # 使用序列匹配计算相似度
            similarity = SequenceMatcher(None, 
                " ".join(case_steps), 
                " ".join(other_steps)
            ).ratio()
            
            if similarity >= 0.7:  # 相似度阈值
                similar_cases.append({
                    "case_id": other_case.id,
                    "case_name": other_case.title,
                    "similarity": round(similarity * 100, 1)
                })
        
        return similar_cases
    
    def _analyze_coverage(self, test_case: TestCase) -> CoverageScore:
        """
        分析覆盖率
        
        评估维度：
        1. 元素定位覆盖率（有多少步骤有定位信息）
        2. 执行历史覆盖率（是否被执行过）
        3. 断言覆盖率（是否有验证步骤）
        """
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        total_steps = len(steps)
        
        if total_steps == 0:
            return CoverageScore(
                locator_coverage=0,
                execution_coverage=0,
                assertion_coverage=0,
                total_score=0
            )
        
        # 1. 元素定位覆盖率（满分40分）
        located_steps = 0
        for step in steps:
            step_id = step.id if hasattr(step, 'id') else None
            if step_id:
                locator = self.db.query(ElementLocator).filter(
                    ElementLocator.step_id == step_id
                ).first()
                if locator:
                    located_steps += 1
        
        locator_coverage = (located_steps / total_steps) * 100
        locator_score = min(40, locator_coverage * 0.4)
        
        # 2. 执行历史覆盖率（满分30分）
        execution_count = self.db.query(TestResult).filter(
            TestResult.case_id == test_case.id
        ).count()
        
        if execution_count >= 5:
            execution_score = 30
        elif execution_count >= 3:
            execution_score = 20
        elif execution_count >= 1:
            execution_score = 10
        else:
            execution_score = 0
        
        execution_coverage = min(100, execution_count * 20)
        
        # 3. 断言覆盖率（满分30分）
        assertion_steps = 0
        for step in steps:
            action = step.action if hasattr(step, 'action') else str(step)
            if any(keyword in action for keyword in ["验证", "检查", "确认", "断言"]):
                assertion_steps += 1
        
        assertion_coverage = (assertion_steps / total_steps) * 100
        assertion_score = min(30, assertion_coverage * 0.3)
        
        # 计算总覆盖率评分
        total_score = locator_score + execution_score + assertion_score
        
        return CoverageScore(
            locator_coverage=round(locator_coverage, 1),
            execution_coverage=round(execution_coverage, 1),
            assertion_coverage=round(assertion_coverage, 1),
            total_score=round(total_score, 1)
        )
    
    def _generate_optimization_suggestions(
        self,
        test_case: TestCase,
        complexity: ComplexityScore,
        redundancy: RedundancyScore,
        coverage: CoverageScore
    ) -> List[Dict[str, Any]]:
        """生成优化建议"""
        suggestions = []
        steps = test_case.test_steps if hasattr(test_case, 'test_steps') else []
        
        # 复杂度优化建议
        if complexity.level == "high":
            suggestions.append({
                "category": "复杂度优化",
                "title": "用例过于复杂，建议拆分",
                "description": f"当前用例包含{len(steps)}个步骤，建议拆分为多个小用例",
                "priority": "high",
                "impact": "提升可维护性和执行稳定性"
            })
        
        # 冗余度优化建议
        if redundancy.redundant_step_indices:
            suggestions.append({
                "category": "冗余优化",
                "title": "删除或合并冗余步骤",
                "description": f"发现{len(redundancy.redundant_step_indices)}个冗余步骤",
                "priority": "medium",
                "impact": "减少执行时间和维护成本"
            })
        
        # 覆盖率优化建议
        if coverage.locator_coverage < 80:
            suggestions.append({
                "category": "覆盖率优化",
                "title": "补充元素定位信息",
                "description": f"当前定位覆盖率仅{coverage.locator_coverage:.1f}%，建议补充缺失的定位信息",
                "priority": "high",
                "impact": "降低AI视觉成本，提升执行稳定性"
            })
        
        if coverage.assertion_coverage < 30:
            suggestions.append({
                "category": "覆盖率优化",
                "title": "增加验证步骤",
                "description": f"当前断言覆盖率仅{coverage.assertion_coverage:.1f}%，建议增加验证点",
                "priority": "medium",
                "impact": "提升测试有效性"
            })
        
        # 添加AI生成的建议
        ai_suggestions = self._generate_ai_suggestions(test_case)
        suggestions.extend(ai_suggestions)
        
        return suggestions
    
    def _generate_ai_suggestions(self, test_case: TestCase) -> List[Dict[str, Any]]:
        """使用AI生成优化建议"""
        suggestions = []
        
        # 分析用例标题和描述
        title = test_case.title if hasattr(test_case, 'title') else ""
        description = test_case.description if hasattr(test_case, 'description') else ""
        
        # 基于规则的建议
        if "登录" in title and "登录" in description:
            suggestions.append({
                "category": "AI建议",
                "title": "考虑使用前置操作",
                "description": "登录操作可以作为前置操作，避免在每个用例中重复执行",
                "priority": "medium",
                "impact": "减少重复执行，提升效率"
            })
        
        if "查询" in title or "搜索" in title:
            suggestions.append({
                "category": "AI建议",
                "title": "添加数据准备步骤",
                "description": "查询用例需要确保测试数据存在，建议添加数据准备或清理步骤",
                "priority": "medium",
                "impact": "提升用例稳定性"
            })
        
        return suggestions
    
    def _calculate_overall_score(
        self,
        complexity: ComplexityScore,
        redundancy: RedundancyScore,
        coverage: CoverageScore
    ) -> float:
        """计算综合质量评分"""
        # 归一化各维度评分到0-100
        complexity_normalized = complexity.total_score
        redundancy_normalized = redundancy.total_score
        coverage_normalized = coverage.total_score
        
        # 加权计算
        overall = (
            complexity_normalized * self.WEIGHTS["complexity"] +
            redundancy_normalized * self.WEIGHTS["redundancy"] +
            coverage_normalized * self.WEIGHTS["coverage"]
        )
        
        return round(overall, 1)
    
    async def analyze_project_quality(self, project_id: int) -> Dict[str, Any]:
        """
        分析整个项目的用例质量
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目质量分析报告
        """
        # 获取项目所有用例
        cases = self.db.query(TestCase).filter(
            TestCase.project_id == project_id
        ).all()
        
        if not cases:
            return {
                "project_id": project_id,
                "total_cases": 0,
                "average_score": 0,
                "quality_distribution": {},
                "top_issues": []
            }
        
        # 分析每个用例
        case_reports = []
        for case in cases:
            try:
                report = await self.analyze_case_quality(case.id)
                case_reports.append(report)
            except Exception as e:
                logger.error(f"分析用例失败 {case.id}: {e}")
        
        # 统计
        total_cases = len(case_reports)
        average_score = sum(r.overall_score for r in case_reports) / total_cases if total_cases > 0 else 0
        
        # 质量分布
        quality_distribution = {
            "excellent": len([r for r in case_reports if r.overall_score >= 80]),
            "good": len([r for r in case_reports if 60 <= r.overall_score < 80]),
            "fair": len([r for r in case_reports if 40 <= r.overall_score < 60]),
            "poor": len([r for r in case_reports if r.overall_score < 40])
        }
        
        # 汇总问题
        all_issues = []
        for report in case_reports:
            for suggestion in report.optimization_suggestions:
                all_issues.append({
                    "case_id": report.case_id,
                    "case_name": report.case_name,
                    **suggestion
                })
        
        # 按优先级排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_issues.sort(key=lambda x: priority_order.get(x.get("priority", "low"), 3))
        
        return {
            "project_id": project_id,
            "total_cases": total_cases,
            "average_score": round(average_score, 1),
            "quality_distribution": quality_distribution,
            "top_issues": all_issues[:10],  # 前10个问题
        }
    
    def get_quality_trend(self, case_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取用例质量趋势
        
        Args:
            case_id: 用例ID
            days: 查询天数
            
        Returns:
            质量趋势数据
        """
        # 获取历史执行记录
        from_date = datetime.now() - timedelta(days=days)
        
        results = self.db.query(TestResult).filter(
            TestResult.case_id == case_id,
            TestResult.exec_time >= from_date
        ).order_by(TestResult.exec_time).all()
        
        trend = []
        for result in results:
            trend.append({
                "date": result.exec_time.isoformat() if result.exec_time else None,
                "status": result.exec_status,
                "execution_time": result.execution_time if hasattr(result, 'execution_time') else None
            })
        
        return trend

