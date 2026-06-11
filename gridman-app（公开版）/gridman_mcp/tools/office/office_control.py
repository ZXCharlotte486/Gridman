"""
办公软件实时操控工具（Microsoft 365 / WPS 通用）

通过 Windows COM (pywin32) 直接操控用户屏幕上正在运行的办公应用实例。
支持：Excel/表格、Word/文字、PowerPoint/演示。

引擎（M365 / WPS）由 _engine 层自动适配，每个工具结果都回报实际操控的引擎。
依赖：pywin32（仅 Windows 可用）

⚠ 实时操控会改动用户正在打开的文件，调用写入类工具前应先经用户确认。
"""

import os

from gridman_mcp.tools.office._engine import (
    get_app,
    detect_all_running,
    ENGINE_LABEL,
    SAVE_FORMATS,
)


def _safe_get_app(category: str, engine: str):
    """
    包装 get_app，把异常转为结构化错误返回值。
    返回 (app, engine_key, error_dict)；error_dict 不为 None 时上层应直接 return 它。
    """
    try:
        app, eng = get_app(category, engine)
        return app, eng, None
    except Exception as e:
        return None, None, {"status": "error", "message": str(e), "engine": None}


# ─────────────────────────────────────────────
# 工具 1：列出当前运行的办公应用（M365 + WPS）
# ─────────────────────────────────────────────

def list_running_apps() -> dict:
    """检测当前运行中的办公应用（Microsoft 365 与 WPS 的 Excel/Word/PowerPoint）。"""
    apps = detect_all_running()
    return {"status": "ok", "applications": apps}


# ─────────────────────────────────────────────
# 工具 2：Excel — 读取区域
# ─────────────────────────────────────────────

def excel_read_range(
    range_address: str = None,
    sheet_name: str = None,
    engine: str = "auto",
    read_formula: bool = False,
) -> dict:
    """
    读取当前打开的表格中的数据。

    - range_address: 如 "A1:D10"。不指定则读取当前选中区域。
    - sheet_name: 工作表名。不指定则读取活动工作表。
    - engine: auto/office/wps
    - read_formula: False(默认)读计算结果值；True 读单元格公式（看底稿的勾稽逻辑）
    """
    app, eng, _err = _safe_get_app("excel", engine)
    if _err: return _err

    if app.Workbooks.Count == 0:
        return {"status": "error", "message": "当前没有打开的工作簿", "engine": ENGINE_LABEL[eng]}

    wb = app.ActiveWorkbook

    if sheet_name:
        try:
            ws = wb.Sheets(sheet_name)
        except Exception:
            available = [wb.Sheets(i + 1).Name for i in range(wb.Sheets.Count)]
            return {
                "status": "error",
                "message": f"找不到工作表 '{sheet_name}'",
                "available_sheets": available,
                "engine": ENGINE_LABEL[eng],
            }
    else:
        ws = app.ActiveSheet

    rng = ws.Range(range_address) if range_address else app.Selection

    # read_formula=True 取 .Formula，否则取 .Value
    values = rng.Formula if read_formula else rng.Value
    if values is None:
        return {"status": "ok", "data": [], "range": rng.Address,
                "sheet": ws.Name, "engine": ENGINE_LABEL[eng]}

    if not isinstance(values, tuple):
        values = ((values,),)

    data = []
    for row in values:
        if isinstance(row, tuple):
            data.append([cell for cell in row])
        else:
            data.append([row])

    return {
        "status": "ok",
        "data": data,
        "rows": len(data),
        "cols": len(data[0]) if data else 0,
        "range": rng.Address,
        "sheet": ws.Name,
        "workbook": wb.Name,
        "engine": ENGINE_LABEL[eng],
        "mode": "formula" if read_formula else "value",
    }


# ─────────────────────────────────────────────
# 工具 3：Excel — 写入数据
# ─────────────────────────────────────────────

def excel_write_range(
    data: list,
    start_cell: str = "A1",
    sheet_name: str = None,
    engine: str = "auto",
) -> dict:
    """
    向当前打开的表格写入数据。

    - data: 二维列表，如 [["姓名","金额"],["张三",1000]]
    - start_cell: 起始单元格
    - sheet_name: 目标工作表名。不存在则自动新建。
    - engine: auto/office/wps
    """
    app, eng, _err = _safe_get_app("excel", engine)
    if _err: return _err

    if app.Workbooks.Count == 0:
        return {"status": "error", "message": "当前没有打开的工作簿", "engine": ENGINE_LABEL[eng]}

    wb = app.ActiveWorkbook

    if sheet_name:
        try:
            ws = wb.Sheets(sheet_name)
        except Exception:
            ws = wb.Sheets.Add()
            ws.Name = sheet_name
    else:
        ws = app.ActiveSheet

    if not data or not isinstance(data, list):
        return {"status": "error", "message": "data 必须是非空的二维列表", "engine": ENGINE_LABEL[eng]}

    rows = len(data)
    cols = max(len(row) for row in data) if data else 0

    normalized = []
    for row in data:
        row = list(row)
        if len(row) < cols:
            row = row + [None] * (cols - len(row))
        normalized.append(tuple(row))

    start_range = ws.Range(start_cell)
    end_range = ws.Cells(start_range.Row + rows - 1, start_range.Column + cols - 1)
    target_range = ws.Range(start_range, end_range)
    target_range.Value = tuple(normalized)

    return {
        "status": "ok",
        "message": f"已写入 {rows} 行 × {cols} 列到 {ws.Name}!{target_range.Address}",
        "sheet": ws.Name,
        "range": target_range.Address,
        "workbook": wb.Name,
        "engine": ENGINE_LABEL[eng],
    }


