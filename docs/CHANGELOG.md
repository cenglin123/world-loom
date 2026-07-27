# CHANGELOG

> 倒序排列，最新在前。操作：python scripts/changelog.py titles/show/add/recent

## 2026-07-27

### 方法论去人名化：功能性文档改用描述性方法名

#### 变更内容
- 把各处按人名/期数命名的方法论引用改为描述其作用的名称，使 agent 不必先认人再解析方法。00_世界观/_设计方法.md 模块由 "#1/#2/#3/#5/#7" 改为 地形生成法/力量与代价体系/城镇选址评分法/底层视角法/反差身份设计法，删除 author 与知识库原文链接段；docs/writing-style.md "端木技法"→"可读性技法（连载长篇）"、"以筠·故事驱动法则"→"故事驱动法则"；核心设定/外围设定/人物模板/主线/伏笔登记表/style-locked/audit-checklist/example_world/check_foreshadowing.py 的引用同步改名；AGENTS.md 三处导航与 rubric 措辞同步（agent_links repair --force）。出处集中到 README 新增「参考来源」段（原作者与书名仅记于此）。历史记录（CHANGELOG 旧条目、docs/plans/completed/）不改写。

### [governance] 取消 main/writing 分支制度，改为单分支 + 推送闸门

#### 变更内容
- **动机**：分支隔离对用户难以分辨；但内容若不入库则失去版本历史与 diff 依据，整套复盘体系失效。最终方案取二者之长：**单分支、内容与源码同库全量入库（都有 git 历史）**，"不外泄"由推送闸门保证，而非分支纪律。
- **划分**：新增 `scripts/layers.py` 作为源码层/内容层划分的**唯一权威源**（`CONTENT_PATTERNS` + `SOURCE_EXCEPTIONS`），提供 `list-content` / `classify` / `verify-tree` 三个 CLI。
- **闸门**：新增 `.githooks/pre-push`——默认拒绝一切推送；`NOVEL_PUBLISH=1`（仅 publish.py 设置）时逐 ref 复核树内无内容层文件才放行。私有整仓推送的例外出口是 `git push --no-verify`，提示语内已写明。
- **分发**：新增 `scripts/publish.py`——以 HEAD 建临时索引剥离内容层 → write-tree/commit-tree 落到本地 `template-dist` 分支 → 复核零泄漏 → 打印将公开的完整文件清单 → `--force` 才推。默认 dry-run，工作区脏时拒绝执行。
- **模板层**：新增 `_模板/` 按原路径存放 9 个可填写文件的空白骨架（核心设定/外围设定/主线/_索引/relationships.json/伏笔登记表/overview/CURRENT/style-locked）+ `scripts/template.py`（check/init/reset，reset 默认 dry-run 需 --force）。
- **钩子调整**：pre-commit 删除 main 分支内容阻断段、新增模板层完整性检查，其余内容层检查照常生效（内容仍入库）；commit-msg 的 `GOVERNANCE_FILES` 补入 pre-push/layers.py/publish.py/_模板/ 下的治理骨架；check_chapters.py 去掉分支提醒，改为内容缺失时提示 `template.py init`。
- **新增 `scripts/check_all.py`**：7 个检查器一键跑全仓（hook 只扫暂存区），列为完工清单必检项。
- **附带**：新增 `.gitattributes`（`* text=auto eol=lf`）；`.claudian/`、`.converge/`、`example_world/*.png` 进 `.gitignore`；`_设计方法.md` 增题材换算表并把西幻专属例子改为西幻/武侠/仙灵/科幻不完全列举；style-locked 文风注册表标注为单一题材示例、需按本书重写；audit-checklist 机械项收敛为指向 check_all.py；主线.md 矛盾五路径改为指针不再重复列举。


---

## 2026-07-07

### 以筠系列第七期（角色反差身份）接入设计方法手册

#### 变更内容
- 00_世界观/_设计方法.md 新增 #7 角色反差身份节（表面身份 vs 秘密自我：四问框架/质量标准/行为一贯性+伏笔/张力-克制/反差被看见，395 字），更新 intro/跨期主线（增设角色层）/知识库原文链接。02_人物/人物模板.md 内核四维后补交叉链接指向 #7（反差两端=表面身份 vs 内核）。#6 仍交叉链接 writing-style 不复述。未触 AGENTS，无 [governance]。

---

## 2026-07-02

### 以筠世界观设计方法自足化（新增 00_世界观/_设计方法.md）

