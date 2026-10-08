# Nature Article 硬性规范速查

> 来源：`nature-shared/journal-formats/nature.md`（flagship Nature Article）。
> **不适用于 Nature 子刊**，各子刊要求可能不同。
> 核对日期：2026-08-08。

## 阶段门槛

| 阶段 | 含义 |
|---|---|
| `initial_submission` | 首次投稿前，Nature 允许合理格式弹性 |
| `revision` | 审稿后，同时遵循处理编辑指示 |
| `accepted_in_principle` | 需生产级正文/图/扩展数据/SI/表格 |
| `proof` | 仅校样更正 |

**不要把"录用后"的生产要求当作首投的硬门槛。**

## 结构顺序（16 项）

1. title
2. authors
3. affiliations and present addresses
4. bold summary paragraph
5. main text
6. main references
7. tables
8. figure legends
9. Methods（含独立的 Data Availability 与 Code Availability）
10. Methods references
11. acknowledgements
12. funding statement
13. author contributions
14. competing-interests declaration
15. additional information（含 SI、通讯作者行）
16. Extended Data figure and table legends

## 字数与长度

| 项 | 限制 |
|---|---|
| 标题 | ≤2 印刷行，≈75 字符（含空格） |
| 摘要段 | ≥参考完整，理想 ≤200 词 |
| 正文（六页 Article） | ≈2500 词 + 4 个适度展示项 |
| 正文（八页 Article） | ≈4300 词 + 5–6 个展示项 |
| 一个适度展示项+图注 | ≈1/4 页 |
| 正文参考文献 | ≈≤50 条 |
| 小标题 | ≤40 字符（含空格） |
| Methods | 通常 ≤3000 词（必要时可更长） |
| 图注 | ≤250 词 |
| Extended Data | ≤10 个多面板图/表 |
| SI 文件数 | 尽量 ≤10 |
| SIGuide 摘要 | ≤50 词（视频/音频标题与图注 ≤100 词） |
| SI 单文件 | ≤30 MB；合计 ≤150 MB |

> 标题、作者列表、致谢、参考文献**不计入**正文词数。

## 标题要求

- 避免数字、缩写、缩写词、标点
- 避免技术术语与主动动词
- 保留索引所需细节，同时让非本领域读者能懂

## 摘要段要求（四段式）

1. 宽领域背景
2. 背景 / 理由
3. 主结论（以 `Here we show` 或等价表述引出）
4. 一般性背景 + 本研究如何推进领域

- 面向非本学科读者
- 非必要不使用数字、缩写、测量值

## 图注要求

- ≤250 词
- 以简短标题句开头
- 描述所绘内容，**不复述结果或方法**
- 尽量使图与图注可独立理解

## Methods

- 包含解读与复现结果所需的一切
- 简短粗体小标题；可设 statistics / reagents / animal-model 子节
- **方法内不放图/表**；必要展示项移 Extended Data 或 SI
- 方法参考文献编号接续正文

## 参考文献

- 按正文首次出现顺序编号（跨正文、表、图注、Methods、Extended Data）
- 正文用上标引用（除非易与其他上标混淆）
- 每个编号只列一篇
- 清除 EndNote 等软件留下的链接域
- 通常只列已发表或已接收工作；在投/在准备的工作写进正文而非文献表
- **须含被引文章与数据集的标题**
- 作者 ≤5 全列；>5 列首位作者 + `et al.`
- 表格配简短标题句，细节入表注

## 声明类

| 项 | 要求 |
|---|---|
| 致谢 | 简短；不谢匿名审稿人与编辑；避免溢美 |
| 资助 | 仅当工作属于且直接源自所列资助时才单独声明 |
| 作者贡献 | 逐作者描述；>3 人同等贡献在此说明 |
| 利益冲突 | 必须包含 |
| 通讯作者 | 用 `*` 标注；列明通信与材料索取 |
| 同等贡献（≤3 人） | 地址列表下方直接标明 |

## 可用性声明

- **Data Availability** 必需
- **Code Availability**：当有核心自定义代码/算法时必需且独立

## 初始投稿文件

- 首选正文与图合并在一个 Word/PDF 文件，≤30 MB
- 每条图注与对应图同页
- 加行号；PDF 每行编号
- 参考文献含被引文章与数据集标题
- TeX/LaTeX 稿件在接收前补 PDF
- 图需有足够分辨率供审稿，但不要求生产级

## 常用检查清单（本 Skill 自动化项）

- [ ] 标题 ≤75 字符
- [ ] 摘要段 ≤200 词且含四段式线索
- [ ] 16 项结构顺序完整
- [ ] Data Availability 存在
- [ ] Code Availability 存在（有核心代码时）
- [ ] 每条图注 ≤250 词
- [ ] 小标题 ≤40 字符
- [ ] 参考文献编号连续且 ≤约50 条
- [ ] References 含被引文章标题
- [ ] 作者 >5 时按 et al. 缩略
