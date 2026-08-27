"""最小 HTTP API 入口（serve 层）：证明"换入口不动 core"。

用法:
    python -m dbreport.api                          # 启动 http://127.0.0.1:8730
    curl -X POST http://127.0.0.1:8730/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "各地区订单量占比？"}'

标准库 http.server 实现，零第三方依赖；装配复用 serve.build_pipeline，
core 模块不知道外面是 CLI 还是 HTTP 在调。
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .serve import build_pipeline

HOST, PORT = "127.0.0.1", 8730


def report_to_dict(report) -> dict:
    """Report → 可 JSON 序列化的 dict（只取叶子字段，不泄露内部对象）。"""
    result = report.result
    return {
        "question": report.question,
        "metric_id": report.metric_id,
        "sql": report.sql,
        "row_count": result.row_count if result else None,
        "columns": list(result.columns) if result else None,
        "rows": [list(row) for row in result.rows] if result else None,
        "chart": report.chart,
        "report_md": report.report_md,
    }


class Handler(BaseHTTPRequestHandler):
    """POST /ask {question} → 报告 JSON。pipeline 可被测试替换（类属性）。"""

    pipeline = build_pipeline()

    def do_POST(self):
        if self.path != "/ask":
            self._send(404, {"error": "not found"})
            return
        try:
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0))))
            report = self.pipeline.ask(body.get("question", ""))
            self._send(200, report_to_dict(report))
        except Exception as exc:
            self._send(400, {"error": str(exc)})

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:  # 静默访问日志，保持输出干净
        pass


def main() -> None:
    print(f"db-report-agent API: http://{HOST}:{PORT}/ask")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
