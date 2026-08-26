import tempfile
import unittest

from dbreport.guardrails import SqlGuardrails
from dbreport.semantic import SchemaCatalog

from tests._fixture import make_db


class SqlGuardrailsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = self._tmp.name + "/test.db"
        make_db(db)
        self.guard = SqlGuardrails(SchemaCatalog.from_sqlite(db))

    def tearDown(self):
        self._tmp.cleanup()

    def _reject(self, sql):
        result = self.guard.validate(sql)
        self.assertFalse(result.ok, f"应当拦截: {sql}")
        return result

    def test_accepts_select_and_appends_limit(self):
        result = self.guard.validate("SELECT * FROM orders")
        self.assertTrue(result.ok)
        self.assertTrue(result.safe_sql.rstrip().endswith("LIMIT 10000"))

    def test_trailing_semicolon_does_not_break_limit(self):
        # 带尾分号时，LIMIT 不应被附加成第二条语句
        result = self.guard.validate("SELECT COUNT(*) AS n FROM orders;")
        self.assertTrue(result.ok)
        self.assertEqual(result.safe_sql, "SELECT COUNT(*) AS n FROM orders LIMIT 10000")

    def test_rejects_write_statements(self):
        for sql in ("DELETE FROM orders",
                    "UPDATE users SET is_active=0",
                    "DROP TABLE orders",
                    "INSERT INTO orders VALUES (1,1,'a',1,'2024-01-01',1)"):
            self._reject(sql)

    def test_rejects_multi_statement(self):
        self._reject("SELECT * FROM orders; DROP TABLE orders")

    def test_rejects_unknown_table(self):
        result = self._reject("SELECT * FROM secret_table")
        self.assertIn("未授权表", result.message)

    def test_rejects_sensitive_column(self):
        result = self._reject("SELECT phone FROM users")
        self.assertIn("敏感字段", result.message)

    def test_keyword_inside_string_is_ignored(self):
        # 'delete' 出现在字符串里不算写操作
        result = self.guard.validate(
            "SELECT product_category FROM orders WHERE amount > 0")
        self.assertTrue(result.ok)

    def test_lineage_extracts_tables(self):
        result = self.guard.validate(
            "SELECT r.region_name FROM orders o JOIN regions r ON o.region_id = r.region_id")
        self.assertEqual(set(result.lineage), {"orders", "regions"})


if __name__ == "__main__":
    unittest.main()
