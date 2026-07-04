"""
企业工商信息查询 — 风鸟 Fengniao (Riskbird) 云端 API

古立特原生工具，借鉴 company-search-fengniao Skill 的 API 形态，重写为古立特风格：
- 任务导向（一个工具=一件事），不暴露底层 discover/call
- 字段标准化（原始 camelCase → 中文键），供下游审计程序直接消费
- 内置「往来单位数据库」缓存：查过的企业写入 gridman-mind/entities/，跨科目复用、不重复计费

定位（审计 P2 工商信息与交易核对 / P8 坏账测算的取数底座）：
  给一个往来单位名称 → 注册资本/经营范围/股东/经营状态/对外投资/变更 + 风险记录，
  供 AI 判断「交易规模 vs 注册资本」「经营范围是否匹配」「是否注销/关联方」等。

使用前需配置环境变量 RISKBIRD_API_KEY（就像 MinerU 用 MINERU_API_TOKEN）。
渠道标识可选用 RISKBIRD_CHANNEL 覆盖，默认 "clawhub"。

注意：本工具只「取数」，不做职业判断；合理性判断、关联方认定由古立特结合知识库完成。
风鸟数据非法定权威，关键户建议人工到国家企业信用信息公示系统(gsxt.gov.cn)终审。
"""
import os
import json
import time
from pathlib import Path

# ── 风鸟云端 API 配置（用户提供 API 后如有不同，改这三处即可） ──
_BASE_URL = "https://m.riskbird.com/prod-qbb-api"
_DEFAULT_CHANNEL = "clawhub"
_TIMEOUT = 20

# ── 维度注册表：古立特维度键 → (风鸟 version, 中文名, 是否单体对象) ──
# searchHint 单独处理；其余走 /skills/dataDimension?version=
_DIMENSIONS = {
    "basic":             ("B1",  "工商基本信息", True),
    "shareholders":      ("B2",  "股东信息",     False),
    "executives":        ("B3",  "高级职员",     False),
    "investments":       ("B4",  "对外投资",     False),
    "changes":           ("B5",  "工商变更",     False),
    "executed":          ("C2",  "被执行人",     False),
    "dishonest":         ("C3",  "失信被执行人", False),
    "limit_consumption": ("C4",  "限制高消费",   False),
    "abnormal":          ("D1",  "经营异常",     False),
    "serious_illegal":   ("D2",  "严重违法",     False),
    "penalty":           ("D11", "行政处罚",     False),
}

# 默认取数维度：工商核心 + 两个最关键的风险旗标（省额度；其余维度按需显式传入）
# 注意：每个维度 = 1 次 API 调用，模糊搜索 = 1 次。部分 Key 有每日调用上限（如 50 次/天），
# 故默认从简，并配合缓存 + 名称索引避免重复消耗。
_DEFAULT_DIMENSIONS = ["basic", "abnormal", "dishonest"]

_RISK_DIMENSIONS = {"executed", "dishonest", "limit_consumption", "abnormal", "serious_illegal", "penalty"}

_KEY_MISSING_MSG = (
    "未配置 RISKBIRD_API_KEY。配置方式（与 MinerU 同理）：\n"
    "1. 取得风鸟(Riskbird)开放接口的 API Key\n"
    "2. 填入 MCP 配置的 env 中：RISKBIRD_API_KEY\n"
    "3. 如渠道标识与默认不同，另配 RISKBIRD_CHANNEL\n"
    "未配置时本工具不可用（不内置公用 Key，避免共享额度与他人冲突）。"
)


def _get_key() -> str:
    return os.environ.get("RISKBIRD_API_KEY", "").strip()


def _get_channel() -> str:
    return os.environ.get("RISKBIRD_CHANNEL", "").strip() or _DEFAULT_CHANNEL


