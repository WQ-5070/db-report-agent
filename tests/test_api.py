"""API 测试：起临时 HTTP server，POST /ask 验证"换入口不动 core"。"""
import json
import os
import pathlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

from tests._fixture import make_db

from dbreport.serve.api import Handler
from dbreport.serve import build_pipeline


class ApiTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db = pathlib.Path(self._tmp.name) / "test.db"
        make_db(str(db))
        Handler.pipeline = build_pipeline(str(db))  # 类属性可替换 → 测试自包含
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self._tmp.cleanup()

    def _post(self, payload: dict) -> dict:
        request = urllib.request.Request(
            f"{self.base}/ask",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_ask_returns_report(self):
        data = self._post({"question": "各地区订单量占比？"})
        self.assertEqual(data["metric_id"], "region_orders")
        self.assertEqual(data["row_count"], 1)
        self.assertIn("region", data["columns"])

    def test_unknown_route_404(self):
        request = urllib.request.Request(
            f"{self.base}/nope",
            data=b"{}", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 404)

    def test_unmatched_question_returns_error_code(self):
        request = urllib.request.Request(
            f"{self.base}/ask",
            data=json.dumps({"question": "统计一下订单总数"}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 400)
        body = json.loads(ctx.exception.read().decode("utf-8"))
        self.assertEqual(body["error"]["code"], "SEMANTIC_NOT_FOUND")

    def test_session_id_continues_multi_turn(self):
        first = self._post({"question": "各地区订单量占比？"})
        self.assertTrue(first["session_id"])
        second = self._post({"session_id": first["session_id"],
                             "question": "各地区订单量占比？"})
        self.assertEqual(second["session_id"], first["session_id"])

    def test_llm_request_without_key_returns_config_error(self):
        """请求 llm=true 但无 key → 400 CONFIG_MISSING（不泄露配置细节）。"""
        with mock.patch("dbreport.core.llm.load_dotenv"):
            with mock.patch.dict(os.environ, {}, clear=True):
                request = urllib.request.Request(
                    f"{self.base}/ask",
                    data=json.dumps({"question": "统计一下订单总数",
                                     "llm": True}).encode("utf-8"),
                    headers={"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(request)
                self.assertEqual(ctx.exception.code, 400)
                body = json.loads(ctx.exception.read().decode("utf-8"))
                self.assertEqual(body["error"]["code"], "CONFIG_MISSING")


if __name__ == "__main__":
    unittest.main()
