"""LLM 接入：可插拔的补全接口。

对应 docs/DESIGN.md 第 8.3 节。用标准库 urllib 实现 OpenAI 兼容的
chat/completions 调用（DeepSeek / OpenAI 及各类兼容网关通用），零第三方依赖。
配置走环境变量，密钥不进代码：
    DBR_LLM_BASE_URL  （默认 https://api.deepseek.com/v1）
    DBR_LLM_API_KEY   （必填，否则无法发起调用）
    DBR_LLM_MODEL     （默认 deepseek-chat）
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Protocol


class LLMClient(Protocol):
    """最小契约：给定提示词，返回补全文本。"""

    def complete(self, prompt: str) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: int = 60):
        self._base_url = (base_url or os.getenv("DBR_LLM_BASE_URL")
                          or "https://api.deepseek.com/v1").rstrip("/")
        self._api_key = api_key or os.getenv("DBR_LLM_API_KEY") or ""
        self._model = model or os.getenv("DBR_LLM_MODEL") or "deepseek-chat"
        self._timeout = timeout
        if not self._api_key:
            raise ValueError(
                "未配置 LLM API Key：请设置环境变量 DBR_LLM_API_KEY，"
                "或不用 --llm 走离线模式（语义层预置口径）")

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
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
