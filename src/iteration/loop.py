"""评估驱动迭代闭环：自动识别失败模式、生成迭代方向建议。"""

from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum

from evaluation.judge import LLMJudge, JudgeResult
from evaluation.metrics import RuleBasedMetrics, MetricResult
from prompt_manager.version_manager import PromptVersionManager


class IterationStatus(str, Enum):
    """迭代状态枚举。"""
    IMPROVED = "improved"        # 新版本优于旧版本
    REGRESSED = "regressed"      # 新版本出现回归
    STABLE = "stable"            # 无显著变化
    INCONCLUSIVE = "inconclusive"  # 数据不足，无法判断


@dataclass
class FailurePattern:
    """失败模式分类。"""
    category: str  # 如 format_error, factual_error, style_drift, safety_violation
    count: int  # 该类失败出现的次数
    sample_ids: list[str]  # 关联的样本 ID
    severity: float  # 0.0~1.0，严重程度


@dataclass
class IterationSuggestion:
    """迭代方向建议。"""
    target_dimension: str  # 建议优化的维度
    direction: str  # 具体的优化方向描述
    priority: float  # 0.0~1.0，优先级
    reasoning: str  # 建议依据
    related_failures: list[str]  # 关联的失败样本 ID


@dataclass
class IterationResult:
    """一次迭代闭环的完整结果。"""
    old_version_id: str
    new_version_id: str
    status: IterationStatus
    delta_scores: dict[str, float]  # 各维度的得分变化
    regressions: list[str]  # 出现回归的维度
    failure_patterns: list[FailurePattern]  # 识别到的失败模式
    suggestions: list[IterationSuggestion]  # 迭代建议
    is_significant: bool  # 变化是否统计显著
    confidence: float  # 结果置信度


