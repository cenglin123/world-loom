# world-loom 开发仓

> 这里是 [world-loom](https://github.com/cenglin123/world-loom) 的**开发环境**，不是分发出去的那份。
> 分发版的 README 在 `_分发/README.md`——用户看到的是它。

| 你想做什么 | 去哪 |
|-----------|------|
| 开发这套工具包 | [AGENTS.md](AGENTS.md) → [docs/development.md](docs/development.md) |
| 改使用层规则（下游用户拿到的） | `_分发/AGENTS.md` |
| 分发到 GitHub | `python scripts/publish.py` （dry-run）→ `--force` |
| 在本仓 dogfooding 写小说 | `_分发/AGENTS.md` 是使用层规范 |

分发机制：`_分发/` 下的使用层文档在推送时映射到目标仓的 `AGENTS.md` / `README.md`，`_分发/` 目录本身不出现在分发树里。细节见 [docs/development.md](docs/development.md)。
