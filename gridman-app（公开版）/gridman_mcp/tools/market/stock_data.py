"""
A 股数据查询工具 — 基于 AkShare

支持：
- 个股实时行情
- 历史 K 线数据
- 财务数据（利润表/资产负债表/现金流量表）

数据源策略（应对挂代理用户）：
═════════════════════════════════════════════════════════
古立特依赖 Kiro，Kiro 需要科学上网，所以用户基本都挂代理。
东方财富某些子域名（push2.eastmoney.com）在代理 + 海外 IP
环境下会被反爬断连。

解决方案：优先用新浪源（海外 IP 友好），失败再降级到东方财富。
- 新浪：finance.sina.com.cn         主源（代理友好）
- 东方财富：push2.eastmoney.com     备选（直连环境用）
═════════════════════════════════════════════════════════
"""
import time


def _retry(fn, max_retries=2, delay=1):
    """通用重试，间隔 1 秒"""
    last_err = None
    for i in range(max_retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            if i < max_retries - 1:
                time.sleep(delay)
    raise last_err


def _normalize_symbol_with_prefix(symbol: str) -> str:
    """
    将 6 位代码转为新浪格式（带 sh/sz/bj 前缀）。
    600 / 601 / 603 / 605 / 688 / 900 → sh
    000 / 001 / 002 / 003 / 200 / 300 → sz
    430 / 8xx / 920 → bj
    """
    s = str(symbol).strip()
    if s.startswith(("sh", "sz", "bj")):
        return s
    if s.startswith(("60", "688", "900", "510", "511", "512", "513", "515", "518", "588")):
        return f"sh{s}"
    if s.startswith(("00", "30", "200")):
        return f"sz{s}"
    if s.startswith(("43", "83", "87", "88", "92")):
        return f"bj{s}"
    # 默认沪市
    return f"sh{s}"


def _strip_prefix(symbol: str) -> str:
    """去掉 sh/sz/bj/hk/us 前缀，返回纯代码"""
    s = str(symbol).strip().lower()
    for p in ("sh", "sz", "bj", "hk", "us"):
        if s.startswith(p):
            return s[len(p):]
    return s


# ═══════════════════════════════════════════════════════════
# 1. 实时行情
# ═══════════════════════════════════════════════════════════

def get_stock_quote(symbol: str) -> dict:
    """
    获取个股实时行情（数据源：新浪分时 + 新浪盘口 + 东方财富备选）。

    Args:
        symbol: 股票代码，如 "000001"（平安银行）或 "600519"（贵州茅台）
                也支持带前缀的 sh600519 / sz000001

    Returns:
        dict: {"status": "success"|"error", "data": {行情数据}, "source": str}
    """
    try:
        import akshare as ak
    except ImportError:
        return {"status": "error", "message": "akshare 未安装（市场数据为可选功能）。启用方式：将 uvx 配置的 --from 改为 \"gridman-mcp[market]\"，或在当前环境执行 pip install akshare"}

    pure_code = _strip_prefix(symbol)
    sina_symbol = _normalize_symbol_with_prefix(pure_code)
    errors = []

    # ── 主源：新浪分时（取最后一条作为最新价，海外 IP 友好）──
    try:
        df = _retry(lambda: ak.stock_zh_a_minute(symbol=sina_symbol, period="1"))
        if df is not None and not df.empty:
            last = df.iloc[-1].to_dict()
            # 计算涨跌幅（用第一根分钟线作为参考）
            try:
                first_close = float(df.iloc[0]["close"])
                last_close = float(last["close"])
                change_pct = (last_close - first_close) / first_close * 100 if first_close > 0 else None
            except Exception:
                change_pct = None

            key_fields = {
                "代码": pure_code,
                "名称": "（详见公告）",  # 分时接口不返回名称
                "时间": str(last.get("day")),
                "最新价": last.get("close"),
                "今开": df.iloc[0].get("open") if len(df) > 0 else None,
                "最高": float(df["high"].astype(float).max()) if "high" in df.columns else None,
                "最低": float(df["low"].astype(float).min()) if "low" in df.columns else None,
                "成交量": last.get("volume"),
                "成交额": last.get("amount"),
                "当日涨跌幅%": round(change_pct, 2) if change_pct is not None else None,
            }
            return {"status": "success", "source": "新浪分时", "data": key_fields}
    except Exception as e:
        errors.append(f"新浪分时失败: {str(e)[:80]}")

    # ── 备选源 1：新浪盘口快照 ──
    try:
        df = _retry(lambda: ak.stock_zh_a_spot())
        row = df[df["代码"] == pure_code]
        if row.empty:
            normalized = _normalize_symbol_with_prefix(pure_code)
            row = df[df["代码"] == normalized]

        if not row.empty:
            record = row.iloc[0].to_dict()
            key_fields = {
                "代码": record.get("代码"),
                "名称": record.get("名称"),
                "最新价": record.get("最新价"),
                "涨跌额": record.get("涨跌额"),
                "涨跌幅": record.get("涨跌幅"),
                "买入": record.get("买入"),
                "卖出": record.get("卖出"),
                "昨收": record.get("昨收"),
                "今开": record.get("今开"),
                "最高": record.get("最高"),
                "最低": record.get("最低"),
                "成交量": record.get("成交量"),
                "成交额": record.get("成交额"),
                "时间戳": record.get("时间戳"),
            }
            return {"status": "success", "source": "新浪盘口", "data": key_fields}
    except Exception as e:
        errors.append(f"新浪盘口失败: {str(e)[:80]}")

    # ── 备选源 2：东方财富 ──
    try:
        df = _retry(lambda: ak.stock_zh_a_spot_em())
        row = df[df["代码"] == pure_code]
        if row.empty:
            return {
                "status": "error",
                "message": f"未找到股票代码：{symbol}（已尝试新浪分时+新浪盘口+东方财富）",
                "errors": errors,
            }

        record = row.iloc[0].to_dict()
        key_fields = {
            "代码": record.get("代码"),
            "名称": record.get("名称"),
            "最新价": record.get("最新价"),
            "涨跌幅": record.get("涨跌幅"),
            "涨跌额": record.get("涨跌额"),
            "成交量": record.get("成交量"),
            "成交额": record.get("成交额"),
            "今开": record.get("今开"),
            "最高": record.get("最高"),
            "最低": record.get("最低"),
            "昨收": record.get("昨收"),
            "换手率": record.get("换手率"),
            "市盈率": record.get("市盈率-动态"),
            "市净率": record.get("市净率"),
            "总市值": record.get("总市值"),
            "流通市值": record.get("流通市值"),
        }
        return {"status": "success", "source": "东方财富", "data": key_fields}

    except Exception as e:
        errors.append(f"东方财富失败: {str(e)[:80]}")
        return {
            "status": "error",
            "message": f"所有数据源都不可用",
            "errors": errors,
            "hint": (
                "如果你在挂代理环境下使用，可能是代理规则把数据源域名走了海外。"
                "可在 Clash 配置中加入：DOMAIN-SUFFIX,eastmoney.com,DIRECT"
            ),
        }


# ═══════════════════════════════════════════════════════════
# 2. 历史 K 线
# ═══════════════════════════════════════════════════════════

def get_stock_history(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> dict:
    """
    获取个股历史 K 线数据（多市场：A股/港股/美股）。

    数据源策略统一为「新浪优先（海外 IP 友好）→ 东方财富备选」：
        - A股：stock_zh_a_daily（新浪）→ stock_zh_a_hist（东财）
        - 港股：stock_hk_daily（新浪）→ stock_hk_hist（东财）
        - 美股：stock_us_daily（新浪）→ stock_us_hist（东财，需交易所前缀，自动解析）
    所有源都取日线，周/月线由本地 _aggregate_kline 统一聚合。

    Args:
        symbol: 股票代码。A股6位或带sh/sz/bj前缀；港股5位或带hk前缀；美股字母代码或带us前缀
        period: 周期，daily/weekly/monthly
        start_date: 开始日期 YYYYMMDD（不指定时取全量）
        end_date: 结束日期 YYYYMMDD
        adjust: 复权方式，qfq(前复权)/hfq(后复权)/空字符串(不复权)

    Returns:
        dict: {"status": "success"|"error", "data": [K线数据], "count": int, "source": str}
    """
    try:
        import akshare as ak
    except ImportError:
        return {"status": "error", "message": "akshare 未安装（市场数据为可选功能）。启用方式：将 uvx 配置的 --from 改为 \"gridman-mcp[market]\"，或在当前环境执行 pip install akshare"}

    market = _detect_market(symbol)
    pure_code = _strip_prefix(symbol)

    if market == "hk":
        return _get_history_hk(ak, pure_code, period, start_date, end_date, adjust)
    elif market == "us":
        return _get_history_us(ak, pure_code, period, start_date, end_date, adjust)
    else:
        return _get_history_a(ak, pure_code, period, start_date, end_date, adjust)


def _sina_adjust(adjust: str) -> str:
    """复权参数归一：新浪只认 qfq/hfq/空"""
    return adjust if adjust in ("qfq", "hfq") else ""


def _finalize_history_df(df, period, start_date, end_date, source_label, symbol):
    """
    K线 DataFrame 统一收尾：列名标准化 → 日期过滤 → 周/月聚合 → 截断 250 条。

    所有市场的取数源都返回日线，差异（英文列名 / 中文列名）在此抹平。
    """
    import pandas as pd

    rename_map = {
        "date": "日期", "open": "开盘", "high": "最高",
        "low": "最低", "close": "收盘", "volume": "成交量",
        "amount": "成交额", "outstanding_share": "流通股本",
        "turnover": "换手率",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "日期" in df.columns:
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        df = df.dropna(subset=["日期"]).sort_values("日期")
        if start_date:
            lo = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
            if pd.notna(lo):
                df = df[df["日期"] >= lo]
        if end_date:
            hi = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
            if pd.notna(hi):
                df = df[df["日期"] <= hi]

    label = source_label
    if period in ("weekly", "monthly"):
        df = _aggregate_kline(df, period)
        label = f"{source_label}聚合为{period}"

    if "日期" in df.columns:
        df["日期"] = df["日期"].astype(str)

    if len(df) > 250:
        df = df.tail(250)
    records = df.to_dict(orient="records")
    return {
        "status": "success",
        "source": label,
        "data": records,
        "count": len(records),
        "message": f"获取 {symbol} {period} K线 {len(records)} 条",
    }


def _get_history_a(ak, pure_code, period, start_date, end_date, adjust):
    """A 股 K 线（新浪日线 → 东方财富备选）"""
    sina_symbol = _normalize_symbol_with_prefix(pure_code)
    errors = []

    # ── 主源：新浪日线（海外友好）──
    try:
        kwargs = {"symbol": sina_symbol, "adjust": _sina_adjust(adjust)}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        df = _retry(lambda: ak.stock_zh_a_daily(**kwargs))
        if df is not None and not df.empty:
            return _finalize_history_df(df, period, start_date, end_date, "新浪", pure_code)
    except Exception as e:
        errors.append(f"新浪源失败: {str(e)[:80]}")

    # ── 备选源：东方财富（取日线，周月线本地聚合）──
    try:
        df = _retry(lambda: ak.stock_zh_a_hist(
            symbol=pure_code, period="daily",
            start_date=start_date or "19700101",
            end_date=end_date or "22220101",
            adjust=adjust,
        ))
        if df is not None and not df.empty:
            return _finalize_history_df(df, period, start_date, end_date, "东方财富", pure_code)
    except Exception as e:
        errors.append(f"东方财富源失败: {str(e)[:80]}")

    return {
        "status": "error",
        "message": f"未获取到 {pure_code} 的历史数据（已尝试新浪+东方财富）",
        "errors": errors,
    }


def _get_history_hk(ak, pure_code, period, start_date, end_date, adjust):
    """港股 K 线（新浪日线 → 东方财富备选）"""
    code = pure_code.zfill(5)
    errors = []

    # ── 主源：新浪港股日线 ──
    try:
        df = _retry(lambda: ak.stock_hk_daily(symbol=code, adjust=_sina_adjust(adjust)))
        if df is not None and not df.empty:
            return _finalize_history_df(df, period, start_date, end_date, "新浪(港股)", code)
    except Exception as e:
        errors.append(f"新浪港股源失败: {str(e)[:80]}")

    # ── 备选源：东方财富港股（取日线，周月线本地聚合）──
    try:
        df = _retry(lambda: ak.stock_hk_hist(
            symbol=code, period="daily",
            start_date=start_date or "19700101",
            end_date=end_date or "22220101",
            adjust=adjust,
        ))
        if df is not None and not df.empty:
            return _finalize_history_df(df, period, start_date, end_date, "东方财富(港股)", code)
    except Exception as e:
        errors.append(f"东方财富港股源失败: {str(e)[:80]}")

    return {
        "status": "error",
        "message": f"未获取到港股 {code} 的历史数据（已尝试新浪+东方财富）",
        "errors": errors,
    }


def _resolve_us_em_symbol(ak, code):
    """解析美股的东财内部代码（形如 105.NVDA / 106.BABA）。仅在新浪源失败时调用。"""
    try:
        spot = ak.stock_us_spot_em()
        hit = spot[spot["代码"].astype(str).str.upper().str.endswith("." + code)]
        if not hit.empty:
            return str(hit.iloc[0]["代码"])
    except Exception:
        return None
    return None


def _get_history_us(ak, pure_code, period, start_date, end_date, adjust):
    """美股 K 线（新浪日线 → 东方财富备选）"""
    code = pure_code.upper()
    errors = []

    # ── 主源：新浪美股日线（直接用 ticker，海外友好）──
    try:
        df = _retry(lambda: ak.stock_us_daily(symbol=code, adjust=_sina_adjust(adjust)))
        if df is not None and not df.empty:
            return _finalize_history_df(df, period, start_date, end_date, "新浪(美股)", code)
    except Exception as e:
        errors.append(f"新浪美股源失败: {str(e)[:80]}")

    # ── 备选源：东方财富美股（需交易所前缀，先解析代码）──
    try:
        em_symbol = _resolve_us_em_symbol(ak, code)
        if em_symbol:
            df = _retry(lambda: ak.stock_us_hist(
                symbol=em_symbol, period="daily",
                start_date=start_date or "19700101",
                end_date=end_date or "22220101",
                adjust=adjust,
            ))
            if df is not None and not df.empty:
                return _finalize_history_df(df, period, start_date, end_date, "东方财富(美股)", code)
        else:
            errors.append("东方财富美股源失败: 未能解析交易所前缀代码")
    except Exception as e:
        errors.append(f"东方财富美股源失败: {str(e)[:80]}")

    return {
        "status": "error",
        "message": f"未获取到美股 {code} 的历史数据（已尝试新浪+东方财富）",
        "errors": errors,
    }


def _aggregate_kline(daily_df, period):
    """从日线聚合为周线/月线"""
    import pandas as pd
    df = daily_df.copy()
    if "日期" not in df.columns:
        return df

    df["日期"] = pd.to_datetime(df["日期"])
    df = df.set_index("日期").sort_index()

    rule = "W-FRI" if period == "weekly" else "ME"  # 周五收盘 / 月末

    agg_dict = {}
    if "开盘" in df.columns: agg_dict["开盘"] = "first"
    if "最高" in df.columns: agg_dict["最高"] = "max"
    if "最低" in df.columns: agg_dict["最低"] = "min"
    if "收盘" in df.columns: agg_dict["收盘"] = "last"
    if "成交量" in df.columns: agg_dict["成交量"] = "sum"
    if "成交额" in df.columns: agg_dict["成交额"] = "sum"

    if not agg_dict:
        return df.reset_index()

    resampled = df.resample(rule).agg(agg_dict).dropna(how="all")
    return resampled.reset_index()


# ═══════════════════════════════════════════════════════════
# 3. 财务数据（新浪源，海外友好）
# ═══════════════════════════════════════════════════════════

def get_financial_data(symbol: str, report_type: str = "income") -> dict:
    """
    获取个股财务数据（多市场：A股/港股/美股）。

    Args:
        symbol: 股票代码。A股6位/港股5位或带hk前缀/美股字母
        report_type: 报表类型
            - "income": 利润表
            - "balance": 资产负债表
            - "cashflow": 现金流量表

    Returns:
        dict: {"status": "success"|"error", "data": [财务数据], "periods": int, "source": str}
    """
    try:
        import akshare as ak
    except ImportError:
        return {"status": "error", "message": "akshare 未安装（市场数据为可选功能）。启用方式：将 uvx 配置的 --from 改为 \"gridman-mcp[market]\"，或在当前环境执行 pip install akshare"}

    # 市场识别
    market = _detect_market(symbol)
    pure_code = _strip_prefix(symbol)

    if market == "hk":
        return _get_financial_hk(ak, pure_code, report_type)
    elif market == "us":
        return _get_financial_us(ak, pure_code, report_type)
    else:
        return _get_financial_a(ak, pure_code, report_type)


def _detect_market(symbol: str) -> str:
    """识别市场：hk/us/a"""
    s = str(symbol).strip().lower()
    if s.startswith("hk"):
        return "hk"
    if s.startswith("us"):
        return "us"
    # 去掉 sh/sz/bj 前缀后判断
    for p in ("sh", "sz", "bj"):
        if s.startswith(p):
            return "a"
    # 纯数字
    bare = s
    if bare.isdigit():
        if len(bare) <= 5:
            return "hk"
        return "a"
    # 纯字母 → 美股
    if bare.isalpha():
        return "us"
    return "a"


def _get_financial_a(ak, pure_code: str, report_type: str) -> dict:
    """A 股财务数据（新浪源）"""
    type_map = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
    if report_type not in type_map:
        return {"status": "error", "message": f"不支持的报表类型：{report_type}，可选：{list(type_map.keys())}"}
    try:
        df = _retry(lambda: ak.stock_financial_report_sina(
            stock=pure_code, symbol=type_map[report_type]
        ))
        if df.empty:
            return {"status": "error", "message": f"未获取到 {pure_code} 的财务数据"}
        if len(df) > 8:
            df = df.head(8)
        records = df.to_dict(orient="records")
        return {"status": "success", "source": "新浪", "data": records, "periods": len(records),
                "message": f"获取 {pure_code} {report_type} 最近 {len(records)} 期"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _get_financial_hk(ak, pure_code: str, report_type: str) -> dict:
    """港股财务数据（东方财富源）"""
    type_map = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
    if report_type not in type_map:
        return {"status": "error", "message": f"不支持的报表类型：{report_type}，可选：{list(type_map.keys())}"}
    # 港股代码补足5位
    code = pure_code.zfill(5)
    try:
        df = _retry(lambda: ak.stock_financial_hk_report_em(
            stock=code, symbol=type_map[report_type], indicator="年度"
        ))
        if df.empty:
            return {"status": "error", "message": f"未获取到港股 {code} 的财务数据"}
        # 只保留最近8期（年度）
        dates = df["REPORT_DATE"].unique()
        dates_sorted = sorted(dates, reverse=True)[:8]
        df = df[df["REPORT_DATE"].isin(dates_sorted)]
        # 转为宽表（每期一行，字段为列）
        pivot = df.pivot_table(index="REPORT_DATE", columns="STD_ITEM_NAME", values="AMOUNT", aggfunc="first")
        pivot = pivot.reset_index().sort_values("REPORT_DATE", ascending=False)
        records = pivot.to_dict(orient="records")
        return {"status": "success", "source": "东方财富(港股)", "data": records, "periods": len(records),
                "message": f"获取港股 {code} {report_type} 最近 {len(records)} 期（年度）"}
    except Exception as e:
        return {"status": "error", "message": f"港股财报获取失败: {str(e)[:120]}"}


def _get_financial_us(ak, pure_code: str, report_type: str) -> dict:
    """美股财务数据（东方财富源）"""
    type_map = {"income": "利润表", "balance": "资产负债表", "cashflow": "现金流量表"}
    if report_type not in type_map:
        return {"status": "error", "message": f"不支持的报表类型：{report_type}，可选：{list(type_map.keys())}"}
    code = pure_code.upper()
    try:
        df = _retry(lambda: ak.stock_financial_us_report_em(
            stock=code, symbol=type_map[report_type], indicator="年度"
        ))
        if df.empty:
            return {"status": "error", "message": f"未获取到美股 {code} 的财务数据"}
        dates = df["REPORT_DATE"].unique()
        dates_sorted = sorted(dates, reverse=True)[:8]
        df = df[df["REPORT_DATE"].isin(dates_sorted)]
        pivot = df.pivot_table(index="REPORT_DATE", columns="STD_ITEM_NAME", values="AMOUNT", aggfunc="first")
        pivot = pivot.reset_index().sort_values("REPORT_DATE", ascending=False)
        records = pivot.to_dict(orient="records")
        return {"status": "success", "source": "东方财富(美股)", "data": records, "periods": len(records),
                "message": f"获取美股 {code} {report_type} 最近 {len(records)} 期（年度）"}
    except Exception as e:
        return {"status": "error", "message": f"美股财报获取失败: {str(e)[:120]}"}