class IterationLoop:
    """评估驱动的迭代闭环引擎。

    核心流程：
    1. 对新旧版本执行双轨评估（Parallel Evaluation）
    2. 对比评估结果，计算各维度差分（Delta）
    3. 判断整体状态（改善/回归/稳定/不确定）
    4. 对失败样本进行聚类归因
    5. 生成结构化的迭代方向建议

    关键设计决策：
    - 采用"双轨并行评估"而非"先后评估"，确保对比公平性
    - 回归检测阈值可配置（默认 tolerance=0.05），
      即新版本分数低于 best_ever * (1 - tolerance) 时标记回归
    - 统计显著性使用 t-test 判断（要求样本量 >= 30）
    """

    def __init__(
        self,
        version_manager: PromptVersionManager,
        judge: LLMJudge,
        rule_metrics: RuleBasedMetrics,
        regression_tolerance: float = 0.05,
        significance_level: float = 0.05,
    ) -> None:
        """初始化迭代闭环。

        Args:
            version_manager: Prompt 版本管理器
            judge: LLM-as-Judge 评估器
            rule_metrics: 规则-based 指标引擎
            regression_tolerance: 回归容忍度（0.0~1.0）
            significance_level: 统计显著性水平
        """
        self.version_manager = version_manager
        self.judge = judge
        self.rule_metrics = rule_metrics
        self.regression_tolerance = regression_tolerance
        self.significance_level = significance_level
        self._best_scores: dict[str, float] = {}  # 各维度的历史最佳分数

    def _compute_delta(
        self,
        old_scores: dict[str, float],
        new_scores: dict[str, float],
    ) -> dict[str, float]:
        """计算两个版本在各维度的得分差分。

        正值表示新版本更优，负值表示回归。

        Args:
            old_scores: 旧版本各维度平均分
            new_scores: 新版本各维度平均分

        Returns:
            各维度的差分字典
        """
        delta: dict[str, float] = {}
        for dim in old_scores:
            if dim in new_scores:
                delta[dim] = new_scores[dim] - old_scores[dim]
        return delta

    def _detect_regressions(
        self,
        delta: dict[str, float],
        new_scores: dict[str, float],
    ) -> list[str]:
        """检测出现回归的维度。

        回归判定条件：
        - 新版本该维度得分 < 历史最佳 * (1 - tolerance)
        - 或新版本该维度得分相比旧版本下降

        Args:
            delta: 各维度差分
            new_scores: 新版本各维度得分

        Returns:
            出现回归的维度列表
        """
        regressions: list[str] = []
        for dim, diff in delta.items():
            if diff < 0:
                best = self._best_scores.get(dim, 0.0)
                if new_scores.get(dim, 1.0) < best * (1 - self.regression_tolerance):
                    regressions.append(dim)
        return regressions

    def _classify_failures(
        self,
        judge_results: list[JudgeResult],
        rule_results: list[list[MetricResult]],
    ) -> list[FailurePattern]:
        """对失败样本进行自动分类与归因。

        分类策略：
        - 规则检查失败的 → format_error / constraint_violation
        - LLM Judge 低分（< 0.4）的 → 按 dimension 聚类
        - 综合两者的结果去重

        Args:
            judge_results: LLM-as-Judge 评估结果
            rule_results: 规则检查结果

        Returns:
            FailurePattern 列表
        """
        patterns: dict[str, FailurePattern] = {}

        # 从规则检查结果中提取格式错误
        for i, results in enumerate(rule_results):
            for r in results:
                if r.value < 0.5 and r.is_binary:
                    category = "format_error" if "json" in r.metric_name or "format" in r.metric_name else "constraint_violation"
                    if category not in patterns:
                        patterns[category] = FailurePattern(
                            category=category, count=0, sample_ids=[], severity=0.5
                        )
                    patterns[category].count += 1
                    patterns[category].sample_ids.append(f"sample_{i}")

        # 从 LLM Judge 结果中提取语义层面的失败
        for jr in judge_results:
            for score in jr.scores:
                if score.score < 0.4:
                    category = f"low_{score.dimension}"
                    if category not in patterns:
                        patterns[category] = FailurePattern(
                            category=category, count=0, sample_ids=[], severity=1.0 - score.score
                        )
                    patterns[category].count += 1
                    patterns[category].sample_ids.append(jr.sample_id)

        return list(patterns.values())

    def _generate_suggestions(
        self,
        failure_patterns: list[FailurePattern],
        delta: dict[str, float],
    ) -> list[IterationSuggestion]:
        """基于失败模式生成迭代方向建议。

        生成策略：
        - 按失败频率和严重程度排序
        - 对 format_error 类建议加强格式约束
        - 对 low_* 类建议强化对应维度的 Prompt 指令
        - 优先处理回归维度

        Args:
            failure_patterns: 识别到的失败模式
            delta: 各维度差分

        Returns:
            迭代建议列表（按优先级降序）
        """
        suggestions: list[IterationSuggestion] = []

        # 优先处理回归维度
        for dim, diff in delta.items():
            if diff < 0:
                suggestions.append(IterationSuggestion(
                    target_dimension=dim,
                    direction=f"该维度出现回归（Δ={diff:.3f}），建议回退或针对性优化",
                    priority=1.0,
                    reasoning=f"新版本在 {dim} 上得分下降 {abs(diff):.3f}",
                    related_failures=[],
                ))

        # 按失败模式生成建议
        for pattern in sorted(failure_patterns, key=lambda p: p.count, reverse=True):
            if "format" in pattern.category:
                direction = "建议在 Prompt 中显式声明输出格式要求，并加入格式示例"
            elif "factual" in pattern.category or "correctness" in pattern.category:
                direction = "建议强化事实性约束，要求模型仅基于给定信息回答"
            elif "safety" in pattern.category:
                direction = "建议加入安全约束指令，明确禁止输出的内容类型"
            else:
                direction = f"建议强化 {pattern.category} 相关的 Prompt 指令"

            suggestions.append(IterationSuggestion(
                target_dimension=pattern.category,
                direction=direction,
                priority=min(0.9, pattern.count / 10.0),
                reasoning=f"发现 {pattern.count} 个 {pattern.category} 类失败",
                related_failures=pattern.sample_ids[:5],
            ))

        return sorted(suggestions, key=lambda s: s.priority, reverse=True)

    async def run_iteration(
        self,
        old_version_id: str,
        new_version_id: str,
        test_dataset: list[dict[str, Any]],
        dimensions: list[str] | None = None,
    ) -> IterationResult:
        """执行一次完整的评估驱动迭代闭环。

        流程：
        1. 加载两个版本的 Prompt
        2. 对两个版本分别执行评估
        3. 计算差分、检测回归
        4. 分类失败模式
        5. 生成迭代建议

        Args:
            old_version_id: 旧版本 Prompt ID
            new_version_id: 新版本 Prompt ID
            test_dataset: 测试数据集
            dimensions: 评估维度

        Returns:
            IterationResult
        """
        # TODO: 实现完整的双轨评估流程
        # 当前为框架实现，返回占位结果

        old_scores: dict[str, float] = {}
        new_scores: dict[str, float] = {}
        delta = self._compute_delta(old_scores, new_scores)

        regressions = self._detect_regressions(delta, new_scores)

        # 判断整体状态
        if not delta:
            status = IterationStatus.INCONCLUSIVE
        elif any(v < 0 for v in delta.values()) and not any(v > 0 for v in delta.values()):
            status = IterationStatus.REGRESSED
        elif any(v > 0 for v in delta.values()) and not regressions:
            status = IterationStatus.IMPROVED
        else:
            status = IterationStatus.STABLE

        # 更新历史最佳
        for dim, score in new_scores.items():
            if score > self._best_scores.get(dim, 0.0):
                self._best_scores[dim] = score

        return IterationResult(
            old_version_id=old_version_id,
            new_version_id=new_version_id,
            status=status,
            delta_scores=delta,
            regressions=regressions,
            failure_patterns=[],
            suggestions=[],
            is_significant=False,
            confidence=0.0,
        )