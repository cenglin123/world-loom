# CHANGELOG

> 倒序排列，最新在前。操作：python scripts/changelog.py titles/show/add/recent

## 2026-06-24

### 归档记忆召回设计决策（暂缓实现）

#### 变更内容
- 结论：不建注意力层/不给记忆打重要性分喂给 agent；改用 RAG 检索，且只用于'选哪些记忆进上下文'。重要性走结构（L1/锚点/未解决问题=保证注入），相关性走 embedding 检索（排序填剩余预算），两条正交轴。触发阈值：L2 涨到~数百条再实现。落盘 docs/plans/deferred/memory-retrieval.md。

---

## 2026-06-22
### 初始化文档体系
建立面向 AI Agent 的四阶段小说写作文档体系：AGENTS.md（含同步副本）+ STRUCTURE.md + docs/ 层级 + 00_世界观/01_大纲/02_人物/03_正文/04_伏笔/05_复盘 目录 + scripts/ + .githooks/。方法论基础：AI 辅助小说写作自动化方法论（converge 迭代收敛 + 端木灵星传统技法 + 业界 AI 写作实践）。
