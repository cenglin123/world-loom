# 20260814-denova借鉴落地 · converge 记录

> 非小说 converge（治理/计划）。审理对象 = docs/plans/active/20260814-denova借鉴落地.md。

## round-1 评审（2 reviewer，独立 fresh context，跨 family）

### reviewer A · xiaomi/mimo-v2.5-pro（mimo family）

verdict: 需修复
hard_blocks:
  - id: H1
    description: "check_foreshadowing.py 实现不兼容新列结构。当前第 64 行解构 cid, desc, buried, expected, actual, status, *_ = cols 仅捕获前 6 列，新增的「回收方式与后果」（第 6 列）被吞入 *_ 而非绑定到变量名；计划要求的检查 open 状态但「回收方式与后果」为空 → [WARN] 无法直接引用该字段。同时状态合法值（open/closed/abandoned）未更新以覆盖计划生命周期模型中的「触发」中间态。"
    location: "变更 2 — scripts/check_foreshadowing.py"
    reason: "硬阻断分类 2：改动会破坏既有脚本或 schema。脚本解构与新表结构不匹配，新检查项无法实现。"
    fix_direction: "将第 64 行解构改为 cid, desc, buried, trigger_cond, expected, recovery, actual, status, *_ = cols（9 列）；若「触发」是独立 status 值则将其加入第 79 行合法值集合；明确「触发」是状态还是纯过渡概念并在表头说明中消除歧义。"
  - id: H2
    description: "治理影响清单遗漏文件。计划修改 04_伏笔/伏笔登记表.md 和 _模板/04_伏笔/伏笔登记表.md，但「治理影响」段未列出这两个文件，也未要求 [governance] 提交标记。同时 04_伏笔/README.md 未列为变更目标但其表结构描述需同步更新（当前写 7 列，改后为 9 列）。"
    location: "变更 2 目标文件 + 治理影响段"
    reason: "硬阻断分类 3（遗漏成对文件同步）+ 分类 5（治理影响判断错误）。commit-msg hook 的 GOVERNANCE_FILES 虽未含 04_伏笔/伏笔登记表.md，但内容层成对保护规则要求「改哪份都要标记」；此外 README 描述与表结构不一致会造成文档漂移。"
    fix_direction: "在变更 2 目标文件中追加 04_伏笔/README.md；在治理影响段补列 04_伏笔/伏笔登记表.md、_模板/04_伏笔/伏笔登记表.md、04_伏笔/README.md 并标注是否需 [governance]（若需则同步更新 .githooks/commit-msg 的 GOVERNANCE_FILES）。"
  - id: H3
    description: "reviewer-prompt-template.md（内容层 + 模板副本）的 YAML 输出格式未同步更新。计划变更 3 只提到在 hard_blocks/soft_blocks 增加 dimension 字段、末尾增加 keep 段，但 reviewer-prompt-template.md 的 YAML 示例未包含这两个字段，会导致 reviewer 按模板启动时输出格式与 reviewer-protocol.md 不一致。"
    location: "变更 3 — 05_复盘/reviewer-prompt-template.md + _模板/05_复盘/reviewer-prompt-template.md"
    reason: "硬阻断分类 6（计划内容自相矛盾或不可执行）。协议要求输出 dimension + keep，但 reviewer 启动模板不含这两个字段，执行时必然产生格式不一致。"
    fix_direction: "在 reviewer-prompt-template.md 的 YAML 输出格式段同步添加 dimension 字段（hard_blocks/soft_blocks 每条）和 keep 段（与 reviewer-protocol.md 一致）；同时统一 verdict 取值（当前模板仅 可收敛|需修复，协议含 需重新设计）。"
soft_blocks:
  - id: S1
    description: "生命周期模型引入「触发」中间态，但未明确它是独立 status 值还是纯过渡概念。计划原文「生命周期 = 埋设(open) → 触发 → 回收(closed) / 放弃(abandoned)」与脚本现有合法值 open/closed/abandoned 的关系未定义。若「触发」是新 status，脚本和表头说明都需更新；若不是，表头说明的箭头记号易误导。"
    location: "变更 2 — 表头说明文字"
    severity: 高
  - id: S2
    description: "dimension 词表引入 plot_logic 和 dialogue 两个新维度，但 docs/audit-checklist.md 的审计维度（世界观/人设/记忆/关系/伏笔/时间线/开篇结构/简介/结构与工具）中无对应条目，reviewer 无法对照审计标准评估这两个维度。"
    location: "变更 3 — dimension 词表"
    severity: 中
  - id: S3
    description: "dimension 与 attribution 语义重叠。计划称二者「正交，不冲突」，但实际映射关系为：world_defect ≈ dimension:world、character_drift ≈ dimension:character，存在大量同义配对，并非真正正交。两套分类同时存在会增加 reviewer 认知负担。"
    location: "变更 3 — 理由段"
    severity: 中
  - id: S4
    description: "变更 4 要求把「以下六条法则」→「以下七条法则」，但 docs/writing-style.md 第 45 行实际措辞为「以下六条法则解决'设定一大堆但写不出故事'的瓶颈」——计划未引用完整上下文，执行时需精确定位替换点，避免误改其他含「六」的措辞。"
    location: "变更 4 — docs/writing-style.md"
    severity: 低
