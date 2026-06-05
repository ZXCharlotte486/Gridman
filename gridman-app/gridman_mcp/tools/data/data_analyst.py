"""
数据分析工具 — CSV/Excel 数据分析与统计

支持：
- 数据概览（行列数、数据类型、缺失值、基本统计）
- 分组汇总（按指定列分组聚合）
- 数据筛选（按条件过滤）
- 透视表生成

读文件统一使用 _shared/io.read_table（支持 Excel/CSV，自动 strip 列名）。
"""
from pathlib import Path

from gridman_mcp.tools._shared.io import read_table


def _read(file_path: str, sheet_name=None):
    """读文件并返回 (df, error_dict)。失败时 df 为 None。"""
    try:
        return read_table(file_path, sheet_name=sheet_name), None
    except FileNotFoundError as e:
        return None, {"status": "error", "message": str(e)}
    except ValueError as e:
        return None, {"status": "error", "message": str(e)}


def data_overview(file_path: str, sheet_name: str = None) -> dict:
    """
    数据概览：行列数、列名、数据类型、缺失值统计、基本描述性统计。

    Args:
        file_path: CSV 或 Excel 文件路径
        sheet_name: Excel 工作表名（可选，默认第一个）

    Returns:
        dict: {"status": "success"|"error", "overview": {...}}
    """
    try:
        import pandas as pd

        df, err = _read(file_path, sheet_name)
        if err:
            return err

        overview = {
            "行数": len(df),
            "列数": len(df.columns),
            "列名": list(df.columns),
            "数据类型": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "缺失值": {col: int(count) for col, count in df.isnull().sum().items() if count > 0},
            "缺失率": {col: f"{count/len(df)*100:.1f}%" for col, count in df.isnull().sum().items() if count > 0},
        }

        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if numeric_cols:
            desc = df[numeric_cols].describe().round(2).to_dict()
            overview["数值统计"] = desc

        overview["前5行"] = df.head(5).to_dict(orient="records")

        return {"status": "success", "overview": overview}

    except ImportError:
        return {"status": "error", "message": "pandas 未安装"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def group_summary(
    file_path: str,
    group_by: str,
    agg_column: str,
    agg_func: str = "sum",
    sheet_name: str = None,
    output_path: str = None,
) -> dict:
    """分组汇总。"""
    try:
        import pandas as pd

        df, err = _read(file_path, sheet_name)
        if err:
            return err

        group_cols = [c.strip() for c in group_by.split(",")]
        for col in group_cols:
            if col not in df.columns:
                return {"status": "error", "message": f"列 '{col}' 不存在，可用列：{list(df.columns)}"}

        if agg_column not in df.columns:
            return {"status": "error", "message": f"列 '{agg_column}' 不存在"}

        valid_funcs = {"sum", "mean", "count", "max", "min", "std", "median"}
        if agg_func not in valid_funcs:
            return {"status": "error", "message": f"不支持的聚合函数：{agg_func}，可选：{valid_funcs}"}

        result = df.groupby(group_cols)[agg_column].agg(agg_func).reset_index()
        result.columns = group_cols + [f"{agg_column}_{agg_func}"]
        result = result.sort_values(f"{agg_column}_{agg_func}", ascending=False)

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                if out.suffix.lower() in (".xlsx", ".xls"):
                    result.to_excel(str(out), index=False)
                else:
                    result.to_csv(str(out), index=False, encoding="utf-8-sig")
            except PermissionError:
                return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{out}"}

        records = result.to_dict(orient="records")

        return {
            "status": "success",
            "data": records[:100],
            "groups": len(records),
            "output_file": output_path,
            "message": f"按 {group_by} 分组，{agg_column} {agg_func}，共 {len(records)} 组",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def filter_data(
    file_path: str,
    column: str,
    operator: str,
    value: str,
    sheet_name: str = None,
    output_path: str = None,
) -> dict:
    """数据筛选。"""
    try:
        import pandas as pd

        df, err = _read(file_path, sheet_name)
        if err:
            return err

        if column not in df.columns:
            return {"status": "error", "message": f"列 '{column}' 不存在，可用列：{list(df.columns)}"}

        col = df[column]

        if operator == "contains":
            mask = col.astype(str).str.contains(value, na=False)
        elif operator == "startswith":
            mask = col.astype(str).str.startswith(value, na=False)
        else:
            # object 列优先字符串比较
            if col.dtype == object and operator in ("==", "!="):
                col_str = col.astype(str).str.strip()
                if operator == "==":
                    mask = col_str == str(value).strip()
                else:
                    mask = col_str != str(value).strip()
            else:
                try:
                    num_value = float(value)
                    num_col = pd.to_numeric(col, errors="coerce")
                    if operator == ">":
                        mask = num_col > num_value
                    elif operator == "<":
                        mask = num_col < num_value
                    elif operator == ">=":
                        mask = num_col >= num_value
                    elif operator == "<=":
                        mask = num_col <= num_value
                    elif operator == "==":
                        mask = num_col == num_value
                    elif operator == "!=":
                        mask = num_col != num_value
                    else:
                        return {"status": "error", "message": f"不支持的运算符：{operator}"}
                except ValueError:
                    if operator == "==":
                        mask = col.astype(str) == value
                    elif operator == "!=":
                        mask = col.astype(str) != value
                    else:
                        return {"status": "error", "message": f"非数值列不支持运算符：{operator}"}

        result = df[mask]

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                if out.suffix.lower() in (".xlsx", ".xls"):
                    result.to_excel(str(out), index=False)
                else:
                    result.to_csv(str(out), index=False, encoding="utf-8-sig")
            except PermissionError:
                return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{out}"}

        records = result.head(100).to_dict(orient="records")

        return {
            "status": "success",
            "data": records,
            "count": len(result),
            "total": len(df),
            "output_file": output_path,
            "message": f"筛选 {column} {operator} {value}，命中 {len(result)}/{len(df)} 条",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}


def pivot_table(
    file_path: str,
    index: str,
    columns: str = None,
    values: str = None,
    agg_func: str = "sum",
    sheet_name: str = None,
    output_path: str = None,
) -> dict:
    """生成透视表。"""
    try:
        import pandas as pd

        df, err = _read(file_path, sheet_name)
        if err:
            return err

        pivot_kwargs = {
            "index": index,
            "aggfunc": agg_func,
        }
        if columns:
            pivot_kwargs["columns"] = columns
        if values:
            pivot_kwargs["values"] = values

        result = pd.pivot_table(df, **pivot_kwargs)
        result = result.reset_index()

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:
                if out.suffix.lower() in (".xlsx", ".xls"):
                    result.to_excel(str(out), index=False)
                else:
                    result.to_csv(str(out), index=False, encoding="utf-8-sig")
            except PermissionError:
                return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{out}"}

        records = result.head(100).to_dict(orient="records")

        return {
            "status": "success",
            "data": records,
            "rows": len(result),
            "output_file": output_path,
            "message": f"透视表生成完成，{len(result)} 行",
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
