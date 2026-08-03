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
  python scripts/method.py ingest <素材路径>        # 吸纳：查重 + 摆出候选
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = ROOT / "_方法"
INDEX_FILE = LIB_DIR / "_索引.md"

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
                 "oneliner", "landing", "related", "body")

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
        self.body = body

    def fields(self) -> dict[str, str]:
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


def _indent(text: str, prefix: str = "  > ") -> str:
    return "\n".join(prefix + ln for ln in text.splitlines())


def cmd_ingest(args: argparse.Namespace) -> int:
    """吸纳素材：查重 → 摆出候选 → 交给 agent 判断。

    脚本只做检索这一步。**"素材是否更优"不设评分标准**——
    任何写死的评判规则都会在遇到没预料过的素材时判错，
    而模型本来就有这个判断力。这里只负责把可比的东西并排放好。
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

    print(f"# 吸纳（{len(materials)} 份素材）\n")
    print("对每份素材：\n")
    print("- **有重复** → 和下面的卡逐一比较。**素材更优就用它改写那张卡**，"
          "否则丢掉这份素材。什么叫更优由你判断，没有清单。")
    print("- **不重复** → 按 `_方法/README.md` 的卡片格式直接开新卡。\n")

    for mat in materials:
        try:
            text = mat.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"\n## {mat.name}\n\n[跳过] 读取失败：{exc}")
            continue

        print(f"\n## {mat.stem}")
        print(f"\n素材：`{mat}`（{len(text)} 字）")

        ranked = bm.score(text)[: args.top]
        if not ranked:
            print("\n库里没有相关卡 → 不重复，直接开新卡。")
            continue

        print("\n查重命中（分数只表示词面相近，是否真重复由你判断）：\n")
        for i, (score, card) in enumerate(ranked):
            print(f"### {card.id}（{score:.0f}，{card.stage}）")
            print(f"\n- 落点：{card.landing}")
            if i == 0:
                # 首位是最可能被替换的那张，给全文才比得了
                print(f"\n{_indent(card.body.strip())}\n")
            else:
                print(f"- 一句话：{card.oneliner}")
                crit = card.criteria()
                if crit:
                    print(f"- 判据：\n\n{_indent(crit)}\n")

    print("\n---\n")
    print("改完或新增完跑："
          "`python scripts/method.py index && python scripts/method.py check`")
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

    p = sub.add_parser("ingest", help="吸纳素材：查重并摆出可比的已有卡")
    p.add_argument("path", help="素材文件或目录")
    p.add_argument("--top", type=int, default=3)
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("check", help="字段/双链/索引/重复检查")
    p.set_defaults(func=cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
