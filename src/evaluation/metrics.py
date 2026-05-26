"""规则-based 评估指标：确定性、低成本、零 LLM 调用。"""

from typing import Any, Optional
from dataclasses import dataclass
import json
import re
import math


@dataclass
class MetricResult:
    """单次规则指标的计算结果。"""
    metric_name: str
    value: float  # 0.0 ~ 1.0
    detail: str  # 可读的结果描述
    is_binary: bool = False  # 是否为二值指标（通过/不通过）


class RuleBasedMetrics:
    """规则-based 指标计算引擎。

    设计原则：
    - 所有指标 100% 确定性，相同输入必定相同输出
    - 零 LLM 调用，执行速度极快（毫秒级）
    - 适用于格式校验、长度约束、结构合规等硬性指标
    - 不适用于语义质量评估（如准确性、流畅度）

    扩展方式：
    - 子类化 RuleBasedMetrics 并添加新的 check_* 方法
    - 或直接向 _custom_checks 注册新的检查函数
    """

    def __init__(self) -> None:
        """初始化规则引擎。"""
        self._custom_checks: dict[str, Any] = {}

    def register_check(self, name: str, fn: Any) -> None:
        """注册自定义规则检查函数。

        Args:
            name: 指标名称
            fn: 检查函数，签名为 (answer: str, reference: Optional[str]) -> MetricResult
        """
        self._custom_checks[name] = fn

    def check_json_validity(self, answer: str, reference: Optional[str] = None) -> MetricResult:
        """检查输出是否为合法 JSON。

        实现逻辑：
        - 直接调用 json.loads 尝试解析
        - 解析失败时提取错误位置信息

        Args:
            answer: 待检查的输出文本
            reference: 未使用（保持接口一致性）

        Returns:
            MetricResult，通过为 1.0，不通过为 0.0
        """
        try:
            json.loads(answer.strip())
            return MetricResult(
                metric_name="json_validity",
                value=1.0,
                detail="JSON 格式合法",
                is_binary=True,
            )
        except json.JSONDecodeError as e:
            return MetricResult(
                metric_name="json_validity",
                value=0.0,
                detail=f"JSON 解析失败: {str(e)[:100]}",
                is_binary=True,
            )

    def check_format_compliance(
        self,
        answer: str,
        reference: Optional[str] = None,
        required_pattern: str = r".*",
    ) -> MetricResult:
        """检查输出是否匹配指定格式（正则表达式）。

        用途：验证 LLM 输出是否符合预设的模板格式，
        例如 "Answer: YES/NO" 或包含特定标记的输出。

        Args:
            answer: 待检查的输出文本
            reference: 未使用
            required_pattern: 要求的正则表达式模式

        Returns:
            MetricResult
        """
        if re.match(required_pattern, answer.strip(), re.DOTALL):
            return MetricResult(
                metric_name="format_compliance",
                value=1.0,
                detail="格式合规",
                is_binary=True,
            )
        return MetricResult(
            metric_name="format_compliance",
            value=0.0,
            detail=f"输出不匹配模式: {required_pattern[:50]}",
            is_binary=True,
        )

    def check_length_constraint(
        self,
        answer: str,
        reference: Optional[str] = None,
        min_length: int = 10,
        max_length: int = 5000,
    ) -> MetricResult:
        """检查输出长度是否在合理范围内。

        过短的输出通常意味着信息不足（如仅返回"是"），
        过长的输出可能导致下游处理成本过高。

        Args:
            answer: 待检查的输出文本
            reference: 未使用
            min_length: 最小字符数
            max_length: 最大字符数

        Returns:
            MetricResult，值为 0.0-1.0 的连续值
        """
        length = len(answer.strip())
        if length < min_length:
            ratio = length / min_length
            return MetricResult(
                metric_name="length_constraint",
                value=ratio,
                detail=f"输出过短: {length} < {min_length} 字符",
            )
        if length > max_length:
            ratio = max_length / length
            return MetricResult(
                metric_name="length_constraint",
                value=ratio,
                detail=f"输出过长: {length} > {max_length} 字符",
            )
        return MetricResult(
            metric_name="length_constraint",
            value=1.0,
            detail=f"长度合规: {length} 字符",
        )

    def check_exact_match(
        self,
        answer: str,
        reference: Optional[str] = None,
    ) -> MetricResult:
        """检查输出是否与参考答案完全匹配。

        适用场景：分类任务、选择题等有唯一正确答案的任务。

        Args:
            answer: 待检查的输出文本
            reference: 参考答案

        Returns:
            MetricResult
        """
        if reference is None:
            return MetricResult(
                metric_name="exact_match",
                value=0.0,
                detail="缺少参考答案，无法评估",
            )
        match = answer.strip().lower() == reference.strip().lower()
        return MetricResult(
            metric_name="exact_match",
            value=1.0 if match else 0.0,
            detail="完全匹配" if match else "与参考答案不一致",
            is_binary=True,
        )

    def check_contains_keywords(
        self,
        answer: str,
        reference: Optional[str] = None,
        required_keywords: list[str] | None = None,
    ) -> MetricResult:
        """检查输出是否包含必需的关键词。

        适用场景：验证 LLM 输出是否覆盖了回答中的关键实体或概念。

        Args:
            answer: 待检查的输出文本
            reference: 未使用
            required_keywords: 必需包含的关键词列表

        Returns:
            MetricResult，值为包含比例（0.0-1.0）
        """
        if not required_keywords:
            return MetricResult(
                metric_name="keyword_coverage",
                value=1.0,
                detail="未指定关键词，跳过检查",
            )

        found = sum(1 for kw in required_keywords if kw.lower() in answer.lower())
        ratio = found / len(required_keywords)
        missing = [kw for kw in required_keywords if kw.lower() not in answer.lower()]

        return MetricResult(
            metric_name="keyword_coverage",
            value=ratio,
            detail=f"覆盖率: {found}/{len(required_keywords)}, 缺失: {missing[:5]}",
        )

    def run_all_checks(
        self,
        answer: str,
        reference: Optional[str] = None,
        enabled_metrics: list[str] | None = None,
    ) -> list[MetricResult]:
        """执行所有已启用的规则检查。

        Args:
            answer: 待评估的输出
            reference: 参考答案（可选）
            enabled_metrics: 启用的指标列表，None 表示全部

        Returns:
            MetricResult 列表
        """
        builtin_checks = {
            "json_validity": self.check_json_validity,
            "format_compliance": self.check_format_compliance,
            "length_constraint": self.check_length_constraint,
            "exact_match": self.check_exact_match,
            "keyword_coverage": self.check_contains_keywords,
        }

        all_checks = {**builtin_checks, **self._custom_checks}
        results: list[MetricResult] = []

        for name, fn in all_checks.items():
            if enabled_metrics and name not in enabled_metrics:
                continue
            try:
                result = fn(answer, reference)
                results.append(result)
            except Exception as e:
                results.append(MetricResult(
                    metric_name=name,
                    value=0.0,
                    detail=f"检查执行异常: {str(e)[:80]}",
                ))

        return results