"""图表处理: 从抽取的表格/指标数据生成趋势、对比、分布三类图.

关键约束:
- 每张图必须在图注中标注数据来源的表/图编号 (source_ref)。
- 中英两套同时产出 (zh / en)。
- 无法定位有效数值时, 不做图, 记录 skipped, 绝不臆造数据点。
- 每张图同时导出其底层数据 CSV。
"""

from __future__ import annotations

import re
from pathlib import Path

from common import Logger, ensure_dir, write_csv, write_json, PaperRecord

# --------------------------------------------------------------------------
# matplotlib 中文字体与双主题
# --------------------------------------------------------------------------

_ZH_FONTS = ["Microsoft YaHei", "SimHei", "SimSun", "KaiTi"]
_EN_FONTS = ["Arial", "DejaVu Sans", "Helvetica"]

# 升/降用中国习惯色: 红涨绿跌(用于对比图中正负)
C_RED = "#c0392b"
C_GREEN = "#27893f"
PALETTE = ["#2b6cb0", "#c05621", "#2f855a", "#6b46c1", "#b7791f",
           "#2c7a7b", "#9b2c2c", "#4a5568", "#553c9a", "#276749"]


def _setup_matplotlib(lang: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import os

    # 直接在 Windows 字体目录注册字体文件, 比依赖 font cache 更可靠
    font_dir = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    zh_files = ["msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc", "simkai.ttf"]
    registered = []
    for fn in zh_files:
        fp = os.path.join(font_dir, fn)
        if os.path.exists(fp):
            try:
                font_manager.fontManager.addfont(fp)
                registered.append(font_manager.FontProperties(fname=fp).get_name())
            except Exception:
                pass

    if lang == "zh":
        # 已注册的字体名优先; 不做 ttflist 过滤(addfont 后 ttflist 未必刷新)
        chosen = registered + [f for f in _ZH_FONTS if f not in registered] + ["DejaVu Sans"]
    else:
        chosen = ["Arial", "DejaVu Sans"]

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = chosen
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update({
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linestyle": "--",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "text.color": "#1a202c",
        "axes.labelcolor": "#1a202c",
        "xtick.color": "#1a202c",
        "ytick.color": "#1a202c",
    })


# 图注标签(中英)
L = {
    "zh": {
        "source": "数据来源", "trend": "趋势图", "compare": "对比图", "dist": "分布图",
        "x": "类别", "y": "数值", "count": "频数", "year": "年份", "cited": "被引数",
        "venue": "期刊/会议", "kw": "关键词", "n_missing": "缺失", "papers": "论文数",
    },
    "en": {
        "source": "Source", "trend": "Trend", "compare": "Comparison", "dist": "Distribution",
        "x": "Category", "y": "Value", "count": "Count", "year": "Year", "cited": "Citations",
        "venue": "Venue", "kw": "Keyword", "n_missing": "MISSING", "papers": "Papers",
    },
}


def _caption(lang: str, title: str, source_ref: str, extra: str = "") -> str:
    tag = L[lang]["source"]
    note = f" | {extra}" if extra else ""
    return f"{title}{note}\n{tag}: {source_ref}"


def _localize_ref(ref: str, lang: str) -> str:
    """把内部中文来源标记转成目标语言, 避免 en 图出现中文字导致缺字."""
    if lang == "zh":
        return ref
    return (ref.replace("元数据", "metadata")
               .replace("表", "Table ")
               .replace("第", "p.")
               .replace("页", "")
               .replace("汇总元数据", "aggregate metadata"))


def _save(fig, out_dir: Path, stem: str) -> dict:
    png = out_dir / f"{stem}.png"
    pdf = out_dir / f"{stem}.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"png": str(png), "pdf": str(pdf)}


# --------------------------------------------------------------------------
# 从记录中提取可绘指标
# --------------------------------------------------------------------------

def collect_metrics(records: list[PaperRecord]) -> dict:
    """汇总可作图的数据. 每个数据点都记录其来源(哪篇论文/哪张表)。"""
    m = {
        "year": [],          # (value, source_ref)
        "citations": [],
        "venue": [],
        "keywords": [],
        "table_numeric": [],  # 从 PDF 表格抽取的数值列
    }
    for r in records:
        y = r.get("year")
        if not y.is_missing and isinstance(y.value, int):
            m["year"].append((y.value, f"{r.record_id} 元数据"))
        c = r.get("citations")
        if not c.is_missing and isinstance(c.value, int):
            m["citations"].append((c.value, f"{r.record_id} 元数据"))
        v = r.get("venue")
        if not v.is_missing:
            m["venue"].append((str(v.value), f"{r.record_id} 元数据"))
        for k in (r.get("keywords").value or []):
            m["keywords"].append((str(k), f"{r.record_id} 元数据"))
        for ti, tbl in enumerate(r.raw_tables):
            ref = f"{r.record_id} 表{tbl['index']} (第{tbl['page']}页)"
            for col in _numeric_columns(tbl["rows"]):
                for cat, val in col["data"]:
                    m["table_numeric"].append({
                        "source_ref": ref,
                        "table_caption": tbl["caption"],
                        "series": col["name"],
                        "category": cat,
                        "value": val,
                    })
    return m


def _numeric_columns(rows: list[list[str]]) -> list[dict]:
    """识别表格中的数值列. 自动判断是否存在表头行."""
    if len(rows) < 2:
        return []
    header = rows[0]
    # 判断首行是否为表头: 若首行数值单元格占比很低(<=1/3), 视为表头
    n_cells = max(len(header), 1)
    n_num_first = sum(1 for c in header if _to_number(c) is not None)
    has_header = n_num_first <= max(1, n_cells // 3)
    data_rows = rows[1:] if has_header else rows
    if not data_rows:
        return []
    names = header if has_header else [f"列{ci+1}" for ci in range(len(rows[0]))]

    out = []
    for ci in range(max(len(r) for r in rows)):
        name = (str(names[ci]).strip() if ci < len(names) and str(names[ci]).strip()
                else f"列{ci+1}")
        data = []
        for r in data_rows:
            if ci >= len(r):
                continue
            val = _to_number(r[ci])
            if val is not None:
                cat = r[0].strip() if r and r[0].strip() else f"行{len(data)+1}"
                # 若该类目本身就是数值(无标签列), 用行号区分
                if _to_number(cat) is not None and ci == 0:
                    cat = f"行{len(data)+1}"
                data.append((cat, val))
        if len(data) >= 2:
            out.append({"name": name, "data": data})
    return out


def _to_number(s: str) -> float | None:
    if s is None:
        return None
    t = str(s).strip()
    if not t or t in ("-", "—", "–", "N/A", "NA", "n/a", "—"):
        return None
    t = t.replace(",", "")
    t = re.sub(r"[%％]$", "", t)
    t = re.sub(r"^[~≈<>≥≤\s]+", "", t)
    # 科学计数 / 普通小数
    m = re.match(r"^-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?$", t)
    if m:
        try:
            return float(t)
        except ValueError:
            return None
    return None


# --------------------------------------------------------------------------
# 三类图
# --------------------------------------------------------------------------

def plot_overview(metrics: dict, out_dir: Path, lang: str) -> dict:
    """论文年度分布趋势 + 被引分布 (总览图)."""
    import matplotlib.pyplot as plt
    from collections import Counter

    _setup_matplotlib(lang)
    results = []
    years = [v for v, _ in metrics["year"]]
    cites = [v for v, _ in metrics["citations"]]

    if not years and not cites:
        return {"status": "skipped", "reason": "无年份与被引数据"}

    n_panels = (1 if years else 0) + (1 if cites else 0)
    fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 4.2))
    if n_panels == 1:
        axes = [axes]
    ai = 0

    if years:
        cnt = Counter(years)
        xs = sorted(cnt)
        ys = [cnt[x] for x in xs]
        ax = axes[ai]; ai += 1
        ax.bar([str(x) for x in xs], ys, color=PALETTE[0], width=0.6)
        ax.set_title(f"{L[lang]['trend']} · {L[lang]['year']} - {L[lang]['papers']}")
        ax.set_xlabel(L[lang]["year"]); ax.set_ylabel(L[lang]["papers"])
        for x, y in zip([str(x) for x in xs], ys):
            ax.text(x, y, str(y), ha="center", va="bottom", fontsize=9)

    if cites:
        ax = axes[ai]; ai += 1
        ax.hist(cites, bins=min(10, max(3, len(set(cites)))), color=PALETTE[1],
                edgecolor="white")
        ax.set_title(f"{L[lang]['dist']} · {L[lang]['cited']}")
        ax.set_xlabel(L[lang]["cited"]); ax.set_ylabel(L[lang]["papers"])

    src = (f"汇总元数据 (年份 n={len(years)}, 被引 n={len(cites)})" if lang == "zh"
           else f"aggregate metadata (year n={len(years)}, citations n={len(cites)})")
    fig.suptitle(_caption(lang, "论文总览 Overview" if lang == "zh" else "Paper Overview", src),
                 fontsize=12, y=0.985)
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    paths = _save(fig, out_dir, f"overview_{lang}")
    results.append({"name": "overview", "lang": lang, "type": "trend+distribution", **paths})

    # 导出数据
    write_csv(out_dir / f"data_overview_{lang}.csv",
              ["指标" if lang == "zh" else "metric",
               "取值" if lang == "zh" else "value",
               "论文数" if lang == "zh" else "papers"],
              [["year", x, Counter(years)[x]] for x in sorted(set(years))] +
              [["citation", c, Counter(cites)[c]] for c in sorted(set(cites))])
    return {"status": "ok", "figures": results}


