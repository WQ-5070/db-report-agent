"""db-report-agent 看板：消费核心包 pipeline（轻路径 + 可选 LLM 重量路径）。

运行:
    pip install -e .
    python demos/seed/generate_sample_data.py
    streamlit run demos/streamlit_app.py

输入问题 → build_pipeline() 真实管线（语义资产 → 护栏 → 执行 → 图表 → 洞察）；
勾选"LLM 重量路径"且 .env 配置了 key 时，未命中语义层的问题由 LLM 生成 SQL。
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from dbreport.core.errors import AgentError
from dbreport.core.llm import OpenAICompatibleClient
from dbreport.core.pipeline import UnmatchedQuestion
from dbreport.serve import build_pipeline

DB_PATH = os.path.join(os.path.dirname(__file__), "db-report-agent.db")


def make_chart(spec: dict):
    """按核心包 chart spec（type/x/y/data）绘制图表。"""
    df = pd.DataFrame(spec["data"])
    kind, title, x, y = spec["type"], spec["title"], spec["x"], spec["y"]
    if kind == "pie":
        return px.pie(df, names=x, values=y, title=title, hole=0.4)
    if kind == "bar":
        return px.bar(df, x=x, y=y, title=title, text_auto=True)
    return px.line(df, x=x, y=y, title=title, markers=True)


def main() -> None:
    st.set_page_config(page_title="db-report-agent", layout="wide")
    st.title("📊 db-report-agent · 数据问答 Agent")
    st.caption("消费核心包 pipeline：语义资产 → 护栏 → 执行 → 图表 → 洞察（可选 LLM 重量路径）")

    if not os.path.exists(DB_PATH):
        st.error("未找到样例库。请先运行: python demos/seed/generate_sample_data.py")
        return

    with st.sidebar:
        st.header("设置")
        use_llm = st.checkbox("启用 LLM 重量路径（需 .env 配 key）", value=False)
        presets = ["各地区订单量占比？", "最近 12 个月每月的销售额是多少？",
                   "各品类销售额对比", "各城市活跃用户数", "统计一下订单总数"]
        choice = st.selectbox("预置问题", presets)
        free = st.text_input("或输入问题", "")
        st.divider()
        st.caption("LLM 未启用时：语义层命中走轻路径；未命中提示需勾选 LLM。")

    question = free.strip() or choice

    llm = None
    if use_llm:
        try:
            llm = OpenAICompatibleClient()
        except AgentError as exc:
            st.error(f"LLM 不可用（{exc.code}）：{exc}")

    pipeline = build_pipeline(DB_PATH)
    try:
        report = pipeline.ask(question, llm=llm)
    except UnmatchedQuestion as exc:
        st.warning(f"{exc.code}: {exc}")
        st.code(question, language="text")
        return

    st.subheader("① 问题 → SQL")
    if report.sql:
        st.code(report.sql, language="sql")
    path = "LLM 重量路径" if report.metric_id == "llm_generated" else "轻路径"
    st.caption(f"trace_id: `{report.trace_id}` · 路径: {path}")

    if report.result is None:
        st.error(report.report_md)
        return

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("② 自动图表")
        if report.chart:
            st.plotly_chart(make_chart(report.chart), width="stretch")
    with col2:
        st.subheader("③ 数据预览")
        st.dataframe(pd.DataFrame(report.result.as_dicts()).head(12),
                     width="stretch")

    st.subheader("④ 报告")
    st.markdown(report.report_md)


if __name__ == "__main__":
    main()