def _request(endpoint: str, params: dict) -> dict:
    """统一请求风鸟接口。apikey/channel 走 URL 参数（非 Header）。返回 dict 或抛异常。"""
    import requests
    from urllib.parse import urlencode

    key = _get_key()
    full = dict(params)
    full["apikey"] = key
    full["channel"] = _get_channel()
    url = f"{_BASE_URL}{endpoint}"
    if "?" in endpoint:
        url = f"{_BASE_URL}{endpoint}&{urlencode({k: v for k, v in full.items()})}"
    else:
        url = f"{_BASE_URL}{endpoint}?{urlencode(full)}"

    resp = requests.get(url, headers={"Accept": "application/json"}, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _interpret_code(body: dict) -> tuple:
    """解析风鸟响应信封，返回 (ok, code, msg)。code 见字段定义：
    20000=成功 / 3000000=无数据 / 8888=参数错 / 9999=系统错或额度达上限。"""
    code = body.get("code")
    msg = body.get("msg", "")
    if code in (20000, "20000"):
        return True, code, msg
    return False, code, msg


# ═══════════════════════════════════════════════════════════════
# 字段标准化：原始 camelCase → 中文键，供下游审计程序直接消费
# ═══════════════════════════════════════════════════════════════
def _norm_basic(d: dict) -> dict:
    """B1 工商基本信息（单体对象）。"""
    op_to = d.get("opTo") or ""
    return {
        "企业全称": d.get("entName"),
        "统一社会信用代码": d.get("uniscid"),
        "工商注册号": d.get("regNo"),
        "经营状态": d.get("entStatus"),
        "企业类型": d.get("entType"),
        "注册资本": d.get("regConcat") or d.get("regCap"),
        "成立日期": d.get("esDate"),
        "营业期限": f"{d.get('opFrom') or ''} 至 {op_to}".strip(),
        "注销日期": d.get("candate"),
        "吊销日期": d.get("revdate"),
        "注册地址": d.get("dom"),
        "注册地区": d.get("regionName"),
        "登记机关": d.get("regOrg"),
        "行业分类": d.get("nicName"),
        "经营范围": d.get("opScope"),
        "法定代表人": d.get("personName"),
        "曾用名": d.get("historyName"),
        "企业标签": d.get("tags"),
        "风险标签": d.get("riskTags"),
        "联系电话": d.get("tel"),
        "联系邮箱": d.get("email"),
        "官网": d.get("website"),
    }


def _norm_shareholders(rows: list) -> list:
    return [{
        "股东名称": r.get("shaName"),
        "股东类型": r.get("invType"),
        "持股比例": r.get("fundedRatio"),
        "认缴出资额": r.get("subConAm"),
        "认缴日期": r.get("conDate"),
        "是否退出": r.get("outState"),
    } for r in rows]


def _norm_executives(rows: list) -> list:
    return [{
        "姓名": r.get("personName"),
        "职务": r.get("position"),
        "持股比例": r.get("fundedRatio"),
    } for r in rows]


def _norm_investments(rows: list) -> list:
    return [{
        "被投企业": r.get("entName"),
        "经营状态": r.get("entStatus"),
        "持股比例": r.get("funderRatio"),
        "认缴出资额": r.get("subConAm"),
        "成立日期": r.get("esDate"),
        "法定代表人": r.get("personName"),
    } for r in rows]


def _norm_changes(rows: list) -> list:
    return [{
        "变更日期": r.get("altDate"),
        "变更事项": r.get("altItemCodeCn"),
        "变更前": r.get("altBe"),
        "变更后": r.get("altAf"),
    } for r in rows]


def _norm_abnormal(rows: list) -> list:
    return [{
        "列入日期": r.get("inDate"),
        "列入原因": r.get("inReason"),
        "列入机关": r.get("inRegOrg"),
        "移出日期": r.get("outDate"),
        # outState 语义与字段名相反：false=仍在名单
        "当前仍在名单": (r.get("outState") is False),
    } for r in rows]


def _norm_serious_illegal(rows: list) -> list:
    return [{
        "列入日期": r.get("indate"),
        "列入原因": r.get("inreason"),
        "列入机关": r.get("inorg"),
        "移出日期": r.get("outdate"),
    } for r in rows]


def _norm_penalty(rows: list) -> list:
    out = []
    for r in rows:
        am = r.get("penaltyAm")
        try:
            am_wan = round(float(am) / 10000, 4) if am not in (None, "") else None
        except (ValueError, TypeError):
            am_wan = None
        out.append({
            "处罚决定书文号": r.get("docNo"),
            "处罚日期": r.get("penaltyDate"),
            "处罚机关": r.get("penaltyOrg"),
            "违法事实": r.get("illegalFact"),
            "违法类型": r.get("illegalType"),
            "罚款金额(万元)": am_wan,
            "处罚依据": r.get("penaltyBasis"),
        })
    return out


def _norm_generic(rows: list) -> list:
    """C2/C3/C4 等未单独建模的维度：原样返回（保留原始字段，避免漏信息）。"""
    return rows


_NORMALIZERS = {
    "basic": _norm_basic,
    "shareholders": _norm_shareholders,
    "executives": _norm_executives,
    "investments": _norm_investments,
    "changes": _norm_changes,
    "abnormal": _norm_abnormal,
    "serious_illegal": _norm_serious_illegal,
    "penalty": _norm_penalty,
}


def _extract_rows(body: dict, version: str) -> tuple:
    """从 dataDimension 响应中取 (totalCount, rows/对象)。
    处理三种形态：B1 单体对象 / D2 在 SERILLEGAL / 其余在 apiData。"""
    data = body.get("data") or {}
    if not isinstance(data, dict):
        return 0, data
    total = data.get("totalCount", 0)
    if version == "D2":
        return total, data.get("SERILLEGAL", []) or []
    api = data.get("apiData")
    if isinstance(api, dict):  # B1 单体
        return total, api
    return total, (api or [])


# ═══════════════════════════════════════════════════════════════
# 工商取数缓存 — 查过一次不再重复查（省额度）
# 落在 gridman-mind/_cache/company/：这是「工具内部的取数底稿」，原始 JSON、带 TTL、可随时删
# （删后重查重花额度，但不丢判断）。与 entities/<名>.md（人/古立特维护的判断上下文）分层：
# 原始证据归 _cache，判断结论归 entities——两者由下面的「沉淀桥」单向连通（取数 → 事实节）。
# ═══════════════════════════════════════════════════════════════
def _cache_dir() -> Path:
    """缓存目录：gridman-mind/_cache/company/。取不到 mind 目录时退回临时目录。"""
    try:
        from gridman_mcp.tools._shared.paths import get_mind_dir
        d = get_mind_dir() / "_cache" / "company"
    except Exception:
        import tempfile
        d = Path(tempfile.gettempdir()) / "gridman_company_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(entid: str) -> Path:
    safe = "".join(c for c in str(entid) if c.isalnum() or c in "-_")
    return _cache_dir() / f"{safe}.json"


def _cache_read(entid: str, ttl_days: float):
    p = _cache_path(entid)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    fetched = payload.get("_fetched_at", 0)
    if ttl_days is not None and (time.time() - fetched) > ttl_days * 86400:
        return None
    return payload


def _cache_write(entid: str, payload: dict):
    payload = dict(payload)
    payload["_fetched_at"] = time.time()
    try:
        _cache_path(entid).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _name_index_path() -> Path:
    return _cache_dir() / "_name_index.json"


def _name_index_get(name: str):
    """名称→entid 索引：让同一家公司用名称重查时也能跳过搜索调用。"""
    p = _name_index_path()
    if not p.exists():
        return None
    try:
        idx = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return idx.get((name or "").strip())


def _name_index_put(name: str, entid: str):
    p = _name_index_path()
    try:
        idx = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        idx = {}
    idx[(name or "").strip()] = entid
    try:
        p.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# 沉淀桥：工商取数 → entity 上下文 md（mcp → mind → skill 回流的一环）
# 工具只写 entities/<企业全称>.md 里的「工商事实」自动节（带标记、幂等更新）；
# 「了解与判断」节留给古立特/人填，工具绝不碰——取数是事实搬运，判断仍归古立特。
# ═══════════════════════════════════════════════════════════════
_FACT_BEGIN = "<!-- GRIDMAN:工商事实:BEGIN（本节由 company_query 自动维护，勿手改） -->"
_FACT_END = "<!-- GRIDMAN:工商事实:END -->"


def _safe_filename(name: str) -> str:
    s = (name or "").strip()
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "_")
    return s[:120] or "未命名企业"