def plot_comparison(metrics: dict, out_dir: Path, lang: str, top_n: int = 12) -> dict:
    """期刊/会议对比 + 高频关键词对比."""
    import matplotlib.pyplot as plt
    from collections import Counter

    _setup_matplotlib(lang)
    results = []

    venues = Counter(v for v, _ in metrics["venue"])
    kws = Counter(k for k, _ in metrics["keywords"])

    if venues:
        top = venues.most_common(top_n)
        labels = [t[0][:32] + ("…" if len(t[0]) > 32 else "") for t in top][::-1]
        vals = [t[1] for t in top][::-1]
        fig, ax = plt.subplots(figsize=(8, max(3, 0.42 * len(labels) + 1.6)))
        ax.barh(labels, vals, color=PALETTE[2])
        ax.set_title(f"{L[lang]['compare']} · {L[lang]['venue']}")
        ax.set_xlabel(L[lang]["papers"])
        for i, v in enumerate(vals):
            ax.text(v, i, f" {v}", va="center", fontsize=9)
        ax.grid(axis="y", visible=False)
        fig.suptitle(_caption(lang,
                              "来源分布 Venue distribution" if lang == "zh" else "Venue distribution",
                              f"{'汇总元数据' if lang == 'zh' else 'aggregate metadata'}: "
                              f"venue, n={sum(venues.values())}"),
                     fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.92])
        results.append({"name": "venues", "lang": lang, "type": "comparison",
                        **_save(fig, out_dir, f"compare_venues_{lang}")})
        write_csv(out_dir / f"data_compare_venues_{lang}.csv",
                  ["venue", "papers"], [[k, v] for k, v in venues.most_common()])

    if kws:
        top = kws.most_common(top_n)
        labels = [t[0][:28] + ("…" if len(t[0]) > 28 else "") for t in top]
        vals = [t[1] for t in top]
        fig, ax = plt.subplots(figsize=(8, 4.6))
        ax.bar(range(len(labels)), vals, color=PALETTE[3], width=0.62)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
        ax.set_title(f"{L[lang]['compare']} · {L[lang]['kw']}")
        ax.set_ylabel(L[lang]["papers"])
        fig.suptitle(_caption(lang,
                              "高频关键词 Top keywords" if lang == "zh" else "Top keywords",
                              f"{'汇总元数据' if lang == 'zh' else 'aggregate metadata'}: "
                              f"keywords, n={sum(kws.values())}"),
                     fontsize=12)
        fig.tight_layout(rect=[0, 0, 1, 0.90])
        results.append({"name": "keywords", "lang": lang, "type": "comparison",
                        **_save(fig, out_dir, f"compare_keywords_{lang}")})
        write_csv(out_dir / f"data_compare_keywords_{lang}.csv",
                  ["keyword", "freq"], [[k, v] for k, v in kws.most_common()])

    if not results:
        return {"status": "skipped", "reason": "无 venue / keywords 数据"}
    return {"status": "ok", "figures": results}


