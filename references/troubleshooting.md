# 故障排查

## PDF 表格抽不到

**现象**：`plot_table_numeric` 跳过，提示"未从表格中抽取到可绘数值列"。

**原因与对策**：

1. **表格无框线**（最常见）。pdfplumber 靠线框识别，无框线表格会失败。
   本 Skill 已内置**坐标聚类兜底**（按 y 分行、x 归列）。若仍失败：
   - 确认表格是**规则网格**（行列对齐）。跨页表、合并单元格表可能识别不全。
   - 检查 `--no-figures` 是否误开。

2. **扫描版 PDF**（图片型）。文本层为空，任何方法都抽不到。对策：
   - 先做 OCR（本 Skill 不含 OCR）；或
   - 从 CSV 提供该表数据，让流水线从元数据画图。

3. **表格数值被识别为表头**。若首行是数据，脚本已自动判断（首行数值占比 ≤1/3 才视为表头）。
   仍误判时，手动调整 CSV 输入。

## 图表中文缺字（方框/警告 "Glyph missing from font"）

**原因**：matplotlib 字体未生效，回落到 Arial。

**已内置修复**：`_setup_matplotlib` 直接 `addfont` 注册 `C:\Windows\Fonts\msyh.ttc`
等中文字体，不依赖 font cache。

**排查**：
```bash
PY="C:/Users/29859/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" -c "
import sys; sys.path.insert(0,'scripts')
from make_figures import _setup_matplotlib
_setup_matplotlib('zh')
import matplotlib.pyplot as plt
print(plt.rcParams['font.sans-serif'][:3])
"
```
应输出含 `Microsoft YaHei` / `SimHei`。若为空，检查系统是否存在 `C:\Windows\Fonts\msyh.ttc`。

**注意**：英文图（`lang=en`）用的是英文字体，若图注混入中文仍会缺字。
本 Skill 已通过 `_localize_ref` 把来源标记本地化，正常不会触发。

## 去重误判 / 漏判

- **误判（不同论文被合并）**：标题高度相似的两篇不同论文（如同一作者系列工作）。
  对策：提高阈值 `--fuzzy 95`，或去掉 `--fuzzy` 只保留 DOI+标题精确去重。
- **漏判（同一篇没合并）**：标题差异大且无 DOI。对策：降低阈值 `--fuzzy 80`。
- 检查 `merge_report.json` 的 `dedup_groups` 确认合并了哪些。

## 年份/被引数被解析成错值

- 年份：只接受 1800–2100，且优先取最常见值。PDF 里若正文引用大量年份可能取错，
  此时建议用 CSV/BibTeX 提供权威值（优先级更高，会覆盖 PDF）。
- 被引数：只有明确字段才解析；从 BibTeX `note` 字段猜测的会标 `low` 置信度。

## 作者抽取不准（PDF）

PDF 作者靠版式启发式抽取，**置信度固定为 low**。跨行标题、多机构作者容易出错。
**建议**：优先用 CSV/BibTeX（置信度 high）提供作者；PDF 只作为兜底。

## 内存/超时

大批量（>200 篇 PDF）时逐篇处理较慢。建议分批跑，或用目录输入让其顺序处理。
单篇 PDF 的表格聚类是 O(词数)，正常论文无压力。

## 依赖缺失

```bash
"C:/Users/29859/.workbuddy/binaries/python/envs/default/Scripts/pip.exe" \
  install -r requirements.txt
```
