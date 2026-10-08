"""nature-manuscript-assembler 主编排入口.

用法:
    python run.py --batch <paper-batch-pipeline输出目录> --out <输出目录> \
        [--title "..."] [--authors "..."] [--affiliations "..."]

示例:
    python run.py --batch ../../paper_pipeline_demo/output/demo --out ./manuscript
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assemble import assemble
from check_compliance import run_check


def build_parser():
    p = argparse.ArgumentParser(
        prog="nature-manuscript-assembler",
        description="从 paper-batch-pipeline 输出组装 Nature 投稿级稿件骨架并做合规检查")
    p.add_argument("--batch", "-b", required=True,
                   help="paper-batch-pipeline 的输出目录 (含 汇总表_summary.csv 等)")
    p.add_argument("--out", "-o", required=True, help="输出目录")
    p.add_argument("--title", default=None, help="自定义标题 (默认自动生成候选)")
    p.add_argument("--authors", default=None, help="作者列表")
    p.add_argument("--affiliations", default=None, help="单位列表")
    return p


def main():
    args = build_parser().parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("【1/2】组装稿件（注入素材）...")
    res = assemble(args.batch, str(out), args.title, args.authors, args.affiliations)
    print(f"  · 文献 {res['n_papers']} 篇, 图 {res['n_figures']} 张, "
          f"摘要卡 {res['n_cards']} 张")
    print(f"  · 稿件: {res['manuscript']}")
    print(f"  · 审稿人质疑清单: {res['reviewer_risks']}")

    print("【2/2】合规检查 ...")
    result = run_check(
        res["manuscript"], res["references"], res["figure_legends"],
        out_json=out / "compliance_report.json",
        out_md=out / "compliance_report.md",
    )
    c = result["counts"]
    print(f"  · 结论: {result['verdict']} "
          f"(ERROR {c.get('ERROR',0)} / WARN {c.get('WARN',0)} / OK {c.get('OK',0)})")
    print(f"  · 报告: {out / 'compliance_report.md'}")

    print(f"\n输出目录: {out}")
    if result["verdict"] == "BLOCKED":
        sys.exit(1)


if __name__ == "__main__":
    main()
