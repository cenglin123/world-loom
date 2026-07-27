# 收敛回溯 — init-agent-docs 改进计划

> 触发：基于 `novel_world_one` 治理重构的实践经验，改进 `init-agent-docs` skill
> 日期：2026-07-28
> 轮数：1 轮（verdict: 需修复 → 全部修复后收敛）
> 目标仓库：`C:\Users\chenr\.agents\skills\init-agent-docs`

## 做了什么

将 `novel_world_one` 仓库积累的三条实践反馈回 init-agent-docs skill：

1. **完工检查脚本化**：新增 `assets/scripts/check_all.py`——`--quiet` 模式下无输出=通过，FAIL 自带修复指引。AGENTS.md.tpl 的完工清单从 7 条散文 → 1 条命令 + 3 条手工确认。

2. **AGENTS.md.tpl 压缩下沉**：235 行 → 123 行（-48%）。完工清单浓缩、硬约束不枚举 hooks 已强制的事项、文档维护原则 14→5 条、记忆/Bugfix/Worktree 指令下沉到子文档、frontmatter schema 独立为 `docs/frontmatter-schemas.md.tpl`。

3. **行数上限 200 → 250**：跨 9 处同步更新（audit.py、SKILL.md、AGENTS.tpl、audit-checklist.tpl、eval-baseline.md）。

4. **多文档同步更新**：SKILL.md 设计哲学/执行步骤/静态自检/反模式全部跟上；README.md 目录树更新；STRUCTURE.tpl 接收下沉的治理规则；测试用例同步模板实际内容。

## Reviewer 发现的关键问题

| 问题 | 修复方式 |
|------|---------|
| H1: frontmatter-schemas 缺少生成指令 | SKILL.md 第 2 步中型项目表追加 + STRUCTURE.tpl 索引追加 |
| H2: check_all.py 不能替代全部散文项 | 两层设计：机械层（check_all）+ 手工确认层（3 条） |
| H3: 行数阈值多源不一致 | grep 全仓 → 逐处更新 9 个位置 |
| S1: check_all 与 audit 职责重叠 | docstring + SKILL.md 明确分工（高频静默 vs 深度详实） |
| S3: 触发条件误下沉 | 记忆/Bugfix 的触发条件保留在 AGENTS，只下沉实现细节 |

## 最终状态

- init-agent-docs `f049627`：64/64 测试通过
- 改动文件数：11（含 3 个新增文件）
- AGENTS.md.tpl：123 行，在 250 行上限内

## 收敛判定

1 轮收敛。零残留硬阻断。软阻断全修复。Flag 3 条已处置、1 条为已知限制（模板更新不回溯）。
