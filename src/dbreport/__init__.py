"""db-report-agent：自动查询数据库并生成报表的数据分析 Agent。

对应 docs/DESIGN.md：语义层 / 护栏 / 执行层 / 呈现层 / 编排层 / LLM 接入。
"""
from .core.executor import QueryExecutor, QueryResult
from .core.guardrails import SqlGuardrails, ValidationResult
from .core.llm import LLMClient, LLMError, OpenAICompatibleClient
from .core.pipeline import Report, ReportPipeline, UnmatchedQuestion
from .core.reporting import build_report, chart_spec, infer_chart
from .core.semantic import (Metric, SchemaCatalog, SemanticRegistry,
                            build_default_registry)

__version__ = "1.0.0"

__all__ = [
    "Metric", "SchemaCatalog", "SemanticRegistry", "build_default_registry",
    "SqlGuardrails", "ValidationResult",
    "QueryExecutor", "QueryResult",
    "build_report", "chart_spec", "infer_chart",
    "LLMClient", "OpenAICompatibleClient", "LLMError",
    "Report", "ReportPipeline", "UnmatchedQuestion",
]