flags:
  - id: F1
    description: "check_foreshadowing.py 第 49 行 expected_cols 变量未被后续代码引用（死代码），计划要求「expected_cols 更新为 9 列」实际无效果——真正控制列数校验的是第 50 行的 len(header) < 6 判断。不影响功能但计划描述不精确。"
  - id: F2
    description: "reviewer-protocol.md 含 round 和 verdict:需重新设计 两个字段，而 reviewer-prompt-template.md 的 YAML 示例不含 round、verdict 取值仅有 可收敛|需修复。计划未提及统一这两个模板的 verdict 取值，可能延续已有的不一致。"
  - id: F3
    description: "04_伏笔/README.md 当前描述伏笔表列为「ID / 内容 / 预期回收方式 / 状态 / 期限」（5 项描述），实际表头为 7 列，已存在轻微漂移。计划扩为 9 列后漂移加剧，但计划未将此文件纳入变更范围。"
reads:
  - C:/Project/novel_world_one/docs/plans/active/20260814-denova借鉴落地.md
  - C:/Project/novel_world_one/AGENTS.md
  - C:/Project/novel_world_one/_分发/AGENTS.md
  - C:/Project/novel_world_one/.githooks/commit-msg
  - C:/Project/novel_world_one/docs/writing-style.md
  - C:/Project/novel_world_one/_模板/README.md
  - C:/Project/novel_world_one/05_复盘/reviewer-prompt-template.md
  - C:/Project/novel_world_one/05_复盘/reviewer-protocol.md
  - C:/Project/novel_world_one/_模板/05_复盘/reviewer-prompt-template.md
  - C:/Project/novel_world_one/_模板/05_复盘/reviewer-protocol.md
  - C:/Project/novel_world_one/04_伏笔/伏笔登记表.md
  - C:/Project/novel_world_one/_模板/04_伏笔/伏笔登记表.md
  - C:/Project/novel_world_one/04_伏笔/README.md
  - C:/Project/novel_world_one/scripts/check_foreshadowing.py
  - C:/Project/novel_world_one/docs/audit-checklist.md
  - C:/Project/novel_world_one/docs/workflow.md
  - C:/Project/novel_world_one/docs/decisions.md
  - C:/Project/novel_world_one/docs/frontmatter-schemas.md
  - C:/Project/novel_world_one/docs/CURRENT.md


---

### reviewer B · deepseek/deepseek-v4-pro（deepseek-thinking family）

