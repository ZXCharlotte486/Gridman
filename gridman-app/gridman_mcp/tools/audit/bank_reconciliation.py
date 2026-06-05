"""银行余额调节表工具

功能：
1. 读取银行对账单和企业银行日记账
2. 按金额+日期容差逐笔匹配
3. 识别已达账项和未达账项
4. 生成调节表
"""
import pandas as pd
from pathlib import Path
from datetime import timedelta

from gridman_mcp.tools._shared.io import read_table


def reconcile_bank(
    bank_statement_path: str,
    ledger_path: str,
    date_tolerance_days: int = 3,
    output_path: str = None,
) -> dict:
    """银行流水核对，生成调节表。

    Args:
        bank_statement_path: 银行对账单 Excel/CSV 文件路径
        ledger_path: 企业银行日记账 Excel/CSV 文件路径
        date_tolerance_days: 日期匹配容差天数
        output_path: 输出文件路径

    Returns:
        调节结果摘要
    """
    try:
        try:
            bank_df = read_table(bank_statement_path)
            ledger_df = read_table(ledger_path)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        # 自动识别金额列和日期列
        bank_amount_col = _find_column(bank_df, ["金额", "发生额", "交易金额", "借方", "贷方"])
        bank_date_col = _find_column(bank_df, ["日期", "交易日期", "记账日期", "入账日期"])
        ledger_amount_col = _find_column(ledger_df, ["金额", "发生额", "借方", "贷方"])
        ledger_date_col = _find_column(ledger_df, ["日期", "记账日期", "凭证日期"])

        if not bank_amount_col:
            return {"status": "error", "message": f"银行对账单中找不到金额列，可用列: {list(bank_df.columns)}"}
        if not ledger_amount_col:
            return {"status": "error", "message": f"日记账中找不到金额列，可用列: {list(ledger_df.columns)}"}

        # 转换日期
        if bank_date_col:
            bank_df[bank_date_col] = pd.to_datetime(bank_df[bank_date_col], errors="coerce")
        if ledger_date_col:
            ledger_df[ledger_date_col] = pd.to_datetime(ledger_df[ledger_date_col], errors="coerce")

        # 匹配逻辑
        bank_matched = [False] * len(bank_df)
        ledger_matched = [False] * len(ledger_df)
        matches = []

        tolerance = timedelta(days=date_tolerance_days)

        for i, bank_row in bank_df.iterrows():
            bank_amt = bank_row[bank_amount_col]
            if pd.isna(bank_amt):
                continue

            for j, ledger_row in ledger_df.iterrows():
                if ledger_matched[j]:
                    continue

                ledger_amt = ledger_row[ledger_amount_col]
                if pd.isna(ledger_amt):
                    continue

                # 金额匹配（精确）
                if abs(float(bank_amt) - float(ledger_amt)) < 0.01:
                    # 日期匹配（容差）
                    date_ok = True
                    if bank_date_col and ledger_date_col:
                        bank_date = bank_row[bank_date_col]
                        ledger_date = ledger_row[ledger_date_col]
                        if pd.notna(bank_date) and pd.notna(ledger_date):
                            date_ok = abs(bank_date - ledger_date) <= tolerance

                    if date_ok:
                        bank_matched[i] = True
                        ledger_matched[j] = True
                        matches.append({"bank_index": int(i), "ledger_index": int(j), "amount": float(bank_amt)})
                        break

        # 未达账项
        unmatched_bank = bank_df[~pd.Series(bank_matched)].copy()
        unmatched_ledger = ledger_df[~pd.Series(ledger_matched)].copy()

        # 计算余额
        bank_balance = float(bank_df[bank_amount_col].sum())
        ledger_balance = float(ledger_df[ledger_amount_col].sum())

        # 输出
        bank_path = Path(bank_statement_path)
        if output_path is None:
            output_path = bank_path.parent / "调节表结果.xlsx"
        else:
            output_path = Path(output_path)

        try:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                if len(unmatched_bank) > 0:
                    unmatched_bank.to_excel(writer, sheet_name="银行有企业无", index=False)
                if len(unmatched_ledger) > 0:
                    unmatched_ledger.to_excel(writer, sheet_name="企业有银行无", index=False)

                # 调节表摘要
                summary = pd.DataFrame({
                    "项目": ["银行对账单合计", "企业日记账合计", "已匹配笔数", "银行未匹配笔数", "企业未匹配笔数"],
                    "金额/数量": [bank_balance, ledger_balance, len(matches), len(unmatched_bank), len(unmatched_ledger)],
                })
                summary.to_excel(writer, sheet_name="调节摘要", index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}"}

        return {
            "status": "success",
            "message": "银行流水核对完成",
            "bank_total_rows": int(len(bank_df)),
            "ledger_total_rows": int(len(ledger_df)),
            "matched_count": int(len(matches)),
            "unmatched_bank_count": int(len(unmatched_bank)),
            "unmatched_ledger_count": int(len(unmatched_ledger)),
            "output_file": str(output_path),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}


def _find_column(df: pd.DataFrame, candidates: list) -> str:
    """从候选列名中找到第一个存在的列"""
    for col in candidates:
        if col in df.columns:
            return col
    # 模糊匹配
    for col in candidates:
        for actual_col in df.columns:
            if col in str(actual_col):
                return actual_col
    return None
