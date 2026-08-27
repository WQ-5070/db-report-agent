"""错误码体系：稳定错误码（程序化处理契约）+ AgentError 基类。

调用方靠 `code` 分支处理（如 API 返回结构化错误），靠 message 读原因。
错误码是外部契约——一旦发布，改动会破坏调用方，新增只加不改。
"""
from __future__ import annotations


class ErrorCode:
    SEMANTIC_NOT_FOUND = "SEMANTIC_NOT_FOUND"  # 语义层未匹配到指标
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"        # LLM 调用失败/不可用
    CONFIG_MISSING = "CONFIG_MISSING"          # 缺必要配置（如 API key）
    ASSET_MISSING = "ASSET_MISSING"            # 指标资产文件缺失
    ASSET_INVALID = "ASSET_INVALID"            # 指标资产格式错误（缺字段/id 重复）


class AgentError(RuntimeError):
    """Agent 业务异常基类：携带稳定错误码。"""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code