def _build_fact_block(out: dict) -> str:
    dims = out.get("dimensions") or {}
    basic = (dims.get("basic") or {}).get("数据") or {}
    lines = [
        _FACT_BEGIN,
        "",
        f"## 工商事实（自动维护 · 数据源：风鸟，非法定权威 · 更新 {time.strftime('%Y-%m-%d')}）",
        "",
    ]

    def add(label, val):
        if val:
            lines.append(f"- {label}：{val}")

    add("企业全称", basic.get("企业全称") or out.get("企业全称"))
    add("统一社会信用代码", basic.get("统一社会信用代码"))
    add("经营状态", basic.get("经营状态"))
    add("企业类型", basic.get("企业类型"))
    add("注册资本", basic.get("注册资本"))
    add("成立日期", basic.get("成立日期"))
    add("法定代表人", basic.get("法定代表人"))
    add("注册地址", basic.get("注册地址"))
    add("行业分类", basic.get("行业分类"))
    scope = basic.get("经营范围")
    if scope:
        add("经营范围", scope if len(scope) <= 200 else scope[:200] + "…")
    tags = basic.get("企业标签")
    if tags:
        add("企业标签", "、".join(tags) if isinstance(tags, list) else tags)
    rtags = basic.get("风险标签")
    if rtags:
        add("风险标签", "、".join(rtags) if isinstance(rtags, list) else rtags)
    sh = (dims.get("shareholders") or {}).get("数据(最多5条)") or []
    if sh:
        lines.append("- 主要股东（前5）：")
        for s in sh[:5]:
            lines.append(f"    - {s.get('股东名称')}（{s.get('持股比例') or '-'}）")
    rs = out.get("风险摘要")
    if rs:
        lines.append("- 风险摘要：" + "、".join(f"{k} {v}" for k, v in rs.items()))
    add("entid", out.get("entid"))
    lines.append("")
    lines.append(_FACT_END)
    return "\n".join(lines)


