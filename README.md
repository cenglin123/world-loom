# novel_world_one

> 一部面向 AI Agent 协作创作的长篇小说项目。

## 这是什么

以 **converge 迭代收敛**为质量控制核心的小说创作仓库。文档体系按四阶段方法论构建——①宪法审查 → ②写前准备 → ③推进执行 → ④阶段复盘。主管 agent 加载 [AGENTS.md](AGENTS.md) 后即可独立运转全部流程。

世界观层融合了三套设计方法论：**以筠世界观设计系列**（物理→社会→张力三层衍生 + 代价体系 + 设定失效驱动）+ **端木灵星传统写作技法**（选题/矛盾/悬念/开篇铁律）+ **业界 AI 长篇写作实践**。

## 快速开始

### 人类作者
1. 打开 [AGENTS.md](AGENTS.md)，让 agent 引导你完成所有设定——**写作前先 `git checkout -b writing`**
2. 想创建角色？告诉 agent，它会跑 `wizard` 逐字段带你填
3. 想推进剧情？告诉 agent 方向，它会跑宪法审查 → 写前准备 → 执行 → 复盘

### AI Agent
1. 加载 [AGENTS.md](AGENTS.md) → 理解项目结构、硬约束、四阶段工作流
2. 接到"推进剧情"任务 → 先跑就绪自检 → 通过后按 ①→②→③→④ 执行
3. 使用 `python scripts/check_tags.py wizard <角色名>` 引导用户创建角色
4. 提交前自动触发 pre-commit 六道硬检查 + commit-msg 治理文档保护
5. **所有写作在 `writing` 分支上进行**——`main` 仅存模板，永不推送写作内容（见 [AGENTS.md §分支策略](AGENTS.md)）

## 项目结构

```
├── AGENTS.md / CLAUDE.md / GEMINI.md   # Agent 入口（三文件同步）
├── README.md                            # 人类入口
├── docs/                                # 项目文档
│   ├── CURRENT.md                       # 当前任务状态
│   ├── overview.md                      # 项目总览 + 设计决策
│   ├── writing-style.md                 # 叙述约定 + 端木技法 + 以筠法则
│   ├── audit-checklist.md               # 一致性审计清单
│   ├── pitfalls.md                      # AI 写作陷阱记录
│   ├── CHANGELOG.md                     # 变更日志
│   └── plans/                           # 执行计划
├── 00_世界观/                            # 核心设定（物理层 locked）+ 外围设定
├── 01_大纲/                              # 主线 + 分卷 + 主线来源表
├── 02_人物/                              # 角色文件 + 模板 + 关系JSON + 标签体系
├── 03_正文/                              # 按卷存放章节 + 上下文包 + 审查记录
├── 04_伏笔/                              # 伏笔登记表（open/closed 状态机）
├── 05_复盘/                              # converge 协议 + reviewer 启动模板 + 复盘记录
├── scripts/                              # CLI 工具链
│   ├── relationship.py                  # 人物关系四格 CRUD
│   ├── check_tags.py                    # 标签校验 + 角色创建向导
│   ├── check_chapters.py                # 章节时空一致性 + 就绪自检
│   ├── check_foreshadowing.py           # 伏笔状态机检查
│   ├── changelog.py / agent_links.py / audit.py  # 文档维护工具
└── .githooks/                            # pre-commit（6 道硬检查）+ commit-msg（治理保护）
```

## 质量门控

| 机制 | 检查项 |
|------|--------|
| **pre-commit 阻断** | AGENTS.md 同步 / 伏笔表格式 / 关系 JSON 完整性 / 标签四类完整性 / 章节时空一致性 + 就绪自检 |
| **pre-commit 提醒** | 人物卡更新提醒（上下文包中的在场角色卡是否同期修改） |
| **commit-msg 阻断** | 治理文档修改必须含 `[governance]` 标记 |

## 分支说明

| 分支 | 内容 | 推送 |
|------|------|------|
| `main` | 模板——治理机制、脚本、空模板文件 | → GitHub |
| `writing` | 写作——角色、正文、记忆、关系、伏笔等所有创作内容 | **本地不推送** |

```bash
git clone <repo>              # 拿到干净模板
git checkout -b writing       # 开写作分支（内容隔离，不会推到 GitHub）
git checkout main             # 回到模板状态
git checkout -b novel-two     # 从模板开一本新书
```

## 技术说明

- **文档格式**：Markdown（Obsidian 兼容，支持 wikilink `[[]]`）
- **版本控制**：Git（`.gitignore` 已排除 `.obsidian/`）
- **治理工具**：converge 迭代收敛（本地实现，不依赖外部 SKILL）
- **方法论依据**：converge 迭代收敛 + 以筠世界观设计 + 端木灵星传统技法 + 业界 AI 写作实践
