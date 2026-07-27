# init-agent-docs 改进计划：完工检查脚本化 + 细节指令下沉

> 基于 `novel_world_one` 仓库治理重构的实践经验。目标：让 init-agent-docs 产出的文档体系**默认不需要 agent 记忆任何可脚本化的事项**，且 AGENTS.md 模板本身就示范了"不重复、只放指针"的极致形态。

## 现状问题

### P0：完工检查清单依赖 agent 记忆

当前 AGENTS.md.tpl 的「完工检查清单」是 7 条自然语言清单，每条都要求 agent **记得去跑并逐项确认**。这违反了设计哲学第 9 条"软约束靠文档，硬约束靠工具"——完工检查是高频重复动作，却完全靠 agent 记忆力兜底。

具体问题：
- "同步一致性"要求 agent 记得跑 `agent_links.py check` —— 但 pre-commit 已经强制，且 agent 不知道 hook 会兜底
- "CHANGELOG.md"是否值得记录——agent 不知道什么是"值得"
- "验证"——模糊到无法操作化
- "记忆自检"——写出/读入两段散文，agent 在任务结束时的认知负载高峰下不可能逐字执行

### P1：AGENTS.md.tpl 自身就违反自己的行数上限

设计哲学第 1 条说"控制在 200 行 / 400 词以内"，静态自检第 9 条说"不超过约 200 行"。但当前模板（含占位注释和候选项）即使中型规模裁剪后也轻松超过 200 行——完工检查清单 + 文档维护原则 + 硬约束枚举 + 项目记忆段 + 多 Agent worktree 路由 + 安全与配置 + 测试要求加起来早已超标。模板本身在教 agent 做一件自己做不到的事。

### P2：硬约束枚举与 hooks 双源漂移

`AGENTS.md.tpl` 的硬约束节包含 `密钥不入库`、`不碰构建产物`、`不绕过 hook` 等条目。这些规则的真正执行者是 pre-commit / CI / lint 配置。AGENTS.md 另起一套散文版描述，意味着修改 hook/CI 后必须同步 AGENTS.md —— 一旦不同步，agent 基于过时描述行动。设计哲学第 9 条明确说"能用工具强制的规则优先编码为工具"，但模板自身没做到。

### P3：完工检查清单和"完工必检"硬约束的重复

模板中「硬约束」节有 `完工必检：任务完成后必须执行末尾的完工检查清单`，然后清单自身又写了一遍"每次编辑任务完成后必须逐项走完"。同一要求在文档里出现了三次（硬约束 + 清单头 + AGENTS.md 口头约定），违反"不重复"原则。

### P4：文档维护原则的散文式枚举

10+ 条"文档维护原则"逐条描述每个 docs/ 文件的更新时机、CHANGELOG 操作规则、合并/拆分阈值。其中 CHANGELOG 规则（titles/show/add/recent）已经由 `changelog.py` 脚本承载，AGENTS.md 不需要翻译脚本功能。文件更新时机的判断属于 agent 常识，不值得用 14 条散文保护。

### P5：细节指令留在 AGENTS.md 而非子文档

- "项目记忆"段的完整维护说明（含 maintain.py 调用、索引标记段说明）在 AGENTS.md 里
- "任务前记忆检索"的 3 步流程在 AGENTS.md 里
- "Bugfix 沉淀"的 4 条写作规范在 AGENTS.md 里
- "多 Agent worktree 路由"的四动作语义在 AGENTS.md 里

这些都有对应的子文档（MEMORY.md、_template.md、workflow-patterns.md），AGENTS.md 只需要告诉 agent "去哪找"，不需要在此复述。

---

## 改进方案

### 改 1：新增 `scripts/check_all.py` 到 assets，完工检查清单改为单条命令

**这是本计划最核心的改动。** 从 `novel_world_one` 的实践经验提炼出一套通用模式。

新增文件：`assets/scripts/check_all.py`

核心设计：
```python
# 设计原则：
# 1. --quiet 模式下，无输出 = 全部通过（不消耗 agent 注意力）
# 2. 每条 FAIL 自带修复指引（agent 不需要记忆"失败后做什么"）
# 3. CHECKS 列表是检查项的单一权威源（AGENTS.md 不枚举）
```

