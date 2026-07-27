# Converge R1 — Reviewer 审计报告

> 审查对象：`init-agent-docs` skill 改进计划 + 实施
> 审查时间：2026-07-28
> 审查模型：general-purpose agent (fresh context)

```yaml
verdict: 需修复
hard_blocks:
  - id: H1
    description: >
      frontmatter-schemas.md.tpl 在 SKILL.md 的执行步骤中没有对应的生成指令。
      如果 AGENTS.md.tpl 添加了指向 docs/frontmatter-schemas.md 的指针，
      但 SKILL.md 第 2 步没有包含将模板写入目标项目的指令，生成的项目中会出现死链。
    location: SKILL.md 第 2 步（docs 创建）、AGENTS.md.tpl 信息导航、STRUCTURE.md.tpl
    fix_direction: >
      在 SKILL.md 第 2 步的中型项目表格中追加一行：`docs/frontmatter-schemas.md`
      → `frontmatter-schemas.md.tpl`。在 STRUCTURE.md.tpl 索引表中加入对应行。
    fixed: true

  - id: H2
    description: >
      check_all.py 无法替代 AGENTS.md.tpl 完工检查清单中所有 7 条散文项。
      其中"验证"、"复查视角"、"跳过条件"三项需要主观判断，不能通过脚本自动检查。
      如果 check_all.py 作为替代品引入，这三项将被静默丢弃。
    location: AGENTS.md.tpl 完工检查清单；assets/scripts/check_all.py
    fix_direction: >
      将完工检查清单重构为两层：(a) check_all.py 自动检查层（可机械化项），
      (b) 手工裁决层（验证/复查视角/跳过条件判定）。
      AGENTS.md.tpl 应写"先跑 check_all.py，再逐项确认 [清单]"。
    fixed: true

  - id: H3
    description: >
      行数上限从 200 改为 250 需要跨 9 个位置一致更新，任一遗漏造成系统内矛盾。
    location: SKILL.md:45,54,751,862; audit.py:375,554,558; audit-checklist.md.tpl:17;
              AGENTS.md.tpl:208; eval-baseline.md:50
    fix_direction: 全局搜索遍历所有 200 引用后逐一更新。
    fixed: true

soft_blocks:
  - id: S1
    description: >
      check_all.py 与已有 audit.py 的职责范围高度重叠。audit.py 已聚合 7 项检查，
      check_all.py 再做类似检查会产生"什么时候该用哪个"的混淆。
    severity: 高
    fix_direction: >
      明确分工——check_all.py = 高频完工检查器（静默，~5项），
      audit.py = 深度审计器（详实，~15项，定期跑）。在两个脚本 docstring 和 SKILL.md 中写清。
    fixed: true

  - id: S2
    description: >
      AGENTS.md.tpl 项目记忆段压缩后，确认 MEMORY.md.tpl + user-role.md.tpl 能独立指导 Agent。
    severity: 中
    fix_direction: >
      审查 MEMORY.md.tpl 是否具备独立指导能力。AGENTS 保留摘要+指针。
    fixed: true

  - id: S3
    description: >
      记忆检索/Bugfix 的触发条件（"什么情况下要查记忆/写 bugfix 文档"）必须留在 AGENTS.md 中，不能下沉。
    severity: 高
    fix_direction: >
      保留触发条件（各 1-2 句），只将字段说明/文件名规范/索引机制等实现细节移到子文档。
    fixed: true

  - id: S4
    description: >
      行数上限改为 250 后，SKILL.md 设计哲学需要对应解释为什么。
    severity: 中
    fix_direction: >
      修改数字并补充"200 理想 vs 250 可执行上限"的说明。
    fixed: true

flags:
  - id: F1
    description: >
      22 条反模式中有 2 条在 check_all.py 引入后需要审视——反模式 #3（"没有完工检查"）
      描述可能需要更新；反模式 #14 与 check_all.py 的互补关系需确认。
    disposition: 已更新：反模式 +2 条（#23 完工清单散文枚举、#24 AGENTS 充当百科全书）

  - id: F2
    description: >
      行数上限改变后，旧项目的审计清单会继续使用 200 行标准，新旧不一致——模板更新不回溯。
    disposition: 已知限制，不改。旧项目在运行 audit.py 时会看到新阈值。

  - id: F3
    description: >
      文档维护原则从 14 条压缩到 5 条时，取舍标准需要说清。
    disposition: 已在改进计划中记录保留判据。CHANGELOG 操作指令由脚本承载，文件更新时机由 agent 常识判断。

  - id: F4
    description: >
      SKILL.md 第 1 步 cp 命令列表需要补 check_all.py。
    disposition: 已修复。
```
