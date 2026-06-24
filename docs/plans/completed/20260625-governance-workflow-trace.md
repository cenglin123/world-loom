# 治理机制强化计划 · 四阶段工作流留痕

> 来源：2026-06-25 治理机制深度审计（converge audit 模式）。
> 目标：把「靠 agent 记性」的四阶段工作流（①宪法审查 →②写前准备 →③写后 reviewer）升级为「无痕不可提交」，并补上 commit 时刻的时空 P0 缺口。
> 状态：**评审基线**——待用户裁决建议 4 的 A/B，治理文档改动须走 ultraverge。

## 审计结论（现状）

机制基本正常：6 项脚本检查可运行、就绪哨兵正确阻断、commit-msg 治理标记生效。
**结构性单点**：所有强制都在 git commit 时刻；agent 工作会话期间零约束。「忘记调用」集中在此盲区——四阶段工作流完全无机械兜底。

关键漏洞（按"忘记调用"风险排序）：

| 编号 | 严重度 | 问题 | 对应建议 |
|------|--------|------|---------|
| P1-A | 高 | `check_chapters.py` 显式排除 `_审查_`/`_准备_`，且从不检查其存在。可裸提交章节，钩子无反应 | 建议 1 |
| P1-B | 高 | 写后 reviewer 不留痕、不可观测，compact 后痕迹全无 | 建议 2 |
| P1-C | 高 | 新伏笔登记不被检测（只校验已在表内条目格式） | 不写正则扫正文；并入 reviewer rubric + 建议 2 artifact 落痕 |
| P2-D | 中 | 记忆回写提醒只在 `_准备_*.md` 被提交时触发，挂在未强制前提下游 | 建议 1 激活后顺带解决 |
| P2-E | 中 | `--staged` 时空检查只在本批暂存章节内比对，跨已提交章节冲突检测不到 | 建议 3 |
| P2-F | 中 | `docs/writing-style.md` 是治理级（就绪自检依赖 + reviewer 查漂移）却未受 `[governance]` 保护 | 建议 4 |
| P3-G | 低 | 治理文件清单三处重复，仍在漂移（F 即一例） | 随建议 4 一并校正 CLAUDE.md 清单 |

## 设计前提（贯穿全部）

- 当前 0 章正文、0 真实角色 → 无存量迁移负担，是加钩子的最佳时机。
- **作者分离作为豁免判据**：用章节 frontmatter 是否含 `model:` 字段区分 agent 生成 vs 用户手写。工作流痕迹检查只对 agent 生成章节强制，用户手写豁免（复用 CLAUDE.md 已有原则，不引入新概念）。

---

## 建议 1 — 工作流痕迹检查（审查 + 准备）

**文件**：`.githooks/pre-commit`（治理文档）

在第 108 行 `[pre-commit] chapters ok` 之后、最终 `all checks passed` 之前新增：

```bash
# —— 6. 四阶段工作流痕迹（agent 生成的章节必须配套 审查/准备[/审查后]） ——
TRUE_CHAPTERS=$(echo "$STAGED" | grep -E "^03_正文/第.+卷/第[^/]+章\.md$" || true)
if [ -n "$TRUE_CHAPTERS" ]; then
    MISSING=""
    for ch in $TRUE_CHAPTERS; do
        [ -f "$ch" ] || continue
        # 用户手写章节（无 model: 字段）豁免
        grep -qE "^model:" "$ch" || continue
        dir=$(dirname "$ch"); base=$(basename "$ch" .md)
        for kind in 审查 准备; do          # 建议 2 时追加 审查后
            sib="$dir/_${kind}_${base}.md"
            if [ ! -f "$sib" ] && ! echo "$STAGED" | grep -qF "$sib"; then
                MISSING="$MISSING\n  缺 $sib"
            fi
        done
    done
    if [ -n "$MISSING" ]; then
        echo ""; echo "============================================"
        echo "[BLOCK] 以下 agent 生成章节缺少四阶段工作流痕迹:"
        echo -e "$MISSING"
        echo "每章须同目录配套：_审查_（①宪法审查）_准备_（②上下文包）"
        echo "用户手写章节（frontmatter 无 model:）豁免本检查。"
        echo "============================================"; exit 1
    fi
    echo "[pre-commit] workflow artifacts ok"
fi
```