def _entity_skeleton(name: str, fact_block: str) -> str:
    return (
        f"# {name}\n\n"
        "> 「工商事实」节由 company_query 工具自动维护（数据源：风鸟，非法定权威）；\n"
        "> 「了解与判断」节由古立特/人填写，工具不碰。\n\n"
        f"{fact_block}\n\n"
        "## 了解与判断（人工 / 古立特维护）\n\n"
        "（科目表、记账惯例、关联方认定、交易规模 vs 注册资本是否匹配、"
        "经营范围是否覆盖业务等——由古立特结合知识库判断后填写）\n"
    )


def _write_entity_context(out: dict):
    """把工商取数的判断相关事实沉淀进 entities/<企业全称>.md 的「工商事实」自动节。
    文件已存在则只替换该节、保留人写的「了解与判断」；不存在则建骨架。失败静默，绝不影响取数。"""
    try:
        name = out.get("企业全称") or ((out.get("dimensions") or {}).get("basic") or {}).get("数据", {}).get("企业全称")
        if not name:
            return
        from gridman_mcp.tools._shared.paths import get_mind_dir
        ent_dir = get_mind_dir() / "entities"
        ent_dir.mkdir(parents=True, exist_ok=True)
        path = ent_dir / f"{_safe_filename(name)}.md"
        fact_block = _build_fact_block(out)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            if _FACT_BEGIN in text and _FACT_END in text:
                pre = text.split(_FACT_BEGIN)[0]
                post = text.split(_FACT_END, 1)[1]
                text = pre + fact_block + post
            else:
                # 防半截标记：只剩 BEGIN 或只剩 END 时，先剥掉孤立标记再追加，避免追加后出现双标记
                for _m in (_FACT_BEGIN, _FACT_END):
                    text = text.replace(_m, "")
                text = text.rstrip() + "\n\n" + fact_block + "\n"
            path.write_text(text, encoding="utf-8")
        else:
            path.write_text(_entity_skeleton(name, fact_block), encoding="utf-8")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# 主函数 1：企业模糊搜索（消歧用）
