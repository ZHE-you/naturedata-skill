# 输出规范

所有产出位于 `output/<批次名>/` 下。

## 1. 汇总表 `汇总表_summary.csv` / `.md`

CSV 带 UTF-8 BOM（Excel 直接打开不乱码）。列结构：

| 列 | 说明 |
|---|---|
| 内部编号 | `P001`、`P002`…（去重后重新编号） |
| 标题 / 作者 / 年份 / 期刊/会议 / DOI / 关键词 / 被引数 / 摘要 / 链接 | 10 个规范字段，缺失显示 `MISSING` |
| 数据来源 | 该记录由哪些输入合并（如 `bibtex:sample.bib + csv:metadata.csv`） |
| 字段来源明细 | 每个非空字段的 `字段<-来源(置信度)` |
| 数据完整度 | `已填字段数/总字段数`（如 `8/10`） |

## 2. 图表 `figures/`

```
figures/
├── figure_manifest.json        # 所有图的索引：名称/语言/类型/来源/路径
├── zh/                         # 中文版
│   ├── overview_zh.png/.pdf        # 趋势 + 分布（年份分布、被引分布）
│   ├── compare_venues_zh.png/.pdf  # 期刊/会议对比
│   ├── compare_keywords_zh.png/.pdf# 高频关键词对比
│   ├── table_N_<列名>_zh.png/.pdf  # 各表格数值列的趋势/对比图
│   └── data_*.csv                  # 每张图的底层数据
└── en/                         # 英文版，同结构
```

三类图对应关系：

| 类型 | 何时生成 | 涉及函数 |
|---|---|---|
| 趋势 (trend) | 有年份序列 / 时间序列表格列 | `plot_overview`, `plot_table_numeric`(时间型) |
| 对比 (comparison) | 有 venue / keywords / 分类表格列 | `plot_comparison`, `plot_table_numeric`(分类型) |
| 分布 (distribution) | 有被引数等连续数值 | `plot_overview`(直方图) |

**每张图的图注格式**：
```
<图名>
数据来源: <source_ref>
```
`source_ref` 精确到表编号，如 `P001 表1 (第1页)`；英文版本地化为 `P001 Table 1 (p.1)`。

### 图数据文件

| 文件 | 列 |
|---|---|
| `data_overview_{lang}.csv` | 指标, 取值, 论文数 |
| `data_compare_venues_{lang}.csv` | venue, papers |
| `data_compare_keywords_{lang}.csv` | keyword, freq |
| `data_table_metrics_{lang}.csv` | 来源表编号, 表标题, 数据列, 类别, 数值 |

## 3. 摘要卡 `cards/`

```
cards/
├── cards_index.json
└── P001/
    ├── card_zh.md
    └── card_en.md
```

每张卡包含：

| 小节 | 内容 | 缺失时 |
|---|---|---|
| 字段表 | 10 个规范字段 + 数据来源 | 显示 `MISSING` |
| 1. 研究问题 | 抽取的 aim/objective 句 | `[MISSING] 需人工补充` |
| 2. 所用方法 | 抽取的方法句 | 同上 |
| 3. 关键实验与结论 | 抽取的结果/结论句 | 同上 |
| 4. 创新点 | **默认留空**（判断类，脚本不臆断） | `[MISSING]` |
| 5. 局限 | 抽取的 limitation 句 | `[MISSING] 原文未明确陈述` |

> 摘要卡是**证据骨架**。脚本只抽取原文句子并标注来源；创新点等判断内容交给
> Agent 结合 `nature-paper-card` 补全，或人工填写。

## 4. 辅助文件

| 文件 | 内容 |
|---|---|
| `缺失字段总览_missing.md` | 逐篇列出缺失字段 |
| `merge_report.json` | 源统计 + 去重分组（哪些记录被合并、原因）|
| `pipeline_result.json` | 全流程结果索引（供程序化消费）|
| `pipeline.log` | 带时间戳的执行日志 |

## 5. 机读 schema（pipeline_result.json）

```json
{
  "ok": true,
  "batch": "my_review",
  "output_dir": "...",
  "n_raw_records": 7,
  "n_papers": 4,
  "dedup_groups": 3,
  "source_stats": {"pdf": 1, "bibtex": 3, "csv": 4, "skipped": 0},
  "summary_csv": "...", "summary_md": "...",
  "figures": [{"name": "...", "lang": "zh", "type": "comparison", "source_ref": "...", "png": "...", "pdf": "..."}],
  "figures_skipped": [{"figure": "...", "lang": "en", "reason": "..."}],
  "cards": [{"record_id": "P001", "title": "...", "zh": "...", "en": "...", "evidence_counts": {...}}],
  "generated_at": "2026-10-08 11:40:18"
}
```
