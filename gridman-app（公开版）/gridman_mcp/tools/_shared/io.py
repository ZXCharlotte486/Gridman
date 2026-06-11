"""共享 I/O 工具：统一文件读取（支持 Excel/CSV）+ 友好错误处理。

避免每个工具各自实现一遍读文件逻辑，并保证：
- Excel/CSV 格式都支持
- 文件不存在 → 友好 error 而非 traceback
- PermissionError（Excel 占用）→ 友好提示
"""
from pathlib import Path
from typing import Optional


def read_table(file_path: str, sheet_name: Optional[str] = None):
    """读取 Excel/CSV 文件，自动识别格式。

    Args:
        file_path: 文件路径
        sheet_name: Excel sheet 名（可选，默认读第一个）

    Returns:
        pandas.DataFrame

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 不支持的文件格式
    """
    import pandas as pd

    fp = Path(file_path)
    if not fp.exists():
        raise FileNotFoundError(f"文件不存在: {fp}")

    suffix = fp.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(fp, sheet_name=sheet_name or 0)
    elif suffix == ".csv":
        # 尝试 utf-8，失败回退 GBK（中文 Excel 导出常见）
        try:
            df = pd.read_csv(fp, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(fp, encoding="gbk")
    else:
        raise ValueError(f"不支持的文件格式: {suffix}（仅支持 .xlsx/.xls/.csv）")

    # 列名预处理：去前后空格（防止用户列名带空格导致匹配失败）
    if hasattr(df, "columns"):
        df.columns = df.columns.astype(str).str.strip()
    return df


def safe_save_workbook(wb, output_path: str) -> dict:
    """安全保存 openpyxl Workbook，捕获文件占用异常。

    Returns:
        {"status": "success", "output_file": path}
        或 {"status": "error", "message": ...}
    """
    try:
        wb.save(output_path)
        return {"status": "success", "output_file": output_path}
    except PermissionError:
        return {
            "status": "error",
            "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}",
        }
    except Exception as e:
        return {"status": "error", "message": f"保存文件失败：{e}"}