# ─────────────────────────────────────────────
# 工具 4：Excel — 设置公式
# ─────────────────────────────────────────────

def excel_set_formula(
    cell: str,
    formula: str,
    sheet_name: str = None,
    engine: str = "auto",
) -> dict:
    """
    在指定单元格设置公式。

    - cell: 如 "E2"
    - formula: 如 "=SUM(B2:D2)"
    - sheet_name: 不指定则用活动工作表
    - engine: auto/office/wps
    """
    app, eng, _err = _safe_get_app("excel", engine)
    if _err: return _err

    if app.Workbooks.Count == 0:
        return {"status": "error", "message": "当前没有打开的工作簿", "engine": ENGINE_LABEL[eng]}

    wb = app.ActiveWorkbook
    ws = wb.Sheets(sheet_name) if sheet_name else app.ActiveSheet

    try:
        ws.Range(cell).Formula = formula
        return {
            "status": "ok",
            "cell": cell,
            "formula": formula,
            "calculated_value": ws.Range(cell).Value,
            "sheet": ws.Name,
            "engine": ENGINE_LABEL[eng],
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "engine": ENGINE_LABEL[eng]}


# ─────────────────────────────────────────────
# 工具 5：Word — 读取文档
# ─────────────────────────────────────────────

def word_read_document(engine: str = "auto") -> dict:
    """读取当前打开的文字文档的全部文本内容。engine: auto/office/wps"""
    app, eng, _err = _safe_get_app("word", engine)
    if _err: return _err

    if app.Documents.Count == 0:
        return {"status": "error", "message": "当前没有打开的文档", "engine": ENGINE_LABEL[eng]}

    doc = app.ActiveDocument
    text = doc.Content.Text
    para_count = doc.Paragraphs.Count

    paragraphs_preview = []
    for i in range(min(20, para_count)):
        p = doc.Paragraphs(i + 1).Range.Text.strip()
        if p:
            paragraphs_preview.append(p)

    return {
        "status": "ok",
        "document_name": doc.Name,
        "full_path": doc.FullName,
        "paragraphs_count": para_count,
        "characters_count": len(text),
        "preview": paragraphs_preview,
        "full_text": text[:10000] if len(text) > 10000 else text,
        "truncated": len(text) > 10000,
        "engine": ENGINE_LABEL[eng],
    }


# ─────────────────────────────────────────────
# 工具 6：Word — 追加文本
# ─────────────────────────────────────────────

def word_append_text(text: str, style: str = None, engine: str = "auto") -> dict:
    """
    在当前文字文档末尾追加一段文本。

    - text: 要追加的文本
    - style: 样式名，如 "Heading 1"、"标题 1"
    - engine: auto/office/wps
    """
    app, eng, _err = _safe_get_app("word", engine)
    if _err: return _err

    if app.Documents.Count == 0:
        return {"status": "error", "message": "当前没有打开的文档", "engine": ENGINE_LABEL[eng]}

    doc = app.ActiveDocument
    end_range = doc.Content
    end_range.Collapse(0)  # wdCollapseEnd
    end_range.InsertAfter("\n" + text)

    if style:
        try:
            doc.Paragraphs(doc.Paragraphs.Count).Style = style
        except Exception:
            pass

    return {
        "status": "ok",
        "message": f"已在文档末尾追加 {len(text)} 个字符",
        "document": doc.Name,
        "style": style,
        "engine": ENGINE_LABEL[eng],
    }


# ─────────────────────────────────────────────
# 工具 7：通用 — 另存为标准格式
# ─────────────────────────────────────────────

