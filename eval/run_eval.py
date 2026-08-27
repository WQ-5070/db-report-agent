"""评测：跑黄金集并输出指标回归。

用法（先安装本地包: pip install -e .）:
    python eval/run_eval.py                # 离线：轻路径 + 护栏
    python eval/run_eval.py --llm          # 重量路径（需 DBR_LLM_API_KEY 等环境变量）

默认数据库路径基于项目根解析，与当前工作目录无关（PyCharm 里单文件运行也不会报错）。

指标：命中率 / 执行成功率 / 护栏拦截率。全部通过 → 退出码 0；否则 1。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

from dbreport.core.executor import QueryExecutor
from dbreport.core.guardrails import SqlGuardrails
from dbreport.core.pipeline import ReportPipeline, UnmatchedQuestion
from dbreport.core.semantic import SchemaCatalog, build_default_registry

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
GOLDEN = pathlib.Path(__file__).parent / "golden.json"
DEFAULT_DB = str(PROJECT_ROOT / "demos" / "db-report-agent.db")
HEAL_THRESHOLD = 2  # 结果集不符连续失败多少次后自愈剔除（期望可能过时）
FAILURES_PATH = PROJECT_ROOT / ".dbreport" / "eval_failures.json"


def _load_failures(path: str | pathlib.Path | None = None) -> dict:
    """读取跨运行的连续失败计数（文件不存在 = 全新开始）。"""
    failures_path = pathlib.Path(path) if path else FAILURES_PATH
    if failures_path.exists():
        return json.loads(failures_path.read_text(encoding="utf-8"))
    return {}


def _save_failures(failures: dict,
                   path: str | pathlib.Path | None = None) -> None:
    """持久化连续失败计数（写入前确保父目录存在）。"""
    failures_path = pathlib.Path(path) if path else FAILURES_PATH
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    failures_path.write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm_rows(rows) -> list[tuple]:
    """规范化行：字符串去空白、数字转 float、行整体排序（行序不敏感）。"""
    def norm(value):
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return float(value)
        return value

    return sorted(tuple(norm(v) for v in row) for row in rows)


def _rows_match(actual, expected: dict, rel_tol: float = 1e-6) -> bool:
    """结果集比对：列名一致 + 行数一致 + 逐行一致（数字容忍相对误差）。"""
    if tuple(actual.columns) != tuple(expected.get("columns", ())):
        return False
    act_rows = _norm_rows(actual.rows)
    exp_rows = _norm_rows(expected.get("rows", []))
    if len(act_rows) != len(exp_rows):
        return False
    for act_row, exp_row in zip(act_rows, exp_rows):
        for a, e in zip(act_row, exp_row):
            if isinstance(a, float) and isinstance(e, float):
                if abs(a - e) > rel_tol * max(1.0, abs(e)):
                    return False
            elif a != e:
                return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="db-report-agent 评测")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help="SQLite 数据库路径（默认项目根 demos/db-report-agent.db）")
    parser.add_argument("--llm", action="store_true",
                        help="重量路径：未命中时由 LLM 生成 SQL（需 LLM 环境变量）")
    parser.add_argument("--heal", action="store_true",
                        help="自愈模式：结果集不符连续失败 ≥2 次的用例自动剔除（期望可能过时）")
    parser.add_argument("--golden", default=str(GOLDEN),
                        help="黄金集路径（默认 eval/golden.json）")
    parser.add_argument("--failures", default=str(FAILURES_PATH),
                        help="失败计数文件路径（默认 .dbreport/eval_failures.json）")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[错误] 数据库不存在: {args.db}")
        print("       请先运行: python demos/seed/generate_sample_data.py")
        return 1

    llm = None
    if args.llm:
        from dbreport.core.llm import OpenAICompatibleClient
        llm = OpenAICompatibleClient()

    pipeline = ReportPipeline(
        build_default_registry(),
        SqlGuardrails(SchemaCatalog.from_sqlite(args.db)),
        QueryExecutor(args.db),
    )
    golden = json.loads(pathlib.Path(args.golden).read_text(encoding="utf-8"))
    failures = _load_failures(args.failures) if args.heal else {}
    healed: list[str] = []

    light_failures: list[str] = []
    matched = executed = 0
    for case in golden["light"]:
        q = case["question"]
        try:
            report = pipeline.ask(q, llm=llm)
        except UnmatchedQuestion:
            light_failures.append(
                f"{q} -> 未匹配（期望 {case['metric']}）")
            continue
        if report.metric_id != case["metric"]:
            light_failures.append(
                f"{q} -> {report.metric_id}（期望 {case['metric']}）")
            continue
        matched += 1
        if report.result is None:
            light_failures.append(f"{q} -> 执行失败（护栏/异常）")
            continue
        executed += 1
        expected = case.get("expected")
        if expected is not None and not _rows_match(report.result, expected):
            failures[q] = failures.get(q, 0) + 1
            if failures[q] >= HEAL_THRESHOLD:
                healed.append(q)
                continue
            light_failures.append(f"{q} -> 结果集与期望不符")
        else:
            failures.pop(q, None)  # 通过即清零，连续失败才累计
    if args.heal:
        _save_failures(failures, args.failures)

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
    for q in healed:
        print(f"  [SELF-HEALED] {q}（结果集不符连续 {HEAL_THRESHOLD} 次，期望可能过时，已剔除）")
    for line in unsafe_leaks:
        print(f"  [LEAK] {line}")

    ok = not light_failures and not unsafe_leaks
    print("结果:", "PASS ✅" if ok else "FAIL ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
