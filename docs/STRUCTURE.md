# novel_world_one — 文档索引

> 协作规则和完工检查统一以 [AGENTS.md](../AGENTS.md) 为准。本文件是项目全部文件/目录/工具的统一索引——AGENTS.md 信息导航指向这里。

## 入口

| 需要了解 | 文件 |
|---------|------|
| Agent 操作准则 + 规则 | [AGENTS.md](../AGENTS.md) |
| 人类面向项目说明 | [README.md](../README.md) |

## 项目文档

| 需要了解 | 文件 |
|---------|------|
| 项目总览 + 世界观梗概 + 设计决策 | [docs/overview.md](overview.md) |
| 叙述约定（视角/时态/文风/端木技法） | [docs/writing-style.md](writing-style.md) |
| AI 写作已知陷阱 | [docs/pitfalls.md](pitfalls.md) |
| 一致性审计清单 | [docs/audit-checklist.md](audit-checklist.md) |
| 当前任务状态 | [docs/CURRENT.md](CURRENT.md) |
| 变更记录 | [docs/CHANGELOG.md](CHANGELOG.md) |
| 复杂任务计划 | [docs/plans/active/](plans/active/) |

## 设定文件

| 需要了解 | 文件 |
|---------|------|
| 世界观·硬核心（locked） | [00_世界观/核心设定.md](../00_世界观/核心设定.md) |
| 世界观·外围（可扩展） | [00_世界观/外围设定.md](../00_世界观/外围设定.md) |
| 故事大纲（主线 + 分卷） | [01_大纲/主线.md](../01_大纲/主线.md) |
| 人物索引 + 关系矩阵 + 标签汇总 | [02_人物/_索引.md](../02_人物/_索引.md) |
| 人物关系数据源（CLI 维护） | [02_人物/relationships.json](../02_人物/relationships.json) |
| 人物创建向导 | `python scripts/check_tags.py wizard <角色名>` |
| 人物模板 | [02_人物/人物模板.md](../02_人物/人物模板.md) |
| 伏笔登记表 | [04_伏笔/伏笔登记表.md](../04_伏笔/伏笔登记表.md) |
| 正文章节 | [03_正文/README.md](../03_正文/README.md) |

## 复盘与质控

| 需要了解 | 文件 |
|---------|------|
| 复盘记录 | [05_复盘/README.md](../05_复盘/README.md) |
| Converge 本地协议 | [05_复盘/reviewer-protocol.md](../05_复盘/reviewer-protocol.md) |
| Reviewer 启动模板 | [05_复盘/reviewer-prompt-template.md](../05_复盘/reviewer-prompt-template.md) |
| 复盘模板 | [05_复盘/复盘模板.md](../05_复盘/复盘模板.md) |

## 工具脚本

| 命令 | 作用 |
|------|------|
| `python scripts/agent_links.py check/repair` | AGENTS.md 同步 |
| `python scripts/audit.py dead-links` | 断链检查 |
| `python scripts/audit.py structure` | 索引完整性 |
| `python scripts/changelog.py titles/show/add/recent` | CHANGELOG 操作 |
| `python scripts/check_foreshadowing.py` | 伏笔状态机 |
| `python scripts/relationship.py list/show/set/update/delete/regenerate/check` | 关系 CRUD |
| `python scripts/check_tags.py wizard/check/list/show/regenerate/_index` | 标签 + 人物向导 |
| `python scripts/check_chapters.py --staged/--readiness` | 章节时空校验 |
