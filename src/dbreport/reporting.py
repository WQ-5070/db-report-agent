"""呈现层：声明式图表 spec + Markdown 报告组装。

对应 docs/DESIGN.md 第 8.6-8.8 节。图表输出为声明式 spec（数据 + 类型），
与渲染后端解耦（Streamlit/Plotly/Vega 均可消费）；报告含血缘与审计信息。
洞察可来自语义层预置文案，也可由 LLM 生成（重量路径）。
"""
from __future__ import annotations

from .executor import QueryResult
from .semantic import Metric

_TABLE_ROWS = 20  # 报告内嵌数据表的最大行数
INSIGHT_ROWS = 8  # 传给 LLM 生成洞察的结果行数上限


def chart_spec(metric: Metric, result: QueryResult) -> dict:
    """生成 plotly 风格图表规范：类型 + 轴 + 数据。"""
    return {
        "type": metric.chart,
        "title": metric.title,
        "x": metric.x,
        "y": metric.y,
        "data": result.as_dicts(),
    }


def infer_chart(result: QueryResult) -> dict:
    """按结果形态自动选图：含时间列 → 折线，否则类别+数值 → 柱状。"""
    columns = result.columns

    def is_time(name: str) -> bool:
        lowered = name.lower()
        return any(k in lowered for k in ("date", "time", "month", "day", "年", "月"))

    time_col = next((c for c in columns if is_time(c)), None)
    if time_col is not None:
        y = next((c for c in columns if c != time_col), columns[-1])
        return {"type": "line", "title": "查询结果", "x": time_col, "y": y,
                "data": result.as_dicts()}
    return {"type": "bar", "title": "查询结果", "x": columns[0], "y": columns[-1],
            "data": result.as_dicts()}


def _markdown_table(result: QueryResult) -> str:
    rows = result.rows[:_TABLE_ROWS]
    header = "| " + " | ".join(result.columns) + " |"
    sep = "|" + "|".join([" --- "] * len(result.columns)) + "|"
    body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in rows)
    return "\n".join([header, sep, body])


def build_report(question: str, metric: Metric, executed_sql: str,
                 result: QueryResult, trace_id: str,
                 validation_message: str = "校验通过",
                 insight: str | None = None,
                 insight_source: str = "predefined") -> str:
    """组装 Markdown 报告：结论、依据 SQL、数据、血缘/审计。"""
    insight = metric.insight if insight is None else insight
    lines = [
        f"# {metric.title}",
        "",
        f"- **问题**：{question}",
        f"- **匹配指标**：`{metric.id}`",
        f"- **执行 SQL**（护栏：{validation_message}）：",
        "```sql",
        executed_sql,
        "```",
        f"- **结果**：{result.row_count} 行，耗时 {result.elapsed_ms} ms",
        "",
        _markdown_table(result),
        "",
        "## 洞察",
        "",
        insight,
        "",
        "## 血缘 / 审计",
        "",
        f"- **trace_id**：`{trace_id}`",
        f"- **洞察来源**：`{insight_source}`（predefined=语义层预置 / llm=模型生成）",
        f"- **指标口径**：`{metric.id}` → 表/列来自样例库 schema",
        f"- **可复现**：同问题同参数重放返回同一结果（结果缓存 + 只读）",
    ]
    return "\n".join(lines)