# ═══════════════════════════════════════════════════════════════
def search_company(keyword: str, limit: int = 5) -> dict:
    """模糊搜索企业，返回候选列表（含 entid / 全称 / 经营状态）。用于主体消歧。"""
    import requests

    if not _get_key():
        return {"status": "error", "engine": "风鸟API", "message": _KEY_MISSING_MSG}
    kw = (keyword or "").strip()
    if not kw:
        return {"status": "error", "message": "搜索关键词为空"}
    # 风鸟 searchHint 不支持英文匹配中文企业名
    if kw.isascii() and any(c.isalpha() for c in kw):
        return {"status": "error", "message": "请使用中文企业名称搜索（风鸟不支持英文关键词）"}

    try:
        body = _request("/skills/searchHint", {"key": kw})
    except requests.exceptions.Timeout:
        return {"status": "error", "engine": "风鸟API", "message": "请求超时，请稍后重试"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "engine": "风鸟API", "message": "无法连接风鸟服务器，请检查网络"}
    except Exception as e:
        return {"status": "error", "engine": "风鸟API", "message": str(e)}

    ok, code, msg = _interpret_code(body)
    if not ok:
        if code in (9999, "9999") and "上限" in str(msg):
            return {"status": "error", "engine": "风鸟API", "message": f"额度已达上限：{msg}"}
        if code in (3000000, "3000000"):
            return {"status": "success", "count": 0, "candidates": [], "message": "未找到相关企业"}
        return {"status": "error", "engine": "风鸟API", "code": code, "message": msg or "搜索失败"}

    rows = body.get("data") or []
    if not isinstance(rows, list):
        rows = []
    candidates = []
    for r in rows[: max(1, limit)]:
        candidates.append({
            "entid": r.get("entid"),
            "企业全称": r.get("entName") or r.get("ENTNAME"),
            "经营状态": r.get("entStatus") or r.get("ENTSTATUS"),
            "命中字段": r.get("highlightNameType"),
        })
    return {"status": "success", "engine": "风鸟API", "count": len(candidates), "candidates": candidates}


def _resolve_entid(keyword: str) -> dict:
    """把企业名解析为唯一 entid。
    - 0 个候选 → not_found
    - 名称与某候选全称完全相等 → 直接命中
    - 1 个候选 → 命中
    - 多个候选且无精确匹配 → ambiguous（要求人工确认）
    """
    res = search_company(keyword, limit=5)
    if res.get("status") != "success":
        return res
    cands = res.get("candidates", [])
    if not cands:
        return {"status": "not_found", "message": f"未找到企业「{keyword}」"}
    kw = keyword.strip()
    exact = [c for c in cands if (c.get("企业全称") or "").strip() == kw]
    if exact:
        return {"status": "resolved", "candidate": exact[0]}
    if len(cands) == 1:
        return {"status": "resolved", "candidate": cands[0]}
    return {
        "status": "ambiguous",
        "message": f"「{keyword}」匹配到多家企业，请确认是哪一家后再查询（传入准确全称或对应 entid）。",
        "candidates": cands,
    }


