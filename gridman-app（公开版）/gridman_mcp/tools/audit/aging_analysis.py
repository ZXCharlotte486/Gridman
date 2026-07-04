"""往来账龄分析工具

功能：
- mode="calc"  ：根据往来明细数据，按先进先出法计算各客商的账龄分布（生成）。
- mode="verify"：根据多年账龄表，重算滚动结转并做四步自洽校验（复核）。

两条路径同属"账龄"域：一个生成、一个复核，合并在同一工具入口下。
复核逻辑由 aging-verify 技能的实现修订而来（已修复终端段结转丢失、
负方向双算、零数据假报通过三处缺陷）。
"""
import pandas as pd
from pathlib import Path
from datetime import datetime

from gridman_mcp.tools._shared.io import read_table


# ── 账龄复核（verify）共用常量与结转逻辑 ───────────────────────────
_AGING_KEYS = ["1year", "1-2year", "2-3year", "3-4year", "4-5year", "5year+"]
_AGE_MAP = {
    "1year": "1-2year", "1-2year": "2-3year", "2-3year": "3-4year",
    "3-4year": "4-5year", "4-5year": "5year+",
}
_AGING_LABELS = {
    "1year": "1年以内", "1-2year": "1-2年", "2-3year": "2-3年",
    "3-4year": "3-4年", "4-5year": "4-5年", "5year+": "5年以上",
}


def _age_forward(oa: dict) -> dict:
    """各账龄段向后滚动一年。5年以上为吸收态：原余额留存并与从 4-5年
    滚入的部分累加（绝不被覆盖丢失）。"""
    aged = {}
    for s, t in _AGE_MAP.items():
        if oa.get(s, 0):
            aged[t] = aged.get(t, 0) + oa[s]
    if oa.get("5year+", 0):
        aged["5year+"] = aged.get("5year+", 0) + oa["5year+"]
    return aged


def _apply_decrease_fifo(aged: dict, dec: float) -> dict:
    """按先进先出冲减（最老的账龄段先冲）；冲完所有段仍有剩余则
    在 1年以内 形成负数（尾部转负）。"""
    rem = dec
    for ab in reversed(_AGING_KEYS):
        if rem <= 0 or ab not in aged:
            continue
        v = aged[ab]
        if v <= 0:
            continue
        if rem >= v:
            rem -= v
            aged[ab] = 0
        else:
            aged[ab] = v - rem
            rem = 0
    if rem > 0:
        aged["1year"] = aged.get("1year", 0) - rem
    return aged


def _expected_closing(atype: str, oa: dict, dr: float, cr: float) -> dict:
    """重算期末各账龄段的期望值。atype: AR/AP（Prepay 归 AR，PreRcv 归 AP）。"""
    top = sum(oa.values())
    if atype == "AR":           # 资产：借增贷减
        inc_raw, dec_raw = dr, cr
    else:                        # 负债：贷增借减
        inc_raw, dec_raw = cr, dr

    increase = max(0, inc_raw)
    decrease = max(0, dec_raw) + max(0, -inc_raw)   # 减少方 + 增加方的负数
    net_change = inc_raw - dec_raw

    if top < 0:
        aged = _age_forward(oa)
        net = sum(aged.values()) + net_change
        if net > 0:
            aged = {"1year": net}
        else:
            for ab in _AGING_KEYS:
                if aged.get(ab, 0) != 0:
                    aged[ab] = net
                    break
            else:
                aged = {"5year+": net}
    elif top > 0 and decrease >= top:
        net = top + net_change
        aged = {"1year": net} if net > 0 else _age_forward({"1year": net})
    else:
        aged = _age_forward(oa)
        aged["1year"] = aged.get("1year", 0) + increase
        aged = _apply_decrease_fifo(aged, decrease)
    return aged


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


def _nz(x) -> float:
    """容错取数：空/NaN/#N/A → 0.0。"""
    if x is None:
        return 0.0
    s = str(x).strip()
    if s == "" or s.upper() == "#N/A" or s.lower() == "nan":
        return 0.0
    try:
        return float(s.replace(",", "").replace(" ", ""))
    except ValueError:
        return 0.0


