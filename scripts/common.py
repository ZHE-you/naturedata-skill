"""paper-batch-pipeline 共享基础模块.

职责:
- 定义规范字段集 (canonical fields) 与缺失/不确定标记常量
- 提供 field(value, source, confidence) 包装, 统一来源与置信度留痕
- 提供论文记录 (PaperRecord) 数据结构
- 提供路径/IO/日志等工具函数

设计红线:
- 任何缺失字段必须显式标记, 绝不臆造数值。
- 每个字段值携带 provenance (来自哪一路输入: pdf / bibtex / csv / web)。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field as dc_field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --------------------------------------------------------------------------
# 常量: 缺失 / 不确定标记
# --------------------------------------------------------------------------

MISSING = "MISSING"            # 该字段在任何输入中都未出现
UNCERTAIN = "UNCERTAIN"        # 出现但置信度低(模糊匹配/解析可疑)
NOT_APPLICABLE = "N/A"         # 该论文类型不适用此字段

# 置信度分级
CONF_HIGH = "high"
CONF_MEDIUM = "medium"
CONF_LOW = "low"

# --------------------------------------------------------------------------
# 规范字段集
# --------------------------------------------------------------------------

# 每个字段: key -> (中文名, 别名列表, 值类型)
CANONICAL_FIELDS: dict[str, dict[str, Any]] = {
    "title":        {"zh": "标题",     "aliases": ["title", "标题", "题目", "论文标题"], "type": "str"},
    "authors":      {"zh": "作者",     "aliases": ["authors", "author", "作者", "作者列表"], "type": "list"},
    "year":         {"zh": "年份",     "aliases": ["year", "年份", "发表年份", "date", "pub_year"], "type": "int"},
    "venue":        {"zh": "期刊/会议", "aliases": ["venue", "journal", "conference", "期刊", "会议", "来源", "期刊/会议", "publication"], "type": "str"},
    "doi":          {"zh": "DOI",      "aliases": ["doi", "DOI"], "type": "str"},
    "keywords":     {"zh": "关键词",   "aliases": ["keywords", "keyword", "关键词", "关键字"], "type": "list"},
    "citations":    {"zh": "被引数",   "aliases": ["citations", "citation_count", "cited_by", "被引数", "被引", "引用数"], "type": "int"},
    "abstract":     {"zh": "摘要",     "aliases": ["abstract", "摘要"], "type": "str"},
    "url":          {"zh": "链接",     "aliases": ["url", "link", "链接", "地址"], "type": "str"},
    "paper_id":     {"zh": "原始编号", "aliases": ["paper_id", "id", "编号"], "type": "str"},
}

FIELD_ORDER = list(CANONICAL_FIELDS.keys())


# --------------------------------------------------------------------------
# 字段包装
# --------------------------------------------------------------------------

@dataclass
class Field:
    """单个字段值 + 来源 + 置信度."""

    value: Any = None
    source: str = ""            # pdf / bibtex / csv / derived / manual
    confidence: str = ""        # high / medium / low
    note: str = ""

    @property
    def is_missing(self) -> bool:
        return self.value is None or self.value == "" or self.value == [] or \
            (isinstance(self.value, str) and self.value.strip() in (MISSING, UNCERTAIN))

    def display(self) -> str:
        """展示用字符串: 缺失/不确定显式标记."""
        if self.value is None or self.value == "" or self.value == []:
            return MISSING
        if isinstance(self.value, list):
            return "; ".join(str(v) for v in self.value)
        return str(self.value)

    def to_dict(self) -> dict:
        return {"value": self.value, "source": self.source,
                "confidence": self.confidence, "note": self.note}


# --------------------------------------------------------------------------
# 论文记录
# --------------------------------------------------------------------------

@dataclass
class PaperRecord:
    """一篇论文的规范化记录."""

    fields: dict[str, Field] = dc_field(default_factory=dict)
    sources: list[str] = dc_field(default_factory=list)   # 该记录由哪些输入合并而来
    record_id: str = ""
    raw_tables: list[dict] = dc_field(default_factory=list)  # 从 PDF 抽取的表格

    def get(self, key: str) -> Field:
        return self.fields.get(key, Field())

    def set(self, key: str, value: Any, source: str, confidence: str = CONF_HIGH,
            note: str = "", overwrite: bool = True) -> None:
        """写入字段. overwrite=False 时仅在当前为空时写入."""
        cur = self.fields.get(key)
        if cur is not None and not cur.is_missing and not overwrite:
            return
        if value is None or value == "" or value == []:
            return
        self.fields[key] = Field(value=value, source=source,
                                 confidence=confidence, note=note)

    def mark_missing(self, key: str) -> None:
        if key not in self.fields or self.fields[key].is_missing:
            self.fields[key] = Field(value=None, source="", confidence="",
                                     note="missing in all inputs")

    def finalize_missing(self) -> None:
        """确保所有规范字段都存在, 缺失的填 None 以便统一展示."""
        for k in FIELD_ORDER:
            if k not in self.fields:
                self.fields[k] = Field(value=None, source="",
                                       confidence="", note="missing in all inputs")

    @property
    def title(self) -> str:
        return self.get("title").display()

    @property
    def doi(self) -> str:
        return self.get("doi").display()

    @property
    def year(self) -> Any:
        return self.get("year").value

    def summary_line(self) -> str:
        return f"[{self.record_id}] {self.title} ({self.year})"

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "sources": self.sources,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
        }


# --------------------------------------------------------------------------
# 去重指纹
# --------------------------------------------------------------------------

def normalize_title(t: str) -> str:
    """标题归一化用于模糊比对: 去标点/大小写/多余空格/Unicode 规范化."""
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", str(t))
    t = t.lower()
    t = re.sub(r"<[^>]+>", " ", t)          # 去 HTML 标签
    t = re.sub(r"[^0-9a-z\u4e00-\u9fff\s]", " ", t)  # 保留字母数字汉字
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_doi(d: str) -> str:
    """DOI 归一化: 去前缀/URL/大小写."""
    if not d:
        return ""
    d = str(d).strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    d = re.sub(r"^doi:\s*", "", d)
    d = re.sub(r"^https?://doi\.org/", "", d)
    return d.strip().strip(".")


def title_fingerprint(t: str) -> str:
    n = normalize_title(t)
    return hashlib.sha1(n.encode("utf-8")).hexdigest()[:12] if n else ""


# --------------------------------------------------------------------------
# 数值 / 年份清洗
# --------------------------------------------------------------------------

_YEAR_RE = re.compile(r"(19|20)\d{2}")


def parse_year(value: Any) -> int | None:
    """从任意值里稳妥提取年份; 提取不到返回 None (绝不猜测)."""
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1800 <= value <= 2100 else None
    m = _YEAR_RE.search(str(value))
    if m:
        y = int(m.group(0))
        return y if 1800 <= y <= 2100 else None
    return None


def parse_int(value: Any) -> int | None:
    """稳妥整数解析; 失败返回 None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    s = re.sub(r"[,\s]", "", str(value))
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def parse_authors(value: Any) -> list[str]:
    """作者字段 -> 标准化列表."""
    if value is None:
        return []
    if isinstance(value, list):
        parts = value
    else:
        s = str(value)
        # 支持 and / ; / 中文分号 / 换行 分隔
        if " and " in s:
            parts = re.split(r"\s+and\s+", s)
        else:
            parts = re.split(r"[;；\n]|,\s*(?=[A-Z\u4e00-\u9fff])", s)
    out = []
    for p in parts:
        p = re.sub(r"\s+", " ", str(p)).strip().strip(".,;")
        if p and p.lower() not in ("et al", "et al.", "等"):
            out.append(p)
    return out


