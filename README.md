# world-loom

> 规则即土壤，故事自己长——面向 AI Agent 协作的小说创作辅助系统。

## 这是什么

以 **[converge](https://github.com/cenglin123/converge-skill) 迭代收敛**为质量控制核心的小说创作仓库。文档体系按四阶段方法论构建——①宪法审查 → ②写前准备 → ③推进执行 → ④阶段复盘。主管 agent 加载 [AGENTS.md](AGENTS.md) 后即可独立运转全部流程。

世界观层融合三条方法线：**结构化世界观构建**（物理→社会→张力三层衍生 + 代价体系 + 设定失效驱动）+ **连载长篇可读性技法**（选题/矛盾/悬念/开篇铁律）+ **业界 AI 长篇写作实践**。方法本身在仓库内自足描述，不依赖外部资料；出处见文末[参考来源](#参考来源)。

## 快速开始

### 人类作者
1. `python scripts/template.py init` —— 从 `_模板/` 生成空白骨架（克隆后第一步）
2. 打开 [AGENTS.md](AGENTS.md)，让 agent 引导你填世界观 / 大纲 / 角色
3. 想创建角色？告诉 agent，它会跑 `wizard` 逐字段带你填
4. 想推进剧情？告诉 agent 方向，它会跑宪法审查 → 写前准备 → 执行 → 复盘

### AI Agent
1. 加载 [AGENTS.md](AGENTS.md) → 理解源码层/内容层边界、硬约束、四阶段工作流
2. 接到"推进剧情"任务 → 先跑就绪自检 → 通过后按 ①→②→③→④ 执行
3. 使用 `python scripts/check_tags.py wizard <角色名>` 引导用户创建角色
4. 完工前跑 `python scripts/check_all.py` —— 全仓机械校验，完工清单必检项
5. 内容与源码同库同分支，正常 `git commit`；**`git push` 会被闸门拒绝**——分发走 `python scripts/publish.py`

## 项目结构

**源码层**（入库、可推送）：

```
├── AGENTS.md / CLAUDE.md / GEMINI.md   # Agent 入口（三文件同步）
├── README.md                            # 人类入口
├── _模板/                                # ★ 可填写文件的空白骨架（按原路径镜像）
├── docs/
│   ├── writing-style.md                 # 叙述约定 + 可读性技法 + 故事驱动法则
│   ├── audit-checklist.md               # 一致性审计清单
│   ├── pitfalls.md                      # AI 写作陷阱记录
│   ├── CHANGELOG.md / plans/            # 变更日志 + 执行计划
├── 00_世界观/_设计方法.md                 # 世界观构建方法手册
├── 02_人物/人物模板.md                    # 实例模板（每个角色复制一份）
├── 05_复盘/                              # converge 协议 + reviewer 模板 + 复盘模板
├── example_world/                        # 示例世界（教学用，非本书内容）
├── scripts/                              # CLI 工具链
│   ├── layers.py                        # ★ 源码层/内容层划分（唯一权威源）
│   ├── publish.py                       # ★ 剥离内容层后分发模板
│   ├── template.py                      # ★ 模板 ↔ 内容：check / init / reset
│   ├── check_all.py                     # ★ 全仓机械校验总入口
│   ├── relationship.py                  # 人物关系四格 CRUD
│   ├── check_tags.py                    # 标签校验 + 角色创建向导
│   ├── check_chapters.py                # 章节时空一致性 + 就绪自检
│   ├── check_foreshadowing.py           # 伏笔状态机检查
│   ├── changelog.py / agent_links.py / audit.py  # 文档维护工具
└── .githooks/                            # pre-commit + commit-msg（治理）+ pre-push（推送闸门）
```

**内容层**（同样入库、同样有 git 历史，但**永不对外推送**）：`00_世界观/{核心设定,外围设定}` · `01_大纲/` · `02_人物/`（角色卡 + 关系 JSON + 索引）· `03_正文/` · `04_伏笔/` · `05_复盘/第N卷_复盘.md` · `docs/{overview,CURRENT,style-locked}.md`
> 划分清单的唯一权威来源是 `scripts/layers.py`，推送闸门与分发脚本都从那里取。

## 质量门控

| 机制 | 时机 | 检查项 |
|------|------|--------|
| **pre-commit 阻断** | 每次提交 | AGENTS 三文件同步 / 模板层完整性 / 伏笔表格式 / 关系 JSON / 标签四类 / 章节时空一致 + 就绪自检 / 工作流痕迹（`_准备_` 缺失阻断）|
| **pre-commit 提醒** | 每次提交 | 人物卡更新提醒（上下文包中的在场角色卡是否同期修改） |
| **commit-msg 阻断** | 每次提交 | 治理文档修改必须含 `[governance]` 标记（清单见 `.githooks/commit-msg`） |
| **pre-push 阻断** | 每次推送 | **默认拒绝一切推送**，分发只能走 `publish.py` |
| **`scripts/check_all.py`** | 完工清单必跑 | 上述机械检查器的全仓版（hook 只看暂存区，这条看当前全量状态） |
| **复盘 converge** | 卷末 | 语义层——人设/记忆/世界观/伏笔漂移，机械层查不出的部分 |

## 单分支 + 推送闸门

**单分支运行，内容和源码都进 git，写坏了能 `git checkout` 回退。** 内容不外泄由推送闸门保证，不靠人为纪律：

```bash
git clone <repo>
python scripts/template.py init              # 生成空白骨架，开写
python scripts/template.py check             # 模板 → 内容对照表
git commit -m "feat: 第三章初稿"             # 内容照常入库，有完整历史

git push                                     # ✗ 被 pre-push 拒绝
python scripts/publish.py                    # 预览：将公开哪些源码层文件
python scripts/publish.py --force            # 剥离内容层后推送到 origin/main
git push --no-verify <私有远端> main          # 有意为之的例外：整仓（含正文）推私有仓

python scripts/template.py reset --all --force   # 开新书：内容层重置（git 里仍有历史）
```

`publish.py` 的保证：以 HEAD 为基础剥掉全部内容层 → 复核生成的树里**一个内容层文件都没有** → 打印将公开的完整文件清单 → 确认后才推。漏推不靠人记，靠脚本和 hook 双重兜底。

## 技术说明

- **文档格式**：Markdown（Obsidian 兼容，支持 wikilink `[[]]`）
- **版本控制**：Git（单分支，内容与源码全量入库；对外分发由 pre-push 闸门 + `publish.py` 把关；换行统一 LF）
- **治理工具**：converge 迭代收敛（本地实现，不依赖外部 SKILL）
- **方法论依据**：converge 迭代收敛 + 结构化世界观构建 + 连载长篇可读性技法 + 业界 AI 写作实践

## 参考来源

功能性文档只按方法本身的作用命名（如「地形生成法」「反差身份设计法」「可读性技法」），出处集中记在此处，便于 agent 直接理解方法含义而不必先认人：

- **世界观构建方法**（[00_世界观/_设计方法.md](00_世界观/_设计方法.md) 各模块 + [docs/writing-style.md](docs/writing-style.md) 故事驱动法则）：改编自 Bilibili UP 主 **-以筠-** 的世界观设计系列，仓库内为可执行凝练版，非原文转载。
- **连载长篇可读性技法**（[docs/writing-style.md](docs/writing-style.md)）：整理自端木灵星《小说写作、投稿技巧与经验汇总》。
- **converge 迭代收敛**：本地实现见 [05_复盘/reviewer-protocol.md](05_复盘/reviewer-protocol.md)。
