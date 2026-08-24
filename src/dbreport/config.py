"""轻量配置加载：读取项目根的 .env 文件并注入环境变量。

用标准库实现（零第三方依赖），只做"KEY=VALUE"解析，不覆盖已存在的变量。
真实密钥放本地 .env（已被 .gitignore 忽略），模板 .env.example 才进仓库。
"""
from __future__ import annotations

import os
import pathlib

# 项目根（src/dbreport/config.py -> parents[2]）
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def load_dotenv(path: str | None = None) -> None:
    """读取 .env 并注入 os.environ；已存在的变量不被覆盖（环境变量优先）。"""
    env_file = pathlib.Path(path) if path else DEFAULT_ENV_PATH
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = _unquote(value.strip())
        if key:
            os.environ.setdefault(key, value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value