def plot_table_numeric(metrics: dict, out_dir: Path, lang: str, max_figs: int = 8) -> dict:
    """针对从 PDF 表格抽取的数值列, 逐表生成对比/趋势图, 图注标注来源表编号."""
    import matplotlib.pyplot as plt

    _setup_matplotlib(lang)
    items = metrics["table_numeric"]
    if not items:
        return {"status": "skipped", "reason": "未从表格中抽取到可绘数值列"}

    # 按 (来源, 列名) 分组
    groups: dict[tuple, list] = {}
    for it in items:
        key = (it["source_ref"], it["series"])
        groups.setdefault(key, []).append(it)

    results = []
    data_rows = []
    for gi, ((ref, series), pts) in enumerate(list(groups.items())[:max_figs]):
        cats = [p["category"] for p in pts]
        vals = [p["value"] for p in pts]
        if len(vals) < 2:
            continue
        is_time = all(re.match(r"^(19|20)\d{2}$", str(c)) for c in cats)
        fig, ax = plt.subplots(figsize=(max(6, 0.5 * len(cats) + 2.4), 4.4))
        if is_time:
            order = sorted(range(len(cats)), key=lambda i: int(cats[i]))
            cats = [cats[i] for i in order]; vals = [vals[i] for i in order]
            ax.plot(cats, vals, marker="o", color=PALETTE[0], linewidth=2)
            ax.set_title(f"{L[lang]['trend']} · {series}")
        else:
            ax.bar([_short(c) for c in cats], vals, color=PALETTE[4], width=0.6)
            ax.set_title(f"{L[lang]['compare']} · {series}")
            ax.tick_params(axis="x", rotation=30, labelsize=9)
        ax.set_ylabel(series)
        ax.set_xlabel(L[lang]["x"])
        fig.suptitle(_caption(lang,
                              f"{'表格指标' if lang == 'zh' else 'Table metric'} · {series}",
                              _localize_ref(ref, lang),
                              extra="从 PDF 表格抽取, 数值需人工复核" if lang == "zh"
                              else "extracted from PDF table; verify numbers manually"),
                     fontsize=11)
        fig.tight_layout(rect=[0, 0, 1, 0.88])
        stem = f"table_{gi+1}_{_slug(series)}_{lang}"
        results.append({"name": f"table_{gi+1}", "lang": lang,
                        "type": "trend" if is_time else "comparison",
                        "source_ref": ref, **_save(fig, out_dir, stem)})
        for p in pts:
            data_rows.append([ref, p["table_caption"], series, p["category"], p["value"]])

    if not results:
        return {"status": "skipped", "reason": "表格数值列不足 2 个数据点"}
    write_csv(out_dir / f"data_table_metrics_{lang}.csv",
              (["来源表编号", "表标题", "数据列", "类别", "数值"] if lang == "zh"
               else ["source_ref", "table_caption", "series", "category", "value"]),
              data_rows)
    return {"status": "ok", "figures": results}


