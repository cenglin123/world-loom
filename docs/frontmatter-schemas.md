# Frontmatter Schema

> 各文件类型的 frontmatter 字段定义。唯一权威源——`AGENTS.md` 与 `05_复盘/reviewer-protocol.md` 的 schema 引用均指向此处。

## 人物卡（`02_人物/<角色名>.md`）

模板实例：[[02_人物/人物模板]]。`python scripts/check_tags.py wizard <角色名>` 会从模板创建并引导填写。

```yaml
---
status: alive        # alive|dead|departed|unknown
role: protagonist    # protagonist|antagonist|deuteragonist|supporting|minor
age: 
faction:             # 所属/阵营
first_appearance:    # 卷/章
world_position:      # 上层|下层|边缘|中心
style_register:      # 文风注册（对应 docs/style-locked.md 文风注册表）
tags:
  - 所属/<组织名>
  - 能力/<能力流派>
  - 等级/<武学等级>
  - 擅用/<武器类型>
---
```

`#tags` 用于 Obsidian 标签面板和 Dataview 快速筛选——agent 写前准备时可按 `#所属/七瑶门` 检索同组织角色、按 `#等级/一流` 定位实力层级。

## 章节正文（`03_正文/第N卷/第M章.md`）

```yaml
---
model: deepseek-v4
generated_at: 2026-06-23T10:00:00Z
volume: 1
chapter: 3
characters_present: ["沈照影", "顾寒枝"]
location: "映月湖"
in_world_date: "大业三年·霜月·初七"
word_count: 3240
status: draft
# author: human   # 仅用户手写章节声明；agent 章节用 model/generated_at，不写 author
---
```

**白名单判据**：agent 章节须有 `model`/`generated_at`；用户手写章节须显式 `author: human`。二者皆无 → pre-commit 阻断（封"沉默漏标"）。

## 写后审结论（`03_正文/第N卷/_工作/_审查后_第M章.md`）

```yaml
---
model: <审稿 agent 模型>
generated_at: 2026-06-25T10:00:00Z
volume: 1
chapter: 3
verdict: 可收敛        # 可收敛 | 需修复（对齐 reviewer-protocol）
blocking_count: 0
flag_count: 1
rounds: 1
# covers: [3, 4, 5]    # 可选：一次写后审覆盖多章
---
```

此 artifact 存在仅证明留痕，**不证明审查质量/独立性**。
