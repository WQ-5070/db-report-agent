"""测试包初始化：
- 使 unittest discover 能从 src/ 导入 dbreport 包；
- 使测试文件能以顶层模块名导入同目录的 _fixture。
"""
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
