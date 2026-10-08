"""核心提炼: 为每篇论文生成中英对照摘要卡.

每张卡包含:
- 研究问题 (Research Question)
- 所用方法 (Methods)
- 关键实验与结论 (Key Experiments & Findings)
- 创新点 (Novelty)
- 局限 (Limitations)

硬约束:
- 只能基于论文文本/摘要归纳, 不臆造数值与结论。
- 无法从现有材料判断的部分, 显式写 [MISSING] / [需人工补充] / Not assessable。
- 该模块产出「证据骨架 + 中英草稿」; 深度语义提炼由 Agent 在 SKILL 工作流中
  结合 nature-paper-card 规范补全(见 SKILL.md 的编排说明)。
"""

from __future__ import annotations

import re
from pathlib import Path

from common import PaperRecord, Logger, ensure_dir, write_text, MISSING, CANONICAL_FIELDS

# 从句式线索里抽取「目的/方法/结论」的启发式模式
_PURPOSE_PAT = re.compile(
    r"(((?:this|the present|our) (?:study|paper|work|research|article|review)|"
    r"we|here we|in this (?:study|paper|work|review))"
    r"[^.]{0,120}?(?:aim|goal|objective|investigat|examin|explor|propos|present|"
    r"develop|assess|evaluat|address|focus|quantif|estimat)[^.]{0,200}\.)", re.I)
_METHOD_PAT = re.compile(
    r"(((?:we |the (?:study|paper) )?(?:use[sd]?|appl(?:y|ied)|employ(?:s|ed)?|adopt(?:s|ed)?|"
    r"propose[sd]?|develop(?:s|ed)?|conduct(?:s|ed)?|perform(?:s|ed)?|"
    r"based on|combining|integrating|model(?:s|ed)?|simulat(?:e|ed|ion)|"
    r"experiment(?:s|al)?|questionnaire|survey|dataset|framework|algorithm)"
    r"[^.]{0,200}\.))", re.I)
_CONCLUSION_PAT = re.compile(
    r"(((?:results? (?:show|indicate|suggest|reveal|demonstrate|revealed|showed)|"
    r"we (?:find|found|conclude)|this (?:study|paper) (?:shows?|demonstrates?|concludes?)|"
    r"conclusion[s]?:|our (?:results|findings)|findings? (?:show|indicate|suggest)|"
    r"表明|结果显示|研究发现|本文|本研究)[^.]{0,220}[.。]))", re.I)
_LIMIT_PAT = re.compile(
    r"(((?:the (?:main|major|primary|key) )?limitation[s]?|future (?:work|research|studies)|"
    r"however,?[^.]{0,60}(?:limit|constrain)|not (?:fully|yet) (?:clear|understood)|"
    r"仍需|局限|不足之处|有待|未来(?:研究|工作))[^.]{0,200}[.。])", re.I)


def _findall(pat, text: str, limit: int) -> list[str]:
    out = []
    for m in pat.finditer(text or ""):
        s = m.group(1) if m.groups() else m.group(0)
        s = re.sub(r"\s+", " ", s).strip()
        # 清洗句首残留的连接词/标点
        s = re.sub(r"^[\s,;:.\-–—]+", "", s)
        if len(s) > 15 and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def extract_evidence(rec: PaperRecord) -> dict:
    """从记录中抽取结构化证据骨架."""
    abstract = rec.get("abstract").value or ""
    sections = rec.fields.get("_sections")
    sec = sections.value if sections and not sections.is_missing else {}
    body = "\n".join(str(v) for v in sec.values()) if sec else abstract

    ev = {
        "research_question": [],
        "methods": [],
        "findings": [],
        "limitations": [],
        "has_fulltext": bool(sec),
    }
    ev["research_question"] = _findall(_PURPOSE_PAT, abstract or body, 3)
    ev["methods"] = _findall(_METHOD_PAT, "\n".join(filter(None, [abstract,
                                                                  sec.get("methods", "")])), 4)
    ev["findings"] = _findall(_CONCLUSION_PAT,
                              "\n".join(filter(None, [abstract, sec.get("results", ""),
                                                      sec.get("conclusion", ""),
                                                      sec.get("discussion", "")])), 5)
    ev["limitations"] = _findall(_LIMIT_PAT,
                                 "\n".join(filter(None, [sec.get("discussion", ""),
                                                         sec.get("conclusion", "")])), 3)
    # 尝试从摘要中直接找 limitations
    ev["limitations"] += _findall(_LIMIT_PAT, abstract, 2)
    ev["limitations"] = list(dict.fromkeys(ev["limitations"]))[:3]
    return ev


