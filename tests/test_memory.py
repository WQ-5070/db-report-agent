"""记忆层测试：问题-SQL 沉淀/检索、去重命中、知识检索、持久化。"""
import pathlib
import tempfile
import unittest

from dbreport.core.memory import Memory


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = str(pathlib.Path(self._tmp.name) / "memory.db")
        self.mem = Memory(self.path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_train_and_similar(self):
        self.mem.train("统计各品类销售额",
                       "SELECT product_category, SUM(amount) FROM orders "
                       "GROUP BY product_category")
        hits = self.mem.similar("各品类的销售额是多少")
        self.assertEqual(len(hits), 1)
        self.assertIn("品类", hits[0][0])
        self.assertIn("SUM(amount)", hits[0][1])

    def test_similar_ignores_unrelated(self):
        self.mem.train("各地区订单量占比", "SELECT 1")
        self.assertEqual(self.mem.similar("今天天气怎么样"), [])

    def test_train_dedup_keeps_latest_sql(self):
        self.mem.train("订单总数", "SELECT COUNT(*) FROM orders")
        self.mem.train("订单总数", "SELECT COUNT(1) FROM orders")
        hits = self.mem.similar("订单总数是多少")
        self.assertEqual(len(hits), 1)
        self.assertIn("COUNT(1)", hits[0][1])

    def test_related_by_kind_and_keywords(self):
        self.mem.add_knowledge("ddl", "orders 表：amount 为订单金额",
                               keywords="订单 金额 amount")
        self.assertEqual(len(self.mem.related("订单金额", "ddl")), 1)
        self.assertEqual(self.mem.related("订单金额", "doc"), [])

    def test_persists_across_instances(self):
        self.mem.train("季度销售趋势", "SELECT 1")
        reopened = Memory(self.path)
        hits = reopened.similar("季度销售趋势")
        self.assertEqual(len(hits), 1)


if __name__ == "__main__":
    unittest.main()