#### 变更内容
- 补足仓库自足性缺陷：README/世界观文件按编号引用『以筠世界观设计系列 #1/#2/#3/#5』，但方法本体仅在知识库、仓内为断头引用。新建 00_世界观/_设计方法.md，将 #1 地图生成/#2 魔法代价体系/#3 城镇选址/#5 下水道视角凝练为可执行步骤（各 200-400 字，署名 -以筠- + 知识库原文链接段），#6 交叉链接 docs/writing-style.md 不重复。外围设定.md/核心设定.md 引用处补仓内指针（设定内容零改动）。AGENTS.md 信息导航新增手册行并同步 CLAUDE/GEMINI。执行按 plan docs/plans/active/20260701-世界观构建方法-以筠系列自足化.md，含 S1.5 独立 reviewer 门控（verdict 可收敛，无硬阻断）。

### 修订角色扮演推进路线计划（按 claude-opus 评议）

#### 变更内容
- 对 docs/plans/active/20260628-角色扮演功能-边界厘清与推进路线.md 按评议未决项修订（补边界/细节，方向未变）：§3.3 反向判据补操作化测试；第二阶段新增前置任务 P2-a/b/c（场景选取标准/防破盲协议/盲审隔离注入包），对照场景≥2、退出条件去'显著'改定性判据；第一阶段退出条件量化 + L2 准入脚本化触发判据；§3.2.4 成本去 AgentSociety 伪精度锚点。计划仍 status:active——第一阶段待正文就绪（当前零正文）才能启动，非本次可执行。

### 角色扮演计划补执行自足性说明（仓内可执行确认）

#### 变更内容
- 对 20260628 计划做执行自足性审计：确认第一阶段（下一个可执行阶段）所有负载性依赖均仓内可解析（人物模板 L1/L2/L3 与写前注入/写后回写、内核四维、recall.py、reviewer-protocol、AGENTS §④ 人设演化留痕；AMAC/F3-F9 已 inline）。line-20 升级为『执行自足性地图』区分阶段；§5 内联三档目标三档含义（主判据/stretch/底线），并标注 critical 预算分级 §7.3 为 Phase 3 前需 inline 的残留项。方向未变、仍 active。

### 角色扮演计划整体夯实（去补丁化，通读连贯）

#### 变更内容
- 把 20260628 计划从补丁式文本整合为完整设计文档：评议修订全部就地融入正文（去掉'评议补/已上移/需 inline/删锚点/删除线'等补丁痕迹）；新增『执行自足性』小节以设计事实陈述取代原 line-20 补丁；三档目标含义内联 §5；冗长的评议问题清单收敛为『评议记录』紧凑治理附注。方向与内容未变，仅结构与措辞夯实。仍 active。




---

## 2026-07-01

### 评议：角色扮演功能边界厘清与推进路线计划

#### 变更内容
- 对 docs/plans/active/20260628-角色扮演功能-边界厘清与推进路线.md 做一次外部评议（claude-opus，verdict ⚠️ 修订后可执行）。评议摘要 inline 追加至该计划 ## Agent 评议 段（source_body_hash 65efa7af0d9ea5ed）。核心：方向正确、结构扎实，但 3 处缺口待补——反向判据缺操作化测试、第二阶段 A/B 退出条件不可证伪且破盲风险被降级、负载性待细化项应上移为第二阶段前置。第一阶段可即刻启动，第二阶段需先补判据。完整评议在对话中给出，未单独落库。

---

## 2026-06-25

### 四阶段工作流留痕机制 v2（建议 1+2+4 经 ultraverge 收敛）

#### 变更内容
- 白名单豁免（缺 model 须 author:human）；_准备_ 阻断、_审查_/_审查后_ 提醒；抽 docs/style-locked.md 单独治理保护；治理清单单一数据源；_审查后_ schema 对齐 reviewer-protocol；诚实标注 --no-verify/commit-time-only 盲区

---

## 2026-06-24

### 归档记忆召回设计决策（暂缓实现）

#### 变更内容
- 结论：不建注意力层/不给记忆打重要性分喂给 agent；改用 RAG 检索，且只用于'选哪些记忆进上下文'。重要性走结构（L1/锚点/未解决问题=保证注入），相关性走 embedding 检索（排序填剩余预算），两条正交轴。触发阈值：L2 涨到~数百条再实现。落盘 docs/plans/deferred/memory-retrieval.md。

---

## 2026-06-22
### 初始化文档体系
建立面向 AI Agent 的四阶段小说写作文档体系：AGENTS.md（含同步副本）+ STRUCTURE.md + docs/ 层级 + 00_世界观/01_大纲/02_人物/03_正文/04_伏笔/05_复盘 目录 + scripts/ + .githooks/。方法论基础：AI 辅助小说写作自动化方法论（converge 迭代收敛 + 端木灵星传统技法 + 业界 AI 写作实践）。
