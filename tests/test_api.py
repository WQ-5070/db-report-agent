"""API 测试：起临时 HTTP server，POST /ask 验证"换入口不动 core"。"""
import json
import pathlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

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


if __name__ == "__main__":
    unittest.main()
