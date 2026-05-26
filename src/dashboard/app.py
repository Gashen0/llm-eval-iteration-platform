"""Streamlit Dashboard：Prompt 版本管理 + 评估可视化 + 迭代闭环。"""

from typing import Any, Optional
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

# TODO: 接入实际模块
# from prompt_manager.version_manager import PromptVersionManager
# from evaluation.judge import LLMJudge
# from iteration.loop import IterationLoop


def render_sidebar() -> dict[str, Any]:
    """渲染侧边栏：全局配置与导航。

    Returns:
        侧边栏配置字典
    """
    st.sidebar.title("🔧 配置")

    config = {
        "page": st.sidebar.radio(
            "导航",
            ["📋 Prompt 版本", "📊 评估结果", "🔄 迭代闭环", "🔬 A/B 对比"],
        ),
        "llm_provider": st.sidebar.selectbox(
            "LLM 提供商",
            ["openai", "deepseek", "anthropic", "zhipu"],
        ),
        "judge_model": st.sidebar.text_input(
            "Judge 模型",
            value="gpt-4o",
        ),
    }

    return config


def render_prompt_versions() -> None:
    """渲染 Prompt 版本管理页面。

    展示内容：
    - 所有 Prompt 的版本列表
    - 单个 Prompt 的内容预览与变量插槽
    - 版本间的 diff 对比
    - 新建版本入口
    """
    st.header("📋 Prompt 版本管理")

    # TODO: 接入 version_manager.list_versions()
    st.info("Prompt 版本列表加载中...")

    # 占位：版本列表
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("版本列表")
        # TODO: 渲染版本树
        st.code("sql_generator_v1.0.0\nsql_generator_v1.1.0\nsql_generator_v1.2.0")

    with col2:
        st.subheader("版本详情")
        # TODO: 渲染选中版本的内容
        st.text_area("Prompt 内容", value="选择左侧版本查看", height=300, disabled=True)


def render_evaluation_results() -> None:
    """渲染评估结果页面。

    展示内容：
    - 各维度的评估得分雷达图
    - 历史评估趋势折线图
    - 失败样本列表与归因
    """
    st.header("📊 评估结果")

    tab1, tab2, tab3 = st.tabs(["雷达图", "趋势", "失败分析"])

    with tab1:
        st.subheader("维度评分雷达图")
        # TODO: 使用 Plotly 渲染雷达图
        # 占位数据
        dimensions = ["correctness", "relevance", "format_compliance", "safety", "conciseness"]
        fig = go.Figure(data=go.Scatterpolar(
            r=[0.8, 0.7, 0.9, 0.95, 0.6],
            theta=dimensions,
            fill="toself",
            name="v1.2.0",
        ))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])))
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("评估得分趋势")
        # TODO: 渲染历史评估趋势折线图
        st.info("趋势图加载中...")

    with tab3:
        st.subheader("失败样本归因")
        # TODO: 渲染失败样本的分类热力图
        st.info("失败分析加载中...")


def render_iteration_loop() -> None:
    """渲染迭代闭环页面。

    展示内容：
    - 迭代状态（改善/回归/稳定）
    - 各维度的差分柱状图
    - 自动生成的迭代建议
    - 一键提交新版本
    """
    st.header("🔄 评估驱动迭代")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("迭代状态")
        # TODO: 从 iteration_loop 获取最新状态
        status = st.selectbox("当前状态", ["improved", "regressed", "stable", "inconclusive"])

        if status == "regressed":
            st.error("⚠️ 检测到回归，建议回退或针对性优化")
        elif status == "improved":
            st.success("✅ 新版本优于旧版本")
        elif status == "stable":
            st.info("➡️ 无显著变化")
        else:
            st.warning("❓ 数据不足，无法判断")

    with col2:
        st.subheader("迭代建议")
        # TODO: 从 iteration_loop 获取建议列表
        st.markdown("1. **format_compliance**: 建议在 Prompt 中显式声明输出格式")
        st.markdown("2. **correctness**: 建议强化事实性约束指令")


def render_ab_comparison() -> None:
    """渲染 A/B 对比页面。

    展示内容：
    - 选择两个版本进行对比
    - 对比结果柱状图（含置信区间）
    - 统计显著性检验结果
    - 逐样本对比明细
    """
    st.header("🔬 A/B 版本对比")

    col1, col2 = st.columns(2)
    with col1:
        version_a = st.text_input("版本 A", value="sql_generator_v1.0.0")
    with col2:
        version_b = st.text_input("版本 B", value="sql_generator_v1.1.0")

    if st.button("开始对比"):
        # TODO: 调用 iteration_loop 的双轨评估
        st.info("A/B 对比评估启动中...")

        # 占位：对比结果
        st.subheader("对比结果")
        comparison_data = pd.DataFrame({
            "维度": ["correctness", "relevance", "format_compliance"],
            "版本 A": [0.72, 0.68, 0.90],
            "版本 B": [0.78, 0.71, 0.85],
        })
        st.dataframe(comparison_data, use_container_width=True)

        # 占位：统计显著性
        st.markdown("**统计显著性**: p = 0.03 (< 0.05)，差异显著")


def main() -> None:
    """Dashboard 主入口。"""
    st.set_page_config(
        page_title="LLM Eval & Iteration Platform",
        page_icon="🧪",
        layout="wide",
    )

    st.title("🧪 LLM Evaluation & Iteration Platform")
    st.caption("Prompt 版本管理 · 自动化评估 · 迭代闭环")

    config = render_sidebar()

    # 根据导航选择渲染页面
    page_renderers = {
        "📋 Prompt 版本": render_prompt_versions,
        "📊 评估结果": render_evaluation_results,
        "🔄 迭代闭环": render_iteration_loop,
        "🔬 A/B 对比": render_ab_comparison,
    }

    renderer = page_renderers.get(config["page"])
    if renderer:
        renderer()


if __name__ == "__main__":
    main()