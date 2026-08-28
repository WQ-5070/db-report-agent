"""定时报表测试：任务注册 + run_due 生成报告落盘。"""
import pathlib
import tempfile
import unittest

from dbreport.serve.scheduler import ReportScheduler


class SchedulerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name) / "reports"

    def tearDown(self):
        self._tmp.cleanup()

    def test_run_due_generates_report(self):
        sched = ReportScheduler(reports_dir=self.dir)
        sched.add_task("各地区订单量占比？", interval_minutes=0.001)  # 立即到期
        produced = sched.run_due()
        self.assertEqual(len(produced), 1)
        content = produced[0].read_text(encoding="utf-8")
        self.assertIn("各地区订单量占比", content)

    def test_not_due_does_not_run(self):
        sched = ReportScheduler(reports_dir=self.dir)
        sched.add_task("各地区订单量占比？", interval_minutes=60)  # 1 小时后才到期
        self.assertEqual(sched.run_due(), [])

    def test_unsafe_question_skipped(self):
        sched = ReportScheduler(reports_dir=self.dir)
        sched.add_task("删除所有订单", interval_minutes=0.001)  # 护栏/未命中 → 无结果
        self.assertEqual(sched.run_due(), [])


if __name__ == "__main__":
    unittest.main()
