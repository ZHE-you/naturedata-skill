---
name: nature-manuscript-assembler
description: >-
  把 paper-batch-pipeline 的批量文献产出（汇总表 / 摘要卡 / 图表）组装成
  **Nature 投稿级稿件**：按 Nature Article 的 16 项固定顺序搭结构，并**注入真实可用素材**——
  从摘要卡自动生成四段式摘要段草稿、按主题归类的可引用结论句、可填的声明模板，
  同时输出**审稿人质疑预判清单**，并对标题 75 字符 / 摘要段 200 词 / 图注 250 词 /
  小标题 40 字符 / 结构完整性做逐项合规体检。
  触发词：Nature 稿件组装、投稿骨架、manuscript assembly、Nature 格式检查、
  审稿人质疑预判、投稿包整理、把文献整理成稿件。不用于：单节正文起草(用 nature-writing)、
  语言润色(用 nature-polishing)、投稿级配图(用 nature-figure)、
  统计报告审查(用 nature-statistics)。
license: MIT
metadata:
  author: 夏至子
  tags: [nature, manuscript, submission, assembly, compliance, reviewer-risk]
  upstream: paper-batch-pipeline
  related_skills: [paper-batch-pipeline, nature-writing, nature-figure,
                  nature-statistics, nature-data, nature-citation, nature-shared]
---

# Nature Manuscript Assembler

把整理好的文献产出，**组装成一份可直接开工的 Nature 稿件**——不只给空骨架，
而是把能自动填的素材都填进去，并告诉你哪里会被审稿人挑。

## 定位（与已有技能的分工）

你本地已有 19 个 nature-* 技能，各管一段。本 Skill 补的是**从素材到稿件的那一步**：

```
paper-batch-pipeline ──► nature-manuscript-assembler ──► nature-writing / nature-figure ...
  (清洗/图表/摘要卡)        (组装 + 素材注入 + 合规体检)    (逐节起草 / 配图 / 润色)
```

| 阶段 | 用什么 |
|---|---|
| 批量文献 → 结构化素材 | `paper-batch-pipeline` |
| **素材 → 稿件 + 素材注入 + 审查预判** | **本 Skill** |
| 逐节正文起草 | `nature-writing` |
| 语言润色 | `nature-polishing` |
| 投稿级图表 | `nature-figure` |
| 统计报告审查 | `nature-statistics` |
| 数据/代码可用性 | `nature-data` |

## 它比"空骨架"具体在哪

| 部分 | 旧版（空骨架） | **本版（做深）** |
|---|---|---|
| 摘要段 | `[DRAFT - 需作者撰写]` | **机器生成四段式草稿**（含背景/理由/Here we show/推进领域），标注需核改 |
| 正文 | 空占位 | **按主题归类的可引用句**，每句带 `<!-- 来源 P001 -->` 溯源 |
| 声明类 | 空占位 | **可填模板**，预填文献 DOI 列表、图数等已知数据 |
| 数据/代码声明 | 空占位 | 预填"来自引用来源"模板 + 提示替换为仓库/登记号 |
| 审稿人质疑 | 无 | **新增 `reviewer_risks.md`**：按 HIGH/MEDIUM/LOW 预判常见质疑 |

## 硬性红线

1. **只重组已有证据，绝不新增事实或数值。** 摘要段与素材句都来自上游摘要卡，保留来源编号。
2. **机器生成内容一律标注** `[机器草稿 - 需作者核改]`，投稿前必须逐句核实。
3. **缺失显式标记。** 字段缺失写 `[MISSING ...]`，待填写 `[待填 - 作者补全]`。
4. **规范数字来自权威源。** 全部取自 `nature-shared/journal-formats/nature.md`，不自创。
5. **只判格式与可得性，不判科学。** 合规报告与质疑清单均声明此边界。

## 快速开始

