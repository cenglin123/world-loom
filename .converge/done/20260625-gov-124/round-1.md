# Round 1 · ultraverge 评议（建议 1+2+4）

- date: 2026-06-25
- mode: ultraverge（≥3 并行独立 reviewer）
- reviewers: 3（general-purpose，fresh context，identical rubric）
  - R1 instance: a4ef3dae697a5c090
  - R2 instance: a903e274ca8b6d643
  - R3 instance: abdbd548994cff454

## Verdict 汇总

| Reviewer | verdict |
|----------|---------|
| R1 | 阻断需修复 |
| R2 | 阻断需修复 |
| R3 | 阻断需修复 |

**并行裁决**：3/3 一致 = `阻断需修复`。多条 severity 为 conceptual/architectural → 升级完整收敛（不能以多数决跳过深层阻断）。

## 收敛阻断集（三方语义等价合并）

| ID | severity | 针对 | 共识度 | 问题 | 修复方向 |
|----|----------|------|--------|------|---------|
| B1 | conceptual | 建议1 | 3/3 | `model:` 豁免判据反向制造漏洞：agent 漏写 model:（与"忘记调用"同类健忘）→ 同时豁免工作流痕迹检查 + 违反「作者分离」标注义务，且无机制反查"无 model 但实为 agent 生成" | 黑名单触发改白名单声明：默认全部 `第M章.md` 要求痕迹；用户手写须显式 `author: human` opt-out；check_chapters 加"无 model 且无 author → BLOCK" |
| B2 | conceptual | 建议2 | 3/3 | `_审查后_` 只查文件存在不查 verdict：可写 `verdict: 通过` 空壳骗过钩子，制造"已审"伪证据，比无痕更危险（污染 compact 恢复 / 复盘） | 二选一：(a) 降为提醒级、文档明确"存在≠审过、质量靠复盘 converge 兜"；(b) 坚持阻断则解析 verdict + 要求 reviewer_model≠model、reviewed_at>generated_at 独立性信号 |
| B3 | architectural | 建议1 | 3/3 | 粒度错配：①宪法审查可一次覆盖多章（"推进剧情第一步"），仅②写前准备逐场；强制逐章 `_审查_第M章.md` 会对"一次审多章"误拦(false positive) + 形式主义 | `_准备_` 保持逐章阻断；`_审查_` 改卷级或支持 `covers: [3,4,5]` / `review_ref:` 引用，钩子校验覆盖关系而非逐章同名 |
| B4 | conceptual | 建议1 | 3/3 | 阻断级 vs Bitter Lesson 张力：就绪自检拦客观硬事实，而"审查做没做"是过程合规、只能验形不验质；commit-time-only 未触审计自认根因（会话期零约束） | `_审查_`/`_审查后_` 降为提醒级，只对 `_准备_`（粒度清晰、形式即足够）保持阻断；或显式论证偏离 Bitter Lesson 的代价权衡 |
| B5 | architectural | 建议4 | 3/3 | (a) 整文件级 [governance] 保护 writing-style.md 过粗——仅视角/时态/注册表是硬参照，其余轻量叙事工艺，与文件自身硬/软分类矛盾；(b) 只往清单再加一项，未解 P3-G 漂移根因（清单散落 4 处无单一真相源） | (a) 抽视角/时态/注册表到独立 locked 文件单独保护，或论证不拆的权衡；(b) 治理清单收敛单一数据源（commit-msg 数组或 governance-files.txt 为唯一真相，AGENTS.md 改指针） |
| B6 | structural | 建议2 | 2/3 | `_审查后_` frontmatter schema 命名/取值与既有不一致：`verdict: 通过\|阻断` vs reviewer-protocol `可收敛\|需修复`、`reviewer_model` vs `model` | 复用既有词汇表：verdict 取值对齐 reviewer-protocol，字段沿用 model/generated_at |

## 跨切诚实性缺口（3/3）

`--no-verify` 绕过 + commit-time-only 盲区在提案"治理/验证/落地"节未承认；"无痕不可提交"是过度承诺。须在提案诚实标注：本机制是 commit-time 留痕兜底（抗 compact 价值真实），非会话期工作流强制；最终防线是 §④ 复盘 converge。

## 事实勘误（R1）

提案建议 4 称"AGENTS.md 第 78 行治理文件清单"——`GOVERNANCE_FILES` 数组实际在 `.githooks/commit-msg`(8-16)，AGENTS.md/CLAUDE.md 是 prose 清单。落地时两处都要改，引用需精确。

## Orchestrator 处理

- boundary_check: pass（未直接改产物；评议结论待 Executor/用户处置）
- 升级完整收敛。B1/B2/B4 为概念级且部分构成方向反转 → 含真实设计裁决点（阻断 vs 提醒 posture、白名单豁免、writing-style 拆分），按确认点分类属宪法强制点 → 报告用户裁决后再进 Executor 修复轮。
