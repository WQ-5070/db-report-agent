"""db-report-agent 最小可运行演示（交互式看板）。

一个可离线跑通的最小骨架，用来证明架构可行。它包含 DESIGN.md 里提到的
"轻路径"关键环节：自然语言 -> 语义层匹配 -> SQL -> 图表 -> 结论。

注意：
- 这里的 NL2SQL 是【规则映射 + 语义匹配】的占位实现，不依赖 LLM。
  真正接入 LLM 后，替换 `semantic_match()` 即可升级为完整 NL2SQL（见 docs/DESIGN.md 第 8.3 节）。
- SQL 执行经过最小安全校验（只读 SELECT + LIMIT），演示护栏概念。

运行:
    pip install streamlit pandas plotly
    python demos/seed/generate_sample_data.py
    streamlit run demos/streamlit_app.py
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "db-report-agent.db")

# --------------------------------------------------------------------------
# 语义层（指标/维度 Registry）—— 对齐 DESIGN.md 第 9 节。
# 一个指标 = 口径(SQL模板) + 建议图表 + 关键词别名。
# --------------------------------------------------------------------------
METRICS: dict[str, dict] = {
    "monthly_sales": {
        "keyword": ["销售额", "sales", "营收", "gmv"],
        "sql": "SELECT strftime('%Y-%m', order_date) AS month, ROUND(SUM(amount),2) AS sales "
               "FROM orders GROUP BY month ORDER BY month",
        "chart": "line",
        "title": "月度销售额",
        "x": "month",
        "y": "sales",
        "insight": "近 24 个月销售额整体呈上升趋势，年底(11-12月)为旺季峰值；"
                   "约在 2024-04 出现一次明显回落，需关注该月异常原因。",
    },
    "region_orders": {
        "keyword": ["地区", "region", "区域", "占比", "订单量"],
        "sql": "SELECT r.region_name AS region, COUNT(o.order_id) AS orders "
               "FROM orders o JOIN regions r ON o.region_id = r.region_id "
               "GROUP BY region ORDER BY orders DESC",
        "chart": "pie",
        "title": "各地区订单量占比",
        "x": "region",
        "y": "orders",
        "insight": "订单量集中在华北、华东、华南等人口密集区域，三者合计占比超七成；"
                   "西南、西北相对较低，可评估渠道投放或市场覆盖率。",
    },
    "category_sales": {
        "keyword": ["品类", "产品", "category", "类别", "销售额"],
        "sql": "SELECT product_category AS category, ROUND(SUM(amount),2) AS sales "
               "FROM orders GROUP BY category ORDER BY sales DESC",
        "chart": "bar",
        "title": "各品类销售额",
        "x": "category",
        "y": "sales",
        "insight": "数码与家电品类贡献销售主体；美妆、服饰次之；"
                   "食品虽订单量较大但客单价较低，销售额靠后，可结合毛利率评估品类结构。",
    },
    "active_users": {
        "keyword": ["用户", "活跃", "user", "retention"],
        "sql": "SELECT city, COUNT(*) AS active_users FROM users "
               "WHERE is_active = 1 GROUP BY city ORDER BY active_users DESC",
        "chart": "bar",
        "title": "各城市活跃用户数",
        "x": "city",
        "y": "active_users",
        "insight": "活跃用户集中于人口密集城市，与订单分布基本一致；"
                   "可结合各城市人口与市场投放评估获客效率。",
    },
}


def semantic_match(question: str) -> dict | None:
    """最小 NL2SQL：关键词路由到语义层指标。

    生产版此处接入 LLM + schema 感知 + 校验器（见 DESIGN.md 第 8.3/8.4 节）。
    """
    q = question.lower()
    best, best_hits = None, 0
    for metric, meta in METRICS.items():
        hits = sum(1 for kw in meta["keyword"] if kw in q)
        if hits > best_hits:
            best, best_hits = metric, hits
    if best:
        return METRICS[best]
    return None


# --------------------------------------------------------------------------
# 执行层（强只读 + LIMIT 护栏概念）
# --------------------------------------------------------------------------
def run_safe(sql: str) -> pd.DataFrame:
    """最小安全执行：仅允许只读 SELECT/CTE，并强制 LIMIT。"""
    sql = sql.strip()
    if not re.match(r"^(select|with)\b", sql, re.IGNORECASE):
        raise ValueError("Demo 护栏：仅允许 SELECT/WITH 只读查询")
    if "limit" not in sql.lower():
        sql += " LIMIT 10000"
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(sql, conn)


# --------------------------------------------------------------------------
# 可视化层 + 报告生成
# --------------------------------------------------------------------------
def make_chart(metric: dict, df: pd.DataFrame):
    kind = metric["chart"]
    x, y = metric["x"], metric["y"]
    if kind == "pie":
        return px.pie(df, names=x, values=y, title=metric["title"], hole=0.4)
    if kind == "bar":
        return px.bar(df, x=x, y=y, title=metric["title"], text_auto=True)
    return px.line(df, x=x, y=y, title=metric["title"], markers=True)


def main() -> None:
    st.set_page_config(page_title="db-report-agent 演示", layout="wide")
    st.title("📊 db-report-agent · 数据问答 Agent 演示")
    st.caption("自然语言 → 语义层匹配 → SQL → 图表 → 结论（最小演示骨架）")

    if not os.path.exists(DB_PATH):
        st.error(f"未找到样例库 {DB_PATH}。请先运行: python demos/seed/generate_sample_data.py")
        return

    # 预设问题（覆盖代表性场景）
    presets = [
        "最近 12 个月每月的销售额是多少？",
        "各地区订单量占比？",
        "各品类销售额对比",
        "各城市活跃用户数",
        "2024-04 的销售额为什么下降？",
    ]
    with st.sidebar:
        st.header("演示问题")
        choice = st.selectbox("选择一个预置问题（或直接输入）", presets)
        free = st.text_input("或输入你的问题", "")
        st.divider()
        st.caption("⭐ 生产版会接入 LLM、schema 感知、护栏与评测，见 docs/DESIGN.md。")

    question = free.strip() if free.strip() else choice

    metric = semantic_match(question)
    if metric is None:
        st.warning("未能匹配到语义层指标（演示未接入 LLM）。请换一个预置问题。")
        st.code(question, language="text")
        return

    try:
        df = run_safe(metric["sql"])
    except Exception as e:  # noqa: BLE001 - 演示统一展示错误
        st.error(f"SQL 执行失败（Demo 护栏拦截或查询异常）: {e}")
        st.code(metric["sql"], language="sql")
        return

    st.subheader("① 生成的自然语言 → SQL")
    st.code(metric["sql"], language="sql")
    st.caption("（Demo 用语义层预置口径；生产版由 LLM 动态生成并经过校验器与护栏）")

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("② 自动生成的图表")
        st.plotly_chart(make_chart(metric, df), width="stretch")
    with col2:
        st.subheader("③ 数据预览")
        st.dataframe(df.head(12), width="stretch")

    st.subheader("④ 自然语言洞察")
    st.info(metric["insight"])

    with st.expander("🔎 审计 / 血缘（概念）"):
        st.write("在生成报告后，记录本次请求的血缘与审计信息（生产版用于审计与回放）：")
        st.json({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "question": question,
            "metric": [k for k, v in METRICS.items() if v is metric][0],
            "sql": metric["sql"],
            "rows": len(df),
            "trace_id": "demo-trace-0001",
        })

    st.caption("演示结束。生产版完整能力（语义层、护栏、评测、tracing、HITL）见 docs/DESIGN.md。")


if __name__ == "__main__":
    main()