检查项（按 target project 实际情况动态生成或用默认集）：
1. 同步：`agent_links.py check` → 修复指引: `agent_links.py repair`
2. 死链：`audit.py dead-links` → 修复指引: 检查标 dead 的链接
3. CHANGELOG 可读性：脚本至少能输出一条标题
4. AGENTS.md 行数：不超过 ~250 行（从 200 上修，见改 3）

**AGENTS.md.tpl 的「完工检查清单」节改为**：

```markdown
## 完工必检

python scripts/check_all.py --quiet

无输出 = 全部通过。每条 FAIL 自带修复指引。
```

7 条清单 → 1 条命令。agent 零记忆负担。

同步更新模板中「硬约束」节的 `完工必检` 条目，改为指向 `check_all.py` 而非"必须执行末尾清单"。

### 改 2：新增 `docs/frontmatter-schemas.md` 到 assets templates

从 `novel_world_one` 的经验：frontmatter 字段定义是引用性数据（agent 查字段时才读），放在 AGENTS.md 里会永久占据 ~40 行。

新增模板：`assets/templates/zh/frontmatter-schemas.md.tpl`（不需要 .tpl——一个空壳即可，由项目填充具体字段）。

AGENTS.md.tpl 的信息导航表追加一行：
```markdown
- 文件格式约定（frontmatter schema）：[docs/frontmatter-schemas.md](docs/frontmatter-schemas.md)
```

这不适用于所有项目（很多项目没有自定义 frontmatter），所以作为可选行——初始化时如果目标项目不需要 frontmatter schema，跳过。

### 改 3：AGENTS.md 行数上限从 200 上修到 250

200 行 / 400 词在实践中过于激进。`novel_world_one` 的 152 行是小说项目特例（四阶段工作流本身就短，且没有 API/部署/测试/安全等通用软件的必需节）。通用模板需要在以下节中保留足够信息：
- 项目概述 + 信息导航（~30 行）
- 行为规则：compact 恢复 + 硬约束 + 默认偏好（~40 行）
- 多 Agent worktree 路由（~10 行，仅协作倾向项目）
- 测试要求 + 安全与配置（~15 行，按项目裁剪）
- 提交规范 + 文档维护原则（~30 行）
- 完工必检（~5 行）

合计 ~130 行，留 120 行给项目特异内容。250 行是现实上限。

同步更新：
- `SKILL.md` 设计哲学第 1 条的 `200 行 / 400 词` → `250 行`
- `SKILL.md` 静态自检第 9 条的 `约 200 行` → `约 250 行`
- `AGENTS.md.tpl` 的 docs/ 文件治理规则中的 `200 行/400 词` → `250 行`

### 改 4：硬约束节收敛——不枚举 hooks 已强制的事项

当前「硬约束」混合了两种内容：
1. 项目特异约束（密钥路径、构建产物路径）——合理留在 AGENTS
2. hooks/脚本已强制的通用规则（不绕过 hook）——应删除或压缩为指针

改进：模板中的通用候选项 `不绕过 hook`、`完工必检`（改为"跑 check_all.py"后已是单条命令）删除或压缩。项目特异的约束保留。新增一行指针：

```markdown
> 以下条目是**没有脚本兜底**的规则。有机执行由 `.githooks/pre-commit` / CI 强制，其具体检查逻辑见各 hook 脚本自身，AGENTS.md 不逐条翻译。
```

### 改 5：文档维护原则压缩

当前 14 条 → 压缩为 5 条核心规则 + 指针：

```markdown
## 文档维护原则

1. **不重复**：同一信息只在最合适的位置出现一次
2. **只记代码/正文里读不出来的东西**：设计原因、协作约束、环境陷阱
3. **CHANGELOG**：用 `python scripts/changelog.py titles/show/add/recent`，不读全文
4. **计划落盘**：跨模块/跨会话的任务在 `docs/plans/active/` 写计划，完成后移 `completed/`
5. **定期审计**：每 ~20 次任务或每月，跑 `python scripts/audit.py check`（有记忆系统用 `maintain.py`）

> docs/ 文件的治理规则（存在条件、合并条件、创建/删除原则）见 [docs/STRUCTURE.md](docs/STRUCTURE.md)「文件治理」段。
```

原来 14 条中的 CHANGELOG 操作细节（titles/show/add/recent）→ 脚本已有 help 和 SKILL.md 文档；文件更新时机判断 → agent 常识；合并/拆分阈值 → 下沉到 STRUCTURE.md。

