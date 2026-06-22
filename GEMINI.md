# 小说写作 AI 协作规范

> `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` 内容一致；只编辑本文件，另两个由脚本同步。
> 本文件是主管 agent 的操作准则与导航入口——精简，只放规则和指针。

## 项目概述

一部正在创作中的长篇小说。Agent 的角色是**受托的执行者 + 质量守护者**——按四阶段工作流推进剧情，用宪法审查 + 迭代收敛防止漂移（吃书）。

不可改动的硬设定在 `世界观/核心设定.md`，任何人（含 agent 和用户）要改都必须走多轮独立评审。

## 就绪自检（接到"推进剧情"任务前强制执行）

以下三项任一不满足 → **拒绝推进正文，提示用户先完成设定**：

1. `世界观/核心设定.md` 的世界法则段**非空**（不是"待填写"）
2. `大纲/主线.md` 的主线一句话**已填写**
3. `人物/_索引.md` 角色清单**至少有一个实际角色**（不含示例/模板行）

> 此哨兵是硬约束——宪法审查、写前准备、复盘 converge 全部依赖这三项有实质内容。设定未就绪时推进正文产生的漂移无法被任何机制兜住。

## 同步声明

- 检查：`python scripts/agent_links.py check`
- 修复：`python scripts/agent_links.py repair`
- 强制覆盖：`python scripts/agent_links.py repair --force`
- 模式：copy

## 信息导航

| 需要什么 | 去哪找 |
|---------|--------|
| 文档总索引 | [STRUCTURE.md](STRUCTURE.md) |
| 项目总览 + 世界观梗概 + 关键设计决策 | [docs/overview.md](docs/overview.md) |
| 叙述约定（视角/时态/文风/端木技法） | [docs/writing-style.md](docs/writing-style.md) |
| AI 写作已知陷阱（本项目专属） | [docs/pitfalls.md](docs/pitfalls.md) |
| 一致性审计清单 | [docs/audit-checklist.md](docs/audit-checklist.md) |
| 复杂任务计划 | [docs/plans/](docs/plans/) |
| 当前任务状态 | [docs/CURRENT.md](docs/CURRENT.md) |
| 变更记录 | [CHANGELOG.md](CHANGELOG.md) |
| 世界观·硬核心（locked，改需治理审批） | [世界观/核心设定.md](世界观/核心设定.md) |
| 世界观·外围（可扩展） | [世界观/外围设定.md](世界观/外围设定.md) |
| 故事大纲（主线 + 分卷） | [大纲/主线.md](大纲/主线.md) |
| 人物（人设 / 记忆 / 关系三层框架） | [人物/_索引.md](人物/_索引.md) |
| 伏笔登记（open/closed 状态机） | [伏笔/伏笔登记表.md](伏笔/伏笔登记表.md) |
| 正文章节 | [正文/README.md](正文/README.md) |
| 阶段性复盘记录 + converge 协议 | [复盘/README.md](复盘/README.md) → [复盘/reviewer-protocol.md](复盘/reviewer-protocol.md) |
| 本方法论依据 | 四阶段工作流（见下方"四阶段工作流"节），融合 converge 迭代收敛质量控制 + 端木灵星传统写作技法 + 业界 AI 长篇写作实践 |

## 行为规则

### Compact 恢复（强制）

若上下文含 "continued from a previous conversation"，在继续任何实质性工作前：

1. 读 [docs/CURRENT.md](docs/CURRENT.md) — 确认当前任务状态
2. 上述步骤完成前，**禁止写操作、禁止有副作用的判断**

### 硬约束（分两级）

**已脚本化 — 有机执行**（绕过会被 pre-commit 拒绝）：

- **AGENTS.md 同步**：`CLAUDE.md` / `GEMINI.md` 必须与 `AGENTS.md` 内容一致。编辑后跑 `python scripts/agent_links.py repair`，pre-commit hook 强制检查。
- **治理文档修改保护**：`.githooks/commit-msg` 检查以下治理文件是否被修改——`AGENTS.md`、`世界观/核心设定.md`、`.githooks/pre-commit`、`.githooks/commit-msg`、`STRUCTURE.md`、`docs/audit-checklist.md`、`复盘/reviewer-protocol.md`。若修改且 commit message 不含 `[governance]` 标记，提交被**拒绝**。治理文档的完整清单与保护细则见 `.githooks/commit-msg`。
- **伏笔表格式完整**：pre-commit 检查 `伏笔/伏笔登记表.md` 的 markdown 表格结构完整性（列数一致、状态字段合法值）。

