"""评测回归测试：离线跑黄金集，断言指标全过、退出码为 0。"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RunEvalTest(unittest.TestCase):
    def test_offline_eval_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "test.db"
            from _fixture import make_db
            make_db(str(db))
            result = subprocess.run(
                [sys.executable, "eval/run_eval.py", "--db", str(db)],
                cwd=ROOT, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
