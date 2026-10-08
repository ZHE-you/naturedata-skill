"""从 paper-batch-pipeline 的输出组装 Nature 投稿级稿件.

相比"空骨架"版本, 本版本做深做具体:
- 摘要段: 基于摘要卡证据自动生成**四段式草稿**(标注为机器草稿, 需作者改写)
- 正文: 按主题归类 findings/methods, 直接给出可引用素材 + 来源编号
- 声明类: 生成**可填模板**, 预填上游可得数据(文献数、图数、DOI 列表)
- 新增: 审稿人质疑清单 (reviewer risk list), 针对本文档预判常见质疑

硬约束:
- 只重组已有证据句, 绝不新增事实或数值。
- 机器生成内容一律标注 [机器草稿], 明确需作者核改。
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from spec import (SPEC, MANUSCRIPT_SECTIONS, REQUIRED_AVAILABILITY,
                  count_words, count_chars, title_ok, summary_ok, legend_ok)
from knowledge import (load_cards, gather_evidence, top_keywords,
                       draft_summary_paragraph, findings_by_theme)

DRAFT_TAG = "[机器草稿 - 需作者核改]"
FILL_TAG = "[待填 - 作者补全]"


# --------------------------------------------------------------------------
# 读取上游产物
# --------------------------------------------------------------------------

def load_upstream(batch_dir: str | Path) -> dict:
    import json
    d = Path(batch_dir)
    data = {"batch_dir": str(d), "papers": [], "figures": [], "cards": []}

    summary = d / "汇总表_summary.csv"
    if summary.exists():
        with open(summary, "r", encoding="utf-8-sig", newline="") as f:
            data["papers"] = list(csv.DictReader(f))

    for name, key in [("pipeline_result.json", "result"),
                      ("figures/figure_manifest.json", "figure_manifest"),
                      ("cards/cards_index.json", "cards_index")]:
        p = d / name
        if p.exists():
            data[key] = json.loads(p.read_text(encoding="utf-8"))

    if "figure_manifest" in data:
        data["figures"] = data["figure_manifest"].get("figures", [])
    if "cards_index" in data:
        data["cards"] = data["cards_index"].get("cards", [])

    # 深读摘要卡, 拿证据句
    data["card_details"] = load_cards(d / "cards")
    return data


# --------------------------------------------------------------------------
# 参考文献 (Nature 格式)
# --------------------------------------------------------------------------

def _parse_authors(s: str) -> list[str]:
    if not s or s == "MISSING":
        return []
    return [p.strip() for p in re.split(r"[;；]", s) if p.strip() and p.strip() != "MISSING"]


def format_reference(idx: int, paper: dict) -> str:
    authors = _parse_authors(paper.get("作者", ""))
    if len(authors) > 5:
        author_str = f"{authors[0]} et al."
    elif authors:
        author_str = "; ".join(authors)
    else:
        author_str = "[MISSING 作者]"

    title = paper.get("标题", "") or "[MISSING 标题]"
    venue = paper.get("期刊/会议", "")
    year = paper.get("年份", "")
    doi = paper.get("DOI", "")

    venue_str = venue if venue and venue != "MISSING" else "[MISSING 期刊]"
    year_str = f"({year})" if year and year != "MISSING" else "(年缺)"
    doi_str = f" doi:{doi}" if doi and doi != "MISSING" else " [MISSING DOI]"
    return f"{idx}. {author_str}. {title}. {venue_str} {year_str}.{doi_str}"


def build_references(papers: list[dict]) -> str:
    lines = ["# References (Nature 格式)", "",
             "> 编号按正文引用顺序排列（此处按汇总表顺序占位，定稿时需重排）。",
             "> Nature 要求：每篇含标题；作者 ≤5 全列，>5 用 et al.；不含未发表工作。", ""]
    notes = []
    for i, p in enumerate(papers, 1):
        lines.append(format_reference(i, p))
        n = len(_parse_authors(p.get("作者", "")))
        if n > 5:
            notes.append(f"  - Ref {i}: 作者 {n} 人 → 已缩略为 et al.")
    if notes:
        lines += ["", "## 需注意", *notes]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 图注 (中英双版合并)
# --------------------------------------------------------------------------

def build_figure_legends(figures: list[dict], lang: str = "en") -> str:
    lines = ["# Figure Legends (Nature 格式)", "",
             "> Nature 要求：每条图注 ≤250 词；以简短标题句开头；描述所绘内容，不复述结果/方法。",
             "> 来源编号来自 paper-batch-pipeline，保留以便溯源。",
             f"> 中英双版图已合并为同一图号（本清单基于 `{lang}` 版编号）。", ""]

    merged: dict[str, dict] = {}
    for f in figures:
        key = str(f.get("name", ""))
        if key not in merged:
            merged[key] = {"name": key, "source_ref": f.get("source_ref", "")}
    name_zh = {"overview": "论文总览", "venues": "来源分布", "keywords": "高频关键词"}

    ordered = ([k for k in ("overview", "venues", "keywords") if k in merged] +
               [k for k in merged if k.startswith("table_")])
    idx = 1
    for key in ordered:
        src = merged[key]["source_ref"] or "汇总元数据"
        if key in name_zh:
            body = (f"Figure {idx} | {name_zh[key]}概览。数据来源: {src}。"
                    f"{DRAFT_TAG} 请作者按图内容撰写描述句（Title sentence + 内容描述）。")
        else:
            body = (f"Figure {idx} | {key} 对应指标。"
                    f"数据来源: {src}（从原文表格抽取，数值需作者复核）。{DRAFT_TAG}")
        ok, msg = legend_ok(body)
        lines.append(f"## Figure {idx}")
        lines.append(body)
        lines.append(f"<!-- 词数: {count_words(body)} / 上限 {SPEC['figure_legend_max_words']} | {msg} -->")
        lines.append("")
        idx += 1
    if idx == 1:
        lines.append("_未检测到图表；请先运行 paper-batch-pipeline。_")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 稿件主体 (含真实素材注入)
# --------------------------------------------------------------------------

def build_manuscript(data: dict, title=None, authors=None, affiliations=None) -> str:
    papers = data.get("papers", [])
    figures = data.get("figures", [])
    cards = data.get("card_details", [])
    ev = gather_evidence(cards)
    kws = top_keywords(cards, 10)
    themes = findings_by_theme(cards)

    cand_title = title or _candidate_title(papers, kws)
    cand_authors = authors or f"{FILL_TAG} 作者列表（含通讯作者 * 标注）"
    cand_affil = affiliations or f"{FILL_TAG} 单位列表（含 present address）"

    p: list[str] = []
    p += ["# Nature Article — 稿件（含自动注入素材）", "",
          f"> 由 paper-batch-pipeline 批次 `{Path(data['batch_dir']).name}` 组装："
          f"{len(papers)} 篇文献、{len(figures)} 张图、{len(cards)} 张摘要卡。",
          "> **机器生成内容一律标注 `[机器草稿 - 需作者核改]`；"
          "素材句保留来源编号，未新增任何事实或数值。**", "", "---", ""]

    # 1 Title
    ok, msg = title_ok(cand_title)
    p += ["## 1. Title（标题）", "", f"**候选标题**：{cand_title}", "",
          f"<!-- {msg}；上限 {SPEC['title_max_chars']} 字符、约两行 -->", ""]

    # 2 Authors
    p += ["## 2. Authors（作者）", "", cand_authors, "",
          "> 通讯作者用 `*`；≤3 名同等贡献者在地址下方标明。", ""]

    # 3 Affiliations
    p += ["## 3. Affiliations and present addresses（单位与现址）", "",
          cand_affil, "", "> present address 紧随作者列表下方。", ""]

    # 4 Summary paragraph —— 注入四段式草稿
    p += [f"## 4. Summary paragraph（摘要段，≤{SPEC['summary_max_words']} 词）", ""]
    sd = draft_summary_paragraph(cards)
    p += [f"**{DRAFT_TAG}**", "", sd["draft"], "",
          f"<!-- 正文词数 {count_words(sd['draft'])} / "
          f"上限 {SPEC['summary_max_words']}；主结论来源: {', '.join(sd['sources']) or '无'} -->",
          "> 四段式：宽领域背景 → 背景/理由 → 主结论（Here we show）→ 推进领域。",
          "> 上方为机器重组草稿，**必须由作者改写并核实**，不得直接投稿。", ""]

    # 5 Main text —— 注入按主题归类的素材
    p += ["## 5. Main text（正文）", "",
          f"> 字数预算：六页 ≈{SPEC['article_6p_words']} 词 / 八页 ≈{SPEC['article_8p_words']} 词；"
          f"小标题 ≤{SPEC['subheading_max_chars']} 字符。", ""]
    p += ["### 引言（紧随摘要段，无小标题）", "", DRAFT_TAG, "",
          "> 可用背景素材（来自摘要卡，保留来源）：", ""]
    for c in cards[:8]:
        q = c.get("research_question") or c.get("methods")
        if q:
            p.append(f"- {q[0]}  <!-- 来源 {c['record_id']} -->")
    if not any(c.get("research_question") or c.get("methods") for c in cards):
        p.append(f"- {FILL_TAG} 上游摘要卡未提供背景句")
    p += ["", "### Results", "", DRAFT_TAG, "",
          "> 可按主题分组的结论素材（来自摘要卡 findings）：", ""]
    for theme, items in themes.items():
        p.append(f"**{theme}**")
        for it in items:
            p.append(f"- {it['text']}  <!-- 来源 {it['record_id']} -->")
        p.append("")
    if not themes:
        p.append(f"- {FILL_TAG} 暂无 findings 素材")
    p += ["", "### Discussion", "", DRAFT_TAG, "",
          "> 可用的局限/边界素材：", ""]
    lims = ev["limitations"]
    if lims:
        for it in lims:
            p.append(f"- {it['text']}  <!-- 来源 {it['record_id']} -->")
    else:
        p.append(f"- {FILL_TAG} 上游未抽取到局限陈述")
    p += ["", "### Conclusion", "", DRAFT_TAG, ""]

    # 6 References
    p += ["## 6. Main references（正文参考文献）", "",
          f"> 上限约 {SPEC['main_references_max']} 条；按正文出现顺序编号；上标引用。",
          f"> 本批次 {len(papers)} 篇，见 `references.md`。", ""]

    # 7 Tables
    p += ["## 7. Tables（表格）", "",
          "> 每表配简短标题句，细节入表注；建议三线表。", "", DRAFT_TAG, ""]

    # 8 Figure legends
    p += ["## 8. Figure legends（图注）", "",
          f"> 每条 ≤{SPEC['figure_legend_max_words']} 词；见 `figure_legends.md`。",
          f"> 本批次图 {len(figures)} 张（含中英双版）。", ""]

    # 9 Methods
    p += [f"## 9. Methods（方法，通常 ≤{SPEC['methods_max_words']} 词）", "",
          "> 方法内不插图/表；简短粗体小标题；可设 statistics / reagents 子节。", ""]
    for key, en, zh in REQUIRED_AVAILABILITY:
        p += [f"### {en}（{zh}）", "",
              _availability_template(key, data), "",
              "> 需给出具体仓库/登记号与访问限制，勿写套话。", ""]

    # 10 Methods references
    p += ["## 10. Methods references（方法参考文献）", "",
          "> 编号接续正文参考文献。", ""]

    # 11-14 声明类 —— 生成可填模板并预填已知数据
    p += ["## 11. Acknowledgements（致谢）", "",
          f"{FILL_TAG} 保持简短；不谢匿名审稿人与编辑。", ""]
    p += ["## 12. Funding statement（资助声明）", "",
          f"{FILL_TAG} 仅当工作属于且直接源自所列资助时声明。", ""]
    p += ["## 13. Author contributions（作者贡献）", "",
          _contrib_template(cand_authors), "",
          "> 逐作者描述贡献；>3 人同等贡献在此说明。", ""]
    p += ["## 14. Competing-interests declaration（利益冲突声明）", "",
          "The authors declare no competing interests.  "
          f"<!-- {FILL_TAG} 若存在冲突请改写 -->", ""]

    # 15 Additional information
    p += ["## 15. Additional information（附加信息）", "",
          f"> 含 Supplementary Information 说明与通讯作者行。",
          f"> SI 最多 {SPEC['si_max_files']} 个文件；SIGuide 摘要 ≤"
          f"{SPEC['si_summary_max_words']} 词。", "",
          f"{FILL_TAG} 通讯作者：***（姓名、邮箱）", ""]

    # 16 Extended Data
    p += [f"## 16. Extended Data figure and table legends（扩展数据，≤"
          f"{SPEC['extended_data_max_items']} 项）", "", DRAFT_TAG, ""]

    p += ["---", "", "## 素材总览", "",
          f"- 文献 {len(papers)} 篇；摘要卡 {len(cards)} 张；图 {len(figures)} 张",
          f"- 高频关键词：" + (", ".join(f"{k}({v})" for k, v in kws) or "无"),
          f"- 可引用 findings 句 {len(ev['findings'])} 条；"
          f"局限句 {len(ev['limitations'])} 条；方法句 {len(ev['methods'])} 条", ""]
    return "\n".join(p)


def _availability_template(key: str, data: dict) -> str:
    papers = data.get("papers", [])
    dois = [p.get("DOI", "") for p in papers if p.get("DOI") and p.get("DOI") != "MISSING"]
    if key == "data_availability":
        listed = "、".join(f"doi:{d}" for d in dois[:5]) if dois else "（本批次文献 DOI：无）"
        return (f"All data supporting this study are available from the cited sources "
                f"({listed}) and/or from the corresponding author on reasonable request.  "
                f"<!-- {FILL_TAG} 若数据已存入仓库/登记号，请替换为具体地址与登记号 -->")
    return (f"Analysis code is available from the corresponding author on reasonable request.  "
            f"<!-- {FILL_TAG} 若有公开代码仓库与版本号，请替换 -->")


def _contrib_template(authors: str) -> str:
    if authors.startswith("[待填"):
        return f"{FILL_TAG} 逐作者列出贡献，例如：A.B. conceived the study; C.D. analysed data; ..."
    return (f"{FILL_TAG} 逐作者列出贡献。当前作者列表：{authors}")


def _candidate_title(papers: list[dict], kws: list[tuple[str, int]]) -> str:
    if kws:
        topic = ", ".join(k for k, _ in kws[:3])
        return f"A systematic study of {topic}"
    return "[MISSING 标题 - 需作者定稿]"


# --------------------------------------------------------------------------
# 审稿人质疑清单 (新增, 做深)
# --------------------------------------------------------------------------

def build_reviewer_risks(data: dict) -> str:
    cards = data.get("card_details", [])
    papers = data.get("papers", [])
    n_no_full = sum(1 for c in cards if not c["has_fulltext"])
    n_no_lim = sum(1 for c in cards if not c["limitations"])
    dois = [p.get("DOI") for p in papers if p.get("DOI") and p.get("DOI") != "MISSING"]
    n_no_doi = len(papers) - len(dois)

    risks: list[tuple[str, str, str]] = []  # (级别, 质疑, 建议)
    if n_no_full:
        risks.append(("HIGH", f"{n_no_full}/{len(cards)} 篇仅有元数据/摘要，无全文",
                      "关键结论须回到全文核实；正文引用前补读原文"))
    if n_no_lim:
        risks.append(("MEDIUM", f"{n_no_lim}/{len(cards)} 篇未抽取到局限陈述",
                      "Discussion 需自行补充各证据的边界与适用条件"))
    if n_no_doi:
        risks.append(("MEDIUM", f"{n_no_doi} 篇缺 DOI",
                      "参考文献可能无法核验；补全 DOI 后再定稿"))
    risks.append(("HIGH", "摘要段为机器重组草稿",
                  "必须由作者改写为 Nature 四段式，核实每句事实"))
    risks.append(("MEDIUM", "证据跨研究可比性",
                  "不同研究的方法/口径可能不一致，综合结论前须说明可比性判据"))
    risks.append(("MEDIUM", "创新点未确立",
                  "上游摘要卡默认未提炼创新点；投稿前须明确本文的 novelty 主张"))
    risks.append(("LOW", "图注为占位",
                  "图注定稿后需与图逐一核对，避免复述结果/方法"))

    lines = ["# 审稿人质疑预判 (Reviewer Risk List)", "",
             "> 针对本稿件当前状态预判审稿人可能的质疑。按严重度排序，供投稿前自查。", "",
             "| 级别 | 可能质疑 | 应对建议 |", "|---|---|---|"]
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    for lvl, q, adv in sorted(risks, key=lambda x: order[x[0]]):
        lines.append(f"| {lvl} | {q} | {adv} |")
    lines += ["", "> 本清单基于上游素材的**可得性**推断，不评价科学结论本身。"]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

def assemble(batch_dir: str, out_dir: str, title=None, authors=None,
             affiliations=None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    data = load_upstream(batch_dir)

    (out / "manuscript_draft.md").write_text(
        build_manuscript(data, title, authors, affiliations), encoding="utf-8")
    (out / "references.md").write_text(
        build_references(data.get("papers", [])), encoding="utf-8")
    (out / "figure_legends.md").write_text(
        build_figure_legends(data.get("figures", [])), encoding="utf-8")
    (out / "reviewer_risks.md").write_text(
        build_reviewer_risks(data), encoding="utf-8")

    return {
        "ok": True,
        "n_papers": len(data.get("papers", [])),
        "n_figures": len(data.get("figures", [])),
        "n_cards": len(data.get("card_details", [])),
        "manuscript": str(out / "manuscript_draft.md"),
        "references": str(out / "references.md"),
        "figure_legends": str(out / "figure_legends.md"),
        "reviewer_risks": str(out / "reviewer_risks.md"),
    }
