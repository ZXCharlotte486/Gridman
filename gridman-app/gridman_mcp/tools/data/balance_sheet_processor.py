"""科目余额表处理工具

功能：
1. 删除非末级科目行（只保留末级科目）
2. 根据科目代码拆分出各级科目名称
3. 标准化输出格式
"""
import pandas as pd
from pathlib import Path

from gridman_mcp.tools._shared.io import read_table


def process_balance_sheet(
    file_path: str,
    code_column: str = "科目代码",
    name_column: str = "科目名称",
    output_path: str = None,
) -> dict:
    """处理科目余额表，保留末级科目并拆分层级。

    Args:
        file_path: 科目余额表 Excel/CSV 文件路径
        code_column: 科目代码列名
        name_column: 科目名称列名
        output_path: 输出文件路径（可选，默认在原文件同目录生成）

    Returns:
        处理结果摘要
    """
    try:
        # 读取文件
        try:
            df = read_table(file_path)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        if code_column not in df.columns:
            return {"status": "error", "message": f"找不到列 '{code_column}'，可用列: {list(df.columns)}"}
        if name_column not in df.columns:
            return {"status": "error", "message": f"找不到列 '{name_column}'，可用列: {list(df.columns)}"}

        # 确保科目代码为字符串，并清掉空行/合计行
        df[code_column] = df[code_column].astype(str).str.strip()
        df = df[df[code_column].notna()]
        df = df[~df[code_column].isin(["", "nan", "NaN", "None"])].copy()
        if df.empty:
            return {"status": "error", "message": "科目代码列全部为空，无有效数据"}

        # 识别末级科目（没有下级科目的行）
        all_codes = set(df[code_column].tolist())
        leaf_mask = []
        for code in df[code_column]:
            is_leaf = not any(
                other.startswith(code) and len(other) > len(code)
                for other in all_codes
                if other != code
            )
            leaf_mask.append(is_leaf)

        df_leaf = df[leaf_mask].copy()

        # 拆分科目层级
        sample_code = df_leaf[code_column].iloc[0] if len(df_leaf) > 0 else ""

        # 检测分隔符
        if "." in sample_code:
            separator = "."
        elif "-" in sample_code:
            separator = "-"
        elif "/" in sample_code:
            separator = "/"
        else:
            separator = None

        if separator:
            parts = df_leaf[code_column].str.split(separator)
            max_level = parts.apply(len).max()

            for level in range(1, min(max_level + 1, 7)):
                level_col = f"{level}级科目代码"
                df_leaf[level_col] = parts.apply(
                    lambda x: separator.join(x[:level]) if len(x) >= level else ""
                )
        else:
            code_lengths = df[code_column].str.len().unique()
            code_lengths = sorted(code_lengths)

            if len(code_lengths) > 1:
                first_len = code_lengths[0]
                df_leaf["1级科目代码"] = df_leaf[code_column].str[:first_len]

                for i, length in enumerate(code_lengths[1:], 2):
                    col_name = f"{i}级科目代码"
                    df_leaf[col_name] = df_leaf[code_column].apply(
                        lambda x, l=length: x[:l] if len(x) >= l else ""
                    )

        # 添加一级科目名称（通过匹配原始数据）
        code_to_name = dict(zip(df[code_column], df[name_column]))

        if "1级科目代码" in df_leaf.columns:
            df_leaf["一级科目名称"] = df_leaf["1级科目代码"].map(code_to_name).fillna("")

        # 输出
        fp = Path(file_path)
        if output_path is None:
            output_path = fp.parent / f"{fp.stem}_处理后.xlsx"
        else:
            output_path = Path(output_path)

        try:
            df_leaf.to_excel(output_path, index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}"}

        return {
            "status": "success",
            "message": f"处理完成",
            "original_rows": int(len(df)),
            "leaf_rows": int(len(df_leaf)),
            "removed_rows": int(len(df) - len(df_leaf)),
            "output_file": str(output_path),
            "columns": list(df_leaf.columns),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}
