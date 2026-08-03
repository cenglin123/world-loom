#!/usr/bin/env python
"""method.py —— 方法卡库的按需检索。

方法论多起来之后，把它们全塞进常驻上下文是不可行的。这里走「路由 + 按需展开」：
`_索引.md` 常驻（每卡一行），需要哪张再 `show` 全文——总量可以涨，单次开销不涨。

检索是纯词面的（BM25 + 中文双字切分），不做向量、不需依赖。方法卡本来就带
`关键词` 与 `tags`，词面命中率足够；语义那一层交给读到索引的 agent 自己判断。

用法:
  python scripts/method.py find "怎么设计一座城"   # 检索，默认 top 5
  python scripts/method.py find "反派" --hop 1     # 额外带出命中卡的双链邻居
  python scripts/method.py show 地形生成法          # 打印整卡
  python scripts/method.py index                    # 重新生成 _方法/_索引.md
  python scripts/method.py check                    # 索引新鲜度 + 双链有效性 + 近重复
  python scripts/method.py dupe "<待收方法的摘要>"   # 吸纳前查重
  python scripts/method.py ingest <素材路径>        # 生成加工工单
  python scripts/method.py skip <来源> --reason ... # 登记「看过，不收」
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "_方法"
INDEX_FILE = LIB_DIR / "_索引.md"
SKIP_FILE = LIB_DIR / "_未收.md"

# 字段权重：标题与关键词是作者显式给的检索钩子，比正文更可信。
# `症状` 权重最高——它是**求助者的原话**，而作者写卡时用的是术语。
# 词面检索跨不过这道词汇鸿沟，只能靠写卡的人把两套词都写进来。
FIELD_WEIGHTS = {"id": 4, "症状": 4, "一句话": 3, "tags": 3, "关键词": 3, "正文": 1}

# 近重复告警线。BM25 无上界，这里用「自查得分的归一化比例」判定，见 _dupe_pairs。
DUPE_RATIO = 0.55

CJK = re.compile(r"[一-鿿]")
ASCII_WORD = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*")


# ---------------------------------------------------------------------------
# 分词：中文双字 + 西文整词
# ---------------------------------------------------------------------------

def _today() -> str:
    return date.today().isoformat()


def tokenize(text: str) -> list[str]:
    """中文按双字滑窗切，西文按整词切。

    双字切分对中文短文本的召回明显优于单字（"选址" 不会被 "选" 和 "址" 拆散命中
    无关卡片），又不需要词典依赖——这是 zero-dep 前提下的合理取舍。
    """
    text = text.lower()
    tokens = ASCII_WORD.findall(text)
    runs = re.findall(r"[一-鿿]+", text)
    for run in runs:
        if len(run) == 1:
            tokens.append(run)
            continue
        tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


# ---------------------------------------------------------------------------
# 卡片加载
# ---------------------------------------------------------------------------

class Card:
    __slots__ = ("path", "id", "stage", "tags", "keywords", "symptoms",
                 "oneliner", "landing", "related", "sources", "body", "history")

    def __init__(self, path: Path, meta: dict[str, str], body: str):
        self.path = path
        self.id = meta.get("id") or path.stem
        self.stage = meta.get("阶段", "")
        self.tags = _split_list(meta.get("tags", ""))
        self.keywords = _split_list(meta.get("关键词", ""))
        self.symptoms = _split_list(meta.get("症状", ""))
        self.oneliner = meta.get("一句话", "")
        self.landing = meta.get("落点", "")
        self.related = _split_list(meta.get("相关", ""))
        self.sources = _split_list(meta.get("来源", ""))
        self.body, self.history = _split_history(body)

    def fields(self) -> dict[str, str]:
        """参与检索的字段。`沿革` 不在内——它记的是这张卡怎么来的，
        不是它能解决什么；混进检索只会让改动多的卡莫名其妙地更容易命中。"""
        return {
            "id": self.id,
            "一句话": self.oneliner,
            "tags": " ".join(self.tags),
            "关键词": " ".join(self.keywords),
            "症状": " ".join(self.symptoms),
            "正文": self.body,
        }

    def criteria(self) -> str:
        """「判据」节——吸纳新素材时，冲突最先发生在这里。"""
        m = re.search(r"^##\s*判据\s*$(.*?)(?=^##\s|\Z)", self.body,
                      re.M | re.S)
        return m.group(1).strip() if m else ""

    def rel(self) -> str:
        return self.path.relative_to(ROOT).as_posix()


def _split_history(body: str) -> tuple[str, str]:
    """把「## 沿革」从正文里切出来。

    卡的**正文只描述当前规则**（无补丁感），演进痕迹另存——
    这和人物卡「演化记录」与当前人设分开存放是同一条规矩。
    """
    m = re.search(r"^##\s*沿革\s*$", body, re.M)
    if not m:
        return body, ""
    return body[:m.start()].rstrip(), body[m.end():].strip()


def _split_list(raw: str) -> list[str]:
    """YAML 行内列表 `[a, b]` 或逗号/顿号分隔，都接受。"""
    raw = raw.strip().strip("[]")
    if not raw:
        return []
    return [x.strip().strip("\"'") for x in re.split(r"[,，、]", raw) if x.strip()]


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    head, body = text[3:end], text[end + 4:]
    meta: dict[str, str] = {}
    for line in head.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, _, val = line.partition(":")
        meta[key.strip()] = val.strip()
    return meta, body


def load_cards() -> list[Card]:
    if not LIB_DIR.is_dir():
        return []
    cards = []
    for p in sorted(LIB_DIR.rglob("*.md")):
        if p.name.startswith("_") or p.name == "README.md":
            continue
        meta, body = _parse_front_matter(p.read_text(encoding="utf-8"))
        cards.append(Card(p, meta, body))
    return cards


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class BM25:
    """字段加权 BM25。文档 = 一张方法卡，字段按权重重复计入词频。"""

    K1 = 1.5
    B = 0.75

    def __init__(self, cards: list[Card]):
        self.cards = cards
        self.tf: list[Counter] = []
        for card in cards:
            counter: Counter = Counter()
            for name, text in card.fields().items():
                weight = FIELD_WEIGHTS.get(name, 1)
                for tok in tokenize(text):
                    counter[tok] += weight
            self.tf.append(counter)
        self.lengths = [sum(c.values()) for c in self.tf]
        self.avg_len = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        self.df: Counter = Counter()
        for counter in self.tf:
            self.df.update(counter.keys())
        self.n = len(cards)

    def _idf(self, term: str) -> float:
        df = self.df.get(term, 0)
        return math.log(1 + (self.n - df + 0.5) / (df + 0.5))

    def score(self, query: str) -> list[tuple[float, Card]]:
        terms = tokenize(query)
        if not terms or not self.n:
            return []
        out = []
        for i, counter in enumerate(self.tf):
            length = self.lengths[i] or 1
            total = 0.0
            for term in terms:
                freq = counter.get(term, 0)
                if not freq:
                    continue
                denom = freq + self.K1 * (1 - self.B + self.B * length / self.avg_len)
                total += self._idf(term) * freq * (self.K1 + 1) / denom
            if total > 0:
                out.append((total, self.cards[i]))
        out.sort(key=lambda x: (-x[0], x[1].id))
        return out


# ---------------------------------------------------------------------------
# 命令
# ---------------------------------------------------------------------------

def cmd_find(args: argparse.Namespace) -> int:
    cards = load_cards()
    if not cards:
        print("[FAIL] _方法/ 下没有方法卡")
        return 1
    ranked = BM25(cards).score(args.query)[: args.top]
    if not ranked:
        print(f"无命中：{args.query}")
        print("（换几个更具体的词；或者这套方法本来就还没收进来）")
        return 0

    by_id = {c.id: c for c in cards}
    hit_ids = {c.id for _, c in ranked}
    print(f"查询「{args.query}」命中 {len(ranked)} 张：\n")
    for score, card in ranked:
        print(f"  [{score:5.1f}] {card.id}（{card.stage}）")
        print(f"          {card.oneliner}")
        print(f"          展开：python scripts/method.py show {card.id}")
    if args.hop:
        neighbors = []
        for _, card in ranked:
            for rid in card.related:
                if rid not in hit_ids and rid in by_id:
                    neighbors.append(by_id[rid])
                    hit_ids.add(rid)
        if neighbors:
            print("\n  ── 双链邻居（未直接命中，可能相关）──")
            for card in neighbors:
                print(f"  · {card.id}：{card.oneliner}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cards = {c.id: c for c in load_cards()}
    card = cards.get(args.id)
    if card is None:
        print(f"[FAIL] 无此方法卡：{args.id}")
        near = BM25(list(cards.values())).score(args.id)[:3]
        if near:
            print("你要找的可能是：" + "、".join(c.id for _, c in near))
        return 1
    print(card.path.read_text(encoding="utf-8"))
    return 0


def _index_text(cards: list[Card], stage: str | None = None) -> str:
    rows = [c for c in cards if not stage or c.stage == stage]
    lines = [
        "# 方法卡索引",
        "",
        "> 本文件由 `python scripts/method.py index` 生成，不要手改。",
        "> 这是路由表——按需 `python scripts/method.py show <id>` 展开整卡，",
        "> 不知道该展开哪张就 `python scripts/method.py find \"<你的问题>\"`。",
        "",
    ]
    for stage_name in _stages(rows):
        lines.append(f"## {stage_name}")
        lines.append("")
        lines.append("| 方法 | 一句话 | tags |")
        lines.append("|------|--------|------|")
        for card in rows:
            if card.stage != stage_name:
                continue
            tags = " ".join(f"#{t}" for t in card.tags)
            lines.append(f"| [[{card.rel()}\\|{card.id}]] | {card.oneliner} | {tags} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _stages(cards: list[Card]) -> list[str]:
    seen = []
    for c in cards:
        if c.stage not in seen:
            seen.append(c.stage)
    return seen


def cmd_index(args: argparse.Namespace) -> int:
    cards = load_cards()
    if not cards:
        print("[FAIL] _方法/ 下没有方法卡")
        return 1
    if args.stage:
        print(_index_text(cards, args.stage))
        return 0
    INDEX_FILE.write_text(_index_text(cards), encoding="utf-8")
    print(f"[OK] 已生成 {INDEX_FILE.relative_to(ROOT)}（{len(cards)} 张卡）")
    return 0


def _dupe_pairs(cards: list[Card]) -> list[tuple[float, Card, Card]]:
    """近重复：拿每张卡的全文当 query 检索，命中他卡分数接近自查分数即告警。

    自查分数（卡对自己的 BM25）随卡长浮动，所以用比例而非绝对分——
    绝对阈值会让长卡永不告警、短卡满屏告警。
    """
    bm = BM25(cards)
    pairs = []
    seen: set[tuple[str, str]] = set()
    for card in cards:
        query = " ".join([card.id, card.oneliner, " ".join(card.tags),
                          " ".join(card.keywords), " ".join(card.symptoms),
                          card.body])
        ranked = bm.score(query)
        if not ranked:
            continue
        self_score = next((s for s, c in ranked if c.id == card.id), 0.0) or 1.0
        for score, other in ranked:
            if other.id == card.id:
                continue
            ratio = score / self_score
            if ratio < DUPE_RATIO:
                break
            key = tuple(sorted((card.id, other.id)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((ratio, card, other))
    pairs.sort(key=lambda x: -x[0])
    return pairs


def cmd_dupe(args: argparse.Namespace) -> int:
    cards = load_cards()
    if not cards:
        print("[FAIL] _方法/ 下没有方法卡")
        return 1
    ranked = BM25(cards).score(args.text)[:5]
    if not ranked:
        print("[OK] 库里没有相近的方法，可以直接收")
        return 0
    top = ranked[0][0]
    print("库里最接近的几张：\n")
    for score, card in ranked:
        print(f"  [{score:5.1f}] {card.id}：{card.oneliner}")
    print()
    if len(ranked) > 1 and ranked[1][0] / top > 0.8:
        print("[INFO] 前两名分数接近——待收方法可能横跨两张卡，先想清楚它到底补的是哪一处")
    print("收之前先判定：**同一套步骤换个外壳**就并进已有卡的换算表，")
    print("**多出了新的判断步骤**才开新卡。拿不准就看落点——落点相同的基本是同一张。")
    return 0


def _iter_material(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*")
                      if p.is_file() and p.suffix.lower() in (".txt", ".md"))
    return []


def cmd_ingest(args: argparse.Namespace) -> int:
    """为每份素材生成加工工单。

    脚本不做蒸馏、不判收不收——它只把**对比材料摆到位**并把问题问出来。
    蒸馏和判定是 agent 的事，这道边界不能越（越了就等于用词面统计替代理解）。
    """
    src = Path(args.path)
    materials = _iter_material(src)
    if not materials:
        print(f"[FAIL] 没有可读素材：{src}")
        return 1

    cards = load_cards()
    if not cards:
        print("[FAIL] _方法/ 下没有方法卡")
        return 1
    bm = BM25(cards)
    skipped = _skipped_sources()

    print(f"# 加工工单（{len(materials)} 份素材）\n")
    print("对每份素材依次回答下面三问，再决定处置。**不许跳过第二问**——")
    print("素材与已有卡重复不等于没价值，它可能正说明那张卡漏了一步或判据站不住。\n")

    for mat in materials:
        try:
            text = mat.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"\n## {mat.name}\n\n[跳过] 读取失败：{exc}")
            continue

        name = mat.stem
        print(f"\n## {name}")
        print(f"\n素材：`{mat}`（{len(text)} 字）")
        key, hit = _match_skipped(name, skipped)
        if hit:
            reason, revised = hit
            print(f"\n> **已登记为不收**（{key}）：{reason}")
            if revised:
                print(f"> 但它修正过：{'、'.join(revised)}")
            print("> 除非有新理由推翻，否则跳过——别重复评估同一份素材。")
            continue

        ranked = bm.score(text)[:3]
        if not ranked:
            print("\n库里没有相关卡——若含可执行步骤，直接开新卡。")
        else:
            print("\n库里最相关的卡（**逐张判断是否受影响**）：\n")
            for score, card in ranked:
                print(f"### {card.id}（{score:.1f} 分，{card.stage}）")
                print(f"\n- 一句话：{card.oneliner}")
                print(f"- 落点：{card.landing}")
                crit = card.criteria()
                if crit:
                    print(f"- 现有判据：\n\n{_indent(crit)}\n")

        print("**三问**：")
        print("1. 这份素材里有**可照做的步骤**吗？没有就是素材不是方法——`skip` 登记掉。")
        print("2. 它和上面每张卡的判据**冲突**吗？")
        print("   - 冲突 → 改那张卡，并在其「## 沿革」记一行（为什么改、依据哪份素材）")
        print("   - 不冲突但补强 → 并进那张卡；新外壳写进 `关键词`，新说法写进 `症状`")
        print("   - 无关 → 开新卡，与最近的卡互相 `相关:`")
        print("3. 处置完了吗？开新卡要写 `来源:`；不开卡要 `skip` 登记——")
        print("   若它虽不成卡却改了某张卡，`skip --revised <卡名>` 把这件事记上。")
        print("   **不收 ≠ 无影响**，混作一谈就等于把最有价值的那类反馈丢了。")

    pending = [m for m in materials if not _match_skipped(m.stem, skipped)[1]]
    if pending:
        print("\n---\n")
        print("不开卡的登记模板（`--revised` 只在它确实改了某张卡时才写）：\n")
        print("```")
        collection = src.name if src.is_dir() else src.parent.name
        for mat in pending:
            print(f'python scripts/method.py skip "{collection}/{mat.stem}" '
                  f'--reason "<为什么不成卡>" --revised "<被它改过的卡>"')
        print("```")
    print("\n处置完跑：`python scripts/method.py index && python scripts/method.py check`")
    return 0


def _indent(text: str, prefix: str = "  > ") -> str:
    return "\n".join(prefix + ln for ln in text.splitlines())


def _match_skipped(stem: str, skipped: dict[str, tuple[str, list[str]]]):
    """台账里的来源标识与文件名对上号。

    来源写的是稳定标识（`频道/标题`），文件名往往还带副标题或后缀。
    两边取末段做双向包含匹配——对不上号的登记等于没登记，
    而这种失效是静默的：脚本照跑，只是永远命中不了。
    """
    for key, val in skipped.items():
        tail = key.rsplit("/", 1)[-1]
        if tail and (tail in stem or stem in tail):
            return key, val
    return None, None


def _skipped_sources() -> dict[str, tuple[str, list[str]]]:
    """`_未收.md` 里已登记的来源 → (不收的理由, 它修正过的卡)。

    **不收 ≠ 无影响**：一份素材可以不含可照做步骤（不该开卡），
    却推翻了某张已有卡的判据。第二列记前者，第三列记后者，两件事分开。
    """
    if not SKIP_FILE.is_file():
        return {}
    out: dict[str, tuple[str, list[str]]] = {}
    for line in SKIP_FILE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|--"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        # 表头只能靠首格精确匹配认——用 "来源" in line 会把名字里带
        # 「来源」的数据行一起吞掉，而且吞得毫无声息。
        if cells and cells[0] == "来源":
            continue
        if len(cells) >= 3:
            revised = [] if cells[2] in ("无", "-", "") else _split_list(cells[2])
            out[cells[0]] = (cells[1], revised)
    return out


def cmd_skip(args: argparse.Namespace) -> int:
    """登记「看过，未开卡」。

    这个判断本身有价值，却不在任何一张卡上留痕——不记下来，
    下次遇到同一份素材就要从头再评估一遍。开了卡的素材自带 `来源:`，
    所以只有没开卡的才需要台账。

    第三列记「虽未开卡但改过哪张卡」——**不收 ≠ 无影响**。
    """
    skipped = _skipped_sources()
    if args.source in skipped and not args.force:
        print(f"[INFO] 已登记过：{args.source} —— {skipped[args.source][0]}")
        return 0
    header = (
        "# 看过但未开卡的素材\n\n"
        "> 由 `python scripts/method.py skip` 追加。\n"
        "> 记在这里是为了**不重复评估**——`ingest` 会自动跳过已登记的来源。\n"
        "> 「修正过的卡」记的是：它虽不成卡，却推翻或补强了某张已有卡。\n"
        "> 有新理由推翻旧判断时，删掉对应行再重新走一遍吸纳。\n\n"
        "| 来源 | 不开卡的理由 | 修正过的卡 | 日期 |\n"
        "|------|-------------|-----------|------|\n"
    )
    if not SKIP_FILE.is_file():
        SKIP_FILE.write_text(header, encoding="utf-8")
    with SKIP_FILE.open("a", encoding="utf-8") as fh:
        fh.write(f"| {args.source} | {args.reason} | {args.revised or '无'} | {args.date} |\n")
    print(f"[OK] 已登记：{args.source}"
          + (f"（修正过 {args.revised}）" if args.revised else ""))
    return 0


def cmd_check(_args: argparse.Namespace) -> int:
    cards = load_cards()
    if not cards:
        print("[SKIP] _方法/ 下没有方法卡")
        return 0

    problems: list[str] = []

    for card in cards:
        missing = [f for f, v in (("阶段", card.stage), ("一句话", card.oneliner))
                   if not v]
        if missing:
            problems.append(f"[FIELD] {card.rel()} 缺字段：{'、'.join(missing)}")
        if not card.tags and not card.keywords:
            problems.append(f"[FIELD] {card.rel()} 既无 tags 也无关键词——检索不到等于没收")
        if not card.symptoms:
            problems.append(
                f"[FIELD] {card.rel()} 缺 症状 —— 求助者不会用术语提问，"
                f"没有原话钩子这张卡就只有作者自己搜得到")

    ids = {c.id for c in cards}
    for source, (reason, revised) in _skipped_sources().items():
        for rid in revised:
            if rid not in ids:
                problems.append(
                    f"[SOURCE] _未收.md 的「{source}」称修正了 {rid}，但没这张卡")

    for card in cards:
        for rid in card.related:
            if rid not in ids:
                problems.append(f"[LINK] {card.rel()} 的 相关: {rid} 不存在")

    expected = _index_text(cards)
    actual = INDEX_FILE.read_text(encoding="utf-8") if INDEX_FILE.is_file() else ""
    if actual != expected:
        problems.append("[INDEX] _方法/_索引.md 与卡片不一致 → python scripts/method.py index")

    for ratio, a, b in _dupe_pairs(cards):
        problems.append(
            f"[DUPE] {a.id} ≈ {b.id}（相似度 {ratio:.0%}）"
            f"——合并，或让两张卡的一句话与落点明确分开"
        )

    if problems:
        print("\n".join(problems))
        print(f"\n[FAIL] {len(problems)} 项")
        return 1
    print(f"[PASS] {len(cards)} 张方法卡：字段完整、双链有效、索引新鲜、无近重复")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="方法卡库检索")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="按问题检索方法卡")
    p.add_argument("query")
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--hop", type=int, default=0, help="额外带出双链邻居")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("show", help="打印整张方法卡")
    p.add_argument("id")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("index", help="生成 _方法/_索引.md")
    p.add_argument("--stage", help="只打印某一阶段的切片，不写文件")
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("dupe", help="吸纳前查重")
    p.add_argument("text")
    p.set_defaults(func=cmd_dupe)

    p = sub.add_parser("ingest", help="为素材生成加工工单（查重 + 反向影响提问）")
    p.add_argument("path", help="素材文件或目录")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("skip", help="登记「看过，不收」，避免重复评估")
    p.add_argument("source")
    p.add_argument("--reason", required=True)
    p.add_argument("--revised", help="虽未开卡，但被这份素材修正过的卡（逗号分隔）")
    p.add_argument("--date", default=_today())
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_skip)

    p = sub.add_parser("check", help="字段/双链/索引/重复检查")
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
