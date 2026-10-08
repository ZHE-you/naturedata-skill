# nature-manuscript-assembler

> 把批量文献产出组装成一份 **Nature 投稿级稿件** —— 不是给空骨架，而是把能自动填的素材全部注入，并预判审稿人会挑哪里。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

本 Skill 是 [`paper-batch-pipeline`](../) 的下游：上游把一批 PDF / BibTeX / CSV 清洗成汇总表、图表与中英对照摘要卡，本 Skill 把这些素材**组装**成符合 Nature Article 规范的稿件骨架 + 素材注入 + 合规体检 + 审稿人质疑预判。

## 它比"空骨架"具体在哪

| 部分 | 旧版（空骨架） | **本版（做深）** |
|---|---|---|
| 摘要段 | `[DRAFT - 需作者撰写]` | **机器生成四段式草稿**（背景 / 理由 / Here we show / 推进领域），标注需核改 |
| 正文 | 空占位 | **按主题归类的可引用句**，每句带 `<!-- 来源 P001 -->` 溯源 |
| 声明类 | 空占位 | **可填模板**，预填文献 DOI 列表、图数等已知数据 |
| 数据/代码声明 | 空占位 | 预填"来自引用来源"模板 + 提示替换为仓库 / 登记号 |
| 审稿人质疑 | 无 | **新增 `reviewer_risks.md`**：按 HIGH / MEDIUM / LOW 预判常见质疑 |

## 硬性红线

1. **只重组已有证据，绝不新增事实或数值。** 摘要段与素材句都来自上游摘要卡，保留来源编号。
2. **机器生成内容一律标注** `[机器草稿 - 需作者核改]`，投稿前必须逐句核实。
3. **缺失显式标记。** 字段缺失写 `[MISSING ...]`，待填写 `[待填 - 作者补全]`。
4. **规范数字来自权威源。** 全部取自 `nature-shared/journal-formats/nature.md`，不自创。
5. **只判格式与可得性，不判科学。** 合规报告与质疑清单均声明此边界。

## 快速开始

```bash
PY="C:/Users/29859/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

# 1) 先跑上游（若无产出）
"$PY" ../scripts/run_pipeline.py --input papers/ --out ./batch

# 2) 组装 + 素材注入 + 合规检查
"$PY" scripts/run.py --batch ./batch/<批次名> --out ./manuscript \
  --title "Your Nature title" --authors "A; B; C" --affiliations "Univ X"
```

### 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `--batch` / `-b` | paper-batch-pipeline 的输出目录 | 必填 |
| `--out` / `-o` | 输出目录 | 必填 |
| `--title` | 自定义标题 | 自动生成候选 |
| `--authors` | 作者列表（分号分隔） | `[待填]` |
| `--affiliations` | 单位列表 | `[待填]` |

## 输出

```
manuscript/
├── manuscript_draft.md        # Nature 16 项顺序 + 注入的摘要段 / 素材 / 模板
├── references.md              # Nature 格式参考文献
├── figure_legends.md          # 图注草稿（含来源表 / 图编号，已合并中英双版）
├── reviewer_risks.md          # 审稿人质疑预判清单
├── compliance_report.md       # 合规体检报告（人读）
└── compliance_report.json     # 合规体检报告（机读）
```

## Nature Article 结构（强制遵守的 16 项顺序）

1. Title　2. Authors　3. Affiliations and present addresses
4. Summary paragraph　5. Main text　6. Main references
7. Tables　8. Figure legends　9. Methods（含 Data / Code Availability）
10. Methods references　11. Acknowledgements　12. Funding statement
13. Author contributions　14. Competing-interests declaration
15. Additional information　16. Extended Data figure and table legends

## 关键数字约束

| 项 | 上限 |
|---|---|
| 标题 | ≤ 75 字符 |
| 摘要段 | ≤ 200 词 |
| 图注 | ≤ 250 词 |
| 小标题 | ≤ 40 字符 |
| 正文 | 2500 / 4300 词 |
| Methods | ≤ 3000 词 |
| 参考文献 | ~≤ 50 |
| Extended Data | ≤ 10 项 |

超出即判 **ERROR**（硬约束），合规判定为 `BLOCKED`；结构缺项判 `REVIEW REQUIRED`。

## 合规判定

| 判定 | 含义 |
|---|---|
| `PASS` | 结构完整、字数合规、占位符已清、可得性声明齐备 |
| `REVIEW REQUIRED` | 无硬错误，但有需人工确认项（缺节、少量占位符） |
| `BLOCKED` | 存在硬约束违反（超字数、缺必需声明），不可投稿 |

## 与其它技能的边界

| 阶段 | 用什么 |
|---|---|
| 批量文献 → 结构化素材 | `paper-batch-pipeline` |
| **素材 → 稿件 + 素材注入 + 审查预判** | **本 Skill** |
| 逐节正文起草 | `nature-writing` |
| 语言润色 | `nature-polishing` |
| 投稿级图表 | `nature-figure` |
| 统计报告审查 | `nature-statistics` |

## 引用

规范数字来自 `nature-shared/journal-formats/nature.md`（本 Skill 不自创规范）。

## License

MIT © 夏至子
