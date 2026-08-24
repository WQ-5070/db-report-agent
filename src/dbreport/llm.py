"""LLM 接入：可插拔的补全接口。

对应 docs/DESIGN.md 第 8.3 节。用标准库 urllib 实现 OpenAI 兼容的
chat/completions 调用（DeepSeek / OpenAI 及各类兼容网关通用），零第三方依赖。
配置走环境变量，密钥不进代码：
    DBR_LLM_BASE_URL  （默认 https://api.deepseek.com/v1）
    DBR_LLM_API_KEY   （必填，否则无法发起调用）
    DBR_LLM_MODEL     （默认 deepseek-chat）

这些变量可从项目根 .env 读取（构造时自动加载，见 config.load_dotenv）。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Protocol

from .config import load_dotenv


class LLMError(RuntimeError):
    """LLM 调用失败（含可读信息，不暴露密钥）。"""


class LLMClient(Protocol):
    """最小契约：给定提示词，返回补全文本。"""

    def complete(self, prompt: str) -> str: ...


def _error_detail(exc: urllib.error.HTTPError) -> str:
    """从 HTTPError 响应体中提取 API 错误信息（如 DeepSeek 的 error.message）。"""
    try:
        data = json.loads(exc.read().decode("utf-8", "ignore"))
        message = data.get("error", {}).get("message") or data.get("message")
        return str(message)
    except Exception:
        return str(exc.reason)


class OpenAICompatibleClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: int = 60):
        load_dotenv()  # 从项目根 .env 读取配置（环境变量优先级更高）
        self._base_url = (base_url or os.getenv("DBR_LLM_BASE_URL")
                          or "https://api.deepseek.com/v1").rstrip("/")
        self._api_key = api_key or os.getenv("DBR_LLM_API_KEY") or ""
        self._model = model or os.getenv("DBR_LLM_MODEL") or "deepseek-chat"
        self._timeout = timeout
        if not self._api_key:
            raise ValueError(
                "未配置 LLM API Key：请在 .env 里设置 DBR_LLM_API_KEY "
                "（或环境变量），或不用 --llm 走离线模式")

    def complete(self, prompt: str) -> str:
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        request = urllib.request.Request(
            f"{self._base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise LLMError(f"LLM 接口返回 HTTP {exc.code}: {_error_detail(exc)}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM 接口无法访问（{exc.reason}）：请检查网络与 DBR_LLM_BASE_URL") from exc
        return data["choices"][0]["message"]["content"].strip()
