"""数据整理: 跨源合并 / 字段补全 / 去重.

策略:
1. 归一化所有字段 (在 common 里完成)。
2. 用 DOI 归一化值 + 标题指纹 做两轮聚类, 同簇视为同一篇论文。
3. 簇内按来源优先级 (csv > bibtex > pdf) 与置信度合并字段:
   - 高优先级来源的非空值优先;
   - 高优先级缺失时, 用低优先级补全 (补全来源与置信度如实记录)。
4. 任何仍缺失的字段统一标记 MISSING。
"""

from __future__ import annotations

from collections import defaultdict

from common import (
    PaperRecord, Field, FIELD_ORDER, CANONICAL_FIELDS,
    normalize_doi, normalize_title, title_fingerprint,
    CONF_HIGH, CONF_MEDIUM, CONF_LOW, Logger, MISSING,
)

# 来源优先级(高 -> 低): 结构化元数据比版式抽取可信
SOURCE_PRIORITY = {"csv": 3, "bibtex": 2, "pdf": 1, "derived": 0, "manual": 4}


def _src_kind(source: str) -> str:
    return source.split(":")[0] if ":" in source else source


def _priority(field: Field) -> int:
    return SOURCE_PRIORITY.get(_src_kind(field.source), 0)


_CONF_RANK = {CONF_HIGH: 3, CONF_MEDIUM: 2, CONF_LOW: 1, "": 0}


def _better(a: Field, b: Field) -> bool:
    """a 是否优于 b."""
    pa, pb = _priority(a), _priority(b)
    if pa != pb:
        return pa > pb
    return _CONF_RANK.get(a.confidence, 0) > _CONF_RANK.get(b.confidence, 0)


def deduplicate(records: list[PaperRecord], logger: Logger,
                fuzzy_threshold: int = 88) -> tuple[list[PaperRecord], list[dict]]:
    """两轮去重, 返回 (去重后记录, 去重报告)."""
    clusters: list[list[PaperRecord]] = []

    # 轮 1: DOI 精确归并
    doi_map: dict[str, list[PaperRecord]] = defaultdict(list)
    no_doi: list[PaperRecord] = []
    for r in records:
        d = normalize_doi(r.get("doi").value or "") if r.get("doi").value else ""
        if d:
            doi_map[d].append(r)
        else:
            no_doi.append(r)
    for d, group in doi_map.items():
        clusters.append(group)

    # 轮 2: 标题指纹精确归并 (仅在 DOI 缺失组内)
    fp_map: dict[str, list[PaperRecord]] = defaultdict(list)
    rest: list[PaperRecord] = []
    for r in no_doi:
        fp = title_fingerprint(r.get("title").value or "")
        if fp:
            fp_map[fp].append(r)
        else:
            rest.append(r)
    for fp, group in fp_map.items():
        clusters.append(group)
    for r in rest:
        clusters.append([r])

    # 轮 3: 标题模糊归并 (跨簇合并)
    merged = _fuzzy_merge_clusters(clusters, fuzzy_threshold, logger)

    out: list[PaperRecord] = []
    report: list[dict] = []
    for i, group in enumerate(merged, start=1):
        rec = merge_group(group, logger)
        rec.record_id = f"P{i:03d}"
        out.append(rec)
        if len(group) > 1:
            report.append({
                "record_id": rec.record_id,
                "title": rec.get("title").display(),
                "merged_from": [{"id": g.record_id, "sources": g.sources} for g in group],
                "reason": "DOI 相同或标题高度相似",
            })
    return out, report


def _fuzzy_merge_clusters(clusters: list[list[PaperRecord]], threshold: int,
                          logger: Logger) -> list[list[PaperRecord]]:
    """对残余簇做标题模糊比对, 合并高相似簇."""
    try:
        from rapidfuzz import fuzz
    except Exception:
        return clusters
    merged: list[list[PaperRecord]] = []
    used = [False] * len(clusters)
    keys = [normalize_title(c[0].get("title").value or "") for c in clusters]
    for i in range(len(clusters)):
        if used[i]:
            continue
        if not keys[i]:
            merged.append(clusters[i]); used[i] = True; continue
        group = list(clusters[i])
        used[i] = True
        for j in range(i + 1, len(clusters)):
            if used[j] or not keys[j]:
                continue
            score = fuzz.token_set_ratio(keys[i], keys[j])
            if score >= threshold:
                group.extend(clusters[j]); used[j] = True
                logger.log(f"  ~ 模糊去重: '{keys[i][:50]}' ≈ '{keys[j][:50]}' (相似度 {score})")
        merged.append(group)
    return merged


def merge_group(group: list[PaperRecord], logger: Logger) -> PaperRecord:
    """把同一篇论文的多条记录合并成一条."""
    out = PaperRecord(record_id=group[0].record_id)
    out.sources = sorted({s for g in group for s in g.sources})
    out.raw_tables = [t for g in group for t in g.raw_tables]

    for key in FIELD_ORDER:
        best: Field | None = None
        for g in group:
            f = g.fields.get(key)
            if f is None or f.is_missing:
                continue
            if best is None or _better(f, best):
                best = f
        if best is not None:
            out.fields[key] = best

    # 合并内部字段(_sections / _extra / _fulltext_chars)
    for g in group:
        for k, f in g.fields.items():
            if k.startswith("_") and not (out.fields.get(k) and not out.fields[k].is_missing):
                out.fields[k] = f

    # 摘要补全: 若 abstract 缺失, 尝试用 _extra 中的 abstract 类字段
    out.finalize_missing()
    return out


def clean_and_merge(records: list[PaperRecord], logger: Logger,
                    fuzzy_threshold: int = 88) -> tuple[list[PaperRecord], list[dict]]:
    """对外主入口: 去重 + 合并 + 缺失标记."""
    logger.log(f"数据整理: 原始记录 {len(records)} 条")
    deduped, report = deduplicate(records, logger, fuzzy_threshold)
    logger.log(f"数据整理: 去重后 {len(deduped)} 篇 (合并 {len(report)} 组重复)")

    for r in deduped:
        missing = [CANONICAL_FIELDS[k]["zh"] for k in FIELD_ORDER if r.get(k).is_missing]
        if missing:
            logger.log(f"  · {r.record_id} 缺失字段: {', '.join(missing)}")
    return deduped, report


# --------------------------------------------------------------------------
# 汇总表导出
# --------------------------------------------------------------------------

def summary_rows(records: list[PaperRecord]) -> tuple[list[str], list[list]]:
    """生成汇总表 (表头 + 行). 每格展示值, 缺失显式标记 MISSING."""
    headers = (["记录编号"] +
               [CANONICAL_FIELDS[k]["zh"] for k in FIELD_ORDER] +
               ["数据来源", "字段来源明细", "数据完整度"])
    rows: list[list] = []
    for r in records:
        row = [r.record_id]
        for k in FIELD_ORDER:
            row.append(r.get(k).display())
        row.append(" + ".join(r.sources))
        detail = []
        for k in FIELD_ORDER:
            f = r.get(k)
            if not f.is_missing:
                detail.append(f"{CANONICAL_FIELDS[k]['zh']}<-{f.source}({f.confidence})")
        row.append("; ".join(detail))
        filled = sum(1 for k in FIELD_ORDER if not r.get(k).is_missing)
        row.append(f"{filled}/{len(FIELD_ORDER)}")
        rows.append(row)
    return headers, rows
