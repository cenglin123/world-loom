# 小说写作 AI 协作规范

> `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` 内容一致；只编辑本文件，另两个由脚本同步。
> 本文件是主管 agent 的操作准则与导航入口——只放规则和指针，细节去对应的子文档找。

## 项目概述

一部正在创作中的长篇小说。Agent 的角色是**受托的执行者 + 质量守护者**——按四阶段工作流推进剧情，用宪法审查 + converge 迭代收敛防止漂移（吃书）。

不可改动的硬设定在 `00_世界观/核心设定.md`，任何人（含 agent 和用户）要改都必须走多轮独立评审。

converge 本地实现见 [[05_复盘/reviewer-protocol]]，reviewer 启动模板见 [[05_复盘/reviewer-prompt-template]]。所有多轮审查、收敛判定、阻断分类走这套协议，不依赖外部 SKILL。

## 源码层 / 内容层

| 层 | 是什么 | 分发 |
|----|--------|------|
| **源码层** | `_模板/` + 治理机制（`.githooks/`、AGENTS.md）+ `scripts/` + 方法文档（`docs/`、`00_世界观/_设计方法.md`）+ `example_world/` | ✓ 可推送到公开仓 |
| **内容层** | 世界观填写、大纲、角色卡、记忆、关系、正文、伏笔、复盘、`docs/{overview,CURRENT,style-locked}` | ✗ 只留本地，永不推送 |

> 划分清单唯一权威源：`scripts/layers.py`。分发走 `python scripts/publish.py`（剥离内容层 + 复核零泄漏 + 清单确认后 `--force` 推送）。`git push` 被 `.githooks/pre-push` 默认拒绝；推整仓到私有远端 → `git push --no-verify`。
>
> 新克隆 / 内容文件缺失 → `python scripts/template.py init`；开新书 → `python scripts/template.py reset --all --force`。

## 就绪自检（接到"推进剧情"任务前强制执行）

以下四项任一不满足 → **拒绝推进正文，提示用户先完成设定**：

1. `00_世界观/核心设定.md` 的世界法则段**非空**（不是"待填写"）
2. `01_大纲/主线.md` 的主线一句话**已填写**
3. `02_人物/_索引.md` 角色清单**至少有一个实际角色**（不含示例/模板行）
4. `docs/style-locked.md` 的视角和时态段**已选定**（非"待选择"）

> 失败时引导用户按 CURRENT.md '下一步'清单逐项填写。若这些文件**不存在**（新克隆只有 `_模板/`）→ 先跑 `python scripts/template.py init`。

## 同步声明

`python scripts/agent_links.py check` / `repair` / `repair --force`，模式 copy。

## 信息导航

| 需要什么 | 去哪找 |
|---------|--------|
| Frontmatter 字段定义（人物卡/章节/写后审结论） | [[docs/frontmatter-schemas]] |
| 项目总览 + 世界观梗概 + 关键设计决策 | [[docs/overview]] |
| 叙述约定·锁定层（视角/时态/文风注册表，治理保护） | [[docs/style-locked]] |
| 叙述约定·工艺层（文风倾向/可读性技法/故事驱动法则） | [[docs/writing-style]] |
| AI 写作已知陷阱（本项目专属） | [[docs/pitfalls]] |
| 一致性审计清单 | [[docs/audit-checklist]] |
| 复杂任务计划 | [[docs/plans/active/]] |
| 当前任务状态 | [[docs/CURRENT]] |
| 变更记录 | [[docs/CHANGELOG]] |
| 模板层与内容层的边界、重置命令 | [[_模板/README]] + `scripts/layers.py`（划分权威源） |
| 世界观（物理层 locked + 社会层/张力层可扩展） | [[00_世界观/核心设定]] |
| 世界观·外围（可扩展） | [[00_世界观/外围设定]] |
| 世界观构建方法 | [[00_世界观/_设计方法]] |
| 故事大纲（主线 + 分卷） | [[01_大纲/主线]] |
| 人物 | [[02_人物/_索引]] + [[02_人物/relationships.json]] + `scripts/check_tags.py` |
| 伏笔登记（open/closed 状态机） | [[04_伏笔/伏笔登记表]] |
| 正文章节 | [[03_正文/README]] |
| 复盘 converge 协议 + reviewer 模板 | [[05_复盘/reviewer-protocol]] → [[05_复盘/reviewer-prompt-template]] |

## 人物创建流程

1. `python scripts/check_tags.py wizard <角色名>` — 从模板创建并输出**待完善清单**（含引导提示和示例值）
2. 逐条与用户确认后，写入前端 matter 和正文对应字段
3. 完成后 `python scripts/check_tags.py check` + `python scripts/check_tags.py _index` 更新索引

## 行为规则

### Compact 恢复（强制）

若上下文含 "continued from a previous conversation"，在继续任何实质性工作前：
1. 读 [[docs/CURRENT]] — 确认当前任务状态
2. 上述步骤完成前，**禁止写操作、禁止有副作用的判断**

### 硬约束

**pre-commit / commit-msg / pre-push 三板斧**——具体检查逻辑见各 hook 脚本自身（`.githooks/`），此处只记哪些事**没有脚本兜底**：

