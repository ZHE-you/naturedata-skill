# 示例输入

用于快速验证流水线的三路混输样例（同一篇论文故意出现在三个来源里，用来演示去重与跨源补全）。

| 文件 | 内容 | 说明 |
|---|---|---|
| `sample_paper.pdf` | 1 篇带表格的论文 | 演示 PDF 元数据抽取 + 表格坐标聚类抽取 |
| `sample.bib` | 3 条 BibTeX | 演示 BibTeX 解析 |
| `metadata.csv` | 4 行元数据 | 演示 CSV 解析（含缺失字段） |

## 试跑

```bash
python scripts/run_pipeline.py \
  --input examples/sample_paper.pdf examples/sample.bib examples/metadata.csv \
  --out ./output --name demo --langs zh,en
```

预期：7 条原始记录 → 去重后 4 篇，生成 12 张图（中英各 6）、4 组摘要卡。

> 示例数据为演示用途虚构，非真实文献。
