import io
import os
import unittest
import urllib.error
from unittest import mock

from dbreport.llm import LLMError, OpenAICompatibleClient
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
        # 隔离项目 .env：清空环境变量，且不加载 .env，模拟"未配置任何 key"
        with mock.patch("dbreport.llm.load_dotenv"):
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    OpenAICompatibleClient(api_key="")

    def test_defaults_from_env(self):
        with mock.patch("dbreport.llm.load_dotenv"):
            with mock.patch.dict(os.environ, {}, clear=True):
                with self.assertRaises(ValueError):
                    OpenAICompatibleClient(base_url="https://x/v1", api_key=None)

    def test_http_error_becomes_readable_llm_error(self):
        client = OpenAICompatibleClient(api_key="sk-test", base_url="https://x/v1")
        http_error = urllib.error.HTTPError(
            "https://x/v1/chat/completions", 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"your api key is invalid"}}'))
        with mock.patch("urllib.request.urlopen", side_effect=http_error):
            with self.assertRaises(LLMError) as ctx:
                client.complete("hi")
        self.assertIn("401", str(ctx.exception))
        self.assertIn("invalid", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
