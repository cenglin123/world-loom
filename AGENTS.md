# world-loom 开发仓协作规范

> `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` 内容一致；只编辑本文件，另两个由脚本同步。
> **本文件是开发层规范，不对外分发。** 使用层规范（下游用户拿到的那份）在 `_分发/AGENTS.md`。

## 本仓是什么

world-loom 小说创作辅助系统的**开发仓**。产出物是一套分发给写作者的工具包——模板骨架、治理机制、脚本工具链、方法论文档。

本仓同时是这套工具的 dogfooding 环境：可以在这里真的写一本小说来检验工具好不好用。**写正文时的规则见 `_分发/AGENTS.md`**——那是使用层的唯一权威源，不在本文件重复。

## 三层结构

| 层 | 是什么 | 分发 | 权威源 |
|----|--------|------|--------|
| **源码层** | `_模板/` + `_分发/` + `.githooks/` + `scripts/` + 使用层方法文档 + `example_world/` | ✓ 推公开仓 | — |
| **内容层** | 世界观填写、大纲、角色卡、正文、伏笔、卷复盘、`docs/{decisions,CURRENT,style-locked,CHANGELOG,plans}` | ✗ 只留本地 | — |
| **开发层** | 本文件、`docs/development.md`、converge 治理记录 | ✗ 只留本地 | — |

划分清单唯一权威源：`scripts/layers.py`。开发层在机制上等同内容层（都不分发），区分只在语义——内容层是"这本书的创作产物"，开发层是"造这套工具的过程"。

## 分发机制

```
python scripts/publish.py            # 预览：列出将公开的文件
python scripts/publish.py --force    # 剥内容层 + 映射 _分发/ + 推送
```

`publish.py` 做三件事：

1. 以 HEAD 建临时索引，删掉全部内容层与开发层路径
2. **把 `_分发/AGENTS.md` 映射到目标树的 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md`**，然后从树里移除 `_分发/` 本身
3. 复核零泄漏 → 打印完整文件清单 → `--force` 才推

`git push` 被 `.githooks/pre-push` 默认拒绝；推整仓到私有远端 → `git push --no-verify`。

**改使用层规则时改 `_分发/AGENTS.md`，不是本文件。** 改完不需要跑 agent_links——那个脚本管的是根目录三文件（开发版）的一致性。

## 治理机制

`.githooks/commit-msg` 的 `GOVERNANCE_FILES` 清单内任一文件被改 → commit message 必须含 `[governance]` 标记。清单为唯一权威源，新增治理文件只改那一处。

清单覆盖两类：**使用层的受保护文档**（世界观硬设定、style-locked、审计清单、reviewer 协议等，保护下游用户的创作基线）+ **开发层的机制文件**（layers.py、publish.py、hooks、`_分发/AGENTS.md`）。

## 同步声明

`python scripts/agent_links.py check` / `repair` / `repair --force`，模式 copy。管的是根目录 AGENTS/CLAUDE/GEMINI 三文件（开发版）。

## 信息导航

| 需要什么 | 去哪找 |
|---------|--------|
| 使用层规范（下游用户拿到的） | `_分发/AGENTS.md` |
| 分发流程细节、源码层清单、闸门机制 | [[docs/development]] |
| 空白骨架与重置命令 | [[_模板/README]] + `scripts/layers.py`（划分权威源） |
| 当前任务状态 | [[docs/CURRENT]] |
| 变更记录 | [[docs/CHANGELOG]] |
| 开发计划 | [[docs/plans/active/]] |
| converge 协议 + reviewer 模板 | [[05_复盘/reviewer-protocol]] → [[05_复盘/reviewer-prompt-template]] |

## 行为规则

### Compact 恢复（强制）

若上下文含 "continued from a previous conversation"，在继续任何实质性工作前：
1. 读 [[docs/CURRENT]] — 确认当前任务状态
2. 上述步骤完成前，**禁止写操作、禁止有副作用的判断**

### 默认偏好

- **先读后改**：修改任何文件前先读取，理解现有内容再动手。
- **Occam**：如无必要，勿增实体。
- **Bitter Lesson**：通用方法优于硬编码先验。语义一致性交 LLM 理解 + converge 审查，不硬编词表和规则表。
- **机制优先**：能用脚本/hook 兜底的，不要靠 agent 记得操作。判据见 [[docs/development]]「机制化三分判据」。
- **执行模式**：单场对话内的小修直接执行；跨文件、改治理规则的走 converge。

## 文档维护原则

1. **不重复**：同一信息只在最合适的位置出现一次。使用层内容只在 `_分发/AGENTS.md`，开发层只在本文件
2. **无补丁感**：文档只描述当前的自洽规则，不留演进痕迹（"原为…现改为…"/"v2 新增"/"不再使用…"）。新内容要融进既有结构并重排编号措辞，不是追加在末尾。变更史归 CHANGELOG 与 `docs/plans/completed/`——那里才记录变化
3. **分发前自检**：改动使用层文档后，跑一次 `python scripts/publish.py`（dry-run）确认清单里没有混进开发层文件
4. **CHANGELOG**：用 `python scripts/changelog.py titles/show/add/recent`，不读全文
5. **计划落盘**：跨文件的改造在 `docs/plans/active/` 写计划，完成后移 `completed/`
6. **定期审计**：每 ~20 次任务或每月，跑 `python scripts/audit.py check`

## 完工必检

```
python scripts/check_all.py --quiet
python scripts/publish.py              # dry-run，确认分发清单
```

无输出 = 全部通过。每条 FAIL 自带修复指引。
