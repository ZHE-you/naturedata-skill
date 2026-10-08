"""Nature 稿件规范常量与校验工具.

规范来源: nature-shared/journal-formats/nature.md (flagship Nature Article).
本模块只承载数字与结构约束, 供 assembler 与 checker 共用。
"""

from __future__ import annotations

import re

# --------------------------------------------------------------------------
# 硬性约束 (来自 nature.md, 不要臆改)
# --------------------------------------------------------------------------

SPEC = {
    "title_max_chars": 75,          # 含空格, 约两行
    "title_max_lines": 2,
    "summary_max_words": 200,       # 建议值
    "figure_legend_max_words": 250,
    "article_6p_words": 2500,       # 六页典型
    "article_8p_words": 4300,       # 八页典型
    "methods_max_words": 3000,      # 通常不超过
    "subheading_max_chars": 40,
    "main_references_max": 50,      # 约
    "extended_data_max_items": 10,
    "si_max_files": 10,
    "si_summary_max_words": 50,
}

# Nature Article 要求的 16 项顺序 (严格)
MANUSCRIPT_SECTIONS = [
    ("title", "Title", "标题"),
    ("authors", "Authors", "作者"),
    ("affiliations", "Affiliations and present addresses", "单位与现址"),
    ("summary", "Summary paragraph", "摘要段"),
    ("main_text", "Main text", "正文"),
    ("main_references", "Main references", "正文参考文献"),
    ("tables", "Tables", "表格"),
    ("figure_legends", "Figure legends", "图注"),
    ("methods", "Methods", "方法"),
    ("methods_references", "Methods references", "方法参考文献"),
    ("acknowledgements", "Acknowledgements", "致谢"),
    ("funding", "Funding statement", "资助声明"),
    ("author_contributions", "Author contributions", "作者贡献"),
    ("competing_interests", "Competing-interests declaration", "利益冲突声明"),
    ("additional_info", "Additional information", "附加信息"),
    ("extended_data", "Extended Data figure and table legends", "扩展数据图注"),
]

# 方法部分内必须包含的可用性声明
REQUIRED_AVAILABILITY = [
    ("data_availability", "Data Availability", "数据可用性声明"),
    ("code_availability", "Code Availability", "代码可用性声明"),
]

# 正文常用小标题 (Nature 允许, 每项 <=40 字符)
DEFAULT_SUBHEADINGS = [
    "Results",
    "Discussion",
    "Conclusion",
]

# --------------------------------------------------------------------------
# 文本度量
# --------------------------------------------------------------------------

_WORD_RE = re.compile(r"[\w\u4e00-\u9fff]+(?:['’\-][\w\u4e00-\u9fff]+)*")


def count_words(text: str) -> int:
    """英文计词: 按空白与标点切分, 中文按字计. 用于 Summary / 图注校验."""
    if not text:
        return 0
    # 先抽出 CJK 字符单独计数, 其余按 token
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    non_cjk = re.sub(r"[\u4e00-\u9fff]", " ", text)
    return len(cjk) + len(_WORD_RE.findall(non_cjk))


def count_chars(text: str) -> int:
    return len(text or "")


def title_ok(title: str) -> tuple[bool, str]:
    n = count_chars(title)
    if n == 0:
        return False, "标题为空"
    if n > SPEC["title_max_chars"]:
        return False, f"标题 {n} 字符, 超过 {SPEC['title_max_chars']} 上限"
    return True, f"标题 {n} 字符, 合规"


def summary_ok(text: str) -> tuple[bool, str]:
    n = count_words(text)
    if n == 0:
        return False, "摘要段为空"
    if n > SPEC["summary_max_words"]:
        return False, f"摘要段 {n} 词, 建议不超过 {SPEC['summary_max_words']}"
    return True, f"摘要段 {n} 词, 合规"


def legend_ok(text: str) -> tuple[bool, str]:
    n = count_words(text)
    if n > SPEC["figure_legend_max_words"]:
        return False, f"图注 {n} 词, 超过 {SPEC['figure_legend_max_words']} 上限"
    return True, f"图注 {n} 词"


def subheading_ok(text: str) -> tuple[bool, str]:
    n = count_chars(text)
    if n > SPEC["subheading_max_chars"]:
        return False, f"小标题 {n} 字符, 超过 {SPEC['subheading_max_chars']} 上限"
    return True, f"小标题 {n} 字符"


# --------------------------------------------------------------------------
# 摘要段 (Summary paragraph) 结构检查
# --------------------------------------------------------------------------

SUMMARY_FLOW = [
    ("broad field", r"\b(recently|in recent years|the field|research on|understanding of)\b", "领域背景"),
    ("rationale", r"\b(however|despite|yet|although|but)\b", "问题/理由"),
    ("main conclusion", r"\b(here we show|here we demonstrate|we show|we report)\b", "主结论(Here we show)"),
]


def summary_flow_check(text: str) -> list[tuple[str, bool, str]]:
    """检查摘要段是否含 Nature 要求的四段式线索."""
    out = []
    for name, pat, zh in SUMMARY_FLOW:
        out.append((zh, bool(re.search(pat, text or "", re.I)), name))
    return out
