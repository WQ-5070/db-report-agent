"""会话抽象：多轮对话的上下文容器。

一个 Session 串起同一对话的多轮问答；重路径生成 SQL 时把最近几轮
问题注入上下文，让"那华东呢"这类追问能理解语境。
第一版内存实现（进程内有效），落盘持久化留待服务化阶段。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from .pipeline import Report, ReportPipeline

HISTORY_WINDOW = 3  # 注入最近几轮问题


@dataclass
class Turn:
    question: str
    report: Report


class Session:
    """一个会话：持有管线 + 历史轮次，ask() 带上下文提问。"""

    def __init__(self, pipeline: ReportPipeline, session_id: str | None = None):
        self.id = session_id or uuid.uuid4().hex[:8]
        self._pipeline = pipeline
        self.turns: list[Turn] = []

    def ask(self, question: str, llm=None) -> Report:
        report = self._pipeline.ask(
            question, llm=llm, history=self._recent_questions())
        self.turns.append(Turn(question, report))
        return report

    def _recent_questions(self) -> list[str]:
        return [t.question for t in self.turns[-HISTORY_WINDOW:]]