# ═══════════════════════════════════════════════════════════════
# 主函数 2：企业画像取数（核心）
# ═══════════════════════════════════════════════════════════════
def query_company(
    name: str = None,
    entid: str = None,
    dimensions: list = None,
    refresh: bool = False,
    cache_ttl_days: float = 7,
) -> dict:
    """查询企业工商 + 风险画像，字段标准化输出，并写入往来单位数据库缓存。

    Args:
        name: 企业名称（与 entid 二选一；传 name 时自动搜索+消歧）
        entid: 企业唯一标识（已知时直接传，跳过搜索）
        dimensions: 维度键列表，默认 basic/股东/董监高/经营异常/失信。
                    可选：basic, shareholders, executives, investments, changes,
                          executed, dishonest, limit_consumption, abnormal,
                          serious_illegal, penalty
        refresh: True 时绕过缓存强制重查
        cache_ttl_days: 缓存有效天数（默认 7 天；工商信息较稳定）

    Returns:
        dict: status / entid / 企业全称 / dimensions{各维度标准化数据} / 风险摘要 / from_cache
    """
    import requests

    if not _get_key():
        return {"status": "error", "engine": "风鸟API", "message": _KEY_MISSING_MSG}

    # 1) 解析主体（名称索引命中则跳过搜索调用，省额度）
    api_calls = 0
    if not entid:
        if not name:
            return {"status": "error", "message": "请提供 name 或 entid"}
        cached_entid = _name_index_get(name)
        if cached_entid:
            entid = cached_entid
            resolved_name = name
        else:
            r = _resolve_entid(name)  # 1 次搜索调用
            api_calls += 1
            if r.get("status") == "resolved":
                entid = r["candidate"].get("entid")
                resolved_name = r["candidate"].get("企业全称")
                if entid:
                    _name_index_put(name, entid)
                    if resolved_name and resolved_name != name:
                        _name_index_put(resolved_name, entid)
            else:
                return r  # not_found / ambiguous / error 原样返回，交古立特处理
    else:
        resolved_name = name

    if not entid:
        return {"status": "error", "message": "未能解析企业 entid"}

    dims = dimensions or list(_DEFAULT_DIMENSIONS)
    unknown = [d for d in dims if d not in _DIMENSIONS]
    if unknown:
        return {"status": "error", "message": f"未知维度 {unknown}，可选：{list(_DIMENSIONS)}"}

    # 2) 缓存命中（要求覆盖所请求的全部维度）
    if not refresh:
        cached = _cache_read(entid, cache_ttl_days)
        if cached and all(d in (cached.get("dimensions") or {}) for d in dims):
            out = {k: v for k, v in cached.items() if not k.startswith("_")}
            out["status"] = "success"
            out["from_cache"] = True
            out["本次消耗API次数"] = api_calls
            _write_entity_context(out)  # 沉淀桥：事实回流进 entities/<名>.md
            return out

    # 3) 逐维度取数
    result_dims = {}
    risk_summary = {}
    errors = []
    for d in dims:
        version, cn_name, _single = _DIMENSIONS[d]
        try:
            body = _request("/skills/dataDimension", {"version": version, "entid": entid})
            api_calls += 1
        except Exception as e:
            errors.append({"维度": cn_name, "错误": str(e)[:120]})
            continue
        ok, code, msg = _interpret_code(body)
        if not ok:
            if code in (9999, "9999") and "上限" in str(msg):
                return {"status": "error", "engine": "风鸟API", "message": f"额度已达上限：{msg}"}
            errors.append({"维度": cn_name, "code": code, "msg": msg})
            continue
        total, rows = _extract_rows(body, version)
        normalizer = _NORMALIZERS.get(d, _norm_generic)
        if d == "basic":
            result_dims[d] = {"名称": cn_name, "数据": normalizer(rows if isinstance(rows, dict) else {})}
        else:
            normalized = normalizer(rows if isinstance(rows, list) else [])
            result_dims[d] = {"名称": cn_name, "记录数": total, "数据(最多5条)": normalized}
            if d in _RISK_DIMENSIONS:
                risk_summary[cn_name] = total

    out = {
        "status": "success",
        "engine": "风鸟API",
        "entid": entid,
        "企业全称": resolved_name,
        "dimensions": result_dims,
        "from_cache": False,
        "本次消耗API次数": api_calls,
    }
    if risk_summary:
        out["风险摘要"] = risk_summary
        out["有风险记录"] = any(v and v > 0 for v in risk_summary.values())
    if errors:
        out["部分失败"] = errors

    # 4) 写缓存 + 沉淀桥（事实回流进 entities/<名>.md）
    _cache_write(entid, out)
    _write_entity_context(out)
    return out
