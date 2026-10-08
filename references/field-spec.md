# 规范字段集与标注约定

## 一、规范字段（canonical fields）

所有输入（PDF / BibTeX / CSV）解析后统一映射到以下 10 个字段：

| key | 中文名 | 类型 | 说明 |
|---|---|---|---|
| `title` | 标题 | str | 论文标题 |
| `authors` | 作者 | list | 作者列表，标准化为 `["姓 名", ...]` |
| `year` | 年份 | int | 发表年份，1800–2100 之外视为无效 |
| `venue` | 期刊/会议 | str | 期刊名或会议名 |
| `doi` | DOI | str | 归一化（去 `https://doi.org/` 前缀、转小写） |
| `keywords` | 关键词 | list | 关键词列表 |
| `citations` | 被引数 | int | 引用次数 |
| `abstract` | 摘要 | str | 摘要全文 |
| `url` | 链接 | str | 原文链接 |
| `paper_id` | 内部编号 | str | 输入自带的编号 |

## 二、别名映射

解析器按别名把原始列名/字段名映射到规范字段（大小写、空格、下划线不敏感）：

| 规范字段 | 可识别的别名 |
|---|---|
| title | title, 标题, 题目, 论文标题 |
| authors | authors, author, 作者, 作者列表 |
| year | year, 年份, 发表年份, date, pub_year |
| venue | venue, journal, conference, 期刊, 会议, 来源, 期刊/会议, publication |
| doi | doi, DOI |
| keywords | keywords, keyword, 关键词, 关键字 |
| citations | citations, citation_count, cited_by, 被引数, 被引, 引用数 |
| abstract | abstract, 摘要 |
| url | url, link, 链接, 地址 |
| paper_id | paper_id, id, 编号 |

CSV 表头采用**包含式匹配**：如 `被引数(次)` 也能识别为 `citations`。

## 三、缺失 / 不确定标记

| 标记 | 含义 | 使用场景 |
|---|---|---|
| `MISSING` | 所有输入中均无此字段 | 字段完全缺失 |
| `UNCERTAIN` | 出现但置信度低 | 模糊匹配、可疑解析 |
| `N/A` | 不适用 | 该论文类型不含此字段 |

**绝不臆造**：宁可标 `MISSING`，也不填猜测值。

## 四、来源与置信度

每个字段值携带两个元数据：

- **source**：来自哪一路输入
  - `pdf:文件名` — PDF 版式抽取
  - `bibtex:文件名` — BibTeX 解析
  - `csv:文件名` — 表格读取
  - `derived` — 派生计算
  - `manual` — 人工填写的覆盖文件

- **confidence**：
  - `high` — 结构化字段直接读取（如 BibTeX 的 doi、CSV 的标题）
  - `medium` — 正则/版式推断（如 PDF 的年份、关键词）
  - `low` — 启发式猜测（如从 PDF 版式推作者、从 note 字段猜被引数）

## 五、合并优先级

同一篇论文由多路输入合并时，字段取值优先级：

```
manual(4) > csv(3) > bibtex(2) > pdf(1) > derived(0)
```

同优先级时比较置信度（high > medium > low）。

**理由**：结构化元数据（CSV/BibTeX）比 PDF 版式抽取更可信；人工覆盖最高。

## 六、去重规则

三轮归并，同一簇视为同一篇论文：

1. **DOI 精确**：归一化 DOI 相同。
2. **标题指纹**：`normalize_title` 后的 SHA1 前 12 位相同。
3. **标题模糊**：rapidfuzz `token_set_ratio ≥ --fuzzy`（默认 88）。

`normalize_title`：Unicode NFKD 规范化 → 转小写 → 去 HTML 标签 →
只保留字母数字汉字 → 压缩空白。这样能容忍大小写、标点、全半角差异。
