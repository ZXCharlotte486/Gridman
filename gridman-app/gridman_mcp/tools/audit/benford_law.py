"""本福特定律检验工具

功能：
对财务数据进行首位数字分布检验，识别可能的数据异常。
"""
import pandas as pd
import math
from pathlib import Path

from gridman_mcp.tools._shared.io import read_table


def check_benford(
    file_path: str,
    amount_column: str,
    output_path: str = None,
) -> dict:
    """本福特定律检验。

    Args:
        file_path: 数据文件 Excel/CSV 路径
        amount_column: 金额列名
        output_path: 输出文件路径

    Returns:
        检验结果
    """
    try:
        try:
            df = read_table(file_path)
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}
        except ValueError as e:
            return {"status": "error", "message": str(e)}

        if amount_column not in df.columns:
            return {"status": "error", "message": f"找不到列 '{amount_column}'，可用列: {list(df.columns)}"}

        # 提取首位数字
        amounts = pd.to_numeric(df[amount_column], errors="coerce").dropna()
        amounts = amounts[amounts.abs() > 0]  # 排除零值

        if len(amounts) < 100:
            return {
                "status": "error",
                "message": f"样本量仅 {len(amounts)} 条，本福特定律检验建议至少 500 条以上才有统计意义",
            }

        first_digits = amounts.abs().apply(lambda x: int(str(x).lstrip("0").lstrip(".")[0]) if str(x).lstrip("0").lstrip(".") else 0)
        first_digits = first_digits[first_digits.between(1, 9)]

        # 统计实际频率
        actual_counts = first_digits.value_counts().sort_index()
        total = len(first_digits)

        # 本福特理论分布
        benford_expected = {d: math.log10(1 + 1 / d) for d in range(1, 10)}

        # 构建对比表
        results = []
        chi_square = 0

        for digit in range(1, 10):
            actual_count = int(actual_counts.get(digit, 0))
            actual_freq = actual_count / total if total > 0 else 0
            expected_freq = benford_expected[digit]
            expected_count = expected_freq * total

            # 卡方统计量
            if expected_count > 0:
                chi_sq_component = (actual_count - expected_count) ** 2 / expected_count
            else:
                chi_sq_component = 0
            chi_square += chi_sq_component

            # Z 检验
            z_score = (actual_freq - expected_freq) / math.sqrt(expected_freq * (1 - expected_freq) / total) if total > 0 else 0

            # 判断是否显著偏离（|Z| > 1.96 为 95% 置信水平）
            significant = abs(z_score) > 1.96

            results.append({
                "首位数字": digit,
                "实际次数": actual_count,
                "实际频率": round(actual_freq * 100, 2),
                "理论频率": round(expected_freq * 100, 2),
                "偏离度": round((actual_freq - expected_freq) * 100, 2),
                "Z值": round(z_score, 3),
                "显著偏离": "是" if significant else "否",
            })

        result_df = pd.DataFrame(results)

        # 卡方检验结论（自由度=8，95%临界值=15.507）
        chi_square_critical = 15.507
        overall_conclusion = "通过" if chi_square < chi_square_critical else "未通过（存在显著偏离）"

        # 输出
        fp = Path(file_path)
        if output_path is None:
            output_path = fp.parent / f"本福特检验结果.xlsx"
        else:
            output_path = Path(output_path)

        try:
            result_df.to_excel(output_path, index=False)
        except PermissionError:
            return {"status": "error", "message": f"输出文件被占用，请先在 Excel 中关闭：{output_path}"}

        # 找出显著偏离的数字
        significant_digits = [r["首位数字"] for r in results if r["显著偏离"] == "是"]

        return {
            "status": "success",
            "message": "本福特定律检验完成",
            "sample_size": int(total),
            "chi_square": round(chi_square, 3),
            "chi_square_critical": chi_square_critical,
            "overall_result": overall_conclusion,
            "significant_deviations": significant_digits,
            "output_file": str(output_path),
            "interpretation": (
                "数据分布符合本福特定律，未发现明显异常。"
                if overall_conclusion == "通过"
                else f"数据分布显著偏离本福特定律，首位数字 {significant_digits} 存在异常，建议进一步调查。"
            ),
        }

    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "trace": traceback.format_exc()}
