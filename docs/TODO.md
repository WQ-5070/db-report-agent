# 待办清单（TODO）

> 走查/开发中发现的"现在不改、将来要改"的项。优先级由实际需求触发时才做。

## 代码走查记录（2026-08-28）

- [ ] **CLI 提示语用户化**（`serve/cli.py`）：「数据库不存在」提示当前给的是开发命令
  （`python demos/seed/generate_sample_data.py`），对"使用者=开发者"的个人项目合理；
  若将来面向真实用户，应改为用户语言（如"系统初始化未完成，请联系管理员"）
  或库不存在时自动初始化。

- [ ] **cli.py docstring 命令过时**（`serve/cli.py` 文件头）：示例命令还是分层前的
  `python -m dbreport.cli`，应更新为 `python -m dbreport.serve.cli`。
