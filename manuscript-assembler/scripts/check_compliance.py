"""Nature 稿件合规检查器.

对组装出的稿件骨架做逐项体检, 输出结构化报告 (JSON + Markdown)。
检查项全部对应 nature-shared/journal-formats/nature.md 的硬性约束。

设计原则:
- 只报告"结构/格式/字数"层面的可判定问题; 科学内容正确性交作者与审稿人。
- 缺失项显式报告, 不臆测。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from spec import (SPEC, MANUSCRIPT_SECTIONS, REQUIRED_AVAILABILITY,
                  count_words, count_chars, title_ok, summary_ok, legend_ok,
                  subheading_ok, summary_flow_check)

SEV_ERROR = "ERROR"     # 必须修
SEV_WARN = "WARN"       # 建议修
SEV_OK = "OK"
SEV_INFO = "INFO"


class Report:
    def __init__(self):
        self.items: list[dict] = []

    def add(self, sev, area, msg, detail=""):
        self.items.append({"severity": sev, "area": area, "message": msg, "detail": detail})

    def counts(self):
        c = {SEV_ERROR: 0, SEV_WARN: 0, SEV_OK: 0, SEV_INFO: 0}
        for it in self.items:
            c[it["severity"]] = c.get(it["severity"], 0) + 1
        return c


# --------------------------------------------------------------------------
# 各检查项
# --------------------------------------------------------------------------

def check_structure(text: str, rep: Report):
    """16 项顺序完整性."""
    missing = []
    for i, (key, en, zh) in enumerate(MANUSCRIPT_SECTIONS, 1):
        # 匹配 "## <i>. " 或中文序号
        if not re.search(rf"^##\s*{i}\.\s", text, re.M):
            missing.append(f"{i}. {en}（{zh}）")
    if missing:
        rep.add(SEV_ERROR, "结构", f"缺失 {len(missing)} 个必需章节", "; ".join(missing))
    else:
        rep.add(SEV_OK, "结构", "Nature 16 项章节顺序完整")


def check_title(text: str, rep: Report):
    m = re.search(r"\*\*候选标题\*\*：(.*)", text)
    if not m:
        rep.add(SEV_WARN, "标题", "未找到候选标题字段")
        return
    title = m.group(1).strip()
    ok, msg = title_ok(title)
    # 标题超限是 Nature 硬约束, 判 ERROR
    rep.add(SEV_OK if ok else SEV_ERROR, "标题", msg)
    if re.search(r"[,:;!?]", title):
        rep.add(SEV_INFO, "标题", "标题含标点，Nature 建议避免")


def _strip_comments(text: str) -> str:
    """去掉 HTML 注释与引用标记, 只留正文."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"^>.*$", "", text, flags=re.M)   # 去掉引导引用行
    return text.strip()


def check_summary(text: str, rep: Report):
    if "Summary paragraph" not in text:
        return
    seg = _section_body(text, "Summary paragraph")
    body = _strip_comments(seg)
    body = re.sub(r"^\*\*\[机器草稿[^\]]*\]\*\*", "", body).strip()
    if not body or "DRAFT" in body or "MISSING" in body:
        rep.add(SEV_INFO, "摘要段", "摘要段为空或含占位符，需作者撰写（≤200 词，四段式）")
        return
    ok, msg = summary_ok(body)
    rep.add(SEV_OK if ok else SEV_ERROR, "摘要段", msg)
    for zh, present, name in summary_flow_check(body):
        if not present:
            rep.add(SEV_WARN, "摘要段", f"缺少“{zh}”线索（{name}）")


def check_legends(legend_file: Path, rep: Report):
    if not legend_file.exists():
        rep.add(SEV_INFO, "图注", "未生成图注文件")
        return
    txt = legend_file.read_text(encoding="utf-8")
    blocks = re.split(r"^##\s", txt, flags=re.M)[1:]
    if not blocks:
        rep.add(SEV_INFO, "图注", "无可检查的图注")
        return
    over = []
    for b in blocks:
        head = b.split("\n", 1)[0].strip()
        body = b.split("\n", 1)[1] if "\n" in b else ""
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
        n = count_words(body)
        if n > SPEC["figure_legend_max_words"]:
            over.append(f"{head}: {n} 词")
    if over:
        rep.add(SEV_ERROR, "图注", f"{len(over)} 条图注超 {SPEC['figure_legend_max_words']} 词",
                "; ".join(over))
    else:
        rep.add(SEV_OK, "图注", f"{len(blocks)} 条图注均在 {SPEC['figure_legend_max_words']} 词以内")


def check_availability(text: str, rep: Report):
    for key, en, zh in REQUIRED_AVAILABILITY:
        if en not in text:
            rep.add(SEV_ERROR, "可用性声明", f"缺少 {en}（{zh}）")


