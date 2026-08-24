"""执行层：只读查询执行 + 结果缓存。

对应 docs/DESIGN.md 第 8.5 节。只读用两层保障：护栏拒绝写语句 +
数据库侧 PRAGMA query_only 兜底（纵深防御，不依赖单一层）。
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    elapsed_ms: float

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def as_dicts(self) -> list[dict]:
        return [dict(zip(self.columns, row)) for row in self.rows]


class QueryExecutor:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._cache: dict[str, QueryResult] = {}

    def run(self, sql: str) -> QueryResult:
        """执行（缓存命中直接返回，保证同 SQL 幂等可复现）。"""
        cache_key = sql.strip()
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        started = time.perf_counter()
        # 注意：sqlite3 连接上下文管理器只管理事务、不关闭连接，
        # 必须显式关闭，否则 Windows 下文件句柄泄漏（测试与生产都会踩到）。
        with closing(sqlite3.connect(self._db_path)) as conn:
            conn.execute("PRAGMA query_only = ON")  # 数据库侧只读兜底
            cursor = conn.execute(sql)
            columns = tuple(col[0] for col in cursor.description)
            rows = tuple(tuple(row) for row in cursor.fetchall())
        elapsed = round((time.perf_counter() - started) * 1000, 1)

        result = QueryResult(columns, rows, elapsed)
        self._cache[cache_key] = result
        return result

    def clear_cache(self) -> None:
        self._cache.clear()
