"""
多市场行情查询 — 零依赖（仅标准库 urllib）

覆盖：A股（沪/深/京）、港股、美股、大盘指数；支持批量（一次最多 20 只）。

设计取舍（与同目录 stock_data.py 的分工）：
═════════════════════════════════════════════════════════
- market_quote.py（本文件）：腾讯财经公开接口，零依赖、海外 IP 友好、
  多市场 + 批量 + 快照行情。定位"快速看盘 / 排雷入口扫描"。
- stock_data.py：akshare，A 股深度（历史 K 线、三大报表）。定位"深度分析"。
两者互补，不重复——本文件不碰 K 线和财务报表。
═════════════════════════════════════════════════════════

古立特基因：返回行情的同时附"异动信号"（接近涨跌停 / 振幅异常），
是排雷工作流的第一道入口——先看价异动，再决定要不要深挖财务。
"""
import re
import time
import urllib.request

# 腾讯财经公开行情接口（GBK 编码，字段以 ~ 分隔）
_TENCENT_API = "https://qt.gtimg.cn/q={symbols}"
_TIMEOUT = 8
_MAX_BATCH = 20

# 输入安全校验：代码仅允许字母数字和前导点（点用于美股指数 .IXIC/.DJI/.INX）
_CODE_RE = re.compile(r"^\.?[A-Za-z0-9]{1,10}$")


def _classify_and_prefix(raw: str) -> str | None:
    """
    识别市场并返回腾讯接口所需的带前缀代码。
    返回 None 表示无法识别。

    规则：
      已带前缀（sh/sz/bj/hk/us）→ 原样小写化前缀
      纯数字 6 位：60/68/90/51x... → sh；00/30/20 → sz；43/83/87/88/92 → bj
      纯数字 ≤5 位 → 港股 hk（补足 5 位）
      字母（可含前导点）→ 美股 us
      已知指数别名 → 映射
    """
    s = raw.strip()
    if not s:
        return None

    low = s.lower()
    # 已带市场前缀
    for p in ("sh", "sz", "bj", "hk", "us"):
        if low.startswith(p) and len(s) > len(p):
            rest = s[len(p):]
            # 港股/美股指数保留大小写，A股数字原样
            return p + rest

    # 指数别名（中文/通用名 → 腾讯代码）
    alias = _INDEX_ALIAS.get(s) or _INDEX_ALIAS.get(low)
    if alias:
        return alias

    # 美股指数：以点开头
    if s.startswith("."):
        return "us" + s.upper()

    # 纯数字
    if s.isdigit():
        if len(s) == 6:
            if s[:2] in ("60", "68", "90", "11", "13") or s[:3] in ("510", "511", "512", "513", "515", "516", "518", "588", "688"):
                return "sh" + s
            if s[:2] in ("00", "30", "20", "15", "16", "18"):
                return "sz" + s
            if s[:2] in ("43", "83", "87", "88", "92"):
                return "bj" + s
            return "sh" + s  # 兜底沪市
        # 港股：≤5 位数字，补足 5 位
        if 1 <= len(s) <= 5:
            return "hk" + s.zfill(5)
        return None

    # 纯字母 → 美股
    if s.isalpha():
        return "us" + s.upper()

    return None


# 大盘指数别名表（中文/俗称 → 腾讯代码）
_INDEX_ALIAS = {
    "上证指数": "sh000001", "上证": "sh000001", "大盘": "sh000001", "沪指": "sh000001",
    "深证成指": "sz399001", "深成指": "sz399001", "深证": "sz399001",
    "创业板指": "sz399006", "创业板": "sz399006",
    "沪深300": "sh000300", "中证500": "sh000905", "上证50": "sh000016",
    "科创50": "sh000688",
    "恒生指数": "hkHSI", "恒指": "hkHSI", "HSI": "hkHSI",
    "国企指数": "hkHSCEI", "H股指数": "hkHSCEI", "HSCEI": "hkHSCEI",
    "恒生科技": "hkHSTECH", "恒生科技指数": "hkHSTECH",
    "纳斯达克": "us.IXIC", "纳指": "us.IXIC",
    "道琼斯": "us.DJI", "道指": "us.DJI",
    "标普500": "us.INX", "标普": "us.INX",
}


