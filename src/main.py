"""FastAPI 应用入口：提供评估与迭代管理的 API 接口。"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from prompt_manager.version_manager import PromptVersionManager
from evaluation.judge import LLMJudge
from evaluation.metrics import RuleBasedMetrics
from iteration.loop import IterationLoop


# ---- 全局状态 ----

version_manager: PromptVersionManager | None = None
judge: LLMJudge | None = None
rule_metrics: RuleBasedMetrics | None = None
iteration_loop: IterationLoop | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理：启动时初始化各模块。"""
    global version_manager, judge, rule_metrics, iteration_loop

    version_manager = PromptVersionManager(prompts_dir="data/prompts")
    judge = LLMJudge(model_name="gpt-4o", temperature=0.1)
    rule_metrics = RuleBasedMetrics()
    iteration_loop = IterationLoop(
        version_manager=version_manager,
        judge=judge,
        rule_metrics=rule_metrics,
    )

    yield

    # 清理资源
    version_manager = None
    judge = None


app = FastAPI(
    title="LLM Eval & Iteration Platform",
    version="0.1.0",
    lifespan=lifespan,
)


# ---- 请求/响应模型 ----

class EvaluateRequest(BaseModel):
    """评估请求。"""
    prompt_id: str = Field(..., description="Prompt 版本 ID")
    dataset_path: str = Field(..., description="测试数据集路径")
    dimensions: list[str] = Field(
        default=["correctness", "relevance", "format_compliance"],
        description="评估维度列表",
    )


class CompareRequest(BaseModel):
    """版本对比请求。"""
    prompt_id_a: str = Field(..., description="版本 A 的 Prompt ID")
    prompt_id_b: str = Field(..., description="版本 B 的 Prompt ID")
    dataset_path: str = Field(..., description="共享测试数据集路径")


class IterationRequest(BaseModel):
    """迭代请求。"""
    prompt_id: str = Field(..., description="当前 Prompt 版本 ID")
    dataset_path: str = Field(..., description="测试数据集路径")
    regression_tolerance: float = Field(
        default=0.05, description="回归容忍度阈值"
    )


# ---- API 路由 ----

@app.post("/api/evaluate")
async def evaluate_prompt(req: EvaluateRequest) -> dict:
    """对指定 Prompt 版本执行评估。"""
    if not judge or not rule_metrics:
        raise HTTPException(status_code=503, detail="服务未初始化")
    # TODO: 实现完整评估流程
    return {"status": "started", "prompt_id": req.prompt_id}


@app.post("/api/compare")
async def compare_versions(req: CompareRequest) -> dict:
    """对两个 Prompt 版本进行 A/B 对比评估。"""
    if not iteration_loop:
        raise HTTPException(status_code=503, detail="服务未初始化")
    # TODO: 实现 A/B 对比流程
    return {"status": "started", "comparison_id": f"{req.prompt_id_a}_vs_{req.prompt_id_b}"}


@app.post("/api/iterate")
async def run_iteration(req: IterationRequest) -> dict:
    """执行评估驱动的迭代闭环。"""
    if not iteration_loop:
        raise HTTPException(status_code=503, detail="服务未初始化")
    # TODO: 实现迭代闭环流程
    return {"status": "started", "prompt_id": req.prompt_id}


@app.get("/api/prompts")
async def list_prompts() -> dict:
    """列出所有 Prompt 版本。"""
    if not version_manager:
        raise HTTPException(status_code=503, detail="服务未初始化")
    prompts = version_manager.list_versions()
    return {"prompts": prompts}


@app.get("/api/prompts/{prompt_id}")
async def get_prompt(prompt_id: str) -> dict:
    """获取指定 Prompt 版本的详情。"""
    if not version_manager:
        raise HTTPException(status_code=503, detail="服务未初始化")
    prompt = version_manager.get_version(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt 版本不存在")
    return {"prompt": prompt}


@app.get("/health")
async def health_check() -> dict:
    """健康检查。"""
    return {"status": "ok"}