**设计决策**
- 阻断而非提醒：四阶段是治理脊柱，与就绪自检同级；留 `model:` 豁免口避免误伤用户手写。
- regex 精度：`第.+卷/第[^/]+章\.md$` 只匹配真章节；`_准备_`/`_审查_` 因 basename 以 `_` 开头被自然排除。
- 存在性判定：`test -f`（已落盘）**或**在本次 STAGED 内——支持章节与配套文件同批提交。
- 边界：纯格式/错字修订旧章节时配套早已存在，`test -f` 命中，不误拦。

---

## 建议 2 — 写后 reviewer artifact `_审查后_第M章.md`

让"写后审查做没做"可观测、抗 compact。

**2a. 命名 + frontmatter（新约定）**
路径 `03_正文/第N卷/_审查后_第M章.md`：
```yaml
---
reviewer_model: claude-opus-4-8
reviewed_at: 2026-06-25T10:00:00Z
volume: 1
chapter: 3
verdict: 通过          # 通过 | 阻断
blocking_count: 0
flag_count: 1
rounds: 1
---
（阻断清单 / flag / 修复记录正文）
```

**2b. 钩子**：建议 1 的 `for kind in 审查 准备` 改为 `审查 准备 审查后`（一行）。

**2c. 文档同步（治理文档，需 `[governance]`）**
- `AGENTS.md`（→ 同步 CLAUDE.md/GEMINI.md）③/④ 节：明确"写后 reviewer 结论必须落盘 `_审查后_第M章.md`"，并在「章节 frontmatter」节旁加该 artifact 的 schema。
- `05_复盘/reviewer-prompt-template.md`：模板末尾要求 reviewer 输出可直接存盘的 `_审查后_` 块。
- `05_复盘/reviewer-protocol.md`：收口步骤加"写 `_审查后_`"。

**设计决策**
- 机械层只校验「文件存在」；verdict 语义不进钩子（reviewer 是否真严格交给人/converge 兜，符合 Bitter Lesson）。
- 可选加严（标 future，本次不做）：钩子解析 `verdict: 阻断` 时阻断提交，除非有用户 waiver 标记。

`check_chapters.py` 需把 `_审查后_` 加入排除名单（见建议 3，合并一处改）。

---

## 建议 3 — `--staged` 时空检查跨已提交章节比对

**文件**：`scripts/check_chapters.py`（**非**治理文档，无需 `[governance]`，最轻，可独立先上）

**改 1**：`check_chapters` 增 `context_files` 只读种子参数：
```python
def check_chapters(chapter_files, issues, context_files=None):
    chars = _list_character_files()
    char_status = {n: (_parse_frontmatter(p) or {}).get("status","alive")
                   for n, p in chars.items()}
    spacetime: dict[str, dict[str, str]] = defaultdict(dict)
    # 只读种子：已提交章节，用于跨 commit 同日两地冲突检测（不报其自身 WARN）
    for cf in sorted(context_files or []):
        fm = _parse_frontmatter(cf)
        if not fm: continue
        loc, date = fm.get("location",""), fm.get("in_world_date","")
        if date and loc:
            for c in _parse_characters_present(fm.get("characters_present")):
                spacetime[date].setdefault(c, loc)
    # ……以下原校验循环不变（共用同一个 spacetime）……
```

**改 2**：main 的 `--staged` 分支构造 context：
```python
all_ch = sorted(p for p in TEXT_DIR.rglob("第*章.md")
                if not any(x in p.name for x in ("_准备_", "_审查_", "_审查后_")))
staged_set = set(chapter_files)
context_files = [p for p in all_ch if p not in staged_set]
...
check_chapters(chapter_files, issues, context_files=context_files)
```

**改 3**：三处排除名单统一加 `_审查后_`（现有代码漏了——`"_审查_"` 不是 `"_审查后_"` 的子串，会把 `_审查后_` 误当章节）。第 194-195、199-200 行。

**效果**：单独提交的新章节能与已提交旧章节做"同日两地"冲突检测，补 P0 缺口。`setdefault` 保证种子不被自身覆盖、不重复报。

---

## 建议 4 — writing-style.md 升为治理（**已裁决：A，2026-06-25**）