verdict: 需修复
hard_blocks:
  - id: H1
    description: >
      变更 2 对 scripts/check_foreshadowing.py 的改动描述不完整，且按描述执行会破坏脚本的列解析。计划只写"expected_cols 更新为 9 列"，但该变量在当前脚本里是死代码——定义后从未被引用，真正的校验是硬编码的 `if len(header) < 6`，改 expected_cols 毫无效果；更关键的是脚本用位置解包读列：`cid, desc, buried, expected, actual, status, *_ = cols`（第 64 行），新 9 列顺序（ID/描述/埋下位置/触发条件/预计回收位置/回收方式与后果/实际回收位置/状态/备注）下，expected 会读到"触发条件"、actual 读到"预计回收位置"、status 读到"回收方式与后果"，导致状态合法性检查、open 超期检查、closed 缺回收位置检查全部读到错误列。同时 `len(header) < 6` 阈值和示例行 F001（仍为 7 列）都未更新。新增的"open 且 回收方式与后果 为空 → WARN"检查也依赖重新定位列，计划未说明如何定位。
    location: "变更 2 · scripts/check_foreshadowing.py（及 04_伏笔/伏笔登记表.md 示例行 F001）"
    reason: "硬阻断 #2（破坏既有脚本）与 #6（不可执行）：expected_cols 是死代码，位置解包未被更新，按计划原样落地后脚本会静默读错列、状态校验全错。"
    fix_direction: "改为按表头名定位列（如解析 header 建立 name→index 映射），或显式更新位置解包与索引；把 `len(header) < 6` 改为 `< 9` 或 `len(expected_cols)`；同步把示例行 F001 扩为 9 列；明确 触发条件/回收方式与后果 两列的读取方式。"
  - id: H2
    description: >
      变更 2 的目标文件清单遗漏成对模板副本 `_模板/04_伏笔/README.md`。计划改了内容层 `04_伏笔/README.md`（用法说明需反映 7→9 列与新生命周期），但 `_模板/README.md`「覆盖范围」表第 25 行明确列出 `_模板/04_伏笔/README.md` ↔ `04_伏笔/README.md` 是一对成对文件（本目录"多份文件与内容层产物成对纳入治理保护"），两者须同步。计划既未把它列入 4 个目标文件，也未在治理影响中提及。
    location: "变更 2 · 目标文件清单（对比 _模板/README.md 覆盖范围表）"
    reason: "硬阻断 #3（遗漏成对文件）：_模板/ 与内容层需成对同步的没同步。"
    fix_direction: "把 `_模板/04_伏笔/README.md` 加入变更 2 目标文件，与 `04_伏笔/README.md` 同步改写（虽非治理清单，但须成对一致）。"
  - id: H3
    description: >
      变更 3 声称 dimension 词表"用本仓自有词表"，但仓库并不存在任何既有英文 dimension 词表——现有审查维度全部是中文（reviewer-prompt-template 的"世界观违反/人设决策违反/记忆矛盾/时空矛盾/伏笔悬空/死角色出场/节奏问题/情感张力/文风漂移"；audit-checklist 小说专项审计的"世界观/人设/记忆/关系/伏笔/时间线/开篇结构/简介/结构与工具"）。计划自造的 `world/character/memory/relationship/foreshadowing/timeline/pacing/style/plot_logic/dialogue` 既漏掉既有维度"情感张力"（软阻断主维度）与"场景生动度/感官细节"（writing-style 明确点名的 reviewer 维度），又新增无既有对应项的 `plot_logic`。结果：以这份词表自查"覆盖度"会系统性漏掉情感张力类阻断，违背其"避免只审连续性漏文风"的初衷。
    location: "变更 3 · dimension 词表定义"
    reason: "硬阻断 #4（术语/字段名与现有词表冲突）：'本仓自有词表'的断言不成立，词表与 reviewer-prompt-template / audit-checklist 既有维度不对齐且缺失项。"
    fix_direction: "要么从 reviewer-prompt-template 审查维度 + audit-checklist 小说专项审计维度反推一份覆盖齐全的 dimension 词表（补 情感张力/场景生动度 等），要么明确声明这是新引入词表并在两处既有维度文档同步登记，确保映射无遗漏。"
  - id: H4
    description: >
      变更 5 追加的"字段结构一旦有内容落盘即冻结：模板/字段演进只作用于新书/新角色（或显式 reset），不自动迁移到在写的书"与 `_模板/README.md`「改模板的注意事项」第 1 条既有内容高度重复——第 1 条已写明"改模板不会自动同步到已存在的内容文件；已在写的书需要人工把结构变化搬过去（或对未填写的文件跑 reset）"。两条说的是同一操作事实（模板演进不自动迁移、靠 reset），在同一个小节并列即违反"不重复"原则。
    location: "变更 5 · _模板/README.md「改模板的注意事项」"
    reason: "硬阻断 #1（违背'不重复'文档维护原则）：同一信息在紧邻的两条 bullet 中出现两次。"
    fix_direction: "不追加第二条，而是把'冻结/只作用新书'的措辞融进第 1 条重写（如：'改模板不会自动同步到已存在的内容文件——字段结构一旦有内容落盘即冻结，模板/字段演进只作用于新书/新角色；在写的书需人工迁移或跑 reset'）。"
