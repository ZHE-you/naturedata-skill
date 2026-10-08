---
name: paper-batch-pipeline
description: >-
  批量论文自动化流水线：输入论文 PDF / BibTeX / CSV 元数据，自动完成
  ①数据整理(字段清洗统一、跨源补全、DOI与标题去重)、
  ②图表处理(从表格与数据提取指标，生成趋势/对比/分布图，每图标注来源表/图编号)、
  ③核心提炼(每篇生成中英对照摘要卡：研究问题/方法/关键实验与结论/创新点/局限)。
  输出汇总表 + 每图数据文件 + 每篇摘要卡。触发词：论文批量整理、文献元数据清洗、
  论文去重、批量摘要卡、论文图表提取、literature batch pipeline、paper dedup、
  BibTeX 整理、综述素材整理、开题文献库。不用于：单篇深度精读(用 nature-paper-card)、
  全文中英对照翻译(用 nature-reader)、投稿配图(用 nature-figure)。
license: MIT
metadata:
  author: 夏至子
  tags: [research, literature, batch, metadata, figures, summary-card, automation]
  related_skills: [nature-paper-card, nature-figure, nature-reader, nature-academic-search]
---

# Paper Batch Pipeline

把一堆论文（PDF / BibTeX / CSV 混搭）一次性整理成**可用的结构化结果**：一张汇总表、
一组带来源标注的统计图、一批中英对照摘要卡。

## 这个 Skill 解决什么

不是"读一篇论文"，而是"把一批论文变成能直接写综述/开题的结构化素材"。三件事：

| 模块 | 做什么 | 产出 |
|---|---|---|
| ① 数据整理 | 三路解析 → 字段归一化 → 跨源补全 → 去重 | `汇总表_summary.csv/.md`、`merge_report.json`、`缺失字段总览_missing.md` |
| ② 图表处理 | 抽取指标 → 趋势/对比/分布图（中英双版） | `figures/{zh,en}/*.png/.pdf` + 每图 `data_*.csv` + `figure_manifest.json` |
| ③ 核心提炼 | 每篇生成中英对照摘要卡 | `cards/<ID>/card_zh.md`、`card_en.md`、`cards_index.json` |

## 硬性红线（不可违背）

1. **缺失字段显式标记，绝不臆造数值。** 缺失写 `MISSING`，低置信度写 `UNCERTAIN`，
   不可评估写 `N/A`。宁可留空，不可编造。
2. **每个字段带来源与置信度留痕。** 汇总表的「字段来源明细」列记录 `字段<-来源(置信度)`。
3. **每张图必须标注数据来源的表/图编号**（如 `P001 表1 (第1页)`）。无来源的图不出。
4. **表格抽取的数值需人工复核**：图注中自动标注此提示。

## 快速开始

```bash
# 统一用受管 Python 环境
PY="C:/Users/29859/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 三路混输（PDF + BibTeX + CSV），输出中英双语
"$PY" scripts/run_pipeline.py \
  --input paper1.pdf paper2.pdf refs.bib metadata.csv \
  --out ./output --name my_review --langs zh,en

# 目录递归扫描
"$PY" scripts/run_pipeline.py --input ./papers_dir --out ./output
```

### 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--input/-i` | 输入文件或目录，可多个（`.pdf/.bib/.csv/.xlsx`） | 必填 |
| `--out/-o` | 输出根目录 | 必填 |
| `--name` | 批次名（作为输出子目录） | 时间戳 |
| `--langs` | 图表语言，逗号分隔 | `zh,en` |
| `--fuzzy` | 标题模糊去重阈值 0–100 | `88` |
| `--no-figures` / `--no-cards` | 跳过对应模块 | 否 |

## 输出结构

```
output/<批次名>/
├── 汇总表_summary.csv / .md      # 主汇总表（含来源明细、完整度）
├── 缺失字段总览_missing.md        # 哪些论文缺哪些字段
├── merge_report.json             # 去重合并报告
├── pipeline_result.json          # 全流程结果索引
├── pipeline.log
├── figures/
│   ├── figure_manifest.json
│   ├── zh/  overview_*.png/pdf, compare_*.png/pdf, table_*.png/pdf, data_*.csv
│   └── en/  同上（英文标签、英文数据列名）
└── cards/
    ├── cards_index.json
    └── P001/ card_zh.md, card_en.md
```

## 工作流（Agent 编排要点）

本 Skill 的脚本负责**确定性部分**（解析/清洗/去重/画图/生成卡骨架）。
Agent 负责**语义增强部分**：

1. 先跑 `run_pipeline.py` 得到结构化底座。
2. 若需**深度摘要卡**（创新点/局限需要真读论文），对重点论文调用
   `nature-paper-card` skill 补全 Section「创新点」「局限」，回填到 `card_zh/en.md`。
   本 Skill 的卡是**证据骨架**，创新点默认标 `MISSING`——因为"创新点"是判断而非抽取，
   脚本不做臆断，交给 Agent 或人工。
3. 若需**投稿级配图**，把 `figures/*/data_*.csv` 交给 `nature-figure` 重绘。
4. 若需**全文精读/翻译**，交给 `nature-reader`。

## 关键实现说明

- **PDF 表格抽取**：先试 pdfplumber 线框识别；失败时用**坐标聚类兜底**
  （按 y 分行、x 归列，识别数值型规则网格并向前并入表头行）。见 `parse_inputs.py`。
- **中文字体**：直接 `addfont` 注册 `msyh.ttc` 等，避免 matplotlib font cache 回落到 Arial 缺字。
- **双语图表**：中文图用中文字体+中文标签，英文图用英文字体+英文标签；**来源标记会按语言本地化**，
  避免英文图出现中文字导致缺字。
- **去重**：三轮——DOI 精确归并 → 标题指纹精确归并 → 标题模糊（rapidfuzz）归并。
  合并时按来源优先级 `manual > csv > bibtex > pdf` 取字段值。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/field-spec.md` | 规范字段集、别名表、缺失标记约定、来源优先级 |
| `references/output-spec.md` | 各类输出的精确 schema 与文件布局 |
| `references/troubleshooting.md` | 常见问题：表格抽不到、字体缺字、去重误判、扫描版 PDF |

## 依赖

见 `requirements.txt`：pymupdf, pdfplumber, pandas, matplotlib, numpy,
bibtexparser, rapidfuzz, pyyaml, python-docx, openpyxl。