def parse_keywords(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = value
    else:
        parts = re.split(r"[;；,\n]|\s{2,}", str(value))
    return [p.strip() for p in parts if p and p.strip()]


# --------------------------------------------------------------------------
# IO / 日志
# --------------------------------------------------------------------------

def ensure_dir(p: str | Path) -> Path:
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(p: str | Path) -> Any:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write_json(p: str | Path, obj: Any) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text(p: str | Path) -> str:
    return Path(p).read_text(encoding="utf-8", errors="replace")


def write_text(p: str | Path, s: str) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(s, encoding="utf-8")


def timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class Logger:
    """极简日志器, 同时写 stdout 与日志文件."""

    def __init__(self, logfile: str | Path | None = None):
        self.lines: list[str] = []
        self.logfile = Path(logfile) if logfile else None

    def log(self, msg: str) -> None:
        line = f"[{timestamp()}] {msg}"
        print(line)
        self.lines.append(line)

    def flush(self) -> None:
        if self.logfile:
            self.logfile.parent.mkdir(parents=True, exist_ok=True)
            self.logfile.write_text("\n".join(self.lines), encoding="utf-8")


# --------------------------------------------------------------------------
# CSV 导出 (带 UTF-8 BOM, Excel 直接打开不乱码)
# --------------------------------------------------------------------------

def write_csv(path: str | Path, headers: list[str], rows: Iterable[Iterable[Any]]) -> None:
    import csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(["" if v is None else v for v in r])
