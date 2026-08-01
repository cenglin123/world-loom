# 正文

> 按卷存放。**正文目录只放正文**——四阶段工作流的过程文件收在各卷的 `_工作/` 里。

## 目录结构

```
03_正文/
└── 第1卷/
    ├── 第1章.md              ← 正文
    ├── 第2章.md
    └── _工作/                 ← 过程文件，不与正文混放
        ├── _准备_第1章.md      ② 写前上下文包
        ├── _审查_第1章.md      ① 宪法审查结论
        └── _审查后_第1章.md    ③ 写后审稿结论
```

宪法审查可以卷级覆盖多章——写 `_工作/_审查_第1卷.md`，各章 frontmatter 用 `review_ref:` 指向它，不必逐章一份。

`check_chapters.py` 会检出放错位置的过程文件（散在卷目录下而非 `_工作/`）。

## 格式约定

- 每章 frontmatter 标注 `model` / `generated_at`（agent 写的正文）
- 用户自己写的章节标 `author: human`，豁免 model 检查与工作流留痕检查
- 完整字段定义见 [[docs/frontmatter-schemas]]

## 相关

- 四阶段工作流细则 → [[docs/workflow]]
- 审稿协议 → [[05_复盘/reviewer-protocol]]
- 写完之后的维护回写 → [[05_复盘/maintenance-executor]]
