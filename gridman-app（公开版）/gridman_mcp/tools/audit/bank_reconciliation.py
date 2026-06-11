"""银行余额调节表工具

功能：
1. 读取银行对账单和企业银行日记账
2. 两轮匹配（Pass1 精确同日 / Pass2 日期容差），带置信度分层
3. 重复流水号检测（数据质量雷，不静默配掉）
4. 未匹配项按摘要关键词做业务性质分类（银行扣费 / 会计估计 / 待核查）
5. 生成调节表

设计原则（与古立特铁律一致）：机器只做确定的事——精确同日匹配才算 100%，
日期差的容差匹配标注置信度和差异天数；不确定的（重复号、性质不明的未匹配）
单独标出来交人判断，绝不静默配掉或假装匹配上。

金额一律走 Decimal，杜绝浮点误差（0.1 + 0.2 ≠ 0.3 在财务上不可接受）。
"""
import pandas as pd
from pathlib import Path
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from gridman_mcp.tools._shared.io import read_table


# 未匹配项业务性质分类关键词
_BANK_FEE_KW = ["手续费", "管理费", "账户管理", "工本费", "短信", "年费", "服务费", "快递", "邮费", "结算费"]
_BANK_INT_KW = ["结息", "利息", "息税"]
_EST_KW = ["预提", "暂估", "计提", "摊销", "待摊"]


def _to_decimal(v):
    """安全转 Decimal：先转 str 避免浮点污染，失败返回 None"""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    try:
        return Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _classify_unmatched(summary_text: str, side: str) -> str:
    """按摘要关键词给未匹配项一个业务性质标签（机械分类，不做判断）"""
    s = str(summary_text or "")
    if side == "bank":
        if any(k in s for k in _BANK_INT_KW):
            return "银行结息/利息"
        if any(k in s for k in _BANK_FEE_KW):
            return "银行扣费类（总账常漏记）"
    else:  # ledger
        if any(k in s for k in _EST_KW):
            return "会计估计类（银行无对应流水）"
    return "待核查"


