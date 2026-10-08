"""paper-batch-pipeline 主编排入口.

用法:
    python run_pipeline.py --input <pdf/bib/csv ...> --out <输出目录> \
        [--config config.yaml] [--langs zh,en] [--fuzzy 88] [--name 批次名]

示例:
    python run_pipeline.py --input ./papers --out ./output --langs zh,en
    python run_pipeline.py --input a.pdf b.bib c.csv --out ./output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (Logger, ensure_dir, write_csv, write_json, write_text,
                    timestamp, CANONICAL_FIELDS, FIELD_ORDER)
from parse_inputs import load_records
from merge_clean import clean_and_merge, summary_rows
from make_figures import make_figures
from make_cards import make_cards


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="paper-batch-pipeline",
        description="批量论文处理: 数据整理 + 图表处理 + 核心提炼 (中英双语)")
    p.add_argument("--input", "-i", nargs="+", required=True,
                   help="输入文件或目录 (支持 .pdf/.bib/.csv/.xlsx, 可多个)")
    p.add_argument("--out", "-o", required=True, help="输出根目录")
    p.add_argument("--name", default=None, help="批次名称 (默认用时间戳)")
    p.add_argument("--langs", default="zh,en", help="图表语言, 逗号分隔 (默认 zh,en)")
    p.add_argument("--fuzzy", type=int, default=88, help="标题模糊去重阈值 0-100")
    p.add_argument("--no-figures", action="store_true", help="跳过图表处理")
    p.add_argument("--no-cards", action="store_true", help="跳过摘要卡")
    return p


def run(args) -> dict:
    batch = args.name or f"batch_{timestamp().replace(':', '').replace(' ', '_').replace('-', '')}"
    out_root = ensure_dir(Path(args.out) / batch)
    logger = Logger(logfile=out_root / "pipeline.log")
    logger.log(f"=== paper-batch-pipeline 启动 ===  批次: {batch}")
    logger.log(f"输入: {args.input}")
    logger.log(f"输出: {out_root}")

    # ---- 1. 解析 ----
    logger.log("【1/3 数据整理】解析输入 ...")
    records, stats = load_records(list(args.input), logger)
    if not records:
        logger.log("! 未解析到任何记录, 流程终止")
        logger.flush()
        return {"ok": False, "reason": "no records"}
    logger.log(f"解析统计: PDF={stats['pdf']}  BibTeX={stats['bibtex']}  "
               f"CSV={stats['csv']}  跳过={stats['skipped']}")

    # ---- 2. 清洗合并去重 ----
    clean, dup_report = clean_and_merge(records, logger, fuzzy_threshold=args.fuzzy)

    # 汇总表 (CSV + 中文 Markdown)
    headers, rows = summary_rows(clean)
    write_csv(out_root / "汇总表_summary.csv", headers, rows)
    write_text(out_root / "汇总表_summary.md", _md_table(headers, rows))
    write_json(out_root / "merge_report.json",
               {"source_stats": stats, "dedup_groups": dup_report,
                "n_raw": len(records), "n_clean": len(clean)})

    # ---- 3. 图表 ----
    fig_manifest = {"figures": [], "skipped": []}
    if not args.no_figures:
        logger.log("【2/3 图表处理】生成趋势/对比/分布图 ...")
        langs = tuple(x.strip() for x in args.langs.split(",") if x.strip())
        fig_manifest = make_figures(clean, out_root / "figures", logger, langs=langs)
    else:
        logger.log("【2/3 图表处理】已跳过 (--no-figures)")

    # ---- 4. 摘要卡 ----
    cards_index = {"cards": []}
    if not args.no_cards:
        logger.log("【3/3 核心提炼】生成中英摘要卡 ...")
        cards_index = make_cards(clean, out_root / "cards", logger)
    else:
        logger.log("【3/3 核心提炼】已跳过 (--no-cards)")

    # ---- 结果清单 ----
    result = {
        "ok": True,
        "batch": batch,
        "output_dir": str(out_root),
        "n_raw_records": len(records),
        "n_papers": len(clean),
        "dedup_groups": len(dup_report),
        "source_stats": stats,
        "summary_csv": str(out_root / "汇总表_summary.csv"),
        "summary_md": str(out_root / "汇总表_summary.md"),
        "figures": fig_manifest.get("figures", []),
        "figures_skipped": fig_manifest.get("skipped", []),
        "cards": cards_index.get("cards", []),
        "generated_at": timestamp(),
    }
    write_json(out_root / "pipeline_result.json", result)

    # 缺失字段总览
    missing_lines = ["# 缺失字段总览 (缺什么列什么, 不臆造)\n"]
    for r in clean:
        miss = [CANONICAL_FIELDS[k]["zh"] for k in FIELD_ORDER if r.get(k).is_missing]
        missing_lines.append(f"- **{r.record_id}** {r.get('title').display()[:60]} → "
                             f"{', '.join(miss) if miss else '无缺失'}")
    write_text(out_root / "缺失字段总览_missing.md", "\n".join(missing_lines))

    logger.log("=== 完成 ===")
    logger.log(f"论文 {len(clean)} 篇 | 图 {len(result['figures'])} 张 | "
               f"摘要卡 {len(result['cards'])} 组")
    logger.flush()
    return result


def _md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(str(h) for h in headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c).replace("|", "\\|") for c in r) + " |")
    return "\n".join(out)


def main():
    args = build_parser().parse_args()
    res = run(args)
    if not res.get("ok"):
        sys.exit(1)
    print(f"\n输出目录: {res['output_dir']}")


if __name__ == "__main__":
    main()
