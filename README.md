# db-report-agent

> 一个**自动查询数据库并生成报表**的数据分析 Agent —— 用户用自然语言提问，系统自动生成安全可信的 SQL、图表与结论，最终交付可交互仪表盘/可导出报告。

- **详细生产级设计**：[`docs/DESIGN.md`](./docs/DESIGN.md)
- **常见问题与踩坑记录**：[`docs/FAQ.md`](./docs/FAQ.md)
- **最小可运行演示**：[`demos/`](./demos/)
- **技术栈**：Python · LangGraph · MySQL/PostgreSQL · Streamlit/Dash · Docker Compose
- **核心价值**：本地一条命令即可演示（`docker compose up`），且设计上可**生产落地**（语义层 + 强安全护栏 + 评测回归 + 全链路可观测），不是一次性玩具。

---

## 为什么值得看这个项目

市面上很多"text-to-SQL"是**演示级**：靠提示词"蒙"，不安全、不可评估、不可复现。本项目把 **"演示"与"生产"的分水岭** 做进了设计：

| 能力 | Demo 水平 | 本项目（生产级） |
|---|---|---|
| SQL 正确性 | 靠提示词 | 结构化语义层 + schema 感知 + 校验器 + 评测回归 |
| 数据安全 | 直接连库 | 强只读 + 行/列级权限 + 脱敏 + 审计 + 白名单（代码层强制） |
| 可复现 | 每次漂移 | 确定性、幂等、可回放（问题+SQL+参数+版本） |
| 可评估 | 无 | 黄金评测集 + 执行准确率/幻觉率回归 + LLM-as-judge |
| 可观测 | 无 | 全链路 tracing、耗时/成本/可信 meter |
| 失败处理 | 报错 | 重试、降级、HITL 复核、标准错误码 |

详情见 **[`docs/DESIGN.md`](./docs/DESIGN.md)**，其中第 5 节调研了 Canner/WrenAI、db-agent、nl2sql、LangGraph 多智能体报告管线等开源成品作为参考。

---

## 架构（一句话版）

```
接入层(Web/API/CLI/定时) → 编排层(Agent:LangGraph 状态机)
    → 语义层(指标/维度/口径 Registry + schema 感知)
    → 执行层(强只读连接 + 缓存 + 限流)
    → 呈现层(交互看板 / PDF / Excel / Markdown 报告)
横切：安全治理 · 全链路可观测 · 评测回归
```

完整架构图与流程图见 DESIGN.md 第 6、7 节。

---

## 快速开始（本地一键演示）

### 方式 A：零依赖快速试跑（SQLite 样例库）

不需要装数据库/容器，仅需 Python 3.11+（**已在本机 Python 3.13 验证**）：

```bash
# 1) 安装依赖
pip install -r requirements.txt

# 2) 生成样例库（SQLite）
python demos/seed/generate_sample_data.py

# 3) 启动交互式看板
streamlit run demos/streamlit_app.py
```

浏览器打开后，在左侧选择问题或直接输入，就能看到：**自然语言 → SQL → 图表 → 自然语言结论** 的完整链路，并展示生成的 SQL。

### 在 PyCharm 中开发（Python 3.13）

1. **打开项目**：`File → Open` 选择 `E:\projects\db-report-agent`（整个目录作为项目根）。
2. **配置解释器**：`Settings → Project: db-report-agent → Python Interpreter → Add Interpreter → Add Local Interpreter`，选择 **Python 3.13**（PyCharm 检测到根目录 `requirements.txt` 会提示安装依赖，点 Install 即可，或终端执行 `pip install -r requirements.txt`）。
3. **生成样例库**：在项目树中右键 `demos/seed/generate_sample_data.py → Run`。
4. **运行看板（推荐配置）**：`Run → Edit Configurations → + → Python`，填：
   - Module name：`streamlit`
   - Parameters：`run demos/streamlit_app.py`
   - Python interpreter：上面配好的 3.13 环境
   保存后点 Run，浏览器打开 `http://localhost:8501`。
5. **验证**：左侧选一个预置问题，应看到 SQL、图表与洞察；输入"删除所有订单"应被护栏拦截。
6. **消除 `import dbreport` 爆红**：右键 `src` 目录 → **「将目录标记为」→「源代码根目录」**（英文：`Mark Directory as → Sources Root`）。这样 `eval/`、`tests/` 里 `from dbreport ... import` 的红色波浪线消失。
7. **运行单元测试**（二选一）：
   - 在项目树中右键 `tests` 目录 → `Run 'Unittest in tests'`（PyCharm 自动以项目根为工作目录）；
   - 或终端先 `cd E:\projects\db-report-agent` 再执行 `python -m unittest discover -s tests -t .`。
   - ⚠️ **不要在项目根的上一级目录跑**：unittest 找不到 `tests` 时会抛误导性的 `TypeError: ... not NoneType`。