def _bullets(items: list[str], empty_note: str) -> str:
    if not items:
        return f"- {empty_note}"
    return "\n".join(f"- {s}" for s in items)


def render_card_zh(rec: PaperRecord, ev: dict) -> str:
    g = lambda k: rec.get(k).display()
    note_no_text = "[MISSING] 现有材料未提供, 需人工补充"
    body_note = ("[提示] 仅基于元数据与摘要, 未获取全文, 结论/局限可能不完整"
                 if not ev["has_fulltext"] else "")
    return f"""# 核心摘要卡 · {g('title')}

| 字段 | 值 |
|---|---|
| 内部编号 | {rec.record_id} |
| 作者 | {g('authors')} |
| 年份 | {g('year')} |
| 期刊/会议 | {g('venue')} |
| DOI | {g('doi')} |
| 关键词 | {g('keywords')} |
| 被引数 | {g('citations')} |
| 数据来源 | {' + '.join(rec.sources)} |

{body_note}

## 1. 研究问题 (Research Question)
{_bullets(ev['research_question'], note_no_text)}

## 2. 所用方法 (Methods)
{_bullets(ev['methods'], note_no_text)}

## 3. 关键实验与结论 (Key Experiments & Findings)
{_bullets(ev['findings'], note_no_text)}

## 4. 创新点 (Novelty)
- {note_no_text}

## 5. 局限 (Limitations)
{_bullets(ev['limitations'], '[MISSING] 原文未明确陈述局限, 或未获取全文')}

---
*证据来源: {'PDF 正文 + ' if ev['has_fulltext'] else ''}摘要/元数据; 缺失项已显式标注, 未做数值臆造。*
"""


def render_card_en(rec: PaperRecord, ev: dict) -> str:
    g = lambda k: rec.get(k).display()
    note_no_text = "[MISSING] Not provided in available material; needs manual input."
    body_note = ("[Note] Abstract/metadata only; full text not retrieved, "
                 "so conclusions/limitations may be incomplete."
                 if not ev["has_fulltext"] else "")
    return f"""# Paper Summary Card · {g('title')}

| Field | Value |
|---|---|
| Record ID | {rec.record_id} |
| Authors | {g('authors')} |
| Year | {g('year')} |
| Venue | {g('venue')} |
| DOI | {g('doi')} |
| Keywords | {g('keywords')} |
| Citations | {g('citations')} |
| Sources | {' + '.join(rec.sources)} |

{body_note}

## 1. Research Question
{_bullets(ev['research_question'], note_no_text)}

## 2. Methods
{_bullets(ev['methods'], note_no_text)}

## 3. Key Experiments & Findings
{_bullets(ev['findings'], note_no_text)}

## 4. Novelty
- {note_no_text}

## 5. Limitations
{_bullets(ev['limitations'], '[MISSING] Not stated in the source, or full text unavailable.')}

---
*Evidence source: {'PDF full text + ' if ev['has_fulltext'] else ''}abstract/metadata. Missing fields are explicitly flagged; no values were fabricated.*
"""


def make_cards(records: list[PaperRecord], out_root: str | Path, logger: Logger) -> dict:
    out_root = ensure_dir(out_root)
    index = {"cards": [], "generated": None}
    from common import timestamp
    for rec in records:
        ev = extract_evidence(rec)
        d = ensure_dir(out_root / rec.record_id)
        write_text(d / "card_zh.md", render_card_zh(rec, ev))
        write_text(d / "card_en.md", render_card_en(rec, ev))
        index["cards"].append({
            "record_id": rec.record_id,
            "title": rec.get("title").display(),
            "zh": str(d / "card_zh.md"),
            "en": str(d / "card_en.md"),
            "evidence_counts": {k: (len(v) if isinstance(v, list) else v) for k, v in ev.items()},
        })
        logger.log(f"  · 摘要卡 {rec.record_id}: 方法证据 {len(ev['methods'])} 条, "
                   f"结论证据 {len(ev['findings'])} 条")
    index["generated"] = timestamp()
    from common import write_json
    write_json(out_root / "cards_index.json", index)
    logger.log(f"核心提炼: 生成 {len(index['cards'])} 组中英摘要卡")
    return index
