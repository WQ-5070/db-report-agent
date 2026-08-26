import tempfile
import unittest

from dbreport.semantic import SchemaCatalog, SemanticRegistry, build_default_registry

from tests._fixture import make_db


class SchemaCatalogTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db = self._tmp.name + "/test.db"
        make_db(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def test_introspects_tables_and_columns(self):
        catalog = SchemaCatalog.from_sqlite(self.db)
        self.assertIn("orders", catalog.table_names)
        self.assertIn("region_name", catalog.column_names("regions"))
        self.assertTrue(catalog.has_table("users"))
        self.assertFalse(catalog.has_table("secret_table"))

    def test_sensitive_column_detection(self):
        catalog = SchemaCatalog.from_sqlite(self.db)
        self.assertTrue(catalog.is_sensitive("phone"))
        self.assertTrue(catalog.is_sensitive("id_card"))
        self.assertFalse(catalog.is_sensitive("amount"))
        self.assertFalse(catalog.is_sensitive("order_date"))


class SemanticRegistryTest(unittest.TestCase):
    def test_match_picks_best_metric(self):
        registry = build_default_registry()
        self.assertEqual(registry.match("各地区订单量占比").id, "region_orders")
        self.assertEqual(registry.match("最近每月的销售额是多少").id, "monthly_sales")
        self.assertIsNone(registry.match("今天天气如何"))

    def test_get_unknown_raises(self):
        registry = build_default_registry()
        with self.assertRaises(KeyError):
            registry.get("no_such_metric")


if __name__ == "__main__":
    unittest.main()
