import tempfile
import unittest

from dbreport.core.executor import QueryExecutor
from dbreport.core.guardrails import SqlGuardrails
from dbreport.core.pipeline import ReportPipeline, UnmatchedQuestion
from dbreport.core.semantic import (Metric, SchemaCatalog, SemanticRegistry,
                               build_default_registry)

from tests._fixture import make_db


class FakeLLM:
    """按顺序返回预设响应的测试替身。"""

    def __init__(self, *responses: str):
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._responses.pop(0) if self._responses else ""


class ReportPipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = self._tmp.name + "/test.db"
        make_db(self.db)
        self.catalog = SchemaCatalog.from_sqlite(self.db)
        self.executor = QueryExecutor(self.db)
        self.guardrails = SqlGuardrails(self.catalog)

    def tearDown(self):
        self._tmp.cleanup()

    def _pipeline(self, registry=None, **kwargs):
        return ReportPipeline(registry or build_default_registry(),
                              self.guardrails, self.executor, **kwargs)

    # ---- 轻路径 ----

    def test_end_to_end_light_path(self):
        report = self._pipeline().ask("各地区订单量占比？")
        self.assertEqual(report.metric_id, "region_orders")
        self.assertTrue(report.validation.ok)
        self.assertEqual(report.result.row_count, 1)
        self.assertIn("订单", report.report_md)
        self.assertEqual(report.chart["type"], "pie")
        self.assertEqual(len(report.trace_id), 8)

    def test_unmatched_question_without_llm_raises(self):
        with self.assertRaises(UnmatchedQuestion):
            self._pipeline().ask("统计一下订单总数")

    def test_guardrail_rejection_path(self):
        leaky = Metric(
            id="leak", aliases=("电话",),
            sql="SELECT phone FROM users",
            title="x", chart="bar", x="a", y="b", insight="",
        )
        report = self._pipeline(SemanticRegistry([leaky])).ask("看所有用户的电话")
        self.assertFalse(report.validation.ok)
        self.assertIn("敏感字段", report.report_md)

    # ---- 重量路径 ----

    def test_heavy_path_with_llm_sql_and_insight(self):
        llm = FakeLLM(
            "SELECT COUNT(*) AS n FROM orders",
            "订单总数稳定在合理区间。",
        )
        report = self._pipeline().ask("统计一下订单总数", llm=llm)
        self.assertIsNone(report.metric_id)
        self.assertEqual(report.result.rows[0][0], 2)  # COUNT(*) = 2 条订单
        self.assertIn("订单总数稳定在合理区间", report.report_md)
        self.assertIn("洞察来源", report.report_md)
        self.assertEqual(len(llm.prompts), 2)  # SQL + 洞察

    def test_heavy_path_retries_after_guardrail_failure(self):
        llm = FakeLLM(
            "DELETE FROM orders",
            "SELECT COUNT(*) AS n FROM orders",
            "洞察文本",
        )
        report = self._pipeline().ask("统计一下订单总数", llm=llm)
        self.assertTrue(report.validation.ok)
        self.assertIsNotNone(report.result)
        self.assertIn("未通过安全校验", llm.prompts[1])  # 反馈进入第二次 prompt

    def test_heavy_path_gives_up_after_retries(self):
        llm = FakeLLM("DELETE FROM orders", "DROP TABLE orders",
                      "UPDATE orders SET amount = 0")
        report = self._pipeline().ask("统计一下订单总数", llm=llm)
        self.assertFalse(report.validation.ok)
        self.assertIsNone(report.result)
        self.assertIn("护栏拦截", report.report_md)

    def test_memory_few_shot_injection_and_auto_train(self):
        from dbreport.core.memory import Memory
        mem = Memory(self._tmp.name + "/mem.db")
        mem.train("各品类销售额对比",
                  "SELECT product_category, SUM(amount) AS sales FROM orders "
                  "GROUP BY product_category ORDER BY sales DESC")
        llm = FakeLLM(
            "SELECT product_category, ROUND(SUM(amount), 2) AS sales "
            "FROM orders GROUP BY product_category ORDER BY sales DESC",
            "洞察文本",
        )
        question = "各品类销售额排行"
        report = self._pipeline(SemanticRegistry([]), memory=mem).ask(
            question, llm=llm)
        self.assertTrue(report.validation.ok)
        self.assertIn("各品类销售额对比", llm.prompts[0])  # few-shot 注入
        self.assertIn(question, [q for q, _ in mem.similar(question)])  # auto-train


if __name__ == "__main__":
    unittest.main()
