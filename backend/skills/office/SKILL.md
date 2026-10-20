---
name: office
description: 生成 Word（.docx）和 Excel（.xlsx）办公文档。
---

# 办公文档生成

当用户要「写一份 Word / Excel / 文档 / 表格 / 报告」时，用 `run_python` 工具跑下面的 Python 代码来生成。

依赖（已装好）：`python-docx`（Word）、`openpyxl`（Excel）。

生成的文件统一存到 `generated/` 目录（代码开头先 `os.makedirs` 确保目录存在）。

## 生成 Word（.docx）

```python
import os
from docx import Document

os.makedirs("generated", exist_ok=True)
doc = Document()
doc.add_heading("标题", level=1)
doc.add_paragraph("正文段落。")
doc.add_heading("小节", level=2)
doc.add_paragraph("一个要点。", style="List Bullet")
doc.save("generated/文档名.docx")
print("已生成 generated/文档名.docx")
```

## 生成 Excel（.xlsx）

```python
import os
from openpyxl import Workbook

os.makedirs("generated", exist_ok=True)
wb = Workbook()
ws = wb.active
ws.title = "Sheet1"
ws.append(["姓名", "年龄", "城市"])
ws.append(["张三", 25, "北京"])
ws.append(["李四", 30, "上海"])
wb.save("generated/表格名.xlsx")
print("已生成 generated/表格名.xlsx")
```

## 技巧

- 文件名按用户要的内容起，中文英文都行。
- Word 常用：`add_heading(text, level)` 标题、`add_paragraph(text)` 段落、`add_table(rows, cols)` 表格。
- Excel 常用：`ws.append([...])` 加一行、`ws["A1"] = 值` 写单元格。
- 生成后告诉用户文件保存在哪（`generated/xxx.docx` 或 `generated/xxx.xlsx`）。
