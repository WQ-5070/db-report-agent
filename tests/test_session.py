"""会话抽象测试：多轮历史注入进 SQL 生成 prompt。"""
import pathlib
import tempfile
import unittest

from tests._fixture import make_db

from dbreport.core.executor import QueryExecutor
from dbreport.core.guardrails import SqlGuardrails
from dbreport.core.pipeline import ReportPipeline
from dbreport.core.semantic import SchemaCatalog, SemanticRegistry
from dbreport.core.session import Session


class FakeLLM:
    def __init__(self, *responses: str):
        self._responses = list(responses)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._responses.pop(0) if self._responses else ""


class SessionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = pathlib.Path(self._tmp.name) / "t.db"
        make_db(str(db))
        self.pipeline = ReportPipeline(
            SemanticRegistry([]),  # 空注册表 → 必走重路径（LLM）
            SqlGuardrails(SchemaCatalog.from_sqlite(str(db))),
            QueryExecutor(str(db)))

    def tearDown(self):
        self._tmp.cleanup()

    def test_history_injected_into_second_turn_prompt(self):
        llm = FakeLLM("SELECT region_name FROM regions", "洞察1",
                      "SELECT region_name FROM regions", "洞察2")
        session = Session(self.pipeline)
        session.ask("华东有多少订单", llm=llm)
        session.ask("那华南呢", llm=llm)
        # 第二轮 SQL prompt（prompts[2]）应包含第一轮问题与"历史对话"引导
        self.assertIn("历史对话", llm.prompts[2])
        self.assertIn("华东有多少订单", llm.prompts[2])

    def test_first_turn_has_no_history(self):
        llm = FakeLLM("SELECT 1", "洞察")
        session = Session(self.pipeline)
        session.ask("订单总数", llm=llm)
        self.assertNotIn("历史对话", llm.prompts[0])


if __name__ == "__main__":
    unittest.main()