> 更多坑（相对路径、sqlite 连接泄漏、歧义措辞等）见 [`docs/FAQ.md`](./docs/FAQ.md)。

### 方式 B：Docker Compose（Postgres 版，贴近生产形态）

```bash
cd demos
docker compose up          # 内置样例库 + 看板 + agent
# 打开 http://localhost:8501
```

---

## 演示脚本（3 分钟让对方建立信任）

1. 问一个**简单问题** → 看"自然语言→SQL→图表"，并**贴出生成的 SQL**。
2. 问一个**复杂问题**（多表 + 环比 + 自动选图）→ 看**自然语言洞察**可溯源到 SQL/口径。
3. 故意问**越权/写操作**（如"删除所有订单"、"看所有人的身份证号"）→ 系统**拒绝**并解释，证明安全不是摆设。
4. 打开一次请求的 **tracing** → 看 问题→SQL→结果→图表 全链路与耗时/成本。
5. 跑一条**评测** → 展示 accuracy / hallucination / unsafe rate 指标。

---

## 目录结构

```text
db-report-agent/
├── README.md              # 本文件
├── pyproject.toml         # 包定义 + 可选依赖组（demo / prod）
├── requirements.txt       # 最小演示依赖（PyCharm 识别，创建 venv 用）
├── docs/
│   └── DESIGN.md          # 生产级详细设计文档
├── src/
│   └── dbreport/          # 完整 Agent（v1.0.0，标准库实现）
│       ├── config.py      # .env 加载（标准库，密钥不进 Git）
│       ├── semantic.py    # 语义层：指标/口径 Registry + Schema 目录
│       ├── guardrails.py  # 护栏：只读/单语句/LIMIT/白名单/敏感列
│       ├── executor.py    # 执行层：只读连接(PRAGMA query_only) + 结果缓存
│       ├── reporting.py   # 呈现层：图表 spec + Markdown 报告(含血缘)
│       ├── pipeline.py    # 编排层：轻/重双路径（LLM 生成 SQL→护栏重试→洞察）
│       ├── llm.py         # LLM 接入：OpenAI 兼容客户端（标准库，自动读 .env）
│       └── cli.py         # 命令行入口
├── .env.example           # 环境配置模板（上传；真实 .env 被忽略，不上传）
├── demos/                 # 最小可运行 UI 演示（Streamlit）
│   ├── docker-compose.yml
│   ├── seed/
│   │   ├── schema.sql
│   │   └── generate_sample_data.py
│   └── streamlit_app.py
├── eval/                  # 评测：黄金集 + 指标回归（命中/执行/护栏拦截）
│   ├── golden.json
│   └── run_eval.py
└── tests/                 # 单元测试（unittest，自包含临时库）
```

---

## 生产骨架（src/）快速上手

生产骨架与 `demos/` 同源：demos 是"能演示"的 UI，`src/` 是可进生产的核心（对应 DESIGN.md 第 8 节）。

```bash
# 以下命令可在任意目录执行：默认数据库路径已基于项目根解析，
# 不依赖当前工作目录（PyCharm 单文件运行也不会报 unable to open database file）
# 1) 安装本地包（无第三方依赖、纯本地秒装；装后 dbreport 可被解释器识别，消除 PyCharm 报红）
pip install -e .

# 2) 生成样例库（如果还没生成）
python demos/seed/generate_sample_data.py

# 3) 命令行问数据（装了包后无需 PYTHONPATH）
python -m dbreport.cli "各地区订单量占比？"      # 轻路径：语义层预置口径
python -m dbreport.cli "统计一下订单总数" --llm  # 重量路径：LLM 生成 SQL + 洞察
python -m dbreport.cli "删除所有订单"            # 护栏拒绝，返回可读错误

# 4) 跑单元测试（28 个用例：护栏/语义/执行/重量路径/评测）
python -m unittest discover -s tests -t .

# 5) 跑离线评测（黄金集回归：命中率/执行成功率/护栏拦截率）
python eval/run_eval.py
```

