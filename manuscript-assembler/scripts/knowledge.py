"""知识抽取: 从 paper-batch-pipeline 的摘要卡中挖出可注入稿件的素材.

不臆造 —— 只抽取卡片里已有的句子, 并保留其来源 record_id, 便于正文标注引用。
"""

from __future__ import annotations

import re
from pathlib import Path


def parse_card(path: str | Path) -> dict:
    """解析一张摘要卡 Markdown, 抽出结构化字段与证据句."""
    p = Path(path)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8", errors="replace")

    card = {"path": str(p), "record_id": "", "title": "", "year": "",
            "venue": "", "doi": "", "keywords": [], "citations": "",
            "research_question": [], "methods": [], "findings": [],
            "novelty": [], "limitations": [], "has_fulltext": False}

    m = re.search(r"^#\s*核心摘要卡\s*·\s*(.+)$", text, re.M)
    if m:
        card["title"] = m.group(1).strip()

    # 字段表
    field_map = {
        "内部编号": "record_id", "年份": "year", "期刊/会议": "venue",
        "DOI": "doi", "被引数": "citations",
    }
    for zh, key in field_map.items():
        mm = re.search(rf"\|\s*{zh}\s*\|\s*(.*?)\s*\|", text)
        if mm:
            card[key] = mm.group(1).strip()
    mk = re.search(r"\|\s*关键词\s*\|\s*(.*?)\s*\|", text)
    if mk:
        card["keywords"] = [x.strip() for x in mk.group(1).split(";") if x.strip()]

    card["has_fulltext"] = "未获取全文" not in text and "PDF 正文" in text

    # 证据句 (二级标题下的 - 列表)
    def section(name_pat: str) -> list[str]:
        mm = re.search(rf"^##\s*[^\n]*{name_pat}[^\n]*\n(.*?)(?=^##\s|\Z)",
                       text, re.M | re.S)
        if not mm:
            return []
        items = []
        for line in mm.group(1).split("\n"):
            line = line.strip()
            if line.startswith("- "):
                s = line[2:].strip()
                if s and not s.startswith("[MISSING") and not s.startswith("[提示"):
                    items.append(s)
        return items

    card["research_question"] = section(r"研究问题")
    card["methods"] = section(r"所用方法")
    card["findings"] = section(r"关键实验与结论")
    card["novelty"] = section(r"创新点")
    card["limitations"] = section(r"局限")
    return card


def load_cards(cards_dir: str | Path) -> list[dict]:
    d = Path(cards_dir)
    out = []
    for sub in sorted(d.glob("*/card_zh.md")):
        c = parse_card(sub)
        if c:
            out.append(c)
    return out


# --------------------------------------------------------------------------
# 素材组织
# --------------------------------------------------------------------------

def gather_evidence(cards: list[dict]) -> dict:
    """把各卡证据按类型聚合, 保留来源编号."""
    ev = {"research_question": [], "methods": [], "findings": [],
          "limitations": [], "novelty": []}
    for c in cards:
        for key in ev:
            for s in c.get(key, []):
                ev[key].append({"record_id": c["record_id"],
                                "title": c["title"], "text": s,
                                "has_fulltext": c["has_fulltext"]})
    return ev


def top_keywords(cards: list[dict], n: int = 10) -> list[tuple[str, int]]:
    from collections import Counter
    cnt: Counter = Counter()
    for c in cards:
        for k in c.get("keywords", []):
            cnt[k.strip()] += 1
    return cnt.most_common(n)


def draft_summary_paragraph(cards: list[dict], field_hint: str = "") -> dict:
    """基于素材生成四段式摘要段**草稿** (标注为机器草稿, 需作者改写).

    不写新事实 —— 只重组已有证据句到 Nature 四段式位置。
    """
    ev = gather_evidence(cards)
    kws = [k for k, _ in top_keywords(cards, 5)]
    topic = ", ".join(kws[:3]) if kws else "[MISSING 主题]"

    p1 = f"Understanding {topic} has become a central concern across the field."
    p2 = ("However, the evidence base remains fragmented: individual studies differ "
          "in scope, method and reported outcomes, making synthesis difficult.")
    # 主结论: 优先用 fulltext 卡片的 findings; 去掉原句的引导词避免 "show that...show that"
    findings = [e for e in ev["findings"] if e["has_fulltext"]] or ev["findings"]
    if findings:
        raw = findings[0]["text"].rstrip(".")
        raw = re.sub(r"^(Results?\s+(show|indicate|suggest|reveal|demonstrate|revealed|showed)"
                     r"|We\s+(find|found|conclude)|Our\s+(results|findings)|"
                     r"Findings?\s+(show|indicate|suggest))\s+that\s+", "", raw, flags=re.I)
        p3 = f"Here we show that {raw}."
    else:
        p3 = "Here we show that [MISSING 主结论句]。"
    p4 = (f"These results consolidate evidence from {len(cards)} studies and "
          f"provide a basis for moving the field toward consistent, comparable reporting.")

    draft = " ".join([p1, p2, p3, p4])
    return {
        "draft": draft,
        "sources": [e["record_id"] for e in findings[:3]],
        "is_machine_draft": True,
    }


def findings_by_theme(cards: list[dict]) -> dict[str, list[dict]]:
    """按关键词把 findings 归主题, 供正文 Results 引用."""
    themes: dict[str, list[dict]] = {}
    for c in cards:
        for s in c.get("findings", []):
            # 用该文关键词里第一个作为主题标签
            tag = c["keywords"][0] if c.get("keywords") else "General"
            themes.setdefault(tag, []).append(
                {"record_id": c["record_id"], "title": c["title"], "text": s})
    return themes
