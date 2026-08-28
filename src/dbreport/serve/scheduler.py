"""定时报表调度器（P4 服务化②）：间隔调度 + 报告落盘。

参考 Superset Alerts & Reports 模型（基座蓝图 5.3）：注册"问题 + 间隔"，
到点自动跑 pipeline 生成报告（Markdown 落盘到 .dbreport/reports/）。
零第三方依赖（标准库 threading）；run_due() 可手动触发（测试/调试用）。
"""
from __future__ import annotations

import pathlib
import threading
import time
from dataclasses import dataclass

from ..core.errors import AgentError
from ..core.log import log
from ..core.pipeline import ReportPipeline
from . import DEFAULT_DB, build_pipeline

REPORTS_DIR = pathlib.Path(DEFAULT_DB).parent.parent / ".dbreport" / "reports"


@dataclass
class Task:
    question: str
    interval_seconds: int
    next_run: float  # 绝对时间戳（time.time()）
    db_path: str
    use_llm: bool = False


class ReportScheduler:
    """间隔调度：到点跑 pipeline 生成报告并落盘。"""

    def __init__(self, reports_dir: str | pathlib.Path | None = None,
                 pipeline_builder=build_pipeline):
        self._dir = (pathlib.Path(reports_dir) if reports_dir
                     else REPORTS_DIR)
        self._builder = pipeline_builder
        self._tasks: list[Task] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def add_task(self, question: str, interval_minutes: float,
                 db_path: str | None = None, use_llm: bool = False) -> Task:
        """注册一个定时任务：每 interval_minutes 分钟生成一次该问题的报告。"""
        seconds = int(interval_minutes * 60)
        task = Task(question=question, interval_seconds=seconds,
                    next_run=time.time() + seconds,
                    db_path=db_path or DEFAULT_DB, use_llm=use_llm)
        with self._lock:
            self._tasks.append(task)
        return task

    def start(self) -> None:
        """后台守护线程轮询到期任务（进程退出自动终止）。"""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def run_due(self) -> list[pathlib.Path]:
        """手动跑所有到期任务（测试/调试用）；返回本次生成的报告路径。"""
        produced: list[pathlib.Path] = []
        with self._lock:
            tasks = list(self._tasks)
        now = time.time()
        for task in tasks:
            if task.next_run <= now:
                path = self._execute(task)
                if path is not None:
                    produced.append(path)
                task.next_run = now + task.interval_seconds
        return produced

    def _execute(self, task: Task) -> pathlib.Path | None:
        """跑一次任务并落盘；任何失败记日志、不抛出（调度器要稳）。"""
        llm = None
        if task.use_llm:
            from ..core.llm import OpenAICompatibleClient
            try:
                llm = OpenAICompatibleClient()
            except AgentError as exc:
                log("定时任务 LLM 不可用", level="WARN",
                    question=task.question, code=exc.code)
                return None
        try:
            report = self._builder(task.db_path).ask(task.question, llm=llm)
        except AgentError as exc:
            log("定时任务失败", level="WARN",
                question=task.question, code=exc.code)
            return None
        if report.result is None:
            log("定时任务无结果", level="WARN", question=task.question)
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / (f"{time.strftime('%Y%m%d_%H%M%S')}_"
                            f"{report.metric_id}.md")
        path.write_text(report.report_md, encoding="utf-8")
        log("定时报告已生成", question=task.question, path=path.name)
        return path

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_due()
            self._stop_event.wait(timeout=1)


if __name__ == "__main__":
    # 简单演示：每分钟生成一次"各地区订单量占比"报告
    scheduler = ReportScheduler()
    scheduler.add_task("各地区订单量占比？", interval_minutes=1)
    scheduler.start()
    print(f"定时报表运行中（Ctrl+C 停止）→ {REPORTS_DIR}")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        scheduler.stop()
