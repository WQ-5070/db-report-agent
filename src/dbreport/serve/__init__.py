"""装配层：把核心模块组装成可用管线，供 CLI / API / 定时任务复用。

对应 DB-GPT 分层思想：core（能力）与 serve（装配/入口）分离——
换入口（CLI → API → 定时任务）只动本层，core 模块完全不知道外面是谁在调。
"""
from __future__ import annotations

from ..core.config import PROJECT_ROOT
from ..core.executor import QueryExecutor
from ..core.guardrails import SqlGuardrails
from ..core.memory import Memory
from ..core.pipeline import ReportPipeline
from ..core.semantic import SchemaCatalog, build_registry

DEFAULT_DB = str(PROJECT_ROOT / "demos" / "db-report-agent.db")


def build_pipeline(db: str | None = None,
                   metrics_path: str | None = None) -> ReportPipeline:
    """组装完整管线：语义层（资产文件）+ 护栏 + 执行 + 记忆。

    db 缺省用样例库；metrics_path 缺省用 semantics/metrics.json。
    """
    db = db or DEFAULT_DB
    return ReportPipeline(
        build_registry(metrics_path),
        SqlGuardrails(SchemaCatalog.from_sqlite(db)),
        QueryExecutor(db),
        memory=Memory(),
    )
