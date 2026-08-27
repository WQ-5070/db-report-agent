"""语义层：指标/口径 Registry + 数据库 Schema 目录。

对应 docs/DESIGN.md 第 9 节。核心思想是"数据代替逻辑"：
指标口径、别名、默认呈现方式都是数据（semantics/metrics.json 资产文件），
匹配与检索只是不变骨架；加指标 = 加一条数据，不改代码。
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass

from .config import PROJECT_ROOT

# 敏感列关键词（小写匹配列名子串）——演示用数据驱动名单，生产接数据分级系统
SENSITIVE_KEYWORDS = ("password", "token", "secret", "id_card", "phone",
                      "email", "身份证", "手机", "电话")

# 指标资产文件（数据唯一来源；生产可指向独立配置路径）
METRICS_PATH = PROJECT_ROOT / "semantics" / "metrics.json"
_REQUIRED_FIELDS = ("id", "aliases", "sql", "title", "chart", "x", "y",
                    "insight")


@dataclass(frozen=True)
class Column:
    name: str
    dtype: str


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]

    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)


class SchemaCatalog:
    """表/列目录 + 敏感列判断，供护栏做白名单与脱敏决策。"""

    def __init__(self, tables: dict[str, Table],
                 sensitive_keywords: tuple[str, ...] = SENSITIVE_KEYWORDS):
        self._tables = tables
        self._keywords = sensitive_keywords

    @classmethod
    def from_sqlite(cls, db_path: str) -> "SchemaCatalog":
        with closing(sqlite3.connect(db_path)) as conn:
            tables: dict[str, Table] = {}
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ):
                cols = tuple(
                    Column(col[1], col[2])
                    for col in conn.execute(f"PRAGMA table_info({name})")
                )
                tables[name] = Table(name, cols)
        return cls(tables)

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self._tables)

    def has_table(self, name: str) -> bool:
        return name in self._tables

    def column_names(self, table: str) -> tuple[str, ...]:
        return self._tables[table].column_names()

    def is_sensitive(self, column: str) -> bool:
        lowered = column.lower()
        return any(kw in lowered for kw in self._keywords)


@dataclass(frozen=True)
class Metric:
    """一个业务指标 = 口径(SQL) + 触发别名 + 默认呈现方式。"""

    id: str
    aliases: tuple[str, ...]
    sql: str
    title: str
    chart: str  # line | bar | pie
    x: str
    y: str
    insight: str

    @classmethod
    def from_dict(cls, data: dict) -> "Metric":
        """从资产文件条目构建；缺字段立即报错（配置错了要大声）。"""
        missing = [f for f in _REQUIRED_FIELDS if f not in data]
        if missing:
            raise ValueError(f"指标缺少字段: {', '.join(missing)}")
        return cls(
            id=data["id"],
            aliases=tuple(data["aliases"]),
            sql=data["sql"],
            title=data["title"],
            chart=data["chart"],
            x=data["x"],
            y=data["y"],
            insight=data["insight"],
        )


class SemanticRegistry:
    """按问题匹配指标。命中别名最多的指标胜出（平局取先定义者）。"""

    def __init__(self, metrics: list[Metric]):
        self._metrics = metrics

    def get(self, metric_id: str) -> Metric:
        for metric in self._metrics:
            if metric.id == metric_id:
                return metric
        raise KeyError(f"未定义的指标: {metric_id}")

    def match(self, question: str) -> Metric | None:
        lowered = question.lower()
        best: Metric | None = None
        best_hits = 0
        for metric in self._metrics:
            hits = sum(1 for alias in metric.aliases if alias in lowered)
            if hits > best_hits:
                best, best_hits = metric, hits
        return best


def load_metrics(path: str | pathlib.Path) -> list[Metric]:
    """从 JSON 资产文件加载指标：字段校验 + id 唯一（防配置手滑）。"""
    raw = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    metrics = [Metric.from_dict(item) for item in raw]
    ids = [m.id for m in metrics]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValueError(f"指标 id 重复: {duplicates}")
    return metrics


def build_registry(path: str | pathlib.Path | None = None) -> SemanticRegistry:
    """构建注册表：从指标资产文件加载（默认 semantics/metrics.json）。

    文件缺失/损坏时直接报错——指标是系统一部分，坏了要大声，不静默回退。
    """
    metrics_path = pathlib.Path(path) if path else METRICS_PATH
    if not metrics_path.exists():
        raise FileNotFoundError(
            f"指标资产文件不存在: {metrics_path}；"
            "请检查 semantics/metrics.json")
    return SemanticRegistry(load_metrics(metrics_path))


def build_default_registry() -> SemanticRegistry:
    """兼容别名：读默认指标资产文件（semantics/metrics.json）。"""
    return build_registry()
