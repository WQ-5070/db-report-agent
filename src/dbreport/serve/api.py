"""最小 HTTP API 入口（serve 层）：证明"换入口不动 core"。

用法:
    python -m dbreport.serve.api                  # 启动 http://127.0.0.1:8730
    curl -X POST http://127.0.0.1:8730/ask \
         -H "Content-Type: application/json" \
         -d '{"question": "各地区订单量占比？"}'
    # 多轮对话：带上 session_id 续接同一会话
    -d '{"session_id": "abc123", "question": "那华东呢？"}'

标准库 http.server 实现，零第三方依赖；装配复用 serve.build_pipeline，
core 模块不知道外面是 CLI 还是 HTTP 在调。
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..core.errors import AgentError
from ..core.session import Session
from . import build_pipeline

HOST, PORT = "127.0.0.1", 8730

# 进程内会话存储：session_id → Session（多轮对话上下文，服务重启即清空）
_sessions: dict[str, Session] = {}


def report_to_dict(report) -> dict:
    """Report → 可 JSON 序列化的 dict（只取叶子字段，不泄露内部对象）。"""
    result = report.result
    return {
        "question": report.question,
        "metric_id": report.metric_id,
        "path": "llm" if report.metric_id == "llm_generated" else "light",
        "sql": report.sql,
        "row_count": result.row_count if result else None,
        "columns": list(result.columns) if result else None,
        "rows": [list(row) for row in result.rows] if result else None,
        "chart": report.chart,
        "report_md": report.report_md,
    }


class Handler(BaseHTTPRequestHandler):
    """POST /ask {question, llm?, session_id?} → 报告 JSON。pipeline 可被测试替换。"""

    pipeline = build_pipeline()

    def do_POST(self):
        if self.path != "/ask":
            self._send(404, {"error": {"code": "NOT_FOUND", "message": "not found"}})
            return
        try:
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0))))
            llm = self._build_llm(body.get("llm", False))
            session = self._get_session(body.get("session_id"))
            report = session.ask(body.get("question", ""), llm=llm)
            payload = report_to_dict(report)
            payload["session_id"] = session.id
            self._send(200, payload)
        except AgentError as exc:
            self._send(400, {"error": {"code": exc.code, "message": str(exc)}})
        except Exception as exc:
            self._send(500, {"error": {"code": "INTERNAL", "message": str(exc)}})

    @staticmethod
    def _build_llm(enabled: bool):
        """按请求参数构造 LLM（重量路径）；未启用返回 None。

        key 从 .env 读（OpenAICompatibleClient 构造时自动加载），
        缺失时抛 AgentError(CONFIG_MISSING) 由上层转结构化错误。
        """
        if not enabled:
            return None
        from ..core.llm import OpenAICompatibleClient
        return OpenAICompatibleClient()

    def _get_session(self, session_id: str | None) -> Session:
        """按 id 取会话；不存在则新建（多轮对话续接的关键）。"""
        session = _sessions.get(session_id or "")
        if session is None:
            session = Session(self.pipeline)
            _sessions[session.id] = session
        return session

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
