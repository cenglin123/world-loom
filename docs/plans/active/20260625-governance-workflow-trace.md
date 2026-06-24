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

## 治理 / 验证 / 落地

- **触及治理文档**：建议 1、2、4 改 `.githooks/*`、`AGENTS.md`、`reviewer-*`、`writing-style.md` → commit 须带 `[governance]`；按 converge skill，治理文档变更**应走 ultraverge**（≥3 reviewer + 收敛 + 设计审查）。建议 3 仅改 `check_chapters.py`，可走普通评议。
- **AGENTS.md 同步**：只编辑 `AGENTS.md`，再 `python scripts/agent_links.py repair`。
- **验证计划**：scratchpad 造带 `model:` 的假章节 + 缺配套，`git add` 后干跑 pre-commit 验阻断；补齐配套验放行；用户手写版（无 `model:`）验豁免。check_chapters 改完跑 `--staged` 造跨章节同日两地用例验证。

## 采纳粒度

- 建议 3：轻量、无依赖，可独立先上。
- 建议 1 + 2：一组（2 的钩子依附 1）。
- 建议 4：待用户选 A/B 后并入整体 ultraverge。

## 进度

- [x] 用户裁决建议 4 → **A 升为治理**（2026-06-25）
- [x] 建议 3 落地（2026-06-25）：`check_chapters.py` 加 `context_files` 只读种子 + `--staged` 跨已提交章节比对 + 三处排除名单补 `_审查后_`。功能测试 4/4 通过（cross-commit 冲突捕获 / 旧 gap 复现 / 批内回归 / 排除过滤）。**未提交**
- [ ] 建议 1+2+4 整体走 ultraverge
- [ ] 验证计划执行
- [ ] CHANGELOG 记录，计划移 completed/
