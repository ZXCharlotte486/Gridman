"""
审计抽样工具

支持三种抽样方法：
- random：随机抽样（每个项目被抽中概率相等）
- systematic：系统抽样（按等距间隔抽取）
- mus：货币单位抽样（PPS抽样，金额越大被抽中概率越高）

适用场景：
- 实质性程序的细节测试
- 控制测试的样本选取
- 函证样本选取
"""
import random
from pathlib import Path


def generate_sample(
    file_path: str,
    method: str = "random",
    sample_size: int = None,
    amount_column: str = None,
    risk_level: str = "medium",
    sheet_name: str = None,
    output_path: str = None,
    random_seed: int = None,
) -> dict:
    """
    生成审计抽样方案。

    Args:
        file_path: 总体数据文件（Excel/CSV）
        method: 抽样方法 random / systematic / mus
        sample_size: 样本量（不指定时根据 risk_level 自动计算）
        amount_column: 金额列名（mus 必需，其他方法用于显示）
        risk_level: 风险等级 low / medium / high（用于自动计算样本量）
        sheet_name: Excel 工作表名
        output_path: 输出文件路径
        random_seed: 随机种子（可重现的抽样）

    Returns:
        dict: {
            "status": "success"|"error",
            "method": 抽样方法,
            "population_size": 总体规模,
            "sample_size": 实际样本量,
            "selection_criteria": 选取标准说明,
            "sample": [选中的样本],
            "output_file": str
        }
    """
    try:
        import pandas as pd

        fp = Path(file_path)
        if not fp.exists():
            return {"status": "error", "message": f"文件不存在：{file_path}"}

        if fp.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(fp, sheet_name=sheet_name or 0)
        elif fp.suffix.lower() == ".csv":
            df = pd.read_csv(fp)
        else:
            return {"status": "error", "message": f"不支持的格式：{fp.suffix}"}

        population_size = len(df)
        if population_size == 0:
            return {"status": "error", "message": "文件为空"}

        # 计算样本量
        if sample_size is None:
            sample_size = _calculate_sample_size(population_size, risk_level)
        sample_size = min(sample_size, population_size)

        # 设置随机种子
        if random_seed is not None:
            random.seed(random_seed)

        # 执行抽样
        method = method.lower().strip()
        if method == "random":
            sample_df, criteria = _random_sample(df, sample_size)

        elif method == "systematic":
            sample_df, criteria = _systematic_sample(df, sample_size)

        elif method == "mus":
            if not amount_column:
                return {"status": "error", "message": "MUS 抽样必须指定 amount_column"}
            if amount_column not in df.columns:
                return {"status": "error", "message": f"列 '{amount_column}' 不存在"}
            sample_df, criteria = _mus_sample(df, sample_size, amount_column)

        else:
            return {"status": "error", "message": f"不支持的抽样方法：{method}，可选：random/systematic/mus"}

        # 添加抽样序号列
        sample_df = sample_df.copy()
        sample_df.insert(0, "抽样序号", range(1, len(sample_df) + 1))

        # 保存
        output_file = None
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix.lower() in (".xlsx", ".xls"):
                with pd.ExcelWriter(str(out), engine="openpyxl") as writer:
                    sample_df.to_excel(writer, sheet_name="抽样样本", index=False)
                    # 写抽样记录表
                    record = pd.DataFrame([
                        {"项目": "抽样方法", "值": method},
                        {"项目": "总体规模", "值": population_size},
                        {"项目": "样本量", "值": sample_size},
                        {"项目": "选取标准", "值": criteria},
                        {"项目": "随机种子", "值": random_seed if random_seed is not None else "未设置"},
                        {"项目": "风险等级", "值": risk_level},
                    ])
                    record.to_excel(writer, sheet_name="抽样记录", index=False)
            else:
                sample_df.to_csv(str(out), index=False, encoding="utf-8-sig")
            output_file = str(out)

        # 计算金额覆盖率（如果有金额列）
        amount_coverage = None
        if amount_column and amount_column in df.columns:
            try:
                total_amount = df[amount_column].astype(float).sum()
                sample_amount = sample_df[amount_column].astype(float).sum()
                if total_amount > 0:
                    amount_coverage = f"{sample_amount / total_amount * 100:.2f}%"
            except (ValueError, TypeError):
                pass

        return {
            "status": "success",
            "method": method,
            "population_size": population_size,
            "sample_size": len(sample_df),
            "selection_criteria": criteria,
            "amount_coverage": amount_coverage,
            "sample": sample_df.head(50).to_dict(orient="records"),
            "output_file": output_file,
            "message": f"使用 {method} 方法从 {population_size} 项总体中抽取 {len(sample_df)} 个样本",
        }

    except ImportError:
        return {"status": "error", "message": "pandas 未安装"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 三种抽样方法 ──

def _random_sample(df, sample_size):
    """随机抽样"""
    indices = sorted(random.sample(range(len(df)), sample_size))
    sample_df = df.iloc[indices].copy()
    criteria = f"使用Python random.sample从 {len(df)} 项总体中随机抽取 {sample_size} 个项目，每个项目被抽中概率相等"
    return sample_df, criteria


def _systematic_sample(df, sample_size):
    """系统抽样（等距）"""
    population_size = len(df)
    interval = population_size // sample_size
    if interval < 1:
        interval = 1

    # 随机起点（0 到 interval-1）
    start = random.randint(0, interval - 1)

    indices = []
    for i in range(sample_size):
        idx = start + i * interval
        if idx >= population_size:
            break
        indices.append(idx)

    sample_df = df.iloc[indices].copy()
    criteria = f"使用系统抽样：从总体 {population_size} 项中按间隔 {interval} 等距抽取，随机起点 {start+1}（第{start+1}项），实际抽取 {len(indices)} 个样本"
    return sample_df, criteria


def _mus_sample(df, sample_size, amount_column):
    """货币单位抽样（PPS）— 按金额加权抽样"""
    # 转换为浮点数并取绝对值（避免负数干扰）
    amounts = df[amount_column].astype(float).abs()
    total = amounts.sum()

    if total <= 0:
        return _random_sample(df, sample_size)

    # 计算抽样间隔
    interval = total / sample_size

    # 累计金额
    cumulative = amounts.cumsum().reset_index(drop=True)

    # 随机起点（0 到 interval）
    start = random.uniform(0, interval)

    selected_indices = []
    target = start
    for _ in range(sample_size):
        if target > total:
            break
        # 找到累计金额首次超过 target 的位置
        idx = cumulative.searchsorted(target, side="left")
        if idx >= len(df):
            break
        selected_indices.append(idx)
        target += interval

    # 去重保持顺序
    seen = set()
    unique_indices = []
    for i in selected_indices:
        if i not in seen:
            seen.add(i)
            unique_indices.append(i)

    sample_df = df.iloc[unique_indices].copy()
    criteria = (
        f"使用货币单位抽样（MUS/PPS）：金额列 '{amount_column}'，"
        f"总金额 {total:.2f}，抽样间隔 {interval:.2f}，随机起点 {start:.2f}，"
        f"金额越大的项目被抽中概率越高，实际抽取 {len(unique_indices)} 个样本"
    )
    return sample_df, criteria


def _calculate_sample_size(population_size: int, risk_level: str) -> int:
    """根据风险等级估算样本量（简化版，实务中应根据 CSA 准则附录细算）"""
    risk_factors = {
        "low": 0.05,    # 低风险 5%
        "medium": 0.10,  # 中等风险 10%
        "high": 0.15,    # 高风险 15%
    }
    rate = risk_factors.get(risk_level.lower(), 0.10)

    # 最小样本量参考 CSA 1314 附录（简化）
    if population_size <= 50:
        return max(int(population_size * rate * 2), 5)
    elif population_size <= 250:
        return max(int(population_size * rate), 25)
    elif population_size <= 1000:
        return max(int(population_size * rate * 0.5), 40)
    else:
        return max(int(population_size * rate * 0.2), 60)