# 期初/期末各账龄段的候选列名（按 _AGING_KEYS 顺序）
_OPEN_COL_CANDS = [
    ["期初1年内", "期初1年以内", "年初1年内", "年初1年以内"],
    ["期初1-2年", "年初1-2年"],
    ["期初2-3年", "年初2-3年"],
    ["期初3-4年", "年初3-4年"],
    ["期初4-5年", "年初4-5年"],
    ["期初5年以上", "期初5年", "年初5年以上"],
]
_CLOSE_COL_CANDS = [
    ["期末1年以内", "期末1年内", "1年以内"],
    ["期末1-2年", "1-2年"],
    ["期末2-3年", "2-3年"],
    ["期末3-4年", "3-4年"],
    ["期末4-5年", "4-5年"],
    ["期末5年以上", "5年以上"],
]


def _find_bracket_col(df, cands, exclude_open=False):
    """在 df 中找某一账龄段列。exclude_open=True 时跳过含'期初/年初'的列
    （用于期末列识别，避免把 '期初1-2年' 误当 '1-2年'）。"""
    for c in cands:
        for actual in df.columns:
            name = str(actual)
            if exclude_open and ("期初" in name or "年初" in name):
                continue
            if c == name or c in name:
                return actual
    return None


def verify_aging(
    file_path: str,
    account_type: str = "AR",
    output_path: str = None,
    sheet_name: str = None,
) -> dict:
    """账龄表四步复核（mode="verify"）。

    输入：多年/多客户账龄表，一行一个 (年度, 客户)，含期初各账龄段、
    借贷发生额、期末各账龄段。
    四步校验：①余额勾稽 ②跨年期初=上年期末（合计）③逐段结转 ④滚动逻辑。

    Args:
        file_path: 账龄表 Excel/CSV
        account_type: AR/AP/Prepay/PreRcv（资产类借增贷减，负债类贷增借减）
        output_path: 输出报告路径
        sheet_name: Excel sheet 名（可选）
    """
    try:
        atype_raw = str(account_type).upper()
        if atype_raw in ("AR", "PREPAY", "应收", "预付"):
            atype = "AR"
        elif atype_raw in ("AP", "PRERCV", "应付", "预收"):
            atype = "AP"
        else:
            return {"status": "error",
                    "message": f"account_type 无法识别：{account_type}，应为 AR/AP/Prepay/PreRcv"}

        try:
            df = read_table(file_path, sheet_name=sheet_name)
        except (FileNotFoundError, ValueError) as e:
            return {"status": "error", "message": str(e)}

        year_col = _find_column(df, ["年度", "年份", "年", "会计年度"])
        name_col = _find_column(df, ["客户", "客户名称", "对方名称", "对方单位",
                                     "往来单位", "供应商", "明细", "单位名称"])
        op_bal_col = _find_column(df, ["期初未审余额", "期初余额", "年初余额", "期初未审"])
        dr_col = _find_column(df, ["借方发生", "借方发生额", "借方"])
        cr_col = _find_column(df, ["贷方发生", "贷方发生额", "贷方"])

        if not name_col:
            return {"status": "error", "message": f"找不到客户/对方名称列，可用列: {list(df.columns)}"}

        open_cols = [_find_bracket_col(df, c) for c in _OPEN_COL_CANDS]
        close_cols = [_find_bracket_col(df, c, exclude_open=True) for c in _CLOSE_COL_CANDS]
        if all(c is None for c in open_cols) or all(c is None for c in close_cols):
            return {"status": "error",
                    "message": f"找不到期初或期末账龄分段列，可用列: {list(df.columns)}"}

        # 逐行解析为结构化条目
        data = {}   # year -> name -> {oa, dr, cr, ca}
        for _, r in df.iterrows():
            name = str(r[name_col]).strip()
            if not name or name in ("合计", "小计", "总计", "nan"):
                continue
            yr = int(_nz(r[year_col])) if year_col else 0
            oa = {k: _nz(r[open_cols[i]]) if open_cols[i] else 0.0
                  for i, k in enumerate(_AGING_KEYS)}
            ca = {k: _nz(r[close_cols[i]]) if close_cols[i] else 0.0
                  for i, k in enumerate(_AGING_KEYS)}
            dr = _nz(r[dr_col]) if dr_col else 0.0
            cr = _nz(r[cr_col]) if cr_col else 0.0
            data.setdefault(yr, {})[name] = {"oa": oa, "dr": dr, "cr": cr, "ca": ca}

        n_items = sum(len(v) for v in data.values())
        if n_items == 0:
            return {"status": "error",
                    "message": "未解析到任何数据行（0 行）。请检查列名、年度列、编码，复核不会在无数据时报通过。"}

        issues = []   # (年度, 客户, 步骤, 项目, 期望, 实际, 差异)
        TOL = 0.5

        def add(yr, name, step, item, exp, act):
            issues.append({"年度": yr, "客户": name, "步骤": step, "项目": item,
                           "期望值": round(exp, 2), "实际值": round(act, 2),
                           "差异": round(act - exp, 2)})

        for yr in sorted(data):
            for name, it in data[yr].items():
                op_sum = sum(it["oa"].values())
                cl_sum = sum(it["ca"].values())
                # Step1 余额勾稽
                exp_cl = op_sum + (it["dr"] - it["cr"] if atype == "AR" else it["cr"] - it["dr"])
                if abs(cl_sum - exp_cl) > TOL:
                    add(yr, name, "①余额勾稽", "期末合计", exp_cl, cl_sum)
                # Step2+3 跨年结转
                prev = data.get(yr - 1, {}).get(name)
                if prev:
                    prev_cl = sum(prev["ca"].values())
                    if abs(op_sum - prev_cl) > TOL:
                        add(yr, name, "②跨年结转", "期初合计", prev_cl, op_sum)
                    for k in _AGING_KEYS:
                        if abs(it["oa"][k] - prev["ca"][k]) > TOL:
                            add(yr, name, "③逐段结转", f"期初[{_AGING_LABELS[k]}]",
                                prev["ca"][k], it["oa"][k])
                # Step4 滚动逻辑
                exp_aged = _expected_closing(atype, it["oa"], it["dr"], it["cr"])
                for k in _AGING_KEYS:
                    e = round(exp_aged.get(k, 0), 2)
                    a = round(it["ca"].get(k, 0), 2)
                    if abs(e - a) > TOL:
                        add(yr, name, "④滚动逻辑", f"期末[{_AGING_LABELS[k]}]", e, a)

        # 输出报告
        fp = Path(file_path)
        if output_path is None:
            output_path = fp.parent / f"账龄复核_{atype}_{datetime.now():%Y%m%d}.xlsx"
        else:
            output_path = Path(output_path)

        issues_df = pd.DataFrame(issues) if issues else pd.DataFrame(
            columns=["年度", "客户", "步骤", "项目", "期望值", "实际值", "差异"])
        by_step = (issues_df.groupby("步骤").size().to_dict() if issues else {})
        summary_df = pd.DataFrame([
            {"项目": "复核条目数(年度×客户)", "值": n_items},
            {"项目": "差异条数", "值": len(issues)},
            {"项目": "①余额勾稽差异", "值": by_step.get("①余额勾稽", 0)},
            {"项目": "②跨年结转差异", "值": by_step.get("②跨年结转", 0)},
            {"项目": "③逐段结转差异", "值": by_step.get("③逐段结转", 0)},
            {"项目": "④滚动逻辑差异", "值": by_step.get("④滚动逻辑", 0)},
            {"项目": "账户类型", "值": atype},
        ])
        try:
            with pd.ExcelWriter(output_path) as w:
                summary_df.to_excel(w, sheet_name="复核摘要", index=False)
                issues_df.to_excel(w, sheet_name="差异明细", index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先关闭：{output_path}"}

        return {
            "status": "success",
            "message": "账龄复核完成" if issues else "账龄复核完成：四步全部自洽，未发现差异",
            "account_type": atype,
            "checked_items": n_items,
            "issue_count": len(issues),
            "issues_by_step": by_step,
            "output_file": str(output_path),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}
