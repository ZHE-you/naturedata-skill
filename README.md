# paper-batch-pipeline

> 批量论文自动化流水线 —— 输入论文 PDF / BibTeX / CSV 元数据，一次整理成汇总表、统计图表与中英对照摘要卡。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/ZHE-you/paper-batch-pipeline/pulls)

不是"读一篇论文"，而是把**一批论文**变成能直接写综述 / 开题的结构化素材。

## 它能做什么

```
输入                          流水线                         输出
─────────────────────────────────────────────────────────────────────────
paper1.pdf  ┐                                              ┌ 汇总表 (CSV/MD)
paper2.pdf  │              ① 数据整理                       ├ 缺失字段总览
refs.bib    ├──────────►   字段清洗统一 · 跨源补全 · 去重   ├ 图表 + 数据文件
meta.csv    │              ② 图表处理                       │  (中英双语)
meta.xlsx   ┘              趋势 / 对比 / 分布 + 来源标注     └ 摘要卡 (中英对照)
                           ③ 核心提炼
                           研究问题/方法/结论/创新点/局限
```

| 模块 | 做什么 | 产出 |
|---|---|---|
| **① 数据整理** | 三路解析 → 字段归一化 → 跨源补全 → 三轮去重 | `汇总表_summary.csv/.md`、`merge_report.json`、`缺失字段总览_missing.md` |
| **② 图表处理** | 从表格与元数据提取指标 → 趋势/对比/分布图（中英双版），每图标注来源表/图编号 | `figures/{zh,en}/*.png/.pdf` + `data_*.csv` |
| **③ 核心提炼** | 每篇生成中英对照摘要卡 | `cards/<ID>/card_zh.md`、`card_en.md` |

## 设计红线

1. **缺失字段显式标记，绝不臆造数值。** 缺失写 `MISSING`，低置信度写 `UNCERTAIN`，不适用写 `N/A`。宁可留空，不可编造。
2. **每个字段带来源与置信度留痕。** 汇总表记录 `字段<-来源(置信度)`，知道每个值从哪来。
3. **每张图必须标注数据来源的表/图编号**（如 `P001 表1 (第1页)`）。无来源的图不出。
4. **表格抽取的数值标注"需人工复核"**，避免把 OCR/版式误差当结论。

## 安装

```bash
git clone https://github.com/ZHE-you/paper-batch-pipeline.git
cd paper-batch-pipeline
pip install -r requirements.txt
```

依赖：`pymupdf` `pdfplumber` `pandas` `matplotlib` `numpy` `bibtexparser` `rapidfuzz` `pyyaml` `python-docx` `openpyxl`

> 中文图表需要系统有中文字体（Windows 自带 `msyh.ttc` / `simhei.ttf`，脚本会自动注册）。

## 快速开始

```bash
# 三路混输（PDF + BibTeX + CSV），输出中英双语
python scripts/run_pipeline.py \
  --input examples/sample_paper.pdf examples/sample.bib examples/metadata.csv \
  --out ./output --name my_review --langs zh,en

# 目录递归扫描
python scripts/run_pipeline.py --input ./papers_dir --out ./output
```

### 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--input/-i` | 输入文件或目录，可多个（`.pdf/.bib/.csv/.xlsx`） | 必填 |
| `--out/-o` | 输出根目录 | 必填 |
| `--name` | 批次名（作为输出子目录名） | 时间戳 |
| `--langs` | 图表语言，逗号分隔 | `zh,en` |
| `--fuzzy` | 标题模糊去重阈值 0–100 | `88` |
| `--no-figures` / `--no-cards` | 跳过对应模块 | 否 |

## 输出结构

```
output/<批次名>/
├── 汇总表_summary.csv / .md      # 主汇总表（含来源明细、完整度）
├── 缺失字段总览_missing.md        # 哪些论文缺哪些字段
├── merge_report.json             # 去重合并报告
├── pipeline_result.json          # 全流程结果索引（机读）
├── pipeline.log
├── figures/
│   ├── figure_manifest.json
│   ├── zh/  overview_*.png/pdf, compare_*.png/pdf, table_*.png/pdf, data_*.csv
│   └── en/  同上（英文标签、英文数据列名）
└── cards/
    ├── cards_index.json
    └── P001/ card_zh.md, card_en.md
```

## 工作原理

- **PDF 表格抽取**：先试 `pdfplumber` 线框识别；失败时用**坐标聚类兜底**（按 y 分行、x 归列，识别数值型规则网格并向前并入表头行）。无框线表格也能抽。
- **去重三轮**：DOI 精确归并 → 标题指纹精确归并 → 标题模糊（rapidfuzz）归并。
- **合并优先级**：`manual > csv > bibtex > pdf`，同优先级比置信度。结构化元数据比版式抽取更可信。
- **双语图表**：中文图用中文字体 + 中文标签，英文图用英文字体 + 英文标签；来源标记按语言本地化，避免混排缺字。
- **中文字体**：直接 `addfont` 注册 `msyh.ttc` 等，不依赖 matplotlib font cache。

## 项目结构

```
paper-batch-pipeline/
├── SKILL.md                 # WorkBuddy / Claude Skill 主入口
├── README.md
├── requirements.txt
├── scripts/
│   ├── common.py            # 字段规范、缺失标记、去重指纹
│   ├── parse_inputs.py      # 三路解析：PDF / BibTeX / CSV
│   ├── merge_clean.py       # 跨源合并、三轮去重、汇总表
│   ├── make_figures.py      # 双语图表 + 来源标注
│   ├── make_cards.py        # 中英对照摘要卡
│   └── run_pipeline.py      # 主编排入口
├── references/
│   ├── field-spec.md        # 字段规范、别名表、缺失标记约定
│   ├── output-spec.md       # 输出 schema 与文件布局
│   └── troubleshooting.md   # 常见问题排查
└── examples/                # 示例输入（PDF + BibTeX + CSV）
```

## 作为 Skill 使用

本仓库同时是一个 [Claude Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) / WorkBuddy Skill。
将整个目录放入 `~/.workbuddy/skills/` 后，可用自然语言直接触发：

> 把 D:\papers 里的论文整理一下，去重、出图表、生成摘要卡

## 路线图

- [ ] OCR 支持（扫描版 PDF）
- [ ] 接入 OpenAlex / Crossref 自动补全 DOI、被引数
- [ ] 摘要卡「创新点」由 LLM 深度提炼（当前默认留空不臆断）
- [ ] 导出 Word / Excel 汇报版

## 许可

[MIT](LICENSE) © 2026 夏至子
