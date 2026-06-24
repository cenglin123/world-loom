# Retrospective · ultraverge 建议 1+2+4

- slug: 20260625-gov-124
- mode: ultraverge（治理文档改动 → 强制 ≥3 reviewer + 收敛 + 设计审查）
- date: 2026-06-25
- 终止类型: 终止-b 渐近通过（评议 3/3 阻断 → 用户裁决 2 个 posture fork + 采纳无争议修复 → v2 定稿，用户确认）

## 轮次

- Round 1 评议：3 并行独立 reviewer（fresh context），verdict 3/3 = `阻断需修复`。
  - conceptual: B1（model 豁免反向漏洞）、B2（_审查后_ 伪证据）、B4（阻断 vs Bitter Lesson）
  - architectural: B3（粒度错配）、B5（writing-style 整文件过粗 + 清单漂移）
  - structural: B6（schema 不一致）
- 升级完整收敛：因含 conceptual/architectural，不以多数决跳过。
- 设计裁决：B1/B3/B6/B5b/诚实标注 = 无争议采纳；B2+B4（强制力 posture）、B5a（writing-style 粒度）= 用户裁决 fork。
- 用户裁决：强制力=「只 _准备_ 阻断，审查类降提醒」；治理粒度=「抽 locked 段单独保护」。
- v2 定稿写入提案 `docs/plans/active/20260625-governance-workflow-trace.md`「Ultraverge 收敛结果」节，取代原建议 1/2/4。

## 收敛结论（v2）

| 原阻断 | 收敛处置 |
|--------|---------|
| B1 | 黑名单触发 → 白名单声明：默认全章要求痕迹，用户手写须 `author: human`；check_chapters 加"无 model 且无 author → BLOCK" |
| B2 | `_审查后_` 降提醒 + 文档诚实"存在≠审过"，质量交复盘 converge |
| B3 | `_准备_` 逐章阻断；`_审查_` 卷级/`review_ref:` 引用，不逐章同名 |
| B4 | `_审查_`/`_审查后_` 提醒级，仅 `_准备_` 阻断 |
| B5a | 抽视角/时态/注册表到 `docs/style-locked.md` 单独 [governance]，writing-style 保持轻量 |
| B5b | 治理清单以 commit-msg `GOVERNANCE_FILES` 为唯一数据源，AGENTS.md 改指针 |
| B6 | `_审查后_` schema 用 model/generated_at + verdict=可收敛\|需修复 |
| 诚实 | 标注 --no-verify + commit-time-only 盲区，删"无痕不可提交"过度承诺 |

## 设计审查

ultraverge 要求强制设计审查。本轮评议 Reviewer prompt 已注入 DR1-DR7 全 7 维（扩域评议），且阻断集本身即覆盖职责分层(DR4)、可维护性(DR5)、Bitter Lesson 一致性(DR6/DR7) 的设计维度发现——设计审查已内联于评议，findings 已纳入 v2。无额外独立设计审查轮。

## 关键收获

1. **并行独立审查的价值被实证**：3 个 fresh-context reviewer 高度收敛于同一组概念硬伤（B1/B2/B3/B4），单 reviewer 评议难达此置信。
2. **审计提案者（agent）的盲区被外部 reviewer 捕获**：原提案的"阻断级 + model 豁免"是提案者自身偏差，3 方一致指出与仓库 Bitter Lesson 哲学冲突——呼应 converge pilot "用户/独立视角是关键外部纠偏来源"。
3. **机械层只能验形不验质**：B2 揭示"文件存在性"检查会被误读为"过程已执行"，治理设计须诚实区分"留痕"与"质量"。

## 实现 + 验收（2026-06-25）

- Executor（in-session）按 v2 落地：新建 `docs/style-locked.md`；改 `.githooks/pre-commit`（第 6 段工作流痕迹）、`.githooks/commit-msg`（GOVERNANCE_FILES + style-locked）、`scripts/check_chapters.py`（白名单 BLOCK + 就绪自检改指 style-locked + args 路径 resolve）、`AGENTS.md`（多处，含 schema/honesty/单一数据源/人物卡注释指针）、`writing-style.md`（slim）、`reviewer-protocol.md` / `reviewer-prompt-template.md`；agent_links repair --force 同步三文件。
- 确定性验证：B1 白名单三章用例（仅无标注章 BLOCK）✓；pre-commit 第 6 段（_准备_ 阻断 / review_ref 卷级覆盖 / _审查后_ 提醒 / author:human 豁免）✓；双钩子 `bash -n` ✓；全量 check 仅余"0 角色"就绪 H1-BLOCK（预期）。
- 独立验收 reviewer（fresh context, a99fdc9d05ba630ca）：verdict `可执行`，0 阻断，0 回归，逐项 pass。捕获 1 处轻微漂移——人物卡 frontmatter 注释 `style_register` 仍指 writing-style.md → 已修为 style-locked.md 并 resync。

## 状态

**收敛完成 + 已落地**。v2 七项修复（B1-B6 + 诚实）全部实现并经独立验收。终止-b 渐近通过（≥2 轮：评议 + 验收，blocking 单调降至 0）。