def _fetch_raw(prefixed_symbols: list[str]) -> str:
    """请求腾讯接口，返回 GBK 解码后的原始文本。"""
    query = ",".join(prefixed_symbols)
    url = _TENCENT_API.format(symbols=query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("gbk", errors="ignore")


def _parse_one(line: str) -> dict | None:
    """
    解析腾讯接口单行返回。格式：v_sh600519="...~字段~字段~...";
    字段索引（各市场统一）：
      [1]名称 [2]代码 [3]当前价 [4]昨收 [5]今开 [6]成交量
      [30]时间 [31]涨跌额 [32]涨跌幅% [33]最高 [34]最低 [37]成交额
    """
    m = re.search(r'="([^"]*)"', line)
    if not m:
        return None
    fields = m.group(1).split("~")
    if len(fields) < 33:
        return None
    # 从 v_sh600519= 提取市场前缀，决定要不要解析 A 股扩展字段
    mkt_m = re.search(r'v_([a-z]{2})', line)
    market = mkt_m.group(1) if mkt_m else ""

    def _num(idx):
        try:
            return float(fields[idx])
        except (ValueError, IndexError):
            return None

    name = fields[1] if len(fields) > 1 else ""
    code = fields[2] if len(fields) > 2 else ""
    if not name and not code:
        return None

    rec = {
        "代码": code,
        "名称": name,
        "当前价": _num(3),
        "昨收": _num(4),
        "今开": _num(5),
        "最高": _num(33),
        "最低": _num(34),
        "成交量": _num(6),
        "成交额": _num(37),
        "涨跌额": _num(31),
        "涨跌幅%": _num(32),
        "时间": fields[30] if len(fields) > 30 else None,
    }
    # A 股扩展字段（沪/深/京）：换手率/市盈率/市净率/市值。港股美股字段布局不同，不取（避免填错值）。
    if market in ("sh", "sz", "bj") and len(fields) > 46:
        rec["换手率%"] = _num(38)
        rec["市盈率TTM"] = _num(39)
        rec["市净率"] = _num(46)
        rec["总市值(亿)"] = _num(45)
        rec["流通市值(亿)"] = _num(44)
    rec["异动信号"] = _spot_flags(rec)
    return rec


def _spot_flags(rec: dict) -> list[str]:
    """
    古立特基因——快照能判断的价异动信号（排雷入口）。
    注意：成交额骤变需历史对比，单次快照判断不了，留给后续工作流。
    """
    flags = []
    pct = rec.get("涨跌幅%")
    if pct is not None:
        if abs(pct) >= 9.8:
            flags.append(f"⚠️ 接近涨跌停（{pct:+.2f}%）")
        elif abs(pct) >= 7:
            flags.append(f"⚠️ 大幅波动（{pct:+.2f}%）")

    hi, lo, prev = rec.get("最高"), rec.get("最低"), rec.get("昨收")
    if hi and lo and prev and prev > 0:
        amplitude = (hi - lo) / prev * 100
        if amplitude >= 15:
            flags.append(f"⚠️ 振幅异常（{amplitude:.1f}%）")

    return flags


def get_market_quote(symbols: str) -> dict:
    """
    多市场行情查询（A股/港股/美股/大盘指数），支持批量。

    Args:
        symbols: 单只或多只，逗号分隔，最多 20。
                 接受代码或常见指数别名，如：
                 "600519" / "00700" / "AAPL" / "上证指数" /
                 "600519,00700,AAPL,纳斯达克"

    Returns:
        dict: {
          "status": "success"|"error",
          "source": "腾讯财经",
          "count": int,
          "data": [ {行情+异动信号}, ... ],
          "unresolved": [无法识别的输入],
        }
    """
    raw_list = [s.strip() for s in str(symbols).split(",") if s.strip()]
    if not raw_list:
        return {"status": "error", "message": "未提供股票代码"}
    if len(raw_list) > _MAX_BATCH:
        return {"status": "error", "message": f"一次最多查询 {_MAX_BATCH} 只，当前 {len(raw_list)} 只"}

    prefixed, unresolved, order = [], [], []
    for raw in raw_list:
        p = _classify_and_prefix(raw)
        if p is None:
            # 安全校验兜底：去前缀后的纯代码必须合法
            unresolved.append(raw)
            continue
        bare = p[2:] if p[:2] in ("sh", "sz", "bj", "hk", "us") else p
        if not _CODE_RE.match(bare):
            unresolved.append(raw)
            continue
        prefixed.append(p)
        order.append(raw)

    if not prefixed:
        return {
            "status": "error",
            "message": "无法识别任何股票代码。支持 A股(6位数字)、港股(5位数字)、美股(字母)、指数别名(如'上证指数')",
            "unresolved": unresolved,
        }

    # 请求（限流重试一次）
    last_err = None
    for attempt in range(2):
        try:
            raw_text = _fetch_raw(prefixed)
            break
        except Exception as e:
            last_err = e
            if attempt == 0:
                time.sleep(1)
    else:
        return {"status": "error", "message": f"行情接口请求失败：{str(last_err)[:100]}"}

    data = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        rec = _parse_one(line)
        if rec:
            data.append(rec)

    if not data:
        return {
            "status": "error",
            "message": "接口未返回有效行情（代码可能无效或非交易品种）",
            "unresolved": unresolved + order,
        }

    result = {
        "status": "success",
        "source": "腾讯财经",
        "count": len(data),
        "data": data,
    }
    if unresolved:
        result["unresolved"] = unresolved
    return result