张力：`docs/writing-style.md` 头部自述「走轻量评审即可」，但就绪自检依赖它、reviewer 查文风漂移。用户裁决 **A 升为治理**——注册表已是 reviewer 硬参照，静默漂移会绕过整个文风治理。

确定的改动清单：
1. `.githooks/commit-msg` `GOVERNANCE_FILES` 数组追加 `"docs/writing-style.md"`。
2. `AGENTS.md`（→ 同步 CLAUDE.md/GEMINI.md）第 78 行治理文件清单追加 `docs/writing-style.md`。
3. `docs/writing-style.md` 文件头：删除"可随项目迭代调整，**走轻量评审即可**"一句，改为"视角/时态/文风注册表为就绪自检与 reviewer 漂移检查的硬参照，修改须带 `[governance]` 标记并复跑漂移检查"。

> 注意：commit-msg 自身在 `GOVERNANCE_FILES` 内——本次同时改 commit-msg + writing-style.md + AGENTS.md，提交须带 `[governance]`。

---

## Ultraverge 收敛结果（v2 定稿，2026-06-25）

> 3 独立 reviewer 一致 `阻断需修复`（artifacts: `.converge/done/20260625-gov-124/`）。下列 v2 **取代上方建议 1/2/4 的原始描述**；原描述保留作审查留痕。用户裁决：强制力度=「只 _准备_ 阻断，审查类降提醒」；writing-style 治理=「抽 locked 段单独保护」。

### 建议 1-v2 — 工作流痕迹（白名单豁免 + 粒度分级 + 强制力分级）

修复 B1/B3/B4。

**a. 豁免改白名单（B1）**：不再用"有无 `model:`"做开关。`scripts/check_chapters.py` 增硬检查——staged `第M章.md` 若 frontmatter **既无 `model:` 又无 `author: human`** → `[BLOCK]`（"缺 model：agent 章节须标 model/generated_at，用户手写章节须显式 `author: human`"）。封死"沉默漏标"灰区，豁免必须主动声明。

**b. 粒度分级（B3）**：
- `_准备_第M章.md`：逐章、**阻断级**（写前上下文包，逐场，形式即足够）。
- `_审查_`：允许卷级 `_审查_第N卷.md` 或区间，章节 frontmatter 用 `review_ref:` 指向覆盖本章的审查文件；钩子校验"被引用/覆盖本章的审查文件存在"，**不要求逐章同名**。

**c. 强制力分级（B4，用户裁决）**：`_准备_` 缺失 → 阻断；`_审查_` 缺失 → **提醒级**（非阻断，与人物卡更新提醒同档）。过程合规质量交复盘 converge。

pre-commit 第 6 段据此重写：先按白名单判定"需痕迹"的章节集 → `_准备_` 缺失进 BLOCK 列表、`_审查_`(via review_ref) 缺失进 REMINDER 列表。`author: human` 章节整体跳过。

### 建议 2-v2 — `_审查后_` 提醒级 + 诚实标注 + schema 对齐

修复 B2/B6。

**a. 降为提醒级（B2，用户裁决）**：`_审查后_` 缺失 → 提醒，不阻断。
**b. 诚实标注（B2）**：钩子输出与 AGENTS.md 文案明确"`_审查后_` 存在仅证明 artifact 落盘，**不证明审查质量/独立性**；质量由复盘 converge 兜底"。消除"存在=审过"的虚假安全感。
**c. schema 对齐既有词汇（B6）**：frontmatter 用 `model:` / `generated_at:`（不另造 `reviewer_model`/`reviewed_at`）；`verdict` 取值对齐 reviewer-protocol = `可收敛 | 需修复`（不用 `通过|阻断`）。可选附 `covers:` 标注覆盖章节。

### 建议 4-v2 — 抽 locked 段单独保护 + 治理清单单一数据源

修复 B5a/B5b（取代原"整文件升治理"）。

