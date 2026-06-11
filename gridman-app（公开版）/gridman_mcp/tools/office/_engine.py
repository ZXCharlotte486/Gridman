"""
办公软件引擎层 —— 所有 M365 / WPS 的差异都锁在这一个文件里。

业务工具（office_control.py）只调用本层，永远不知道底下是微软还是金山。
未来要加第三个引擎（LibreOffice / 信创办公软件），只改这里，工具一行不动。
"""

import platform


# 应用类别 → 各引擎的 COM ProgID
# WPS ProgID：kwps=文字, ket=表格, kwpp=演示
APP_PROGIDS = {
    "excel": {"office": "Excel.Application", "wps": "ket.Application"},
    "word": {"office": "Word.Application", "wps": "kwps.Application"},
    "ppt": {"office": "PowerPoint.Application", "wps": "kwpp.Application"},
}

# 引擎中文标签（回报给用户/古立特，始终知道在操控谁）
ENGINE_LABEL = {"office": "Microsoft 365", "wps": "WPS"}

# 文件格式枚举码（M365 与 WPS 兼容，但集中放这便于差异维护）
SAVE_FORMATS = {
    "excel": {"xlsx": 51, "xls": 56, "csv": 6, "pdf": 57},
    "word": {"docx": 16, "doc": 0, "pdf": 17},
    "ppt": {"pptx": 24, "ppt": 1, "pdf": 32},
}


def check_windows():
    """确认运行环境为 Windows（COM 仅 Windows 可用）"""
    if platform.system() != "Windows":
        raise RuntimeError("办公软件实时操控仅支持 Windows 系统（需要 COM 接口）")


def get_com_client():
    """惰性导入 win32com"""
    try:
        import win32com.client
        return win32com.client
    except ImportError:
        raise RuntimeError(
            "缺少 pywin32 依赖。请运行: pip install pywin32\n"
            "或安装古立特 Office 扩展: pip install gridman-mcp[office]"
        )


def _try_get_running(com, prog_id):
    """尝试连接正在运行的实例，失败返回 None"""
    try:
        return com.GetActiveObject(prog_id)
    except Exception:
        return None


def get_app(category: str, engine: str = "auto"):
    """
    获取指定类别的办公应用实例，返回 (app, engine_key)。

    - category: "excel" / "word" / "ppt"
    - engine: "auto"（默认）/ "office" / "wps"

    auto 检测顺序：
    1. 先连正在运行的 M365 实例
    2. 再连正在运行的 WPS 实例
    3. 都没运行 → 按 office→wps 顺序尝试启动（哪个装了启动哪个）

    返回的 engine_key 让上层始终知道实际操控的是谁。
    """
    check_windows()
    com = get_com_client()

    if category not in APP_PROGIDS:
        raise ValueError(f"不支持的应用类别: {category}（可选 excel/word/ppt）")

    if engine not in ("auto", "office", "wps"):
        raise ValueError(f"不支持的引擎: {engine}（可选 auto/office/wps）")

    progids = APP_PROGIDS[category]

    # 指定引擎：只连/启该引擎
    if engine in ("office", "wps"):
        app = _try_get_running(com, progids[engine])
        if app is None:
            app = com.Dispatch(progids[engine])
            _set_visible(app)
        return app, engine

    # auto：先找运行中的（M365 优先），再按需启动
    for eng in ("office", "wps"):
        app = _try_get_running(com, progids[eng])
        if app is not None:
            return app, eng

    # 都没运行，按顺序尝试启动
    last_err = None
    for eng in ("office", "wps"):
        try:
            app = com.Dispatch(progids[eng])
            _set_visible(app)
            return app, eng
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        f"未检测到可用的办公软件（Microsoft 365 / WPS 均未安装或无法启动）。最后错误: {last_err}"
    )


def _set_visible(app):
    """让应用窗口可见（个别应用无此属性，安全忽略）"""
    try:
        app.Visible = True
    except Exception:
        pass


def detect_all_running() -> dict:
    """
    检测 M365 和 WPS 各自运行中的应用状态。
    用于古立特动手前先看清用户开的是哪个引擎、哪个文件。
    """
    check_windows()
    com = get_com_client()

    result = {}
    for category, progids in APP_PROGIDS.items():
        for eng, prog_id in progids.items():
            app = _try_get_running(com, prog_id)
            label = f"{category}/{ENGINE_LABEL[eng]}"
            if app is None:
                result[label] = {"running": False}
                continue

            info = {"running": True, "engine": ENGINE_LABEL[eng]}
            try:
                if category == "excel" and app.Workbooks.Count > 0:
                    info["active_workbook"] = app.ActiveWorkbook.Name
                    info["sheets"] = [
                        app.ActiveWorkbook.Sheets(i + 1).Name
                        for i in range(app.ActiveWorkbook.Sheets.Count)
                    ]
                elif category == "word" and app.Documents.Count > 0:
                    info["active_document"] = app.ActiveDocument.Name
                elif category == "ppt" and app.Presentations.Count > 0:
                    info["active_presentation"] = app.ActivePresentation.Name
                    info["slides_count"] = app.ActivePresentation.Slides.Count
            except Exception:
                pass

            result[label] = info

    return result
