# 常见问题与踩坑记录（FAQ）

> 本项目开发过程中遇到的真实问题与解决办法。写代码 / 改代码时先翻这里。

## 1. PyCharm 里 `import dbreport` 爆红（Unresolved reference）

- **现象**：`eval/run_eval.py`、`tests/` 里 `from dbreport... import ...` 标红，但运行时正常。
- **原因**：PyCharm 的 Python 解释器找不到 `dbreport` 这个包（`src` 既没被标记为源码根，也没被安装成包）。
- **解决**（**推荐：① `pip install -e .`，一劳永逸**）：
  1. **在 PyCharm 终端（用 Python 3.12 解释器）执行 `pip install -e .`**。项目无第三方依赖、纯本地秒装；装完后 `dbreport` 成为解释器可见的正式包，**所有报红消失**，且 `from dbreport...` 可以写回模块顶部、代码最干净（本仓库 `eval/run_eval.py` 已是这种写法），CLI 也不再需要 `PYTHONPATH`。
  2. 或不装包，把 `src` 标记为源码根：右键 `src` → **「将目录标记为」→「源代码根目录」**（英文：`Mark Directory as → Sources Root`）。
  3. 或 `Ctrl+Alt+Shift+S`（项目结构）→ 选中项目 → 把 `src` 标记为 Sources。
- **注意**：`pip install -e .` 之后，`eval/run_eval.py` 里已无 `sys.path` 补丁、无 `# noqa`，模块顶部就是标准库 + 顶层 `from dbreport...`。

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

- **装了包（`pip install -e .`）后都不需要**：
  - `python -m dbreport.serve.cli "各地区订单量占比？"` 直接跑；
  - `python eval/run_eval.py` 直接跑（`from dbreport...` 在模块顶部，解释器可见）。
- **没装包**时：`python -m dbreport.serve.cli` 需 `$env:PYTHONPATH = "src"`；`run_eval.py` 需装包，测试自包含会自动注入 `src`。

## 8. git 基线与回退

- **v1.0.0** 是完整可用基线（`git tag v1.0.0`）。
- 之后的新需求都在 master 上迭代；做错 / 不想要时：
  ```powershell
  git checkout v1.0.0      # 回到完整基线
  git revert HEAD          # 撤销最近一次提交（保留历史）
  ```

## 9. 密钥/环境变量怎么不进 Git？（.env 封装）

- **模板**：`.env.example` 上传仓库（含占位说明，无真实值）。
- **真实配置**：复制为 `.env`，**已被 `.gitignore` 忽略**（`.env`、`.env.*`），不会提交、不会在 GitHub 暴露。
- **自动加载**：`dbreport/config.py` 的 `load_dotenv()`（标准库实现，零依赖）在构造 `OpenAICompatibleClient` 时自动读取项目根 `.env` 并注入环境变量；**已存在的环境变量优先**（不会被 `.env` 覆盖）。
- **验证**：
  ```powershell
  copy .env.example .env     # Windows
  git status                 # 应看不到 .env，只能看到 .env.example
  ```
- 多个 `.env` 变体（如 `.env.local`）也已在 `.gitignore` 中忽略。

## 10. `closing(sqlite3.connect())` 只关连接、不提交事务（数据写进去却读不出来）

- **现象**：`train()` 写入后 `similar()` 检索为空，单测断言 `0 != 1`；代码看着"写进去了"，下次连接却读不到。
- **原因**：`contextlib.closing` 只负责 `close()`，**不负责 `commit()`**。sqlite3 默认开启事务，INSERT 后不提交，连接关闭时事务回滚，数据静默丢失。
- **解决**：写操作（INSERT/UPDATE/DDL）后**显式 `conn.commit()`**；读操作不需要。
- **注意**：这是第 4 条（`with sqlite3.connect()` 不关连接）的**孪生坑**——一个管"不关"，一个管"不提交"。经验公式：**任何 sqlite3 写代码 = `closing`（关连接）+ `commit()`（写操作提交），一个都不能少**（`src/dbreport/memory.py` 即此写法）。

## 11. `unable to open database file` 的另一诱因：父目录不存在

- **现象**：`sqlite3.connect('.dbreport/memory.db')` 报 `unable to open database file`，路径看起来没问题。
- **原因**：sqlite **不会自动创建父目录**（`.dbreport/`），目录不存在就直接报错——这是与第 3 条（相对路径依赖工作目录）**不同的诱因**，同一个报错。
- **解决**：连接前 `pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)`（`memory.py` 构造即此写法）。
- **注意**：默认库路径若含自定义子目录，务必先建目录；报错文案相同，排查时先分"路径错"还是"目录不存在"。

## 12. 移动模块目录后 `PROJECT_ROOT` 错位（默认路径多了一层 src）

- **现象**：把 `config.py` 从 `src/dbreport/` 移到 `src/dbreport/core/` 后，所有默认路径（库/指标/记忆/.env）变成 `src\demos\...`、找不到文件。
- **原因**：`PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[2]` 按"文件所在层级"推算；**模块每下沉一层目录，parents 索引就要 +1**（core/config.py 需要 `parents[3]`）。
- **解决**：`src/dbreport/core/config.py` 用 `parents[3]`（代码注释已提醒）。**移动目录层级时必须同步检查 `config.py` 的 parents 索引**，这是本次 core/serve 分层踩到的坑。
