import tempfile
import unittest

from dbreport.executor import QueryExecutor

from _fixture import make_db


class QueryExecutorTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = self._tmp.name + "/test.db"
        make_db(self.db)
        self.executor = QueryExecutor(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_runs_select_and_returns_result(self):
        result = self.executor.run("SELECT amount FROM orders ORDER BY order_id")
        self.assertEqual(result.columns, ("amount",))
        self.assertEqual(result.row_count, 2)
        self.assertEqual(result.rows[0], (100.0,))

    def test_cache_returns_same_object(self):
        sql = "SELECT COUNT(*) AS n FROM orders"
        first = self.executor.run(sql)
        second = self.executor.run(sql)
        self.assertIs(first, second)

    def test_db_side_readonly_backstop_blocks_write(self):
        # 护栏外的第二道防线：PRAGMA query_only 在数据库侧拒绝写
        with self.assertRaises(Exception):
            self.executor.run("UPDATE users SET is_active = 0")


if __name__ == "__main__":
    unittest.main()
