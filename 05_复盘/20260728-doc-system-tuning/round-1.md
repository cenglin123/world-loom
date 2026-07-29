# Converge R1 — Reviewer 审计报告

> 审查对象：文档体系微调提案（AGENTS.md + audit-checklist.md 三处摩擦优化）
> 日期：2026-07-28

```yaml
verdict: 需修复
hard_blocks:
  - id: H1
    description: >
      提案 §A 声称 check_all.py 会自动捕获 [governance] 标记缺失，但
      check_all.py 的 CHECKS 列表仅包含同步、模板、死链、伏笔、关系、标签、章节共
      7 项，无任何一项检查治理文档标记。[governance] 的检查在 .githooks/commit-msg，
      不在 check_all.py 中。提案对代码库行为做出了可验证的错误断言。
    location: §A「改为」区块
    attribution: contradiction
    fix_direction: >
      从「脚本会帮你检查的」清单中移除「治理文档 [governance] 标记」，
      或澄清其检查时机（commit-msg hook，非 check_all.py）。

  - id: H2
    description: >
      提案将「伏笔登记」和「关系同步」列入「脚本会帮你检查的」，声称 check_all.py
      会自动捕捉遗漏。但 check_foreshadowing.py 仅检查已登记项的格式（列数、ID、状态值）
      和超期检测——无法检测「新伏笔被引入但未登记」（语义判断）。
      relationship.py check 仅检查 JSON 格式与角色文件存在性，不检测「角色间发生
      有意义互动但未写入关系」。原文本中「不登记=不存在=收不回来」的关键后果提示被移除。
    location: §A「改为」区块
    attribution: contradiction
    fix_direction: >
      补充脚本覆盖范围的明确说明（格式层 vs 语义层），
      或将伏笔登记/关系同步保留在 agent 主动责任清单中。

soft_blocks:
  - id: S1
    description: >
      提案 §C 将 audit-checklist 维度按阻断级别重新分组的做法，
      与各维度实际包含的混合类型检查项冲突。例如「人设一致性」维度的
      「角色行动可由信念解释」需要审美判断（软），但「演化记录已追加」
      是可客观判定的事实（硬）。将整个维度归入「硬阻断维度（客观可判定
      ——发现即阻断，无灰色地带）」会给 reviewer 错误预期。
    location: §C「改为」区块
    severity: 中
    fix_direction: >
      改为更精确的分组标注——不按整个维度分组，而是在每个维度下标注其主导阻断级别；
      或将节标题措辞从断言式（「无灰色地带」）改为描述式（「以硬阻断为主」）。

  - id: S2
    description: >
      「脚本会帮你检查的」在「行为规则」下作为一个子节，内容却是
      「不需要刻意记住」——行为规则的本质是「必须遵守的约束」，
      两者在逻辑上矛盾。
    location: §A「改为」区块
    severity: 低
    fix_direction: >
      调整结构定位：不从「行为规则」下拆分，而是在每条硬约束旁直接标注脚本覆盖范围。

  - id: S3
    description: >
      提案 §B 将 recall.py 移至「可用工具」时丢失了原文本中关于输出处理的指导：
      「（agent 压缩转写为自然语言，不机械粘贴输出）」。
      同时原始步骤 2 支持多角色一次查询（`recall.py <角色1> <角色2>`），
      提案改为单角色模式（`<角色名>`）。
    location: §B「改为」区块
    severity: 中
    fix_direction: >
      在「可用工具」描述中保留「压缩转写为自然语言」的处理指导；
      恢复多角色参数说明。

  - id: S4
    description: >
      如果 H1 和 H2 的修正导致伏笔登记/关系同步/治理文档标记回到 agent 责任清单，
      则 §A 的核心价值主张「记忆负担从 6 条降到 2 条」就会崩塌。
      提案需重新评估其简化是否建立在准确的前提上。
    location: §A 全局
    severity: 中
    fix_direction: >
      放弃「脚本兜底 vs 无兜底」的二分法，改为更诚实的表述：
      每条约束标注脚本覆盖的层面（格式/超期/完整性），
      价值主张从「减负」改为「明确分工」。

flags:
  - id: F1
    description: >
      「没有脚本兜底——你必須記住」作為子節標題，語氣偏消極/責備。
      原有「硬約束」更中性且專業。
  - id: F2
    description: >
      提案 §B recall.py 參數從多角色改為單角色——若工具實際支援多角色，
      描述會誤導 agent 低估工具能力。
  - id: F3
    description: >
      audit-checklist 人設一致性維度下的條目本身需要翻閱人物卡多個欄位才能判斷
      ——即使歸入硬阻斷，與節標題「客觀可判定」之間存在張力。
```
