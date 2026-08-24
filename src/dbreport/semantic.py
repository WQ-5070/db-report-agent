"""语义层：指标/口径 Registry + 数据库 Schema 目录。

对应 docs/DESIGN.md 第 9 节。核心思想是"数据代替逻辑"：
指标口径、别名、默认呈现方式都是数据；匹配与检索只是不变骨架。
"""
from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass

# 敏感列关键词（小写匹配列名子串）——演示用数据驱动名单，生产接数据分级系统
SENSITIVE_KEYWORDS = ("password", "token", "secret", "id_card", "phone",
                      "email", "身份证", "手机", "电话")


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


# 内置指标：与 demos/seed 样例库对齐的口径（生产从语义层配置/数据库加载）
DEFAULT_METRICS = [
    Metric(
        id="monthly_sales",
        aliases=("销售额", "sales", "营收", "gmv", "每月"),
        sql="SELECT strftime('%Y-%m', order_date) AS month, "
            "ROUND(SUM(amount), 2) AS sales FROM orders "
            "GROUP BY month ORDER BY month",
        title="月度销售额", chart="line", x="month", y="sales",
        insight="销售额整体呈上升趋势，年底为旺季峰值；留意异常月份回落原因。",
    ),
    Metric(
        id="region_orders",
        aliases=("地区", "region", "区域", "占比", "订单量"),
        sql="SELECT r.region_name AS region, COUNT(o.order_id) AS orders "
            "FROM orders o JOIN regions r ON o.region_id = r.region_id "
            "GROUP BY region ORDER BY orders DESC",
        title="各地区订单量占比", chart="pie", x="region", y="orders",
        insight="订单集中在人口密集区域，西北、西南相对较低，可评估渠道投放。",
    ),
    Metric(
        id="category_sales",
        aliases=("品类", "产品", "category", "类别"),
        sql="SELECT product_category AS category, ROUND(SUM(amount), 2) AS sales "
            "FROM orders GROUP BY category ORDER BY sales DESC",
        title="各品类销售额", chart="bar", x="category", y="sales",
        insight="数码、家电贡献销售主体；可结合毛利率评估品类结构。",
    ),
    Metric(
        id="active_users",
        aliases=("用户", "活跃", "user"),
        sql="SELECT city, COUNT(*) AS active_users FROM users "
            "WHERE is_active = 1 GROUP BY city ORDER BY active_users DESC",
        title="各城市活跃用户数", chart="bar", x="city", y="active_users",
        insight="活跃用户集中于人口密集城市，与订单分布基本一致。",
    ),
]


def build_default_registry() -> SemanticRegistry:
    """内置指标注册表（与 demos/seed 样例库口径对齐）。

    生产形态：指标从语义层配置/数据库加载（见 docs/DESIGN.md 第 9 节），
    此处是随库分发的默认集。
    """
    return SemanticRegistry(list(DEFAULT_METRICS))
