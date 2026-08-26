"""评测回归测试：离线跑黄金集，断言指标全过、退出码为 0。"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


def _eval_env() -> dict:
    """子进程需要可见 dbreport：src 存在则注入，与父进程同源（免疫环境差异）。"""
    env = os.environ.copy()
    if SRC.is_dir():
        env["PYTHONPATH"] = str(SRC) + os.pathsep + env.get("PYTHONPATH", "")
    return env


class RunEvalTest(unittest.TestCase):
    def test_offline_eval_passes(self):
        """评测回归：用确定性样例库（seed=42）跑黄金集，expected 与其强绑定。"""
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "sample.db"
            gen = subprocess.run(
                [sys.executable, "demos/seed/generate_sample_data.py",
                 "--output", str(db)],
                cwd=ROOT, capture_output=True, text=True, env=_eval_env(),
            )
            self.assertEqual(gen.returncode, 0, gen.stdout + gen.stderr)
            result = subprocess.run(
                [sys.executable, "eval/run_eval.py", "--db", str(db)],
                cwd=ROOT, capture_output=True, text=True, env=_eval_env(),
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_heal_removes_stale_expected(self):
        """结果集期望过时：连续失败 2 次后 --heal 自动剔除并报告 SELF-HEALED。"""
        golden = {"light": [
            {"question": "各地区订单量占比？", "metric": "region_orders",
             "expected": {"columns": ["region", "orders"],
                          "rows": [["华北", 608], ["华东", 602]]}}],
            "unsafe": []}
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "test.db"
            from tests._fixture import make_db
            make_db(str(db))  # 小库：region_orders 实际只返回 1 行 → 与 expected 不符
            gpath = pathlib.Path(tmp) / "golden.json"
            gpath.write_text(json.dumps(golden, ensure_ascii=False),
                             encoding="utf-8")
            fpath = pathlib.Path(tmp) / "failures.json"
            env = _eval_env()
            args = [sys.executable, "eval/run_eval.py", "--db", str(db),
                    "--heal", "--golden", str(gpath), "--failures", str(fpath)]
            first = subprocess.run(args, cwd=ROOT, capture_output=True,
                                   text=True, env=env)
            self.assertEqual(first.returncode, 1,
                             first.stdout + first.stderr)  # 第 1 次：计数 1，仍失败
            second = subprocess.run(args, cwd=ROOT, capture_output=True,
                                    text=True, env=env)
            self.assertEqual(second.returncode, 0,
                             second.stdout + second.stderr)  # 第 2 次：自愈剔除
            self.assertIn("SELF-HEALED", second.stdout)


if __name__ == "__main__":
    unittest.main()