**流程强制 — 完工清单兜底**（无脚本强制，但必须在完工检查清单逐项确认）：

- **世界观硬核心 locked**：`世界观/核心设定.md` frontmatter `locked: true`。任何修改必须走多轮独立评审。pre-commit 会检测该文件的修改并要求 `[governance]` 标记。
- **人设内核不可轻改**：核心欲望/核心恐惧/底线/应激模式是行为边界。修改需标注触发事件 + 走 reviewer 验证 + 完工清单确认。
- **伏笔必须登记**：新伏笔 → `伏笔/伏笔登记表.md` 登记（状态=open），回收后 → closed。不登记 = 不存在 = 收不回来。完工清单逐章确认。
- **人物记忆必须回写**：每卷/关键场景后，受影响角色的 `人物/<角色名>.md` 记忆段必须更新。完工清单逐卷确认（漏回写的记忆漂移在复盘 converge 中由 reviewer 检查）。
- **完工必检**：任务完成后必须执行末尾"完工检查清单"，不可跳过。

### 默认偏好

- **先读后改**：修改任何文件前先读取，理解现有内容再动手。
- **Occam**：如无必要，勿增实体。新增角色、设定、分支剧情前先确认它解决的具体问题。
- **Bitter Lesson**：通用方法优于硬编码先验。优先用 LLM 理解 + converge 审查覆盖一致性检查，谨慎手工写规则枚举。
- **作者分离**：Agent 写的内容（正文、记忆回写、复盘报告）必须在 frontmatter 标注 `model` / `generated_at`；用户写的内容不标。
- **执行模式**：单场对话内的小修用直接执行；涉及跨卷、跨角色需评审的走四阶段闭环。

## 四阶段工作流（核心操作协议）

agent 接到"推进剧情"类任务时，先跑**就绪自检**（见上方），通过后按以下流程执行。

### ① 宪法审查

推进剧情的第一步**不是写**，而是对照 `世界观/核心设定.md` 和 `大纲/主线.md` 评审用户方向：

- **不违反且自洽** → 推进
- **违反（硬冲突）** → 指出具体冲突点 + 修正意见，等用户裁决
- **与已埋伏笔/人物记忆/主线有张力（非违宪但不自洽）** → 预检 flag + 提示用户确认
- **方向模糊/歧义/不在设定覆盖范围** → 向用户提问澄清，不自行推断

审查结论写入 `正文/第N卷/_审查_第M章.md`（frontmatter 标注审查日期 + 判据 + 结论），供跨会话追溯。

### ② 写前准备

审过后，为每场戏整理**写前上下文包**（约 300-500 字），写入 `正文/第N卷/_准备_第M章.md`：

- 本场大纲 + 为什么重要
- 在场角色：内核要义 + 最近 3-5 条 L2 记忆 + 未解决问题 + 两两关系四格摘要
- 场景初始状态
- **达成断言**（可被 reviewer 核验的具体目标，每场至少 1 条主断言 + 覆盖在场角色的核心欲望/恐惧之一）

> 上下文包落盘后，compact 恢复时 AGENTS.md 自动指向该文件——防止上下文衰减。

### ③ 推进执行

- **默认：直接写**（单 agent 按上下文包生成正文）
- **博弈场景（有效博弈方 ≥ 2 且目标冲突）**：可试用角色扮演（子代理各持人物卡 + 三档目标自主互动，主控按终止条件收口），标为实验性
- **单人+环境对抗 / 内心冲突场景**：用直接写 + 对应维度 reviewer rubric（见 `docs/audit-checklist.md` 环境逻辑一致性 / 心理演化自洽性）

正文产出后：**写后 reviewer 审查**（spawn 新 agent 实例，只注入上下文包+产出正文，不含写作 agent 的推理过程）：