- **治理文档**：修改 `.githooks/commit-msg` 的 `GOVERNANCE_FILES` 清单内任一文件 → commit message 必须含 `[governance]` 标记。清单为该文件的唯一权威源。
- **人设演化记载**：剧情导致人物卡「当前稳定内核」或「身份矛盾」任一字段改变 → 必须在「演化记录」追加触发事件、付出代价、旧状态与新状态；禁止覆盖历史。
- **伏笔登记**：新伏笔 → `04_伏笔/伏笔登记表.md` 登记（状态=open），回收后 → closed。不登记 = 不存在 = 收不回来。
- **记忆回写**：每卷/关键场景后，受影响角色的 `02_人物/<角色名>.md` 记忆段必须更新。
- **关系同步**：角色间有意义互动后，`python scripts/relationship.py set/update` 写入关系 JSON。卷末 `regenerate` 重建矩阵。
- **标签同步**：角色创建或能力变化后更新 frontmatter tags。卷末 `python scripts/check_tags.py regenerate`。

### 默认偏好

- **先读后改**：修改任何文件前先读取，理解现有内容再动手。
- **Occam**：如无必要，勿增实体。
- **Bitter Lesson**：通用方法优于硬编码先验。优先用 LLM 理解 + converge 审查覆盖一致性检查。
- **作者分离**：Agent 写的内容（正文、记忆回写、复盘报告）须在 frontmatter 标注 `model` / `generated_at`；用户写的内容不标。章节缺 `model` 且缺 `author: human` → pre-commit 阻断。
- **执行模式**：单场对话内的小修用直接执行；涉及跨卷、跨角色需评审的走四阶段闭环。

## 四阶段工作流

agent 接到"推进剧情"任务时，先跑**就绪自检**，通过后按以下流程执行。

### ① 宪法审查

对照 `00_世界观/核心设定.md` 和 `01_大纲/主线.md` 评审用户方向：
- 不违反且自洽 → 推进
- 违反（硬冲突）→ 指出具体冲突点 + 修正意见，等用户裁决
- 与已埋伏笔/人物记忆/主线有张力（非违宪但不自洽）→ 预检 flag + 提示用户确认
- 方向模糊/歧义 → 向用户提问澄清，不自行推断

审查结论写入 `03_正文/第N卷/_审查_第M章.md`（一次可覆盖多章——改写卷级 `_审查_第N卷.md`，各章 frontmatter 用 `review_ref:` 指向）。

### ② 写前准备

为每场戏整理上下文包（~300-500 字），写入 `03_正文/第N卷/_准备_第M章.md`：

1. 确定在场角色列表
2. `python scripts/recall.py <角色1> <角色2>` — 获取人物生成内核 + L2 写前注入集（agent 压缩转写为自然语言，不机械粘贴输出）
3. `python scripts/relationship.py show <角色名>` — 两两关系摘要
4. 将以上与本场大纲、场景初始状态、**场景决策**（Belief / Desire / Intention / Obstacle / Tactic / 换挡条件 / 可接受代价）和**达成断言**组装为自然语言；达成断言至少 1 条，并覆盖在场角色的本场目标及一个相关的人设字段

### ③ 推进执行

- **默认：直接写**（单 agent 按上下文包生成正文）
- **博弈场景**（有效博弈方 ≥ 2 且目标冲突）：可尝试角色扮演，标为实验性
- **单人+环境对抗 / 内心冲突**：直接写 + `docs/audit-checklist.md` 对应维度 rubric

正文产出后 spawn 独立 reviewer（只注入上下文包+产出正文，不含写作 agent 推理过程），按 [[docs/audit-checklist]] 小说专项审计 + [[docs/writing-style]] 可读性技法。0 阻断项且 flag ≤ 2 → 通过；不通过 → 修复 → 二审，最多 3 轮。结论写入 `_审查后_第M章.md`（schema 见 [[docs/frontmatter-schemas]]）。reviewer 启动模板：[[05_复盘/reviewer-prompt-template]]。

### ④ 阶段复盘（卷结束时）

**机械层**：`python scripts/check_all.py`

**语义层**：按 [[05_复盘/reviewer-protocol]] 执行——spawn reviewer → 全量审计 → executor 修复 → 零硬阻断（世界观违反/人设违反/伏笔悬空/时间线倒流）可收敛。最多 5 轮，同阻断源 ≥3 次振荡硬停。完成后回写 L2 记忆 + 关系 + 必要时人设演化，复盘结论写入 `05_复盘/第N卷_复盘.md`。

## 提交规范

Conventional Commit（`feat:` / `fix:` / `chore:`）。治理文档提交须含 `[governance]` 标记（清单见 `.githooks/commit-msg`）。完成一卷或关键场景后主动提交。

## 文档维护原则

1. **不重复**：同一信息只在最合适的位置出现一次
2. **只记正文里读不出来的东西**：世界观、大纲、人物内核、设计决策
3. **CHANGELOG**：用 `python scripts/changelog.py titles/show/add/recent`，不读全文
4. **计划落盘**：跨卷/多角色的任务在 `docs/plans/active/` 写计划，完成后移 `completed/`
   ⚠️ `docs/plans/` 与 `docs/CHANGELOG.md` 属**源码层、会被分发**——含剧透的剧情计划放内容层（`03_正文/第N卷/_准备_*.md` 或 `05_复盘/`）
5. **定期审计**：每 ~20 次任务或每月，跑 `python scripts/audit.py check`

## 完工必检

```
python scripts/check_all.py --quiet
```

无输出 = 全部通过。每条 FAIL 自带修复指引。机械层查不出的语义一致性（人设漂移、记忆矛盾、世界观违反）走 §④ 复盘 converge 兜底。
