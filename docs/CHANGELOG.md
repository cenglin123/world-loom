# CHANGELOG

> 倒序排列，最新在前。操作：python scripts/changelog.py titles/show/add/recent

## 2026-07-01

### 评议：角色扮演功能边界厘清与推进路线计划

#### 变更内容
- 对 docs/plans/active/20260628-角色扮演功能-边界厘清与推进路线.md 做一次外部评议（claude-opus，verdict ⚠️ 修订后可执行）。评议摘要 inline 追加至该计划 ## Agent 评议 段（source_body_hash 65efa7af0d9ea5ed）。核心：方向正确、结构扎实，但 3 处缺口待补——反向判据缺操作化测试、第二阶段 A/B 退出条件不可证伪且破盲风险被降级、负载性待细化项应上移为第二阶段前置。第一阶段可即刻启动，第二阶段需先补判据。完整评议在对话中给出，未单独落库。

---

## 2026-06-25

### 四阶段工作流留痕机制 v2（建议 1+2+4 经 ultraverge 收敛）

#### 变更内容
- 白名单豁免（缺 model 须 author:human）；_准备_ 阻断、_审查_/_审查后_ 提醒；抽 docs/style-locked.md 单独治理保护；治理清单单一数据源；_审查后_ schema 对齐 reviewer-protocol；诚实标注 --no-verify/commit-time-only 盲区

---

## 2026-06-24

### 归档记忆召回设计决策（暂缓实现）

#### 变更内容
- 结论：不建注意力层/不给记忆打重要性分喂给 agent；改用 RAG 检索，且只用于'选哪些记忆进上下文'。重要性走结构（L1/锚点/未解决问题=保证注入），相关性走 embedding 检索（排序填剩余预算），两条正交轴。触发阈值：L2 涨到~数百条再实现。落盘 docs/plans/deferred/memory-retrieval.md。

---

## 2026-06-22
### 初始化文档体系
建立面向 AI Agent 的四阶段小说写作文档体系：AGENTS.md（含同步副本）+ STRUCTURE.md + docs/ 层级 + 00_世界观/01_大纲/02_人物/03_正文/04_伏笔/05_复盘 目录 + scripts/ + .githooks/。方法论基础：AI 辅助小说写作自动化方法论（converge 迭代收敛 + 端木灵星传统技法 + 业界 AI 写作实践）。
