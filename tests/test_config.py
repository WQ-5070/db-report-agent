import os
import tempfile
import unittest

from dbreport.config import load_dotenv


class LoadDotenvTest(unittest.TestCase):
    KEYS = ("DBR_LLM_API_KEY", "DBR_LLM_MODEL", "DBR_LLM_BASE_URL")

    def setUp(self):
        self.addCleanup(self._clean_env)

    def _clean_env(self):
        for key in self.KEYS:
            os.environ.pop(key, None)

    def _write_env(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".env", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        self.addCleanup(os.unlink, path)
        return path

    def test_loads_key_values(self):
        path = self._write_env("DBR_LLM_API_KEY=sk-test\nDBR_LLM_MODEL=deepseek-chat\n")
        load_dotenv(path)
        self.assertEqual(os.getenv("DBR_LLM_API_KEY"), "sk-test")
        self.assertEqual(os.getenv("DBR_LLM_MODEL"), "deepseek-chat")

    def test_does_not_override_existing_variable(self):
        os.environ["DBR_LLM_API_KEY"] = "sk-existing"
        self.addCleanup(os.environ.pop, "DBR_LLM_API_KEY", None)
        path = self._write_env("DBR_LLM_API_KEY=sk-new\n")
        load_dotenv(path)
        self.assertEqual(os.getenv("DBR_LLM_API_KEY"), "sk-existing")  # 已存在，不覆盖

    def test_ignores_comments_blank_and_quotes(self):
        path = self._write_env(
            "# 注释\n\nDBR_LLM_MODEL = \"deepseek-chat\"\nBAD_LINE\n")
        load_dotenv(path)
        self.assertEqual(os.getenv("DBR_LLM_MODEL"), "deepseek-chat")
        self.assertNotIn("BAD_LINE", os.environ)

    def test_missing_file_is_noop(self):
        load_dotenv("definitely/not/exists.env")  # 不应抛异常


if __name__ == "__main__":
    unittest.main()
