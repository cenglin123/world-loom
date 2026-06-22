# 初始化文档体系

- **日期**：2026-06-23
- **状态**：✅ completed
- **规模**：中型（小说创作项目，含全套 docs/ + plans/ + 内容目录 + 脚本 + hook）

## 项目画像（10 维度）

1. **项目做什么**：长篇小说写作。agent 按四阶段工作流（宪法审查→准备→执行→复盘）辅助推进。
2. **技术栈**：Markdown（Obsidian 兼容），Python 工具脚本，Git，bash hook
3. **硬约束**：世界观核心设定 locked（改需 ultraverge）；人设内核不可轻改；伏笔必须登记；人物记忆必须回写；不得绕过 pre-commit hook
4. **已存在文档**：无（全新项目，已删除 Obsidian 欢迎文件）
5. **AI Agent**：Claude Code（加载 CLAUDE.md），Codex（加载 AGENTS.md），Gemini CLI（加载 GEMINI.md）
6. **构建产物**：不适用（非代码项目）
7. **测试**：不适用——小说不靠自动化测试，靠 converge 多视角互审
8. **协作倾向**：单 Agent 顺序推进为主，复盘阶段并行多人 review
9. **常见任务类型**：推进剧情（走四阶段闭环）> 人设/世界观微调 > 复盘审计
10. **文档语言**：中文

## 创建的文件清单

- AGENTS.md / CLAUDE.md / GEMINI.md（同步）
- STRUCTURE.md
- README.md
- CHANGELOG.md
- .gitignore
- scripts/（changelog.py / agent_links.py / audit.py，取自 init-agent-docs assets）
- .githooks/pre-commit
- docs/（CURRENT / overview / writing-style / pitfalls / audit-checklist / plans/）
- 世界观/（核心设定 / 外围设定）
- 大纲/（主线）
- 人物/（_索引 + 三份模板）
- 正文/（README）
- 伏笔/（登记表）
- 复盘/（README + 模板）

## 初始化自检结果

- sync check: pass
- audit check: 预期 directory-link 告警（正文/ 复盘/ 等为目录非文件，audit.py 按代码项目设计，不影响小说项目使用）。AGENTS.md 129 行/437 词（接近限，但小说项目需要嵌入四阶段工作流操作协议）。
- 初始化未触达的步骤：小型项目省略记忆系统（不建 .agent/memory/），init-agent-docs 设计哲学第 8 步 reviewer-perspective 自检——当前仅主 agent 执行初始化，未做 subagent blind read 验证（待后续任务中补）。
