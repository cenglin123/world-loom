# 开发规范

> world-loom 工具包本身的开发约定。**本文件不对外分发。**
> 使用层规范在 `_分发/AGENTS.md`——改那里，不改这里。

## 三层的边界

| 层 | 判据 | 例子 |
|----|------|------|
| **源码层** | 下游用户需要的工具与方法 | `_模板/` `_分发/` `scripts/` `.githooks/` `使用手册.md` `docs/writing-style.md` |
| **内容层** | 这本书的创作产物 | 世界观填写、大纲、角色卡、正文、伏笔、卷复盘、`docs/{decisions,CURRENT,style-locked,CHANGELOG,plans}` |
| **开发层** | 造这套工具的过程 | `AGENTS.md` `README.md` `docs/development.md` converge 治理记录 |

内容层与开发层在机制上等同——`layers.py` 的 `is_content()` 对两者都返回 True，都不分发。区分只在语义，方便判断"这东西该往哪写"。

**唯一权威源是 `scripts/layers.py`**。新增目录只改那一处，`publish.py` 和 `.githooks/pre-push` 都从它取清单。

## 分发映射

下游用户拿到的 `AGENTS.md` / `README.md` 不是本仓根目录那两份——那是开发版。分发时由 `publish.py` 做路径映射：

```
_分发/AGENTS.md  →  AGENTS.md + CLAUDE.md + GEMINI.md
_分发/README.md  →  README.md
```

同一个 git blob 映射多个文件名，单一源，天然同步。映射完成后 `_分发/` 目录本身从分发树里移除。

映射表在 `scripts/publish.py` 的 `DIST_MAP`。

**改使用层规则改 `_分发/AGENTS.md`**。它不参与 `agent_links.py` 的三文件同步——那个脚本管的是根目录开发版。

## 分发流程

```bash
python scripts/publish.py            # dry-run：打印将公开的完整清单
python scripts/publish.py --force    # 真推
```

`--force` 时的完整链路：

1. 以 HEAD 建临时索引（`.git/publish-index`），删掉全部内容层与开发层路径
2. 应用 `DIST_MAP` 映射，移除 `_分发/`
3. **硬复核**：树里不含内容层文件（映射产生的路径豁免）、不含 `_分发/` 残留
4. 打印完整文件清单
5. `write-tree` → `commit-tree` → 落到本地 `template-dist` 分支
6. 带 `NOVEL_PUBLISH=1` 推送（这是 `pre-push` 唯一放行条件）

工作区脏时拒绝执行——分发基于 HEAD，未提交的改动不会出去。

### 推送闸门

`.githooks/pre-push` 默认拒绝一切推送。两个出口：

- `publish.py` 设 `NOVEL_PUBLISH=1` 放行，且逐 ref 复核树内零内容层文件
- 整仓推私有远端：`git push --no-verify`

## 治理清单

`.githooks/commit-msg` 的 `GOVERNANCE_FILES` 是唯一权威源。清单覆盖两类：

- **使用层受保护文档**：世界观硬设定、`docs/style-locked.md`、审计清单、reviewer 协议、维护协议——保护下游用户的创作基线
- **开发层机制文件**：`layers.py` `publish.py` 三个 hook `_分发/AGENTS.md`

内容层文件与其 `_模板/` 骨架**成对保护**——改哪一份都要标记，否则模板与产物会漂移。

## 机制化三分判据

判断一件事该不该脚本化，三条都满足才做：

1. **机制不执行任务本身**——只检测缺失信号，不代替 agent 做判断。`check_maintenance.py` 报"记忆没回写"，但不代写记忆
2. **不收窄编排空间**——agent 仍可判定"这里确实不需要"，机制提供明示出口（如 `maintenance_skip`）
3. **契约违反 fail-closed，判断分歧 fail-open**——结构性缺失阻断，语义判断只提醒

反例：给文风做正则黑名单。它违反第 2 条（收窄表达空间）且误报高。按 Bitter Lesson，语义一致性交 LLM + converge，不硬编词表。

## 中文 Windows 的编码陷阱

写任何调用外部命令或读写文件的脚本时，**必须显式指定 UTF-8**：

```python
subprocess.run(..., text=True, encoding="utf-8", errors="replace")
path.read_text(encoding="utf-8")
```

不指定就按**系统区域**解码。中文 Windows 的区域是 GBK，而 git 输出的路径、仓库里的文档全是 UTF-8——内容一含中文就炸：

```
subprocess 读取线程 UnicodeDecodeError → stdout 变 None → 调用方 AttributeError
```

这类崩溃的隐蔽之处在于：只有路径含中文时才触发，而本仓的目录名（`03_正文/第1卷/`）天然全是中文，所以一定会踩到；但如果本机区域是 UTF-8，自测又发现不了——只在别人机器上崩。

`scripts/check_encoding.py` 静态扫描这两类调用，接在 `check_all.py` 与 pre-commit 上，改脚本时自动拦。

## 文档 vs 制品

孤儿检查（`check_docs.py`）只管**文档**——位置由导航链接决定的东西。**制品**的位置由命名约定和专门的登记表决定，各有专门检查器：

| 制品 | 登记在哪 | 谁检查 |
|------|---------|--------|
| 正文章节 | `第N卷_大纲.md` 场景清单 | `check_maintenance.py` |
| 过程文件（`_工作/`） | 命名规则即导航 | pre-commit 工作流留痕 |
| 人物卡 | `02_人物/_索引.md` | `check_tags.py` |

在孤儿检查里重复管制品，除了误报还会给出**错误的修复指引**——"接进导航或删掉"对一张缺登记的人物卡是误导，正确动作是跑 `check_tags.py _index`。新增检查器时先问：这个失效已经有主了吗？

引用匹配会剥掉围栏代码块——目录示例树里的 `第1章.md` 不算真引用。否则前两章侥幸通过、第三章才报错，这种偶然豁免比不检查更坏。

## 链接完整性

`audit.py dead-links` 扫全部入库 markdown 的 `[](路径)` 与 `[[wikilink]]`，报两类失效：

| 状态 | 含义 | 修法 |
|------|------|------|
| `DEAD` | 目标在当前树里就不存在 | 查拼写，或文件被移动 |
| `CROSS` | 源码层文档指向内容层文件——**当前能解析，分发后必断** | 补 `_模板/` 骨架，或把这份文档划入内容层 |

`CROSS` 是这个仓特有的失效：开发仓里两层同在，链接跑得通；下游只拿到源码层，指过去就是空的。判据用 `layers.is_content()` + `template.products()`——**指向内容层不一定错，指向"下游 init 也生不出来的内容层文件"才错**。

相对链接按**内容落地后所在的目录**解析，不是文件当前位置：`_分发/README.md` 映射到根目录，`_模板/docs/CURRENT.md` 由 init 生成到 `docs/`。按当前位置算，这两类的相对链接全是假死链。

## 检查器清单

`scripts/check_all.py` 的 `CHECKS` 是权威源，新增机械检查只改那一处。当前十一项：同步 / 模板 / 链接 / 伏笔 / 关系 / 标签 / 章节 / 文档 / 方法 / 编码 / 维护。

hook 只扫暂存区，`check_all.py` 扫全量工作区——互补，不重复。

## 分发前自检

改动使用层文档后：

```bash
python scripts/check_all.py --quiet    # 无输出 = 通过
python scripts/publish.py              # dry-run，逐行核对清单
```

重点看两件事：**开发层文件有没有混进清单**、**映射的三个文件名有没有正确出现**。链接那一头由 `CROSS` 检查兜底，不用手核。
