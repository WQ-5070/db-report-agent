import tempfile
import unittest

from dbreport.core.executor import QueryExecutor, QueryResult
from dbreport.core.reporting import infer_chart

from tests._fixture import make_db


class InferChartTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = self._tmp.name + "/test.db"
        make_db(db)
        self.executor = QueryExecutor(db)

    def tearDown(self):
        self._tmp.cleanup()

    def _result(self, sql):
        return self.executor.run(sql)

    def test_time_column_yields_line(self):
        result = self._result(
            "SELECT order_date AS month, SUM(amount) AS sales "
            "FROM orders GROUP BY month ORDER BY month")
        spec = infer_chart(result)
        self.assertEqual(spec["type"], "line")
        self.assertEqual(spec["x"], "month")

    def test_category_yields_bar(self):
        result = self._result(
            "SELECT product_category AS category, COUNT(*) AS orders "
            "FROM orders GROUP BY category")
        spec = infer_chart(result)
        self.assertEqual(spec["type"], "bar")
        self.assertEqual(spec["x"], "category")
        self.assertEqual(spec["y"], "orders")


if __name__ == "__main__":
    unittest.main()
