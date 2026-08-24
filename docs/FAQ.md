# 常见问题与踩坑记录（FAQ）

> 本项目开发过程中遇到的真实问题与解决办法。写代码 / 改代码时先翻这里。

## 1. PyCharm 里 `import dbreport` 爆红（Unresolved reference）

- **现象**：`eval/run_eval.py`、`tests/` 里 `from dbreport... import ...` 标红，但运行时正常。
- **原因**：这些脚本顶部用 `sys.path.insert(...)` 在**运行时**把 `src/` 加进搜索路径；PyCharm 的静态分析**不会执行**这行代码，所以它不知道 `dbreport` 在哪。
- **解决**（任选其一）：
  1. 右键 `src` 目录 → **「将目录标记为」→「源代码根目录」**（英文界面：`Mark Directory as → Sources Root`），图标变蓝即生效；
  2. 或 `Ctrl+Alt+Shift+S`（项目结构）→ 选中项目 → 把 `src` 标记为 Sources；
  3. 或 `pip install -e .`（editable 安装），让 `dbreport` 成为解释器可见的包。
- **注意**：`sys.path.insert` 保留，它是「不安装包也能直接跑」的兜底。

## 2. `python -m unittest discover` 报 `TypeError: expected str, bytes or os.PathLike object, not NoneType`

- **现象**：在项目根**上一级**目录（如 `E:\projects`）运行测试命令时，报一个很误导人的 TypeError。
- **原因**：`tests` 目录不在当前目录下，unittest 找不到它时把它当模块导入、拿到 `None`，于是抛 TypeError（不是真正的类型错误）。
- **解决**：
  ```powershell
  cd E:\projects\db-report-agent
  python -m unittest discover -s tests -t .
  ```
  或在 PyCharm 里**右键 `tests` 目录 → Run 'Unittest in tests'**（自动以项目根为工作目录）。

## 3. `sqlite3.OperationalError: unable to open database file`

- **现象**：PyCharm 单文件运行 `eval/run_eval.py`（或 `cli.py`）时报错打不开库。
- **原因**：早期默认库路径 `demos/db-report-agent.db` 是**相对路径**，依赖「当前工作目录」；PyCharm 单文件运行时工作目录不是项目根，相对路径解析失败。
- **现状**：默认路径已改为**基于项目根解析的绝对路径**（`PROJECT_ROOT / "demos" / "db-report-agent.db"`），与工作目录无关，已修复。
- **注意**：自己传 `--db` 时，请传绝对路径或相对项目根的路径；库不存在时会给出「请先运行 `python demos/seed/generate_sample_data.py`」的提示。

## 4. Windows 下临时文件删不掉（`PermissionError: [WinError 32]`）

- **现象**：单元测试 `tearDown` 清理临时库时 `PermissionError`（文件被占用）。
- **原因**：Python 3.x 里 `with sqlite3.connect(...) as conn:` 的上下文管理器**只管理事务、不关闭连接**，连接对象要等 GC 才释放文件句柄——Windows 上表现为文件被锁。
- **现状**：已用 `contextlib.closing(sqlite3.connect(...))` 修复（`src/dbreport/executor.py`、`semantic.py`）。
- **注意**：以后**写任何 sqlite 连接代码，都必须显式关闭连接**（`closing` 或 `finally: conn.close()`），不要只用 `with sqlite3.connect()`。

## 5. 规则匹配对歧义措辞的局限

- **现象**：「各品类销售额对比」同时命中 `monthly_sales`（"销售额"）与 `category_sales`（"品类"），离线路径命中先定义的指标。
- **原因**：语义层的关键词匹配无法做意图级消歧。
- **解决**：
  - 意图级理解（歧义消解、拒绝"查手机号"这类危险意图）依赖 **LLM 重量路径**（`--llm`）；
  - 评测集 `eval/golden.json` 的正向用例使用无歧义措辞；这是规则匹配的已知边界，不试图在规则里"修好"。

## 6. 运行 Streamlit 演示看板

```powershell
pip install -r requirements.txt
python demos/seed/generate_sample_data.py
streamlit run demos/streamlit_app.py
```

PyCharm 里运行：`Run → Edit Configurations → + → Python`，Module name 填 `streamlit`，Parameters 填 `run demos/streamlit_app.py`。

## 7. 命令行/评测需要 `PYTHONPATH=src` 吗？

- `python -m dbreport.cli ...`：需要 `src` 在搜索路径（PowerShell: `$env:PYTHONPATH = "src"`），或 `pip install -e .` 后不需要；
- `python eval/run_eval.py`：**不需要**（脚本内置 `sys.path` 注入，单文件运行即可）。

## 8. git 基线与回退

- **v1.0.0** 是完整可用基线（`git tag v1.0.0`）。
- 之后的新需求都在 master 上迭代；做错 / 不想要时：
  ```powershell
  git checkout v1.0.0      # 回到完整基线
  git revert HEAD          # 撤销最近一次提交（保留历史）
  ```