def _confidence(date_diff_days: int, tolerance_days: int) -> float:
    """容差匹配置信度：同日 1.00；日期差越大越低，线性落到 0.90"""
    if date_diff_days <= 0:
        return 1.00
    if tolerance_days <= 1:
        return 0.95
    span = 0.99 - 0.90
    conf = 0.99 - (date_diff_days - 1) * (span / (tolerance_days - 1))
    return round(max(conf, 0.90), 2)


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

        # 自动识别金额列、日期列、摘要列、流水号列
        bank_amount_col = _find_column(bank_df, ["金额", "发生额", "交易金额", "借方", "贷方"])
        bank_date_col = _find_column(bank_df, ["日期", "交易日期", "记账日期", "入账日期"])
        bank_memo_col = _find_column(bank_df, ["摘要", "交易摘要", "用途", "备注", "附言", "摘要说明"])
        bank_serial_col = _find_column(bank_df, ["流水号", "交易流水号", "交易流水", "凭证号", "业务流水号"])
        ledger_amount_col = _find_column(ledger_df, ["金额", "发生额", "借方", "贷方"])
        ledger_date_col = _find_column(ledger_df, ["日期", "记账日期", "凭证日期"])
        ledger_memo_col = _find_column(ledger_df, ["摘要", "凭证摘要", "用途", "备注", "摘要说明"])
        ledger_serial_col = _find_column(ledger_df, ["凭证号", "凭证字号", "流水号", "记账凭证号"])

        if not bank_amount_col:
            return {"status": "error", "message": f"银行对账单中找不到金额列，可用列: {list(bank_df.columns)}"}
        if not ledger_amount_col:
            return {"status": "error", "message": f"日记账中找不到金额列，可用列: {list(ledger_df.columns)}"}

        # 转换日期
        if bank_date_col:
            bank_df[bank_date_col] = pd.to_datetime(bank_df[bank_date_col], errors="coerce")
        if ledger_date_col:
            ledger_df[ledger_date_col] = pd.to_datetime(ledger_df[ledger_date_col], errors="coerce")

        # ── 重复流水号检测（数据质量雷，不参与自动匹配）──
        dup_bank_idx = _detect_duplicates(bank_df, bank_serial_col)
        dup_ledger_idx = _detect_duplicates(ledger_df, ledger_serial_col)

        # 预解析金额为 Decimal
        bank_amts = {i: _to_decimal(bank_df.at[i, bank_amount_col]) for i in bank_df.index}
        ledger_amts = {j: _to_decimal(ledger_df.at[j, ledger_amount_col]) for j in ledger_df.index}

        bank_matched = {i: False for i in bank_df.index}
        ledger_matched = {j: False for j in ledger_df.index}
        # 重复项先占位为"已处理"，不让它进自动匹配
        for i in dup_bank_idx:
            bank_matched[i] = True
        for j in dup_ledger_idx:
            ledger_matched[j] = True

        matches = []  # 每条含 confidence / match_type / date_diff
        tolerance = timedelta(days=date_tolerance_days)
        cent = Decimal("0.01")

        def _try_match(require_same_day: bool):
            for i in bank_df.index:
                if bank_matched[i]:
                    continue
                b_amt = bank_amts.get(i)
                if b_amt is None:
                    continue
                best_j = None
                best_diff = None
                for j in ledger_df.index:
                    if ledger_matched[j]:
                        continue
                    l_amt = ledger_amts.get(j)
                    if l_amt is None:
                        continue
                    if abs(b_amt - l_amt) >= cent:
                        continue
                    # 日期判断
                    diff_days = 0
                    if bank_date_col and ledger_date_col:
                        bd = bank_df.at[i, bank_date_col]
                        ld = ledger_df.at[j, ledger_date_col]
                        if pd.notna(bd) and pd.notna(ld):
                            delta = abs(bd - ld)
                            diff_days = delta.days
                            if require_same_day:
                                if diff_days != 0:
                                    continue
                            else:
                                if delta > tolerance:
                                    continue
                    if best_diff is None or diff_days < best_diff:
                        best_diff = diff_days
                        best_j = j
                        if diff_days == 0:
                            break
                if best_j is not None:
                    bank_matched[i] = True
                    ledger_matched[best_j] = True
                    conf = _confidence(best_diff or 0, date_tolerance_days)
                    matches.append({
                        "bank_index": int(i),
                        "ledger_index": int(best_j),
                        "金额": float(bank_amts[i]),
                        "日期差天数": int(best_diff or 0),
                        "置信度": conf,
                        "匹配类型": "精确(同日)" if (best_diff or 0) == 0 else "容差(日期偏移)",
                    })

        # Pass 1：精确同日优先
        _try_match(require_same_day=True)
        # Pass 2：日期容差兜底
        if bank_date_col and ledger_date_col and date_tolerance_days > 0:
            _try_match(require_same_day=False)

        # 未达账项（排除重复项后剩下的真未匹配）
        unmatched_bank_idx = [i for i in bank_df.index if not bank_matched[i]]
        unmatched_ledger_idx = [j for j in ledger_df.index if not ledger_matched[j]]
        unmatched_bank = bank_df.loc[unmatched_bank_idx].copy()
        unmatched_ledger = ledger_df.loc[unmatched_ledger_idx].copy()

        # 未匹配项业务性质分类
        if len(unmatched_bank) > 0:
            unmatched_bank["性质判断"] = [
                _classify_unmatched(bank_df.at[i, bank_memo_col] if bank_memo_col else "", "bank")
                for i in unmatched_bank_idx
            ]
        if len(unmatched_ledger) > 0:
            unmatched_ledger["性质判断"] = [
                _classify_unmatched(ledger_df.at[j, ledger_memo_col] if ledger_memo_col else "", "ledger")
                for j in unmatched_ledger_idx
            ]

        # 重复流水明细
        dup_bank_df = bank_df.loc[dup_bank_idx].copy() if dup_bank_idx else pd.DataFrame()
        dup_ledger_df = ledger_df.loc[dup_ledger_idx].copy() if dup_ledger_idx else pd.DataFrame()

        # 计算余额
        bank_balance = float(sum((v for v in bank_amts.values() if v is not None), Decimal("0")))
        ledger_balance = float(sum((v for v in ledger_amts.values() if v is not None), Decimal("0")))

        # 置信度计数
        exact_cnt = sum(1 for m in matches if m["匹配类型"].startswith("精确"))
        tol_cnt = len(matches) - exact_cnt

        # 输出
        bank_path = Path(bank_statement_path)
        if output_path is None:
            output_path = bank_path.parent / "调节表结果.xlsx"
        else:
            output_path = Path(output_path)

        try:
            with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
                # 匹配明细（带置信度）
                if matches:
                    match_rows = []
                    for m in matches:
                        bi, lj = m["bank_index"], m["ledger_index"]
                        row = {
                            "匹配类型": m["匹配类型"],
                            "置信度": m["置信度"],
                            "日期差天数": m["日期差天数"],
                            "金额": m["金额"],
                        }
                        if bank_date_col:
                            row["银行日期"] = bank_df.at[bi, bank_date_col]
                        if bank_memo_col:
                            row["银行摘要"] = bank_df.at[bi, bank_memo_col]
                        if ledger_date_col:
                            row["总账日期"] = ledger_df.at[lj, ledger_date_col]
                        if ledger_memo_col:
                            row["总账摘要"] = ledger_df.at[lj, ledger_memo_col]
                        match_rows.append(row)
                    pd.DataFrame(match_rows).to_excel(writer, sheet_name="匹配明细", index=False)

                if len(unmatched_bank) > 0:
                    unmatched_bank.to_excel(writer, sheet_name="银行有企业无", index=False)
                if len(unmatched_ledger) > 0:
                    unmatched_ledger.to_excel(writer, sheet_name="企业有银行无", index=False)
                if len(dup_bank_df) > 0:
                    dup_bank_df.to_excel(writer, sheet_name="银行重复流水", index=False)
                if len(dup_ledger_df) > 0:
                    dup_ledger_df.to_excel(writer, sheet_name="总账重复凭证", index=False)

                # 调节表摘要
                summary = pd.DataFrame({
                    "项目": [
                        "银行对账单合计", "企业日记账合计",
                        "匹配合计笔数", "  其中-精确同日(100%)", "  其中-日期容差匹配",
                        "银行未匹配笔数", "企业未匹配笔数",
                        "银行重复流水笔数", "总账重复凭证笔数",
                    ],
                    "金额/数量": [
                        bank_balance, ledger_balance,
                        len(matches), exact_cnt, tol_cnt,
                        len(unmatched_bank), len(unmatched_ledger),
                        len(dup_bank_idx), len(dup_ledger_idx),
                    ],
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
            "matched_exact": int(exact_cnt),
            "matched_tolerance": int(tol_cnt),
            "unmatched_bank_count": int(len(unmatched_bank)),
            "unmatched_ledger_count": int(len(unmatched_ledger)),
            "duplicate_bank_count": int(len(dup_bank_idx)),
            "duplicate_ledger_count": int(len(dup_ledger_idx)),
            "serial_check": bool(bank_serial_col or ledger_serial_col),
            "output_file": str(output_path),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}


def _detect_duplicates(df: pd.DataFrame, serial_col: str) -> list:
    """检测重复流水号/凭证号，返回除首次出现外的重复行索引列表。
    无流水号列时返回空（不做重复检测）。"""
    if not serial_col or serial_col not in df.columns:
        return []
    dup_idx = []
    seen = {}
    for i in df.index:
        key = str(df.at[i, serial_col]).strip()
        if not key or key.lower() in ("nan", "none", ""):
            continue
        if key in seen:
            dup_idx.append(i)
        else:
            seen[key] = i
    return dup_idx


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
