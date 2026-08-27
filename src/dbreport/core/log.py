"""轻量结构化日志：print 到 stderr，key=value 平铺可 grep（零依赖）。

一条日志长这样：`[INFO] 轻路径命中指标 trace=ab12cd34 metric=region_orders`
trace 永远放最前——同一请求的所有日志用它串成一条链。
"""
import sys


def log(message: str, level: str = "INFO", **fields) -> None:
    """打一条结构化日志；trace 字段紧跟级别后，便于一行内一眼串联。"""
    parts = [f"[{level}]"]
    trace = fields.pop("trace", None)
    if trace:
        parts.append(f"trace={trace}")
    parts.append(message)
    parts.extend(f"{k}={v}" for k, v in fields.items())
    print(" ".join(parts), file=sys.stderr)
