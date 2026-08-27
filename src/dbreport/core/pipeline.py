"""编排层：轻/重双路径管线。

对应 docs/DESIGN.md 第 7 节：
- 轻路径：问题命中语义层指标 → 预置口径 SQL → 护栏 → 执行 → 报告；
- 重量路径：未命中时由 LLM 生成 SQL（schema 感知）→ 护栏校验（失败带反馈重试）
  → 执行 → LLM 生成洞察 → 报告。重量路径需要传入 LLMClient。
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass

from .executor import QueryExecutor, QueryResult
from .guardrails import SqlGuardrails, ValidationResult
from .llm import LLMClient
from .log import log
from .reporting import INSIGHT_ROWS, build_report, chart_spec, infer_chart
from .semantic import Metric, SemanticRegistry


class UnmatchedQuestion(Exception):
    """未匹配到任何语义层指标，且未提供 LLM 走重量路径（SEMANTIC_NOT_FOUND）。"""


@dataclass(frozen=True)
class Report:
    question: str
    metric_id: str | None
    sql: str | None
    validation: ValidationResult | None
    result: QueryResult | None
    chart: dict | None
    report_md: str
    trace_id: str


_SQL_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.S)


def _extract_sql(text: str) -> str:
    """从模型输出中提取 SQL：优先取 ```sql 围栏，否则取首个完整语句。"""
    fenced = _SQL_FENCE.search(text)
    if fenced:
        text = fenced.group(1)
    lines = [ln for ln in text.strip().splitlines()
             if ln.strip() and not ln.strip().startswith("--")]
    return "\n".join(lines).strip()


class ReportPipeline:
    def __init__(self, registry: SemanticRegistry,
                 guardrails: SqlGuardrails,
                 executor: QueryExecutor,
                 memory=None,
                 max_sql_retries: int = 3):
        self._registry = registry
        self._guardrails = guardrails
        self._executor = executor
        self._memory = memory
        self._max_sql_retries = max_sql_retries

    def ask(self, question: str, llm: LLMClient | None = None) -> Report:
        trace_id = uuid.uuid4().hex[:8]
        log("收到问题", trace=trace_id, question=question)
        metric = self._registry.match(question)
        if metric is not None:
            return self._light(question, metric, trace_id)
        if llm is None:
            log("未匹配语义层且无 LLM", level="WARN", trace=trace_id)
            raise UnmatchedQuestion(
                f"未匹配到语义层指标（SEMANTIC_NOT_FOUND）: {question!r}；"
                "如需动态生成 SQL，请启用 --llm")
        return self._heavy(question, llm, trace_id)

    def _light(self, question: str, metric: Metric, trace_id: str) -> Report:
        log("轻路径命中", trace=trace_id, metric=metric.id)
        validation = self._guardrails.validate(metric.sql)
        if not validation.ok:
            log("护栏拦截", level="WARN", trace=trace_id,
                reason=validation.message)
            return Report(question, metric.id, metric.sql, validation, None, None,
                          f"SQL 被护栏拦截：{validation.message}", trace_id)
        log("护栏通过", trace=trace_id)
        result = self._executor.run(validation.safe_sql)
        log("执行完成", trace=trace_id, rows=result.row_count,
            elapsed_ms=round(result.elapsed_ms, 2))
        report_md = build_report(question, metric, validation.safe_sql,
                                 result, trace_id, validation.message)
        return Report(question, metric.id, validation.safe_sql, validation,
                      result, chart_spec(metric, result), report_md, trace_id)

    def _heavy(self, question: str, llm: LLMClient, trace_id: str) -> Report:
        sql, validation = self._generate_valid_sql(question, llm, trace_id)
        if validation is None:
            log("LLM 未产出可用 SQL", level="ERROR", trace=trace_id)
            return Report(question, None, sql, None, None, None,
                          "SQL 生成失败：LLM 未产出可用 SQL", trace_id)
        if not validation.ok:
            log("护栏拦截", level="WARN", trace=trace_id,
                reason=validation.message)
            return Report(question, None, sql, validation, None, None,
                          f"SQL 生成被护栏拦截：{validation.message}", trace_id)

        result = self._executor.run(validation.safe_sql)
        log("执行完成", trace=trace_id, rows=result.row_count,
            elapsed_ms=round(result.elapsed_ms, 2))
        chart = infer_chart(result)
        insight = self._generate_insight(question, llm, result)
        self._remember(question, validation.safe_sql, result)
        metric = Metric(id="llm_generated", aliases=(), sql=validation.safe_sql,
                        title=question, chart=chart["type"],
                        x=chart["x"], y=chart["y"], insight="")
        report_md = build_report(question, metric, validation.safe_sql, result,
                                 trace_id, validation.message,
                                 insight=insight, insight_source="llm")
        return Report(question, None, validation.safe_sql, validation,
                      result, chart, report_md, trace_id)

    def _remember(self, question: str, sql: str, result: QueryResult) -> None:
        """自学习闭环：重量路径执行成功且返回数据 → 沉淀问题-SQL 样本。"""
        if self._memory is not None and result.row_count > 0:
            self._memory.train(question, sql)

    def _generate_valid_sql(self, question: str, llm: LLMClient,
                            trace_id: str) -> tuple[str | None, ValidationResult | None]:
        """生成 SQL 并过护栏；失败时把护栏原因反馈给 LLM 重试。"""
        schema_text = self._schema_text()
        examples = self._memory.similar(question) if self._memory else []
        if examples:
            log("记忆命中 few-shot", trace=trace_id, samples=len(examples))
        last_validation: ValidationResult | None = None
        for attempt in range(1, self._max_sql_retries + 1):
            feedback = last_validation.message if last_validation else None
            raw = llm.complete(
                self._sql_prompt(question, schema_text, feedback, examples))
            sql = _extract_sql(raw)
            if not sql:
                last_validation = ValidationResult(False, "LLM 未输出 SQL", "", ())
                continue
            validation = self._guardrails.validate(sql)
            log("LLM SQL 尝试", trace=trace_id, attempt=attempt,
                ok=validation.ok)
            if validation.ok:
                return sql, validation
            last_validation = validation
        return sql, last_validation

    def _generate_insight(self, question: str, llm: LLMClient,
                          result: QueryResult) -> str:
        summary = result.as_dicts()[:INSIGHT_ROWS]
        prompt = (
            f"用户问题：{question}\n"
            f"查询结果（前 {len(summary)} 行）：\n"
            f"{json.dumps(summary, ensure_ascii=False, indent=2)}\n\n"
            "请用中文给出 2-4 句数据洞察：指出关键数值、趋势或异常。"
            "只依据给出的数据，不要编造。"
        )
        return llm.complete(prompt).strip()

    def _schema_text(self) -> str:
        catalog = self._guardrails.catalog
        return "\n".join(
            f"表 {table}({', '.join(catalog.column_names(table))})"
            for table in catalog.table_names
        )

    @staticmethod
    def _sql_prompt(question: str, schema_text: str,
                    feedback: str | None = None,
                    examples: list[tuple[str, str]] | None = None) -> str:
        prompt = (
            "你是数据查询 Agent。根据数据库 schema 与用户问题，"
            "生成一条只读 SELECT SQL（SQLite 方言）。\n"
            "要求：\n"
            "- 只能 SELECT / WITH，禁止任何写操作（insert/update/delete/drop 等）\n"
            "- 禁止查询敏感字段（含 phone/password/token/email 等列名）\n"
            "- 直接输出 SQL 本身，不要解释、不要 markdown 围栏\n\n"
            f"数据库 schema：\n{schema_text}\n\n"
        )
        if examples:
            lines = [f"问题: {q}\nSQL: {sql}" for q, sql in examples]
            prompt += ("历史相似问题的参考 SQL（写法可复用，注意不要照抄业务条件）：\n"
                       + "\n\n".join(lines) + "\n\n")
        prompt += f"用户问题：{question}"
        if feedback:
            prompt += (f"\n\n上次生成的 SQL 未通过安全校验：{feedback}\n"
                       "请修正后重新输出，只输出 SQL。")
        return prompt