**分层对应**：`semantic.py`（语义层）→ `guardrails.py`（护栏）→ `executor.py`（执行）→ `reporting.py`（呈现）→ `pipeline.py`（编排：轻/重双路径）→ `llm.py`（LLM 接入，可插拔）。核心全用标准库，无第三方依赖；`sqlglot`/`LangGraph` 等生产增强见 `pyproject.toml` 的 `prod` 可选组（按 DESIGN.md 第 21.2 节引入）。

## LLM 接入（重量路径）

未命中语义层的问题，由 LLM 动态生成 SQL（schema 感知）→ 护栏校验（失败带反馈重试 ≤3 次）→ 执行 → LLM 生成洞察 → 自动选图出报告。**密钥不进代码、不进 Git**。

**推荐方式：用 `.env`**

```powershell
# 1) 复制模板为 .env，填入你的真实 key（.env 已被 .gitignore 忽略，不会上传）
copy .env.example .env

# 2) 编辑 .env：把 DBR_LLM_API_KEY 换成你的真实值（可选改 base_url / model）
DBR_LLM_API_KEY=sk-你的真实key

# 3) 跑重量路径（代码会自动读取项目根的 .env）
python -m dbreport.cli "统计一下订单总数" --llm
```

**或**直接用环境变量（等价，优先级更高）：

```powershell
$env:DBR_LLM_API_KEY = "sk-你的真实key"
python -m dbreport.cli "统计一下订单总数" --llm
```

> 兼容任意 OpenAI 格式的 chat/completions 服务（OpenAI / DeepSeek / 各类网关）。`.env.example` 模板会上传，`.env` 真实配置不会。

## 评测（黄金集回归）

```bash
python eval/run_eval.py          # 离线：轻路径 + 护栏（无需 LLM）
python eval/run_eval.py --llm    # 重量路径（需在 .env 配 DBR_LLM_API_KEY）
```

指标：**轻路径命中率**（语义匹配是否选对指标）、**执行成功率**（SQL 过护栏并成功执行）、**护栏拦截率**（unsafe 用例必须全部被拒，期望 100%）。任一 unsafe 放行或 light 失败 → 退出码 1（可接入 CI 阻断回归）。

**已知局限（如实说明）**：规则匹配对**歧义措辞**能力有限——例如"各品类销售额对比"同时含"销售额"与"品类"两个指标关键词，离线路径会命中先定义的指标；意图级理解（歧义消解、拒绝"查手机号"这类危险意图）依赖 LLM 重量路径（`--llm`）。这正是评测集与重量路径存在的意义。

---

## 参考开源项目（本设计的对标调研）

- [Canner / WrenAI — GenBI 语义上下文层 text-to-SQL](https://github.com/Canner/WrenAI)
- [db-agent/db-agent — 生产级 text-to-SQL，安全护栏 + schema 感知](https://github.com/db-agent/db-agent)
- [nadeem4/nl2sql — 企业级多 Agent NL→SQL，schema 检索 + 验证 + 可观测](https://github.com/nadeem4/nl2sql)
- [ishaanchowdhury1/Multi-Agent-AI-System-for-Automated-Database-Insights — LangGraph Analyst→Expert→Reviewer 报告管线](https://github.com/ishaanchowdhury1/Multi-Agent-AI-System-for-Automated-Database-Insights)
- [spring-ai-alibaba/DataAgent — Spring 生态数据问答 Agent](https://github.com/spring-ai-alibaba/DataAgent)
- [SAMithila/nl-db-agent — Agentic RAG，路由 SQL/文档，0% SQL 幻觉](https://github.com/SAMithila/nl-db-agent)

---

## 本地开发说明

- `src/dbreport/` 是**完整 Agent**（v1.0.0）：语义层 / 护栏 / 执行层 / 呈现层 / 编排层（轻+重双路径）/ LLM 接入，标准库实现，28 个单元测试 + 评测回归兜底；后续演进以 [`docs/DESIGN.md`](./docs/DESIGN.md) 为蓝图。
- `demos/` 是**最小可运行 UI**（Streamlit），证明"能演示"；后续可改为消费 `src/` 的 pipeline 输出（替换内置规则匹配）。
- **版本基线与回退**：`git tag v1.0.0` 是完整基线。之后任何新需求在 master 上迭代；做错/不想要时 `git revert` 或切回 `v1.0.0` 即可回到完整可用的版本。

---

## License

（请根据实际选择：建议 **Apache-2.0** / **MIT**。欢迎 issue 与 PR。）

_本目录由 `db-report-agent` 项目维护。_
