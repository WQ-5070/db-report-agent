"""日志模块测试：结构化格式输出到 stderr。"""
import contextlib
import io
import unittest

from dbreport.core.log import log


class LogTest(unittest.TestCase):
    def test_log_format_with_trace_and_fields(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            log("轻路径命中", trace="ab12cd34", metric="region_orders")
        line = buf.getvalue().strip()
        self.assertIn("[INFO]", line)
        self.assertIn("trace=ab12cd34", line)
        self.assertIn("metric=region_orders", line)

    def test_trace_placed_first(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            log("消息", trace="t1")
        line = buf.getvalue().strip()
        self.assertLess(line.index("trace=t1"), line.index("消息"))


if __name__ == "__main__":
    unittest.main()