def office_save_as(
    output_path: str,
    app_type: str = "excel",
    file_format: str = None,
    engine: str = "auto",
) -> dict:
    """
    将当前打开的文档另存为指定格式（可把 WPS 私有/加密格式转为标准格式）。

    - output_path: 输出文件完整路径
    - app_type: "excel" / "word" / "ppt"（或 "powerpoint"）
    - file_format: 不指定则按扩展名判断
    - engine: auto/office/wps
    """
    output_path = os.path.abspath(output_path)
    category = "ppt" if app_type.lower() in ("ppt", "powerpoint") else app_type.lower()

    if category not in SAVE_FORMATS:
        return {"status": "error", "message": f"不支持的应用类型: {app_type}"}

    app, eng, _err = _safe_get_app(category, engine)
    if _err: return _err
    ext = (file_format or os.path.splitext(output_path)[1].lstrip(".")).lower()
    fmt_map = SAVE_FORMATS[category]
    fmt_code = fmt_map.get(ext, list(fmt_map.values())[0])

    try:
        if category == "excel":
            if app.Workbooks.Count == 0:
                return {"status": "error", "message": "当前没有打开的工作簿", "engine": ENGINE_LABEL[eng]}
            app.ActiveWorkbook.SaveAs(output_path, FileFormat=fmt_code)
            src = app.ActiveWorkbook.Name
        elif category == "word":
            if app.Documents.Count == 0:
                return {"status": "error", "message": "当前没有打开的文档", "engine": ENGINE_LABEL[eng]}
            doc = app.ActiveDocument
            if ext == "pdf":
                doc.ExportAsFixedFormat(output_path, 17)  # wdExportFormatPDF
            else:
                doc.SaveAs2(output_path, FileFormat=fmt_code)
            src = doc.Name
        else:  # ppt
            if app.Presentations.Count == 0:
                return {"status": "error", "message": "当前没有打开的演示文稿", "engine": ENGINE_LABEL[eng]}
            prs = app.ActivePresentation
            if ext == "pdf":
                prs.ExportAsFixedFormat(output_path, 2)  # ppFixedFormatTypePDF
            else:
                prs.SaveAs(output_path, FileFormat=fmt_code)
            src = prs.Name

        return {
            "status": "ok",
            "message": f"已保存为 {output_path}",
            "format": ext,
            "source": src,
            "engine": ENGINE_LABEL[eng],
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "engine": ENGINE_LABEL[eng]}


# ─────────────────────────────────────────────
# 工具 8：PowerPoint — 获取演示文稿信息
# ─────────────────────────────────────────────

def ppt_get_info(engine: str = "auto") -> dict:
    """获取当前打开的演示文稿信息（幻灯片列表和标题）。engine: auto/office/wps"""
    app, eng, _err = _safe_get_app("ppt", engine)
    if _err: return _err

    if app.Presentations.Count == 0:
        return {"status": "error", "message": "当前没有打开的演示文稿", "engine": ENGINE_LABEL[eng]}

    prs = app.ActivePresentation
    slides_info = []
    for i in range(1, prs.Slides.Count + 1):
        slide = prs.Slides(i)
        title = ""
        if slide.Shapes.HasTitle:
            title = slide.Shapes.Title.TextFrame.TextRange.Text
        slides_info.append({"slide_number": i, "title": title})

    return {
        "status": "ok",
        "presentation_name": prs.Name,
        "full_path": prs.FullName,
        "slides_count": prs.Slides.Count,
        "slides": slides_info,
        "engine": ENGINE_LABEL[eng],
    }


# ─────────────────────────────────────────────
# 工具 9：PowerPoint — 添加新幻灯片
# ─────────────────────────────────────────────

def ppt_add_slide(title: str = "", content: str = "", layout_index: int = 2, engine: str = "auto") -> dict:
    """
    在当前演示文稿末尾添加一张新幻灯片。

    - title: 标题文字
    - content: 正文文字
    - layout_index: 版式（1=标题页, 2=标题+内容, 3=节标题, 7=空白）
    - engine: auto/office/wps
    """
    app, eng, _err = _safe_get_app("ppt", engine)
    if _err: return _err

    if app.Presentations.Count == 0:
        return {"status": "error", "message": "当前没有打开的演示文稿", "engine": ENGINE_LABEL[eng]}

    prs = app.ActivePresentation
    layout_count = prs.SlideMaster.CustomLayouts.Count
    if layout_index < 1 or layout_index > layout_count:
        layout_index = min(2, layout_count)
    layout = prs.SlideMaster.CustomLayouts(layout_index)
    new_slide = prs.Slides.AddSlide(prs.Slides.Count + 1, layout)

    if title and new_slide.Shapes.HasTitle:
        new_slide.Shapes.Title.TextFrame.TextRange.Text = title

    if content:
        title_shape = new_slide.Shapes.Title if new_slide.Shapes.HasTitle else None
        for i in range(1, new_slide.Shapes.Count + 1):
            shape = new_slide.Shapes(i)
            if title_shape is not None and shape.Name == title_shape.Name:
                continue
            try:
                if shape.HasTextFrame:
                    shape.TextFrame.TextRange.Text = content
                    break
            except Exception:
                continue

    return {
        "status": "ok",
        "message": f"已添加第 {new_slide.SlideIndex} 张幻灯片",
        "slide_number": new_slide.SlideIndex,
        "title": title,
        "engine": ENGINE_LABEL[eng],
    }
