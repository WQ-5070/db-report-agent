"""评测：跑黄金集并输出指标回归。

用法:
    python eval/run_eval.py                # 离线：轻路径 + 护栏
    python eval/run_eval.py --llm          # 重量路径（需 DBR_LLM_API_KEY 等环境变量）

说明：默认数据库路径基于项目根解析，与当前工作目录无关
（在 PyCharm 里单文件运行也不会因工作目录报错）。

指标：
- 命中率：light 用例正确匹配期望指标的比例；
- 执行成功率：命中后 SQL 过护栏并成功执行的比例；
- 护栏拦截率：unsafe 用例全部被拒（未匹配或被护栏拦截），期望 100%。

退出码：全部通过 → 0；任一 unsafe 放行或 light 失败 → 1。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dbreport.executor import QueryExecutor  # noqa: E402
from dbreport.guardrails import SqlGuardrails  # noqa: E402
from dbreport.pipeline import ReportPipeline, UnmatchedQuestion  # noqa: E402
from dbreport.semantic import SchemaCatalog, build_default_registry  # noqa: E402

GOLDEN = pathlib.Path(__file__).parent / "golden.json"
DEFAULT_DB = str(PROJECT_ROOT / "demos" / "db-report-agent.db")


def main() -> int:
    parser = argparse.ArgumentParser(description="db-report-agent 评测")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="SQLite 数据库路径（默认项目根 demos/db-report-agent.db）")
    parser.add_argument("--llm", action="store_true",
                        help="重量路径：未命中时由 LLM 生成 SQL（需 LLM 环境变量）")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[错误] 数据库不存在: {args.db}")
        print("       请先运行: python demos/seed/generate_sample_data.py")
        return 1

    llm = None
    if args.llm:
        from dbreport.llm import OpenAICompatibleClient
        llm = OpenAICompatibleClient()

    pipeline = ReportPipeline(
        build_default_registry(),
        SqlGuardrails(SchemaCatalog.from_sqlite(args.db)),
        QueryExecutor(args.db),
    )
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))

    light_failures: list[str] = []
    matched = executed = 0
    for case in golden["light"]:
        try:
            report = pipeline.ask(case["question"], llm=llm)
        except UnmatchedQuestion:
            light_failures.append(
                f"{case['question']} -> 未匹配（期望 {case['metric']}）")
            continue
        if report.metric_id != case["metric"]:
            light_failures.append(
                f"{case['question']} -> {report.metric_id}（期望 {case['metric']}）")
        else:
            matched += 1
        if report.result is None:
            light_failures.append(f"{case['question']} -> 执行失败（护栏/异常）")
        else:
            executed += 1

    unsafe_leaks: list[str] = []
    unsafe_handled = 0
    for question in golden["unsafe"]:
        try:
            report = pipeline.ask(question, llm=llm)
        except UnmatchedQuestion:
            unsafe_handled += 1
            continue
        if report.result is None:
            unsafe_handled += 1
        else:
            unsafe_leaks.append(
                f"{question} -> 被放行（返回 {report.result.row_count} 行）")

    total_light = len(golden["light"])
    total_unsafe = len(golden["unsafe"])
    print("=== db-report-agent 评测 ===")
    print(f"轻路径命中率:   {matched}/{total_light}")
    print(f"执行成功率:     {executed}/{total_light}")
    print(f"护栏拦截率:     {unsafe_handled}/{total_unsafe}（unsafe 用例未被放行）")
    for line in light_failures:
        print(f"  [FAIL] {line}")
    for line in unsafe_leaks:
        print(f"  [LEAK] {line}")

    ok = not light_failures and not unsafe_leaks
    print("结果:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
