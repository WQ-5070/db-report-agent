import unittest

from dbreport.llm import OpenAICompatibleClient
from dbreport.pipeline import _extract_sql


class ExtractSqlTest(unittest.TestCase):
    def test_extracts_fenced_sql(self):
        text = "好的，这是 SQL：\n```sql\nSELECT COUNT(*) FROM orders\n```\n请执行"
        self.assertEqual(_extract_sql(text), "SELECT COUNT(*) FROM orders")

    def test_extracts_plain_sql(self):
        self.assertEqual(_extract_sql("SELECT * FROM users"), "SELECT * FROM users")

    def test_strips_comment_lines(self):
        text = "```sql\n-- 统计订单\nSELECT COUNT(*) AS n FROM orders\n```"
        self.assertEqual(_extract_sql(text), "SELECT COUNT(*) AS n FROM orders")


class OpenAICompatibleClientTest(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleClient(api_key="")

    def test_defaults_from_env(self):
        # 显式传参应覆盖环境变量读取，且无 key 时报错
        with self.assertRaises(ValueError):
            OpenAICompatibleClient(base_url="https://x/v1", api_key=None)


if __name__ == "__main__":
    unittest.main()
