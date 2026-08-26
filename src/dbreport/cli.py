"""命令行入口。

用法:
    python -m dbreport.cli "各地区订单量占比？"          # 轻路径（语义层预置口径）
    python -m dbreport.cli "统计一下订单总数" --llm      # 重量路径（LLM 生成 SQL）
    python -m dbreport.cli "删除所有订单"                # 护栏拦截演示

说明：默认数据库路径基于项目根解析，与当前工作目录无关
（在 PyCharm 里直接运行 cli.py 也不会因工作目录报错）。

LLM 配置（环境变量，见 llm.py）: DBR_LLM_BASE_URL / DBR_LLM_API_KEY / DBR_LLM_MODEL
"""
from __future__ import annotations

import argparse
import os
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DB = str(PROJECT_ROOT / "demos" / "db-report-agent.db")


def _build_pipeline(db: str):
    from .executor import QueryExecutor
    from .guardrails import SqlGuardrails
    from .memory import Memory
    from .pipeline import ReportPipeline
    from .semantic import SchemaCatalog, build_default_registry

    return ReportPipeline(
        build_default_registry(),
        SqlGuardrails(SchemaCatalog.from_sqlite(db)),
        QueryExecutor(db),
        memory=Memory(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dbreport", description="db-report-agent：自然语言查库并生成报表")
    parser.add_argument("question", help="自然语言问题，如：各地区订单量占比？")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="SQLite 数据库路径（默认项目根 demos/db-report-agent.db）")
    parser.add_argument("--llm", action="store_true",
                        help="启用重量路径：未命中语义层时由 LLM 动态生成 SQL 与洞察")
    args = parser.parse_args(argv)

    if not os.path.exists(args.db):
        print(f"[错误] 数据库不存在: {args.db}")
        print("       请先运行: python demos/seed/generate_sample_data.py")
        return 1

    llm = None
    if args.llm:
        from .llm import OpenAICompatibleClient
        try:
            llm = OpenAICompatibleClient()
        except ValueError as exc:
            print(f"[错误] {exc}")
            return 1

    from .pipeline import ReportPipeline, UnmatchedQuestion
    pipeline = _build_pipeline(args.db)
    try:
        report = pipeline.ask(args.question, llm=llm)
    except UnmatchedQuestion as exc:
        print(f"[错误] {exc}")
        return 1
    except Exception as exc:  # LLMError 等，给出可读提示而非原始堆栈
        print(f"[错误] 生成失败: {exc}")
        return 1

    print(report.report_md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