def check_placeholders(text: str, rep: Report):
    n_draft = text.count("机器草稿 - 需作者核改")
    n_fill = text.count("待填 - 作者补全")
    n_missing = len(re.findall(r"\[MISSING", text))
    if n_draft:
        rep.add(SEV_WARN, "机器草稿", f"{n_draft} 处机器生成内容需作者核改",
                "含摘要段草稿/素材注入，投稿前必须逐句核实")
    if n_fill:
        rep.add(SEV_INFO, "待填字段", f"{n_fill} 处待作者补全（作者/单位/声明等）")
    if n_missing:
        rep.add(SEV_WARN, "缺失字段", f"{n_missing} 处 [MISSING] 标记",
                "需作者或上游数据补全")


def check_references(ref_file: Path, rep: Report):
    if not ref_file.exists():
        rep.add(SEV_INFO, "参考文献", "未生成参考文献文件")
        return
    txt = ref_file.read_text(encoding="utf-8")
    entries = re.findall(r"^(\d+)\.\s", txt, re.M)
    n = len(entries)
    if n == 0:
        rep.add(SEV_INFO, "参考文献", "暂无文献条目")
        return
    if n > SPEC["main_references_max"]:
        rep.add(SEV_WARN, "参考文献",
                f"{n} 条，超过建议上限 {SPEC['main_references_max']}（Nature 约限）")
    else:
        rep.add(SEV_OK, "参考文献", f"{n} 条，在建议上限内")
    # 缺失标记
    miss_auth = txt.count("[MISSING 作者]")
    miss_doi = txt.count("[MISSING DOI]")
    miss_venue = txt.count("[MISSING 期刊]")
    if miss_auth or miss_doi or miss_venue:
        rep.add(SEV_WARN, "参考文献", "部分条目字段缺失",
                f"作者 {miss_auth} / 期刊 {miss_venue} / DOI {miss_doi}")
    # 序号连续性
    nums = [int(x) for x in entries]
    if nums != list(range(1, len(nums) + 1)):
        rep.add(SEV_ERROR, "参考文献", "编号不连续")


def check_subheadings(text: str, rep: Report):
    bad = []
    for m in re.finditer(r"^###\s+(.*)$", text, re.M):
        h = m.group(1).strip()
        if h in ("Data Availability（数据可用性声明）",
                 "Code Availability（代码可用性声明）"):
            continue
        ok, msg = subheading_ok(h)
        if not ok:
            bad.append(h)
    if bad:
        rep.add(SEV_WARN, "小标题", f"{len(bad)} 个小标题超 {SPEC['subheading_max_chars']} 字符",
                "; ".join(bad))
    else:
        rep.add(SEV_OK, "小标题", "小标题均在长度限制内")


def _section_body(text: str, heading_substr: str) -> str:
    m = re.search(rf"^##[^\n]*{re.escape(heading_substr)}[^\n]*\n(.*?)(?=^##\s|\Z)",
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------
# 主入口
# --------------------------------------------------------------------------

def run_check(manuscript: str | Path, references: str | Path | None = None,
              legends: str | Path | None = None,
              out_json: str | Path | None = None,
              out_md: str | Path | None = None) -> dict:
    text = Path(manuscript).read_text(encoding="utf-8")
    rep = Report()
    check_structure(text, rep)
    check_title(text, rep)
    check_summary(text, rep)
    check_availability(text, rep)
    check_placeholders(text, rep)
    check_subheadings(text, rep)
    if references:
        check_references(Path(references), rep)
    if legends:
        check_legends(Path(legends), rep)

    counts = rep.counts()
    verdict = ("BLOCKED" if counts[SEV_ERROR] else
               "REVIEW REQUIRED" if counts[SEV_WARN] else "PASS")

    result = {"verdict": verdict, "counts": counts, "items": rep.items}

    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(render_md(result), encoding="utf-8")
    return result


def render_md(result: dict) -> str:
    lines = ["# Nature 稿件合规检查报告", "",
             f"**结论：{result['verdict']}**", "",
             f"- ERROR（必须修）：{result['counts'].get('ERROR', 0)}",
             f"- WARN（建议修）：{result['counts'].get('WARN', 0)}",
             f"- OK：{result['counts'].get('OK', 0)}",
             f"- INFO：{result['counts'].get('INFO', 0)}",
             "", "| 严重度 | 领域 | 说明 | 详情 |", "|---|---|---|---|"]
    for it in result["items"]:
        d = it.get("detail", "").replace("|", "\\|")
        lines.append(f"| {it['severity']} | {it['area']} | {it['message']} | {d} |")
    lines += ["", "> 本报告只判定结构与格式合规性，不评价科学内容的正确性。"]
    return "\n".join(lines)