```bash
PY="C:/Users/29859/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 先跑上游（若无产出）
"$PY" ../../paper-batch-pipeline/scripts/run_pipeline.py --input papers/ --out ./batch

# 组装 + 素材注入 + 合规检查
"$PY" scripts/run.py --batch ./batch/<批次名> --out ./manuscript \
  --title "Your Nature title" --authors "A; B; C" --affiliations "Univ X"
```

### 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--batch/-b` | paper-batch-pipeline 的输出目录 | 必填 |
| `--out/-o` | 输出目录 | 必填 |
| `--title` | 自定义标题 | 自动生成候选 |
| `--authors` | 作者列表（分号分隔） | `[待填]` |
| `--affiliations` | 单位列表 | `[待填]` |

## 输出

```
manuscript/
├── manuscript_draft.md        # Nature 16 项顺序 + 注入的摘要段/素材/模板
├── references.md              # Nature 格式参考文献
├── figure_legends.md          # 图注草稿（含来源表/图编号，已合并中英双版）
├── reviewer_risks.md          # 审稿人质疑预判清单（新增）
├── compliance_report.md       # 合规体检报告（人读）
└── compliance_report.json     # 合规体检报告（机读）
```

## Nature Article 结构（本 Skill 强制遵守的 16 项顺序）

1. Title（标题）
2. Authors（作者）
3. Affiliations and present addresses（单位与现址）
4. Summary paragraph（摘要段）
5. Main text（正文）
6. Main references（正文参考文献）
7. Tables（表格）
8. Figure legends（图注）
9. Methods（方法，含 Data/Code Availability）
10. Methods references（方法参考文献）
11. Acknowledgements（致谢）
12. Funding statement（资助声明）
13. Author contributions（作者贡献）
14. Competing-interests declaration（利益冲突声明）
15. Additional information（附加信息）
16. Extended Data figure and table legends（扩展数据图注）

## 关键数字约束

| 项 | 限制 | 严重度 |
|---|---|---|
| 标题 | ≤75 字符，约两行 | ERROR |
| 摘要段 | ≤200 词，四段式 | ERROR |
| 图注 | ≤250 词 | ERROR |
| 小标题 | ≤40 字符 | WARN |
| 正文 | 六页≈2500 词 / 八页≈4300 词 | INFO |
| Methods | 通常 ≤3000 词 | INFO |
| 正文参考文献 | 约 ≤50 条 | WARN |
| Extended Data | ≤10 项 | — |
| Supplementary Information | ≤10 文件，SIGuide 摘要 ≤50 词 | — |

## 合规检查的严重度

| 级别 | 含义 | 对最终结论的影响 |
|---|---|---|
| `ERROR` | 硬性约束违反，必须修 | 结论 `BLOCKED`，退出码 1 |
| `WARN` | 建议修 | 结论 `REVIEW REQUIRED` |
| `OK` | 通过 | — |
| `INFO` | 提示（如占位符待撰） | 不影响结论 |

## 工作流（Agent 编排要点）

1. 确认上游 `paper-batch-pipeline` 已完成（有 `汇总表_summary.csv` / `figure_manifest.json` / `cards/`）。
2. 跑 `run.py` 得到稿件 + 合规报告 + 审稿人质疑清单。
3. **先读 `reviewer_risks.md`**：HIGH 级项（如"多数文献无全文"）往往决定稿件能否成立，
   优先解决。
4. 按 `compliance_report.md` 的 `ERROR` 逐项修（标题超限、摘要超词、缺可用性声明）。
5. 摘要段草稿交 `nature-writing` 按四段式改写定稿；素材句按主题扩写为 Results。
6. 图注定稿后交 `nature-figure` 核对图与图注一致性。
7. 数据/代码声明交 `nature-data` 精修；统计小节交 `nature-statistics`。

## 参考文档

| 文件 | 内容 |
|---|---|
| `references/nature-article-spec.md` | Nature Article 全部硬性规范（摘自 nature-shared）|
| `references/checklist.md` | 投稿前逐项自检清单 |

## 依赖

仅需标准库 + 上游产物。无第三方依赖。
