"""SQL 护栏：执行前的强制安全校验。

对应 docs/DESIGN.md 第 8.4 节。原则：护栏是代码层的硬墙，不依赖模型自觉。
当前用词法级校验（标准库，零依赖）；生产建议叠加 sqlglot AST 解析
（见 pyproject.toml 的 prod 可选依赖组），规则与本模块一致。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .semantic import SchemaCatalog

# 写/危险关键字：命中即拒绝（词边界匹配）
WRITE_KEYWORDS = frozenset((
    "insert", "update", "delete", "drop", "alter", "create", "truncate",
    "replace", "attach", "detach", "grant", "revoke", "vacuum", "pragma",
))

_FROM_TABLE = re.compile(r"\b(?:from|join|into|update|table)\s+([a-z_][a-z0-9_]*)", re.I)
_WORD = re.compile(r"[a-z_][a-z0-9_]*", re.I)
_LIMIT = re.compile(r"\blimit\b", re.I)
# 剔除字符串字面量与注释，避免关键字伪装（如 'delete' 出现在字符串里）
_STRING_OR_COMMENT = re.compile(
    r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"|--[^\n]*|/\*.*?\*/", re.S
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    message: str
    safe_sql: str  # 校验通过后（可能已附加 LIMIT）可直接执行的 SQL
    lineage: tuple[str, ...]  # 涉及的表，供审计/血缘


class SqlGuardrails:
    def __init__(self, catalog: SchemaCatalog, max_rows: int = 10_000):
        self._catalog = catalog
        self._max_rows = max_rows

    @property
    def catalog(self) -> SchemaCatalog:
        return self._catalog

    def validate(self, sql: str) -> ValidationResult:
        body = _STRING_OR_COMMENT.sub("", sql)
        statements = [s.strip() for s in body.split(";") if s.strip()]

        if len(statements) != 1:
            return ValidationResult(False, "仅允许单条 SQL 语句", sql, ())
        statement = statements[0]

        head = statement.split(None, 1)[0].lower()
        if head not in ("select", "with"):
            return ValidationResult(False, f"仅允许只读查询（SELECT/WITH），收到: {head.upper()}", sql, ())

        words = {w.lower() for w in _WORD.findall(statement)}
        if words & WRITE_KEYWORDS:
            return ValidationResult(False, "检测到写/危险关键字，已拒绝", sql, ())

        tables = tuple(_FROM_TABLE.findall(statement))
        unknown = [t for t in tables if not self._catalog.has_table(t)]
        if unknown:
            return ValidationResult(False, f"访问了未授权表: {', '.join(unknown)}", sql, ())

        sensitive = sorted(w for w in words if self._catalog.is_sensitive(w))
        if sensitive:
            return ValidationResult(False, f"涉及敏感字段: {', '.join(sensitive)}，已拒绝", sql, ())

        safe_sql = sql.strip().rstrip(";").strip()  # 去尾分号，避免 LIMIT 附加成第二条语句
        if not _LIMIT.search(statement):
            safe_sql += f" LIMIT {self._max_rows}"
        return ValidationResult(True, "校验通过", safe_sql, tables)
