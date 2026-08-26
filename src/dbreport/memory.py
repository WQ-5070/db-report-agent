"""记忆层：问题-SQL 样本沉淀与检索（Vanna 式记忆的轻量实现）。

对应 docs/DESIGN.md 第 5.3 节基座蓝图：借鉴 Vanna 的三类训练内容
（DDL / 文档 / 问题-SQL 对）+ 成功查询自学习闭环。零第三方依赖：
- 存储用 SQLite，库文件默认在项目根 .dbreport/（不进 Git）；
- 检索用字符 bigram Jaccard 相似度，对中文友好，无需 embedding/向量库。
"""
from __future__ import annotations

import pathlib
import re
import sqlite3
from contextlib import closing

from .config import PROJECT_ROOT

DEFAULT_MEMORY_PATH = str(PROJECT_ROOT / ".dbreport" / "memory.db")
SIMILARITY_THRESHOLD = 0.12  # bigram Jaccard 下限，过滤无关样本
_CJK = re.compile(r"[\u4e00-\u9fff]+")


def _bigrams(text: str) -> set[str]:
    """归一化后取字符 bigram 集合（中文整串 + 英文/数字按词）。"""
    lowered = text.lower()
    parts = list(_CJK.findall(lowered)) + lowered.split()
    tokens = "".join(parts)
    return {tokens[i:i + 2] for i in range(len(tokens) - 1)}


def _similarity(a: str, b: str) -> float:
    """两个文本的 bigram Jaccard 相似度。"""
    set_a, set_b = _bigrams(a), _bigrams(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


class Memory:
    """问题-SQL 样本记忆：train() 沉淀、similar() 检索注入。

    表结构：
    - question_sql：问题-SQL 对（问题唯一，hits 记录复用次数——自学习闭环的
      "哪些样本常用"信号，供检索排序）；
    - knowledge：DDL/文档类知识（kind 区分，content 唯一）。
    """

    def __init__(self, path: str | None = None):
        self._path = path or DEFAULT_MEMORY_PATH
        pathlib.Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._path)) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS question_sql (
                    question TEXT PRIMARY KEY,
                    sql TEXT NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS knowledge (
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    keywords TEXT NOT NULL DEFAULT '',
                    UNIQUE(kind, content)
                );
                """
            )
            conn.commit()

    def train(self, question: str, sql: str) -> None:
        """沉淀一条问题-SQL 样本；已存在则 hits+1（复用即权重）。"""
        with closing(sqlite3.connect(self._path)) as conn:
            conn.execute(
                "INSERT INTO question_sql(question, sql, hits, updated_at) "
                "VALUES (?, ?, 1, datetime('now')) "
                "ON CONFLICT(question) DO UPDATE SET "
                "sql=excluded.sql, hits=hits+1, updated_at=datetime('now')",
                (question.strip(), sql.strip()),
            )
            conn.commit()

    def add_knowledge(self, kind: str, content: str, keywords: str = "") -> None:
        """沉淀一条 DDL/文档知识（kind: ddl | doc），内容唯一去重。"""
        with closing(sqlite3.connect(self._path)) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO knowledge(kind, content, keywords) "
                "VALUES (?, ?, ?)",
                (kind, content.strip(), keywords.strip()),
            )
            conn.commit()

    def similar(self, question: str, k: int = 3) -> list[tuple[str, str]]:
        """返回与问题最相似的 k 条 (问题, SQL) 样本，按相似度降序。"""
        rows = self._query("SELECT question, sql FROM question_sql", ())
        scored: list[tuple[float, str, str]] = []
        for q, sql in rows:
            score = _similarity(question, q)
            if score >= SIMILARITY_THRESHOLD:
                scored.append((score, q, sql))
        scored.sort(reverse=True)
        return [(q, sql) for _, q, sql in scored[:k]]

    def related(self, question: str, kind: str, k: int = 3) -> list[str]:
        """返回与问题相关的 k 条指定类别知识内容（ddl | doc）。"""
        rows = self._query(
            "SELECT content, keywords FROM knowledge WHERE kind = ?", (kind,))
        scored: list[tuple[float, str]] = []
        for content, keywords in rows:
            score = max(_similarity(question, content),
                        _similarity(question, keywords))
            if score >= SIMILARITY_THRESHOLD:
                scored.append((score, content))
        scored.sort(reverse=True)
        return [c for _, c in scored[:k]]

    def _query(self, sql: str, params: tuple) -> list[tuple]:
        with closing(sqlite3.connect(self._path)) as conn:
            return list(conn.execute(sql, params))