def _slug(s: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "_", str(s)).strip("_")
    return s[:24] or "series"


def _short(s: str, n: int = 26) -> str:
    """类别标签截断: 超长才截, 并加省略号."""
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def make_figures(records: list[PaperRecord], out_root: str | Path,
                 logger: Logger, langs=("zh", "en")) -> dict:
    out_root = ensure_dir(out_root)
    metrics = collect_metrics(records)
    manifest = {"generated_at": None, "figures": [], "skipped": [], "metrics_count": {
        "year": len(metrics["year"]), "citations": len(metrics["citations"]),
        "venue": len(metrics["venue"]), "keywords": len(metrics["keywords"]),
        "table_numeric": len(metrics["table_numeric"]),
    }}
    for lang in langs:
        d = ensure_dir(out_root / lang)
        for fn in (plot_overview, plot_comparison, plot_table_numeric):
            try:
                res = fn(metrics, d, lang)
            except Exception as e:
                logger.log(f"  ! 绘图 {fn.__name__}[{lang}] 失败: {e}")
                manifest["skipped"].append({"figure": fn.__name__, "lang": lang, "reason": str(e)})
                continue
            if res.get("status") == "ok":
                manifest["figures"].extend(res["figures"])
            else:
                manifest["skipped"].append({"figure": fn.__name__, "lang": lang,
                                            "reason": res.get("reason")})
    from common import timestamp
    manifest["generated_at"] = timestamp()
    write_json(out_root / "figure_manifest.json", manifest)
    logger.log(f"图表处理: 生成 {len(manifest['figures'])} 张图, 跳过 {len(manifest['skipped'])} 项")
    return manifest