- **检查维度**：以 `docs/audit-checklist.md`「小说专项审计」为 rubric（人设一致性 / L2 记忆引用正确 / 关系更新合规 / 世界观无违反 / 前文无矛盾），加 `docs/writing-style.md` 端木技法作为"好看"维度
- **通过阈值**：0 阻断项，flag 项 ≤ 2
- **不通过** → 输出阻断清单（具体到人设第 X 条 / 记忆第 Y 条 / 世界观第 Z 条）→ 原写作 agent 修复 → reviewer 二审 → 最多 3 轮否则升级用户裁决
- **通过** → 进入下一场或复盘

### ④ 阶段复盘（卷结束时）

复盘分两层：先跑机械脚本，再跑人工 converge。

**机械层**（脚本自动执行）：
- `python scripts/audit.py check` — 断链 / STRUCTURE 完整性 / AGENTS.md 行数 / 同步
- `python scripts/check_foreshadowing.py` — 伏笔 open/closed 状态 + 超期检测
- （角色出勤 / 时间线校验脚本待实现）

**语义层（复盘 converge）**——详见 `复盘/reviewer-protocol.md` 的本地协议。核心流程：
1. **Spawn 独立 reviewer**（新 agent 实例），注入全卷正文 + 世界观 + 大纲 + 人物卡 + 伏笔表
2. Reviewer 按 `docs/audit-checklist.md` 全量审计，输出阻断清单（每条标归因：plan_defect / writer_error）+
   建议清单
3. Executor 修复阻断项 → reviewer 二审 → 反复到**零硬阻断**（世界观违反/人设违反/伏笔悬空/时间线倒流）
   或软阻断经用户确认可接受
4. **最多 5 轮外循环**；同阻断源出现 ≥3 次 → 振荡硬停，问用户
5. 回写：受影响角色的 L2 记忆 + 关系 + 必要时人设演化
6. 复盘结论写入 `复盘/第N卷_复盘.md`

## 写作风格约定

详见 [docs/writing-style.md](docs/writing-style.md)。简述：
- 视角、时态、文风倾向已在该文档定义
- 端木灵星技法（矛盾冲突五路径、开篇三章强化主角、章末钩子、伏笔快速回收）作为 reviewer rubric 的"好看"可操作抓手

## 提交规范

使用 Conventional Commit 风格：`feat:` / `fix:` / `chore:` 等。提交信息写清改了什么、为什么。

**治理文档标记**：修改 `AGENTS.md`、`世界观/核心设定.md`、`.githooks/pre-commit` 时，commit message 必须含 `[governance]` 标记，否则 pre-commit 拒绝提交。

**及时提交**：完成一卷或关键场景后主动提交，避免 diff 膨胀。

## 文档维护原则

1. **不重复**：同一信息只在最合适的位置出现一次。
2. **只记正文里读不出来的东西**：世界观、大纲、人物内核、设计决策。正文本身的内容不往文档抄。
3. **CHANGELOG 不读全文**：用 `python scripts/changelog.py titles/show/add/recent`。
4. **计划落盘**：涉及跨卷、多角色、需要评审的任务在 `docs/plans/active/` 写计划，完成后移 `docs/plans/completed/`。
5. **定期审计**：每 ~20 次任务或每月，跑 `python scripts/audit.py check`。

## 完工检查清单

任务完成后逐项走完：

- [ ] **正文一致性**：本场/本卷是否有漂移——人设违反、记忆矛盾、关系混乱、世界观冲突？走写后审或复盘 converge。
- [ ] **人物记忆回写**：受影响角色的 `人物/<角色名>.md` 记忆段是否已更新？L2 新条目是否正确？
- [ ] **伏笔登记**：埋了新伏笔？`伏笔/伏笔登记表.md` 已录入。收了旧伏笔？状态已改 closed。
- [ ] **CHANGELOG**：是否值得记录？用 `python scripts/changelog.py add ...` 追加。
- [ ] **同步一致性**：本文件若被编辑，跑 `python scripts/agent_links.py repair`。
- [ ] **世界观无违**：硬核心设定未被本节/本卷违反？
- [ ] **跳过条件**：纯格式修改、注释修改、同一会话内已记录的变更可跳过文档更新（验证不可跳过）。
