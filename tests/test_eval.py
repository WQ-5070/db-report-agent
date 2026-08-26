"""评测回归测试：离线跑黄金集，断言指标全过、退出码为 0。"""
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
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "test.db"
            from tests._fixture import make_db
            make_db(str(db))
            result = subprocess.run(
                [sys.executable, "eval/run_eval.py", "--db", str(db)],
                cwd=ROOT, capture_output=True, text=True, env=_eval_env(),
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
