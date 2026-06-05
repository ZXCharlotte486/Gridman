"""往来账龄分析工具

功能：
根据往来明细数据，按先进先出法计算各客商的账龄分布。
"""
import pandas as pd
from pathlib import Path
from datetime import datetime

from gridman_mcp.tools._shared.io import read_table


def analyze_aging(
    file_path: str,
    base_date: str,
    aging_brackets_months: list = None,
    output_path: str = None,
) -> dict:
    """往来账龄分析。

    Args:
        file_path: 往来明细 Excel/CSV 文件路径
        base_date: 分析基准日（YYYY-MM-DD）
        aging_brackets_months: 账龄分段月数列表，如 [12, 24, 36]
        output_path: 输出文件路径

    Returns:
        分析结果摘要
    """
    if aging_brackets_months is None:
        aging_brackets_months = [12, 24, 36]

    try:
        try:
            df = read_table(file_path)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        try:
            base_dt = datetime.strptime(base_date, "%Y-%m-%d")
        except ValueError:
            return {"status": "error", "message": f"base_date 格式错误：{base_date}，应为 YYYY-MM-DD"}

        # 自动识别列
        customer_col = _find_column(df, ["客户", "客户名称", "对方单位", "往来单位", "供应商"])
        date_col = _find_column(df, ["日期", "发生日期", "记账日期", "凭证日期", "业务日期"])
        amount_col = _find_column(df, ["余额", "金额", "期末余额", "发生额"])

        if not customer_col:
            return {"status": "error", "message": f"找不到客户/往来单位列，可用列: {list(df.columns)}"}
        if not amount_col:
            return {"status": "error", "message": f"找不到金额列，可用列: {list(df.columns)}"}

        # 转换日期
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        # 构建账龄标签
        brackets = sorted(aging_brackets_months)
        labels = []
        for i, months in enumerate(brackets):
            if i == 0:
                labels.append(f"{months}个月以内" if months < 12 else f"{months // 12}年以内")
            else:
                prev = brackets[i - 1]
                prev_label = f"{prev}个月" if prev < 12 else f"{prev // 12}年"
                cur_label = f"{months}个月" if months < 12 else f"{months // 12}年"
                labels.append(f"{prev_label}-{cur_label}")
        labels.append(f"{brackets[-1] // 12}年以上" if brackets[-1] >= 12 else f"{brackets[-1]}个月以上")

        # 计算每笔的账龄
        results = []

        if date_col:
            df["账龄月数"] = ((base_dt - df[date_col]).dt.days / 30.44).fillna(0).astype(int)

            for customer, group in df.groupby(customer_col):
                row = {"客户名称": customer, "合计": float(group[amount_col].sum())}

                for i, months in enumerate(brackets):
                    if i == 0:
                        mask = group["账龄月数"] <= months
                    else:
                        mask = (group["账龄月数"] > brackets[i - 1]) & (group["账龄月数"] <= months)
                    row[labels[i]] = float(group.loc[mask, amount_col].sum())

                mask = group["账龄月数"] > brackets[-1]
                row[labels[-1]] = float(group.loc[mask, amount_col].sum())

                results.append(row)
        else:
            for customer, group in df.groupby(customer_col):
                row = {"客户名称": customer, "合计": float(group[amount_col].sum())}
                row[labels[0]] = float(group[amount_col].sum())
                for label in labels[1:]:
                    row[label] = 0.0
                results.append(row)

        result_df = pd.DataFrame(results)

        # 添加合计行
        total_row = {"客户名称": "合计"}
        for col in result_df.columns:
            if col != "客户名称":
                total_row[col] = float(result_df[col].sum())
        result_df = pd.concat([result_df, pd.DataFrame([total_row])], ignore_index=True)

        # 输出
        fp = Path(file_path)
        if output_path is None:
            output_path = fp.parent / f"账龄分析_{base_date}.xlsx"
        else:
            output_path = Path(output_path)

        try:
            result_df.to_excel(output_path, index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}"}

        return {
            "status": "success",
            "message": "账龄分析完成",
            "customer_count": len(results),
            "total_amount": float(result_df.loc[result_df["客户名称"] == "合计", "合计"].iloc[0]),
            "aging_brackets": labels,
            "output_file": str(output_path),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}


def _find_column(df: pd.DataFrame, candidates: list) -> str:
    for col in candidates:
        if col in df.columns:
            return col
    for col in candidates:
        for actual_col in df.columns:
            if col in str(actual_col):
                return actual_col
    return None
