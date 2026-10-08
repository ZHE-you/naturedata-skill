"""三路输入解析器: PDF / BibTeX / CSV.

每个解析器返回 list[PaperRecord] 或 (list[PaperRecord], 附带原始数据)。
解析阶段只做「抽取」, 不做跨源合并; 合并由 merge.py 负责。
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from common import (
    PaperRecord, parse_year, parse_int, parse_authors, parse_keywords,
    normalize_doi, CONF_HIGH, CONF_MEDIUM, CONF_LOW, read_text, Logger,
)

# --------------------------------------------------------------------------
# BibTeX
# --------------------------------------------------------------------------

_BIB_TYPE = "article|inproceedings|conference|book|incollection|phdthesis|mastersthesis|techreport|misc|unpublished"


def parse_bibtex(path: str | Path) -> list[PaperRecord]:
    """解析 .bib 文件 -> PaperRecord 列表."""
    text = read_text(path)
    records: list[PaperRecord] = []
    try:
        import bibtexparser
        from bibtexparser.bparser import BibTexParser
        parser = BibTexParser(common_strings=True)
        parser.ignore_nonstandard_types = False
        db = bibtexparser.loads(text, parser=parser)
        entries = db.entries
    except Exception:
        entries = _fallback_bib_entries(text)

    for i, e in enumerate(entries):
        src = f"bibtex:{Path(path).name}"
        rec = PaperRecord(record_id=f"bib{i+1:03d}", sources=[src])
        g = lambda *keys: next((e[k] for k in keys if e.get(k)), None)
        rec.set("title", _clean_latex(g("title")), src, CONF_HIGH)
        rec.set("authors", parse_authors(g("author")), src, CONF_HIGH)
        rec.set("year", parse_year(g("year", "date")), src, CONF_HIGH)
        rec.set("venue", _clean_latex(g("journal", "booktitle", "journaltitle",
                                       "publisher", "series", "howpublished")), src, CONF_MEDIUM)
        rec.set("doi", normalize_doi(g("doi")), src, CONF_HIGH)
        rec.set("keywords", parse_keywords(g("keywords")), src, CONF_MEDIUM)
        rec.set("abstract", _clean_latex(g("abstract")), src, CONF_MEDIUM)
        rec.set("url", g("url"), src, CONF_MEDIUM)
        if g("note"):
            rec.set("citations", parse_int(g("note")), src, CONF_LOW,
                    note="从 note 字段猜测被引数, 置信度低")
        rec.finalize_missing()
        records.append(rec)
    return records


def _fallback_bib_entries(text: str) -> list[dict]:
    """不依赖 bibtexparser 的极简兜底解析."""
    entries = []
    for m in re.finditer(r"@\s*(?:" + _BIB_TYPE + r")\s*\{[^,]+,(.*?)\n\}", text,
                         re.DOTALL | re.IGNORECASE):
        body = m.group(1)
        d: dict[str, str] = {}
        for fm in re.finditer(r"(\w+)\s*=\s*\{(.*?)\}\s*,?", body, re.DOTALL):
            d[fm.group(1).lower()] = fm.group(2).strip()
        if d:
            entries.append(d)
    return entries


def _clean_latex(s: Any) -> Any:
    """去除常见 LaTeX 包裹与转义."""
    if s is None:
        return None
    s = str(s)
    s = re.sub(r"[{}]", "", s)
    s = s.replace("\\&", "&").replace("\\%", "%").replace("--", "-")
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s)   # 去除 \textit 等命令
    return re.sub(r"\s+", " ", s).strip()


# --------------------------------------------------------------------------
# CSV / Excel 元数据表
# --------------------------------------------------------------------------

from common import CANONICAL_FIELDS

_ALIAS_INDEX: dict[str, str] = {}
for _k, _meta in CANONICAL_FIELDS.items():
    _ALIAS_INDEX[_k.lower()] = _k
    for _a in _meta["aliases"]:
        _ALIAS_INDEX[_a.lower()] = _k


def _map_header(h: str) -> str | None:
    if h is None:
        return None
    key = re.sub(r"[\s_\-]+", "", h).lower()
    for alias, canon in _ALIAS_INDEX.items():
        if re.sub(r"[\s_\-]+", "", alias) == key:
            return canon
    # 包含式匹配(如 "被引数(次)")
    for alias, canon in _ALIAS_INDEX.items():
        if alias and alias in h.lower():
            return canon
    return None


def parse_csv(path: str | Path) -> list[PaperRecord]:
    """解析 .csv / .xlsx 元数据表 -> PaperRecord 列表."""
    path = Path(path)
    rows: list[dict] = []
    if path.suffix.lower() in (".xlsx", ".xls"):
        rows = _read_excel_rows(path)
    else:
        for enc in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    rows = list(csv.DictReader(f))
                break
            except UnicodeDecodeError:
                continue

    src = f"csv:{path.name}"
    records: list[PaperRecord] = []
    for i, row in enumerate(rows):
        if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
            continue
        rec = PaperRecord(record_id=f"csv{i+1:03d}", sources=[src])
        mapped: dict[str, Any] = {}
        for h, v in row.items():
            canon = _map_header(h)
            if canon and canon not in mapped and v not in (None, ""):
                mapped[canon] = v
        if "year" in mapped:
            mapped["year"] = parse_year(mapped["year"])
        if "citations" in mapped:
            mapped["citations"] = parse_int(mapped["citations"])
        if "authors" in mapped:
            mapped["authors"] = parse_authors(mapped["authors"])
        if "keywords" in mapped:
            mapped["keywords"] = parse_keywords(mapped["keywords"])
        if "doi" in mapped:
            mapped["doi"] = normalize_doi(mapped["doi"])
        for k, v in mapped.items():
            rec.set(k, v, src, CONF_HIGH if k in ("title", "authors", "doi", "year") else CONF_MEDIUM)
        # 保留未被识别的列, 供后续参考
        unknown = {h: v for h, v in row.items() if not _map_header(h) and v}
        if unknown:
            rec.fields["_extra"] = __import__("common").Field(value=unknown, source=src,
                                                              confidence=CONF_LOW,
                                                              note="未映射的额外列")
        rec.finalize_missing()
        records.append(rec)
    return records


def _read_excel_rows(path: Path) -> list[dict]:
    try:
        import openpyxl
    except Exception as e:
        raise RuntimeError(f"读取 Excel 需要 openpyxl: {e}")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    it = ws.iter_rows(values_only=True)
    headers = [str(h) if h is not None else "" for h in next(it)]
    out = []
    for r in it:
        out.append({headers[i]: ("" if r[i] is None else str(r[i]))
                    for i in range(min(len(headers), len(r)))})
    wb.close()
    return out


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------

_DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")

# 章节标题(用于摘要卡定位)
_SECTION_PATTERNS = {
    "abstract": r"^\s*(abstract|摘\s*要)\b",
    "introduction": r"^\s*(1\.?\s*)?(introduction|引\s*言|前\s*言)\b",
    "methods": r"^\s*(2\.?\s*|3\.?\s*)?(methods?|materials?\s+and\s+methods?|methodology|实验方法|方\s*法|材料与方法)\b",
    "results": r"^\s*(\d\.?\s*)?(results?|results?\s+and\s+discussion|结\s*果|结果与分析)\b",
    "discussion": r"^\s*(\d\.?\s*)?(discussions?|讨\s*论)\b",
    "conclusion": r"^\s*(\d\.?\s*)?(conclusions?|结\s*论|总结)\b",
    "references": r"^\s*(references?|bibliography|参考文献)\b",
}


def parse_pdf(path: str | Path, logger: Logger | None = None) -> PaperRecord:
    """从单篇 PDF 抽取元数据 + 正文结构 + 表格."""
    import pymupdf  # PyMuPDF

    path = Path(path)
    src = f"pdf:{path.name}"
    doc = pymupdf.open(str(path))
    pages_text: list[str] = []
    for page in doc:
        pages_text.append(page.get_text("text"))
    full = "\n".join(pages_text)
    first = pages_text[0] if pages_text else ""

    rec = PaperRecord(record_id=f"pdf_{path.stem[:20]}", sources=[src])

    # --- 标题: 首页最大的字体块 ---
    title = _extract_title(doc)
    rec.set("title", title, src, CONF_HIGH if title else CONF_LOW)

    # --- DOI ---
    m = _DOI_RE.search(full)
    if m:
        rec.set("doi", normalize_doi(m.group(0)), src, CONF_HIGH)

    # --- 年份: 首页/页脚中的 19xx-20xx ---
    year = _extract_year(doc, full)
    rec.set("year", year, src, CONF_MEDIUM if year else CONF_LOW)

    # --- 摘要 ---
    abstract = _extract_abstract(full)
    rec.set("abstract", abstract, src, CONF_MEDIUM)

    # --- 关键词 ---
    kw = _extract_keywords(full)
    rec.set("keywords", kw, src, CONF_MEDIUM)

    # --- 作者: 启发式(标题下方、非邮箱、非机构行) ---
    authors = _extract_authors(doc, title)
    rec.set("authors", authors, src, CONF_LOW if authors else CONF_LOW,
            note="作者从 PDF 版式启发式抽取, 建议人工核对")

    # --- 表格 ---
    tables = _extract_tables(doc, logger)
    rec.raw_tables = tables

    # --- 正文结构 ---
    sections = _split_sections(full)
    rec.fields["_sections"] = __import__("common").Field(
        value={k: v[:6000] for k, v in sections.items()}, source=src,
        confidence=CONF_MEDIUM, note="PDF 章节切分结果, 供摘要卡提炼")
    rec.fields["_fulltext_chars"] = __import__("common").Field(
        value=len(full), source=src, confidence=CONF_HIGH, note="正文总字符数")
    doc.close()
    rec.finalize_missing()
    return rec


def _extract_title(doc) -> str:
    """取首页字号最大的一档文本块作为标题.

    策略: 收集首页上半部(排除页眉)所有文本块的字号, 取最大字号档位;
    只在"最大字号"这一档里拼接文本, 避免把次级标题(章节名)混入。
    若最大档位块数过多(说明字体层级不明显), 退化为取最靠上的 1-3 块。
    """
    if doc.page_count == 0:
        return ""
    page = doc[0]
    d = page.get_text("dict")
    blocks: list[tuple[float, float, str]] = []   # (size, y0, text)
    for block in d.get("blocks", []):
        if block.get("type") != 0:
            continue
        bbox = block.get("bbox", [0, 0, 0, 0])
        y0 = bbox[1]
        if y0 < page.rect.height * 0.05 or y0 > page.rect.height * 0.72:
            continue
        txt = " ".join(
            s.get("text", "") for line in block.get("lines", []) for s in line.get("spans", [])
        ).strip()
        if len(txt) < 10 or not re.search(r"[A-Za-z\u4e00-\u9fff]", txt):
            continue
        # 排除常见的章节小标题行
        if re.match(r"^\s*(\d+\.?\s*)?(introduction|methods?|results?|discussion|"
                    r"conclusions?|references?|abstract|引言|方法|结果|讨论|结论|摘要)\b",
                    txt, re.I) and len(txt) < 30:
            continue
        size = max((s.get("size", 0) for line in block.get("lines", [])
                    for s in line.get("spans", [])), default=0)
        blocks.append((size, y0, txt))
    if not blocks:
        return ""

    max_size = max(b[0] for b in blocks)
    top = [b for b in blocks if b[0] >= max_size - 0.5]
    # 若同档位块过多, 说明层级不清, 只保留最靠上的几块
    if len(top) > 3:
        top = sorted(top, key=lambda b: b[1])[:2]
    else:
        top = sorted(top, key=lambda b: b[1])
    title = re.sub(r"\s+", " ", " ".join(b[2] for b in top)).strip()
    return title[:400]


def _extract_year(doc, full: str) -> int | None:
    # 优先首页靠上的年份
    first = doc[0].get_text("text") if doc.page_count else ""
    m = re.search(r"(?:©|\(c\)|Published|发表|received|accepted)[^\n]{0,40}?(19|20)\d{2}", first, re.I)
    if m:
        return parse_year(m.group(0))
    years = re.findall(r"\b(19|20)\d{2}\b", full[:8000])
    if years:
        ys = [int(y + d) for y, d in zip(years, re.findall(r"\b((?:19|20)\d{2})\b", full[:8000]))] \
            if False else [int(x) for x in re.findall(r"\b((?:19|20)\d{2})\b", full[:8000])]
        # 取最常见的
        from collections import Counter
        return Counter(ys).most_common(1)[0][0]
    return None


def _extract_abstract(full: str) -> str | None:
    m = re.search(r"\b(?:Abstract|ABSTRACT|摘\s*要)\b[\s:：\-—]*", full)
    if not m:
        return None
    start = m.end()
    # 摘要结束标志
    end_m = re.search(
        r"\n\s*(?:Keywords?|KEYWORDS?|关键词|1\.?\s+Introduction|Introduction|引言|"
        r"1\s+引言|CCS Concepts|Categories and Subject)\b",
        full[start:start + 6000], re.I)
    seg = full[start:start + (end_m.start() if end_m else 3500)]
    seg = re.sub(r"\s+", " ", seg).strip()
    return seg[:3500] if len(seg) > 40 else None


def _extract_keywords(full: str) -> list[str]:
    m = re.search(r"(?:Keywords?|KEYWORDS?|关键词|关键字)\s*[:：]?\s*(.+)", full)
    if not m:
        return []
    seg = m.group(1)
    seg = re.split(r"\n\s*\n|\b(?:1\.?\s+Introduction|Introduction|引言)\b", seg)[0]
    return parse_keywords(seg[:600])


def _extract_authors(doc, title: str) -> list[str]:
    """启发式: 标题之后、Abstract 之前, 去邮箱/机构/数字上标."""
    if doc.page_count == 0:
        return []
    page = doc[0]
    text = page.get_text("text")
    if title:
        pos = text.find(title[:40])
        if pos >= 0:
            text = text[pos + len(title[:40]):]
    text = text[:1500]
    text = text.split("Abstract")[0].split("ABSTRACT")[0].split("摘要")[0]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    # 剔除与标题高度重合的残留行(标题跨行时常见)
    if title:
        tnorm = re.sub(r"[^a-z0-9]", "", title.lower())
        lines = [l for l in lines
                 if not _title_overlap(l, tnorm)]
    authors: list[str] = []
    for l in lines[:12]:
        if _EMAIL_RE.search(l):
            continue
        if re.search(r"\b(university|institute|college|academy|department|laboratory|school|"
                     r"univ\.|大学|学院|研究所|实验室)\b", l, re.I):
            continue
        if len(l) > 200 or len(l) < 3:
            continue
        # 作者行特征: 含逗号分隔的姓名, 或 "A and B"
        if re.search(r"[A-Z][a-z]+\s+[A-Z]", l) or (" and " in l) or re.search(r"[\u4e00-\u9fff]{2,4}[,，、]", l):
            l = re.sub(r"[\d\*†‡§¶,]+", "", l).strip(" ,;.")
            if l:
                authors.extend(parse_authors(l))
        if len(authors) >= 1 and any(_EMAIL_RE.search(x) for x in lines[:12]):
            break
    # 去重保序
    seen, out = set(), []
    for a in authors:
        if a.lower() not in seen:
            seen.add(a.lower())
            out.append(a)
    return out[:20]


def _title_overlap(line: str, title_norm: str) -> bool:
    """判断一行是否其实是标题的一部分(标题跨行残留)."""
    ln = re.sub(r"[^a-z0-9]", "", line.lower())
    if not ln or len(ln) < 6:
        return False
    # 该行子串几乎完整出现在标题里 => 是标题残留
    return ln in title_norm and len(ln) / max(len(title_norm), 1) > 0.08


def _extract_tables(doc, logger: Logger | None = None) -> list[dict]:
    """抽取表格. 先用 pdfplumber 线框识别; 失败则用坐标聚类兜底."""
    tables: list[dict] = []
    try:
        import pdfplumber
    except Exception:
        if logger:
            logger.log("  ! pdfplumber 不可用, 使用坐标聚类兜底")
        return _extract_tables_by_coords(doc, logger)

    try:
        with pdfplumber.open(doc.name) as pdf:
            for pno, page in enumerate(pdf.pages, start=1):
                try:
                    found = page.extract_tables()
                except Exception:
                    found = []
                ptext = page.extract_text() or ""
                for ti, tbl in enumerate(found):
                    if not tbl or len(tbl) < 2:
                        continue
                    cap = _find_caption(ptext, pno, f"Table {ti+1}")
                    tables.append({
                        "page": pno, "index": ti + 1, "caption": cap,
                        "n_rows": len(tbl),
                        "n_cols": max(len(r) for r in tbl),
                        "rows": [[("" if c is None else str(c).strip()) for c in r] for r in tbl],
                        "method": "pdfplumber",
                    })
    except Exception as e:
        if logger:
            logger.log(f"  ! pdfplumber 表格抽取异常: {e}")

    # 兜底: 若线框识别不到表格, 用坐标聚类
    if not tables:
        coord_tables = _extract_tables_by_coords(doc, logger)
        tables.extend(coord_tables)
    return tables


def _extract_tables_by_coords(doc, logger: Logger | None = None) -> list[dict]:
    """坐标聚类兜底: 按 y 分行、x 归列, 识别数值型规则网格."""
    tables: list[dict] = []
    for pno, page in enumerate(doc, start=1):
        data = page.get_text("dict")
        words: list[tuple[float, float, str]] = []   # (y, x, text)
        for block in data.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    t = span.get("text", "").strip()
                    if t:
                        x0, y0 = span["bbox"][0], span["bbox"][1]
                        words.append((y0, x0, t))
        if len(words) < 8:
            continue
        # 按 y 聚类成行 (容忍 3pt 抖动)
        words.sort(key=lambda w: (w[0], w[1]))
        rows: list[list[tuple[float, str]]] = []
        cur: list[tuple[float, str]] = []
        cur_y = None
        for y, x, t in words:
            if cur_y is None or abs(y - cur_y) <= 3.5:
                cur.append((x, t)); cur_y = y if cur_y is None else cur_y
            else:
                rows.append(cur); cur = [(x, t)]; cur_y = y
        if cur:
            rows.append(cur)

        # 每行按 x 排序拼成单元格
        grid = [[t for _, t in sorted(r, key=lambda c: c[0])] for r in rows]
        grid = [g for g in grid if g]
        if len(grid) < 3:
            continue
        # 找连续 ≥3 行、且至少一列含数值的块
        block_start = None
        for i in range(len(grid) + 1):
            numeric_row = (i < len(grid) and
                           sum(1 for c in grid[i] if _looks_numeric(c)) >= 1 and
                           any(_looks_numeric(c) for c in grid[i]) and
                           3 <= len(grid[i]) <= 12)
            if numeric_row and block_start is None:
                block_start = i
            elif not numeric_row and block_start is not None:
                # 向前包含紧邻的一行作为表头(若其不含数值)
                start = block_start
                if block_start - 1 >= 0:
                    prev = grid[block_start - 1]
                    if sum(1 for c in prev if _looks_numeric(c)) == 0 and 2 <= len(prev) <= 12:
                        start = block_start - 1
                seg = grid[start:i]
                if len(seg) >= 3:
                    cap = _find_caption(page.get_text("text"), pno,
                                        f"Table (p.{pno})")
                    tables.append({
                        "page": pno, "index": len(tables) + 1, "caption": cap,
                        "n_rows": len(seg), "n_cols": max(len(r) for r in seg),
                        "rows": seg, "method": "coord-cluster",
                    })
                block_start = None
    if tables and logger:
        logger.log(f"  · 坐标聚类识别到 {len(tables)} 个候选表格")
    return tables


def _looks_numeric(s: str) -> bool:
    return bool(re.match(r"^[~≈<>≥≤\s]*[-+]?\d+(?:[.,]\d+)?(?:[eE][-+]?\d+)?\s*%?$", str(s).strip()))


def _find_caption(text: str, page: int, fallback: str) -> str:
    m = re.search(r"(Table\s*\d+[^\n]{0,180}|表\s*\d+[^\n]{0,180})", text)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else f"{fallback} (第 {page} 页)"


def _split_sections(full: str) -> dict[str, str]:
    """按章节标题把正文切成若干段."""
    lines = full.split("\n")
    marks: list[tuple[int, str]] = []
    for i, l in enumerate(lines):
        for name, pat in _SECTION_PATTERNS.items():
            if re.match(pat, l.strip(), re.I):
                marks.append((i, name))
                break
    sections: dict[str, str] = {}
    for idx, (i, name) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        seg = "\n".join(lines[i:end]).strip()
        if name not in sections or len(seg) > len(sections[name]):
            sections[name] = seg
    return sections


def load_records(inputs: list[str], logger: Logger) -> tuple[list[PaperRecord], dict]:
    """按扩展名分派到对应解析器, 返回 (records, 统计)."""
    recs: list[PaperRecord] = []
    stats = {"pdf": 0, "bibtex": 0, "csv": 0, "skipped": 0}
    for inp in inputs:
        p = Path(inp)
        if not p.exists():
            logger.log(f"  ! 跳过不存在的输入: {inp}")
            stats["skipped"] += 1
            continue
        ext = p.suffix.lower()
        if ext == ".pdf":
            logger.log(f"  · 解析 PDF: {p.name}")
            recs.append(parse_pdf(p, logger))
            stats["pdf"] += 1
        elif ext in (".bib", ".bibtex"):
            logger.log(f"  · 解析 BibTeX: {p.name}")
            r = parse_bibtex(p)
            recs.extend(r)
            stats["bibtex"] += len(r)
        elif ext in (".csv", ".xlsx", ".xls"):
            logger.log(f"  · 解析表格: {p.name}")
            r = parse_csv(p)
            recs.extend(r)
            stats["csv"] += len(r)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() in (".pdf", ".bib", ".bibtex", ".csv", ".xlsx", ".xls"):
                    sub, _ = load_records([str(f)], logger)
                    recs.extend(sub)
        else:
            logger.log(f"  ! 不支持的输入类型, 跳过: {p.name}")
            stats["skipped"] += 1
    return recs, stats
