"""
固定资产折旧重算工具

输入：固定资产明细表（Excel/CSV）
功能：根据折旧方法重新计算每项资产至检查日的累计折旧，与账面累计折旧比对，找出差异。

支持的折旧方法：
- straight_line：年限平均法（直线法）
- double_declining：双倍余额递减法
- sum_of_years：年数总和法
- units_of_production：工作量法（需提供本期工作量和总工作量）
"""
from pathlib import Path
from datetime import datetime, date


def check_depreciation(
    file_path: str,
    check_date: str,
    method_column: str = "折旧方法",
    cost_column: str = "原值",
    salvage_rate_column: str = "净残值率",
    useful_life_column: str = "使用年限",
    start_date_column: str = "入账日期",
    book_accumulated_column: str = "账面累计折旧",
    name_column: str = "资产名称",
    sheet_name: str = None,
    output_path: str = None,
) -> dict:
    """
    固定资产折旧重算。

    Args:
        file_path: 固定资产明细表（Excel/CSV）
        check_date: 检查截止日期 YYYY-MM-DD
        method_column: 折旧方法列名（值为 straight_line/double_declining/sum_of_years/units_of_production）
        cost_column: 原值列名
        salvage_rate_column: 净残值率列名（如 5 表示 5%，0.05 也行）
        useful_life_column: 使用年限列名（年）
        start_date_column: 开始计提折旧的日期列名
        book_accumulated_column: 账面累计折旧列名（用于比对）
        name_column: 资产名称列名
        sheet_name: Excel 工作表名（可选）
        output_path: 输出文件路径（可选）

    Returns:
        dict: {
            "status": "success"|"error",
            "summary": {"总资产数": N, "差异资产数": M, "差异总额": X},
            "differences": [差异明细],
            "all_results": [所有资产重算结果],
            "output_file": str
        }
    """
    try:
        import pandas as pd

        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在：{file_path}"}

        # 读取
        if fp.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(fp, sheet_name=sheet_name or 0)
        elif fp.suffix.lower() == ".csv":
            df = pd.read_csv(fp)
        else:
            return {"status": "error", "message": f"不支持的格式：{fp.suffix}"}

        # 验证必要列
        required = [cost_column, useful_life_column, start_date_column]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return {"status": "error", "message": f"缺少必要列：{missing}，可用列：{list(df.columns)}"}

        # 解析检查日期
        try:
            chk = datetime.strptime(check_date, "%Y-%m-%d").date()
        except ValueError:
            return {"status": "error", "message": f"check_date 格式错误：{check_date}，应为 YYYY-MM-DD"}

        # 重算
        results = []
        for idx, row in df.iterrows():
            asset = {
                "资产名称": str(row.get(name_column, f"行{idx+2}")) if name_column in df.columns else f"行{idx+2}",
                "原值": float(row[cost_column]),
                "使用年限": float(row[useful_life_column]),
            }

            # 输入校验：使用年限必须 > 0，原值不能为负
            if asset["使用年限"] <= 0:
                results.append({**asset, "状态": "错误", "错误信息": f"使用年限必须大于 0（当前 {asset['使用年限']}）"})
                continue
            if asset["原值"] < 0:
                results.append({**asset, "状态": "错误", "错误信息": f"原值不能为负（当前 {asset['原值']}）"})
                continue

            # 解析开始日期
            start = row[start_date_column]
            if isinstance(start, str):
                try:
                    start = datetime.strptime(start, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        start = datetime.strptime(start, "%Y/%m/%d").date()
                    except ValueError:
                        results.append({**asset, "状态": "错误", "错误信息": f"开始日期格式错误：{start}"})
                        continue
            elif hasattr(start, "date"):
                start = start.date() if hasattr(start, "date") else start
            
            asset["开始日期"] = start.isoformat() if hasattr(start, "isoformat") else str(start)

            # 净残值率
            salvage_rate = 0.0
            if salvage_rate_column in df.columns:
                v = row.get(salvage_rate_column, 0)
                if pd.notna(v):
                    salvage_rate = float(v)
                    # 如果输入是百分比形式（如 5），转为小数
                    if salvage_rate > 1:
                        salvage_rate = salvage_rate / 100

            # 折旧方法（默认直线法）
            method = "straight_line"
            if method_column in df.columns:
                m = row.get(method_column, "")
                if pd.notna(m) and str(m).strip():
                    method = str(m).strip().lower()
            asset["折旧方法"] = method
            asset["净残值率"] = f"{salvage_rate * 100:.2f}%"

            # 计算已使用月数（从下月起计提，至检查月止）
            months_used = _months_between(start, chk)
            total_months = asset["使用年限"] * 12
            months_used = min(months_used, total_months)
            asset["已使用月数"] = months_used

            # 计算重算累计折旧
            cost = asset["原值"]
            salvage = cost * salvage_rate
            depreciable = cost - salvage

            try:
                if method == "straight_line":
                    monthly = depreciable / total_months if total_months > 0 else 0
                    recalc = monthly * months_used

                elif method == "double_declining":
                    # 双倍余额递减法（年度）
                    recalc = _double_declining(cost, salvage, asset["使用年限"], months_used)

                elif method == "sum_of_years":
                    # 年数总和法
                    recalc = _sum_of_years(depreciable, asset["使用年限"], months_used)

                elif method == "units_of_production":
                    # 工作量法 — 需要工作量列（暂不支持，标注）
                    asset["状态"] = "工作量法需专用工具"
                    asset["重算累计折旧"] = None
                    asset["账面累计折旧"] = None
                    asset["差异"] = None
                    results.append(asset)
                    continue

                else:
                    asset["状态"] = f"未知折旧方法：{method}"
                    results.append(asset)
                    continue

            except Exception as e:
                asset["状态"] = f"计算错误：{e}"
                results.append(asset)
                continue

            asset["重算累计折旧"] = round(recalc, 2)

            # 与账面对比
            if book_accumulated_column in df.columns:
                book_val = row.get(book_accumulated_column, 0)
                book_val = float(book_val) if pd.notna(book_val) else 0
                asset["账面累计折旧"] = round(book_val, 2)
                diff = round(recalc - book_val, 2)
                asset["差异"] = diff
                asset["差异_绝对值"] = abs(diff)
                # 容差 1 元（防止小数舍入）
                asset["状态"] = "正常" if abs(diff) <= 1 else ("账面少计" if diff > 0 else "账面多计")
            else:
                asset["账面累计折旧"] = None
                asset["差异"] = None
                asset["状态"] = "重算完成（无账面数据可对比）"

            results.append(asset)

        # 汇总
        total = len(results)
        diffs = [r for r in results if r.get("状态") in ("账面少计", "账面多计")]
        diff_total = round(sum(r.get("差异", 0) or 0 for r in diffs), 2)

        summary = {
            "总资产数": total,
            "差异资产数": len(diffs),
            "差异总额": diff_total,
            "检查日期": check_date,
        }

        # 保存
        output_file = None
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            df_out = pd.DataFrame(results)
            if out.suffix.lower() in (".xlsx", ".xls"):
                df_out.to_excel(str(out), index=False)
            else:
                df_out.to_csv(str(out), index=False, encoding="utf-8-sig")
            output_file = str(out)

        return {
            "status": "success",
            "summary": summary,
            "differences": diffs[:50],  # 限制返回条数
            "all_results": results[:100],
            "output_file": output_file,
            "message": f"重算 {total} 项资产，发现差异 {len(diffs)} 项，差异总额 {diff_total:.2f} 元",
        }

    except ImportError:
        return {"status": "error", "message": "pandas 未安装"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 辅助函数 ──

def _months_between(start, end) -> int:
    """计算两个日期之间的完整月数（从次月起至当月止）"""
    if not isinstance(start, date):
        start = start.date() if hasattr(start, "date") else start
    if not isinstance(end, date):
        end = end.date() if hasattr(end, "date") else end
    if end < start:
        return 0
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0, months)


def _double_declining(cost: float, salvage: float, life_years: float, months_used: int) -> float:
    """
    双倍余额递减法（按年计算，最后两年改用直线法）
    返回累计折旧
    """
    rate = 2 / life_years
    accumulated = 0
    book_value = cost
    full_years = int(life_years)
    months_used_full_years = months_used // 12
    remaining_months = months_used % 12

    # 最后两年改用直线法
    switch_year = max(0, full_years - 2)

    for year in range(min(months_used_full_years + 1, full_years)):
        if year < switch_year:
            # 双倍余额递减
            year_dep = book_value * rate
        else:
            # 最后两年直线法（按剩余可折旧额平均）
            remaining_depreciable = book_value - salvage
            remaining_years = full_years - year
            year_dep = remaining_depreciable / remaining_years if remaining_years > 0 else 0

        if year < months_used_full_years:
            # 满一年
            accumulated += year_dep
            book_value -= year_dep
        else:
            # 不满一年，按月份分摊
            if remaining_months > 0:
                accumulated += year_dep * remaining_months / 12
                book_value -= year_dep * remaining_months / 12
            break

    return min(accumulated, cost - salvage)


def _sum_of_years(depreciable: float, life_years: float, months_used: int) -> float:
    """
    年数总和法（按月精度）
    返回累计折旧
    """
    full_years = int(life_years)
    sum_years = full_years * (full_years + 1) / 2
    accumulated = 0

    months_per_year = 12
    for year in range(1, full_years + 1):
        # 第 year 年的折旧率 = (剩余年限 / 年数总和)
        rate = (full_years - year + 1) / sum_years
        year_dep = depreciable * rate

        # 这一年用了多少个月
        year_start_month = (year - 1) * months_per_year
        year_end_month = year * months_per_year

        if months_used <= year_start_month:
            break
        elif months_used >= year_end_month:
            accumulated += year_dep
        else:
            # 部分月份
            partial_months = months_used - year_start_month
            accumulated += year_dep * partial_months / 12
            break

    return min(accumulated, depreciable)