soft_blocks:
  - id: S1
    description: >
      变更 2 把 `04_伏笔/README.md` 列为目标文件，但"改动"段完全没写 README 要改什么。且 README 现有字段清单"（ID / 内容 / 预期回收方式 / 状态 / 期限）"与"怎么用"三步（设定回收期限/记录实际回收方式）在新 9 列（触发条件/回收方式与后果）与新生命周期（埋设→触发→回收/放弃）下会失实；README 里的"预期回收方式"与表列名"预计回收位置"本就不一致，计划未顺手统一。
    location: "变更 2 · 04_伏笔/README.md"
    severity: 中
  - id: S2
    description: >
      变更 1 "事实分仓"的"世界观硬设定 + docs/style-locked.md = 稳定 canon"与既有"受保护文档"硬约束条目重叠（该条目已点名世界观硬设定、style-locked 的保护），且新引入的"canon / 历史真源 / 当前可计算态"是全新英文/造词术语，未与既有词表（硬设定 / 锁定层 / 受保护文档）对齐，下游用户需额外建立术语映射。核心增量"未来意图不随进度自动改"确实新，但外包装术语偏重。
    location: "变更 1 · _分发/AGENTS.md 硬约束段"
    severity: 中
  - id: S3
    description: >
      变更 4 落点标"reviewer 软阻断维度"，但该法则后半句"核心线索/伏笔不能因一次失败彻底断线"是客观可判定的（等价既有硬阻断"伏笔悬空/断线"），全归软阻断会弱化其执行力；同时"软阻断维度"措辞与变更 3 新引入的 reviewer `dimension` 字段容易混淆，两个变更各自用"维度"指不同东西。
    location: "变更 4 · docs/writing-style.md 第 7 行落点列"
    severity: 中
  - id: S4
    description: >
      变更 3 在给 hard_blocks/soft_blocks 加 dimension、末尾加 keep 的同时，未处理两份文件之间既有的输出格式分叉：reviewer-prompt-template 的 hard_blocks 含 `violated_rule` 而 reviewer-protocol 没有；soft_blocks 前者含 location/severity 而后者只有 id/description。照此落地，新增字段会叠加在两条本就分叉的 YAML 模板上，分叉继续扩大而非收敛。
    location: "变更 3 · 05_复盘/reviewer-prompt-template.md vs reviewer-protocol.md（及各自 _模板/ 副本）"
    severity: 低
flags:
  - id: F1
    description: "变更 2 引入生命周期阶段"触发"，但脚本状态白名单仍为 open/closed/abandoned，无对应 status 值；"已触发未回收"的伏笔如何表示（仍标 open？加新状态值？）未定义，落地后登记规则与脚本校验可能错位。"
  - id: F2
    description: "变更 2 表头说明 prose 要求登记时必填"触发条件"+"回收方式与后果"，但脚本只对 open 状态查"回收方式与后果"为空，触发条件为空无任何检查，abandoned 状态的回收方式与后果是否要求也未说明——prose 强制力与脚本 enforcement 范围不一致。"
  - id: F3
    description: "变更 1 把"统摄性心智模型"用与其余条目完全相同的 bullet 格式放在硬约束段首条，落地者可能误当普通并列条目而非统摄性框架；且条目标 `[你负责]`（无脚本覆盖）与计划标题"新硬约束"之间的张力未在文中说明。"
  - id: F4
    description: "验证段对 `template.py check` 的注释写"模板↔内容成对一致"，但 _模板/README.md 对该命令的描述是"模板→内容文件是否存在、是否已填写"，两者不一致 [UNCERTAIN：scripts/template.py 未读，无法确认其是否含内容一致性比对]——若只查存在性，则 H2 的成对 README 遗漏不会被该命令拦截。"
  - id: F5
    description: "check_foreshadowing.py 中 `expected_cols` 变量本为死代码（定义后从未引用），计划以"更新 expected_cols"作为脚本改动主表述，暴露计划作者未精读脚本实现，建议落地前全文通读该脚本。"
reads:
  - C:/Project/novel_world_one/docs/plans/active/20260814-denova借鉴落地.md
  - C:/Project/novel_world_one/AGENTS.md
  - C:/Project/novel_world_one/_分发/AGENTS.md
  - C:/Project/novel_world_one/.githooks/commit-msg
  - C:/Project/novel_world_one/docs/writing-style.md
  - C:/Project/novel_world_one/_模板/README.md
  - C:/Project/novel_world_one/05_复盘/reviewer-prompt-template.md
  - C:/Project/novel_world_one/05_复盘/reviewer-protocol.md
  - C:/Project/novel_world_one/_模板/05_复盘/reviewer-prompt-template.md
  - C:/Project/novel_world_one/_模板/05_复盘/reviewer-protocol.md
  - C:/Project/novel_world_one/04_伏笔/伏笔登记表.md
  - C:/Project/novel_world_one/_模板/04_伏笔/伏笔登记表.md
  - C:/Project/novel_world_one/04_伏笔/README.md
  - C:/Project/novel_world_one/scripts/check_foreshadowing.py
  - C:/Project/novel_world_one/docs/audit-checklist.md
  - C:/Project/novel_world_one/docs/workflow.md
  - C:/Project/novel_world_one/docs/decisions.md
  - C:/Project/novel_world_one/docs/frontmatter-schemas.md
  - C:/Project/novel_world_one/docs/CURRENT.md