### 改 6：项目记忆段压缩为指针 + 内联摘要

当前的"项目记忆"段含 maintain.py 调用说明、索引标记段说明、日常维护步骤——这些应该只在 MEMORY.md 和 maintain.py --help 里。

改进：AGENTS.md.tpl 的「项目记忆」段只保留 ~5 行摘要 + 一句指针。维护细节留给 maintain.py 和 SKILL.md 第 5.5 步。

### 改 7：任务前记忆检索 + Bugfix 沉淀 → 下沉到子文档

当前 3 步检索流程在 AGENTS.md 中占用 ~12 行。改为：

```markdown
### 任务前记忆检索

除非任务非常简单明确，开始前先查经验系统：`.agents/memory/MEMORY.md` 索引段 → 按需深入。
Bugfix 任务另见 [docs/problems/bugfix/_template.md](docs/problems/bugfix/_template.md) 前置规则。
```

检索步骤的详情（git log -15, MEMORY.md 索引, 触发词硬性前置的具体词表）→ 下沉到 MEMORY.md 的索引段引导文案或 _template.md。

Bugfix 沉淀的 4 条写作规范 → 已经在 `_template.md` 里，AGENTS.md 只需一行指针。

### 改 8：SKILL.md 同步上述改动

- 设计哲学第 1 条：行数 200→250
- 设计哲学第 9 条：增加 `check_all.py --quiet` 模式的说明，作为"硬约束靠工具"的示范案例
- 静态自检第 9 条：行数 200→250
- 第 7 步静态自检：增加 `check_all.py --quiet` 退出码为 0
- 反模式：新增"完工检查清单散文枚举"为反模式（当前反模式 12 "全靠软约束"已经接近，但没点到清单自己就是软约束）

### 改 9：check_all.py 的 CHECKS 列表需确认与目标项目规模匹配

`check_all.py` 需要知道目标项目的规模（小型/中型/大型），因为检查项不同：
- 小型：同步 + 死链 + CHANGELOG 可读 + AGENTS 行数
- 中型+：上述 + 记忆系统有效性 + STRUCTURE 索引完整性 + bugfix 索引

实现方式：`check_all.py` 启动时读取 AGENTS.md 的信息导航表判断规模，或接受 `--small` / `--medium` 参数。默认为中型。

---

## 改动清单

| # | 文件 | 改动类型 | 预估行数变化 |
|---|------|---------|------------|
| 1 | `assets/scripts/check_all.py` | **新增** | +80 |
| 2 | `assets/templates/zh/frontmatter-schemas.md.tpl` | **新增** | +15 |
| 3 | `assets/templates/zh/AGENTS.md.tpl` | 修改 | 250→180 行 |
| 4 | `assets/templates/zh/STRUCTURE.md.tpl` | 修改 | +10（接收下沉的治理规则） |
| 5 | `SKILL.md` 设计哲学 | 修改 | ~5 处数字/描述更新 |
| 6 | `SKILL.md` 第 7 步静态自检 | 修改 | +2 项（check_all.py 检查） |
| 7 | `SKILL.md` 第 2 步 | 修改 | 增加 frontmatter-schemas 到中型文件清单 |
| 8 | `SKILL.md` 反模式 | 修改 | +1（完工清单散文枚举） |
| 9 | README.md | 修改 | assets 目录树更新 |

### 不改的部分

- **`check_all.py` 不替代 `audit.py`**：`audit.py` 做结构/死链/漂移的深度检查；`check_all.py` 是高频完工检查，两者互补。`check_all.py` 内部调用 `audit.py dead-links` 作为一项，但不替代 `audit.py check` 的完整输出。
- **`check_all.py` 不替代 memory 系统的 touch/维护**：记忆回写是语义判断（"本次对话是否产生了值得沉淀的记忆"），脚本只能提示"距离上次记忆写入已 X 天"，不能替 agent 决定写什么。
- **`docs/ 文件治理规则`保留在 AGENTS.md**：这节是 AGENTS.md 对自身和 docs/ 关系的元规则，下沉后会形成"规则说要把自己下沉"的悖论。但可以压缩到 5 行。
- **SKILL.md 的 design philosophy 保持详尽**：SKILL.md 在初始化时被一次性加载，不会驻留，不需要压缩。只修改涉及行数、文件名、流程描述的引用。