**a. 抽 locked 段（B5a，用户裁决）**：新建 `docs/style-locked.md`，迁入 writing-style.md 的「视角 / 时态 / 文风注册表」三段（硬参照）。`writing-style.md` 保留其余轻量叙事工艺，文件头改为指向 `style-locked.md`。
- `.githooks/commit-msg` `GOVERNANCE_FILES` 加 **`docs/style-locked.md`**（而非整个 writing-style.md）。
- `scripts/check_chapters.py` 就绪自检的"视角/时态"检查目标从 `writing-style.md` 改为 `style-locked.md`（H1-BLOCK 引用同步）。
- `reviewer-prompt-template.md` 文风漂移检查参照改指 `style-locked.md`。

**b. 治理清单单一数据源（B5b）**：以 `.githooks/commit-msg` 的 `GOVERNANCE_FILES` 数组为**唯一权威清单**；`AGENTS.md` 第 78 行**停止枚举**，改为"完整清单见 `.githooks/commit-msg`"指针（消除 P3-G 的多源漂移，新增治理文件只改一处）。

### 跨切诚实性（3/3 共识）

提案"治理/验证/落地"节 + AGENTS.md 须诚实标注：本机制是 **commit-time 留痕兜底**（抗 compact 价值真实），对 `--no-verify` 无效、且不覆盖会话期；工作流真实性的最终防线是 **§④ 复盘 converge**，非 commit 钩子。删除"无痕不可提交"等过度承诺措辞。

### 勘误

建议 4 落地时：`GOVERNANCE_FILES` 数组在 `.githooks/commit-msg`(8-16)；AGENTS.md/CLAUDE.md 是 prose——b 项正是消除这处双源。

---

## 治理 / 验证 / 落地

- **触及治理文档**：建议 1、2、4 改 `.githooks/*`、`AGENTS.md`、`reviewer-*`、`writing-style.md` → commit 须带 `[governance]`；按 converge skill，治理文档变更**应走 ultraverge**（≥3 reviewer + 收敛 + 设计审查）。建议 3 仅改 `check_chapters.py`，可走普通评议。
- **AGENTS.md 同步**：只编辑 `AGENTS.md`，再 `python scripts/agent_links.py repair`。
- **验证计划（含 reviewer 要求的负向用例）**：
  - 正向：带 `model:` 缺 `_准备_` → 阻断；补齐 → 放行。
  - B1 负向：`第M章.md` 既无 `model:` 又无 `author: human` → 阻断（封沉默漏标）；标 `author: human` → 豁免。
  - B3 负向：一份 `_审查_第N卷.md` 经 `review_ref:` 覆盖第 3-5 章 → 三章均放行（不强逐章同名）。
  - `_审查_`/`_审查后_` 缺失 → 仅提醒、不阻断（确认 posture）。
  - check_chapters `--staged` 跨章节同日两地用例（建议 3 回归）。

## 采纳粒度

- 建议 3：轻量、无依赖，可独立先上。
- 建议 1 + 2：一组（2 的钩子依附 1）。
- 建议 4：待用户选 A/B 后并入整体 ultraverge。

## 进度

- [x] 用户裁决建议 4 → A 升为治理（2026-06-25），后经 ultraverge B5a 细化为「抽 locked 段单独保护」
- [x] 建议 3 落地并提交 `a5fc512`（2026-06-25）
- [x] 建议 1+2+4 ultraverge（2026-06-25）：3 reviewer 一致 `阻断需修复` → 完整收敛 → v2 定稿（B1 白名单 / B2 提醒+诚实 / B3 粒度分级 / B4 强制力分级 / B5a 抽 locked / B5b 单一数据源 / B6 schema 对齐）。retrospective: `.converge/done/20260625-gov-124/`
- [x] 按 v2 实现建议 1+2+4（2026-06-25）：新建 `docs/style-locked.md`；改 `.githooks/*`、`check_chapters.py`、`AGENTS.md`(+CLAUDE/GEMINI)、`writing-style.md`、`reviewer-*`
- [x] 验证计划执行（2026-06-25）：B1 白名单三章用例 ✓、pre-commit 第 6 段粒度/强制力/豁免 ✓、双钩子语法 ✓、三文件同步 ✓；独立验收 reviewer `可执行` 0 阻断 0 回归
- [x] 提交 `24e2c20`（带 `[governance]`）+ CHANGELOG + 计划移 completed/（2026-06-25）
- [ ] 验证计划执行
- [ ] CHANGELOG 记录，计划移 completed/
