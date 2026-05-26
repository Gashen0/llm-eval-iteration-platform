"""LLM-as-Judge 评估模块：调用更强 LLM 对输出进行结构化评分。"""

from typing import Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import json
import time

# TODO: 接入实际 LLM SDK
# from langchain_openai import ChatOpenAI


@dataclass
class JudgeScore:
    """单维度的 Judge 评分结果。"""
    dimension: str
    score: float  # 0.0 ~ 1.0
    reasoning: str  # LLM 给出的评分理由
    confidence: float = 1.0  # 评判置信度


@dataclass
class JudgeResult:
    """一次 LLM-as-Judge 评估的完整结果。"""
    sample_id: str
    scores: list[JudgeScore]
    judge_model: str
    judge_prompt_hash: str  # 评判 Prompt 的哈希，用于可复现性
    raw_response: str  # LLM 原始输出
    latency_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


class LLMJudge:
    """LLM-as-Judge 评估器。

    核心设计思路：
    - 评判 Prompt 模板化，支持用户自定义评估维度
    - 输出强制为 JSON 格式，解析失败时标记为低置信度
    - 支持多次采样取均值，降低 LLM 评分的非确定性
    """

    def __init__(
        self,
        model_name: str = "gpt-4o",
        temperature: float = 0.1,
        num_samples: int = 1,
    ) -> None:
        """初始化 Judge。

        Args:
            model_name: 评判用的 LLM 模型名称
            temperature: 评判温度，建议低温度（0.0~0.2）以保证一致性
            num_samples: 对同一样本重复评判的次数，取均值提升稳定性
        """
        self.model_name = model_name
        self.temperature = temperature
        self.num_samples = num_samples
        # TODO: 初始化 LLM 客户端
        # self._llm = ChatOpenAI(model=model_name, temperature=temperature)

    def _build_judge_prompt(
        self,
        question: str,
        answer: str,
        reference: Optional[str],
        dimensions: list[str],
    ) -> str:
        """构造评判 Prompt。

        设计要点：
        - 明确告知 Judge 其角色是客观评判者，不是对话伙伴
        - 要求输出严格的 JSON 格式，包含各维度分数和理由
        - 对每个维度给出明确的评分标准（1-5 分制映射到 0.0-1.0）
        - 引入 reference answer 作为锚点，减少评分漂移

        Args:
            question: 原始问题
            answer: 被评估的输出
            reference: 参考答案（可选）
            dimensions: 评估维度列表

        Returns:
            构造好的评判 Prompt 文本
        """
        dimensions_str = ", ".join(dimensions)
        reference_section = ""
        if reference:
            reference_section = f"\n\nReference Answer:\n{reference}"

        # TODO: 补充完整的评判 Prompt 模板
        prompt = f"""You are an objective evaluator. Assess the following answer.

Question: {question}
Answer: {answer}{reference_section}

Evaluate on these dimensions: {dimensions_str}

Respond ONLY with valid JSON:
{{
    "scores": {{
        "dimension_name": {{
            "score": <1-5>,
            "reasoning": "<brief explanation>"
        }}
    }}
}}"""
        return prompt

    def _parse_judge_response(self, raw: str) -> list[JudgeScore]:
        """解析 LLM 返回的 JSON 评分。

        解析策略：
        - 优先尝试 json.loads 解析完整 JSON
        - 如果失败，尝试提取 ```json ... ``` 代码块
        - 仍然失败则标记为低置信度，返回默认分数 0.0

        Args:
            raw: LLM 原始输出文本

        Returns:
            解析后的 JudgeScore 列表
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            import re
            match = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    return [JudgeScore(dimension="unknown", score=0.0, reasoning="Parse failed", confidence=0.0)]
            else:
                return [JudgeScore(dimension="unknown", score=0.0, reasoning="Parse failed", confidence=0.0)]

        scores: list[JudgeScore] = []
        for dim, val in data.get("scores", {}).items():
            raw_score = val.get("score", 0)
            # 将 1-5 分制映射到 0.0-1.0
            normalized = max(0.0, min(1.0, (raw_score - 1) / 4.0))
            scores.append(JudgeScore(
                dimension=dim,
                score=normalized,
                reasoning=val.get("reasoning", ""),
                confidence=1.0,
            ))
        return scores

    async def evaluate_single(
        self,
        sample_id: str,
        question: str,
        answer: str,
        reference: Optional[str] = None,
        dimensions: list[str] | None = None,
    ) -> JudgeResult:
        """对单个样本执行 LLM-as-Judge 评估。

        Args:
            sample_id: 样本唯一标识
            question: 原始问题
            answer: 被评估的输出
            reference: 参考答案
            dimensions: 评估维度

        Returns:
            完整的 JudgeResult
        """
        if dimensions is None:
            dimensions = ["correctness", "relevance"]

        prompt = self._build_judge_prompt(question, answer, reference, dimensions)
        start_time = time.time()

        # TODO: 实际调用 LLM
        # response = await self._llm.ainvoke(prompt)
        # raw_response = response.content
        raw_response = '{"scores": {"correctness": {"score": 3, "reasoning": "placeholder"}}}'
        latency_ms = (time.time() - start_time) * 1000

        scores = self._parse_judge_response(raw_response)

        return JudgeResult(
            sample_id=sample_id,
            scores=scores,
            judge_model=self.model_name,
            judge_prompt_hash=hash(prompt) & 0xFFFFFFFF,
            raw_response=raw_response,
            latency_ms=latency_ms,
        )

    async def evaluate_batch(
        self,
        samples: list[dict[str, Any]],
        dimensions: list[str] | None = None,
    ) -> list[JudgeResult]:
        """批量评估多个样本。

        Args:
            samples: 样本列表，每个样本包含 id, question, answer, reference(可选)
            dimensions: 评估维度

        Returns:
            JudgeResult 列表
        """
        results: list[JudgeResult] = []
        for sample in samples:
            result = await self.evaluate_single(
                sample_id=sample["id"],
                question=sample["question"],
                answer=sample["answer"],
                reference=sample.get("reference"),
                dimensions=dimensions,
            )
            results.append(result)
        return results