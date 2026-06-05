"""
上市公司公告/年报批量下载工具

数据源：巨潮资讯网（cninfo.com.cn）公开接口，无需 API Key。
支持：年报、半年报、季报、IPO、配股、增发等各类公告。
"""
import os
import re
import time
from pathlib import Path


# 公告类型映射
_CATEGORY_MAP = {
    "年报": "category_ndbg_szsh",
    "半年报": "category_bndbg_szsh",
    "一季报": "category_yjdbg_szsh",
    "三季报": "category_sjdbg_szsh",
    "IPO": "category_sf_szsh",
    "配股": "category_pg_szsh",
    "增发": "category_zf_szsh",
    "债券": "category_zq_szsh",
    "全部": "",
}


def _resolve_stock_code(company: str, headers: dict) -> tuple:
    """
    通过巨潮搜索接口解析公司简称/代码 → (orgId, stock_code, sec_name)。
    
    巨潮的 hisAnnouncement/query 接口用 stock 参数（格式 "代码,orgId"）
    可以精确匹配到具体公司，避免 searchkey 全文搜索的误匹配。
    """
    import requests
    
    # 如果输入的是纯数字（股票代码），直接用代码搜索
    # 如果是中文名称，先通过搜索建议接口获取 orgId
    suggest_url = "http://www.cninfo.com.cn/new/information/topSearch/query"
    
    try:
        resp = requests.post(
            suggest_url,
            data={"keyWord": company, "maxNum": 5},
            headers=headers,
            timeout=10,
        )
        results = resp.json()
        
        if not results:
            return None, None, None
        
        # results 是列表，每项有 code, zwjc(中文简称), orgId 等字段
        # 优先精确匹配
        for item in results:
            code = item.get("code", "")
            short_name = item.get("zwjc", "") or item.get("shortName", "")
            org_id = item.get("orgId", "")
            
            # 精确匹配：代码完全一致 或 简称完全一致
            if code == company or short_name == company:
                return org_id, code, short_name
        
        # 没有精确匹配，取第一个结果
        first = results[0]
        return first.get("orgId", ""), first.get("code", ""), first.get("zwjc", "") or first.get("shortName", "")
        
    except Exception:
        return None, None, None


def download_reports(
    company: str,
    report_type: str = "年报",
    output_dir: str = None,
    max_count: int = 10,
    years: list = None,
) -> dict:
    """
    从巨潮资讯网批量下载上市公司公告/年报 PDF。

    Args:
        company: 公司简称或股票代码（如 "五粮液"、"贵州茅台" 或 "600519"）
        report_type: 报告类型，可选：年报/半年报/一季报/三季报/IPO/配股/增发/债券/全部
        output_dir: 下载目录（不指定则使用当前目录下的 reports/ 子目录）
        max_count: 最多下载几份（默认 10），仅在 years 未指定时生效
        years: 指定年份列表（如 [2015, 2023]）。指定后只下载标题含对应年份的公告，
               max_count 失效，命中多少下多少。年份可用 int 或 str。

    Returns:
        dict: {
            "status": "success"|"error",
            "company": 公司名称,
            "report_type": 报告类型,
            "downloaded": [下载成功的文件列表],
            "failed": [下载失败的列表],
            "message": str
        }
    """
    import requests

    if not company:
        return {"status": "error", "message": "请输入公司简称或股票代码"}

    # 解析报告类型
    category = _CATEGORY_MAP.get(report_type, "")
    if report_type not in _CATEGORY_MAP:
        return {
            "status": "error",
            "message": f"不支持的报告类型：{report_type}，可选：{list(_CATEGORY_MAP.keys())}",
        }

    # 输出目录：默认存到 gridman-mind/reports/公司名
    if output_dir:
        out_dir = Path(output_dir)
    else:
        from gridman_mcp.tools._shared.paths import get_mind_dir
        out_dir = get_mind_dir() / "reports" / company
    out_dir.mkdir(parents=True, exist_ok=True)

    # 归一化年份列表：[2015, "2023"] → ["2015", "2023"]
    year_strs = []
    if years:
        for y in years:
            try:
                ys = str(int(y))  # 防止 "2015年" 这种带后缀的
                if len(ys) == 4 and ys.isdigit():
                    year_strs.append(ys)
            except (ValueError, TypeError):
                # 用户传 "2015年" 之类，提取 4 位数字
                m = re.search(r"(19|20)\d{2}", str(y))
                if m:
                    year_strs.append(m.group(0))

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl",
    }

    try:
        # ── 步骤 1：解析公司 → 获取 orgId 和精确代码 ──
        org_id, stock_code, sec_name = _resolve_stock_code(company, headers)
        
        # 构建 stock 参数（精确匹配格式："代码,orgId"）
        stock_param = ""
        if org_id and stock_code:
            stock_param = f"{stock_code},{org_id}"
        
        # ── 步骤 2：查询公告列表 ──
        search_url = "http://www.cninfo.com.cn/new/hisAnnouncement/query"

        # 指定年份模式：拉大页面，确保老年份能被覆盖到
        # 巨潮按时间倒序返回，年报每年 1-2 份，30 年也就 30-60 份；
        # 季报每年 4 份，30 年也就 120 份。pageSize=200 通常够用
        page_size = 200 if year_strs else max_count * 2

        payload = {
            "stock": stock_param,
            "searchkey": "" if stock_param else company,  # 有精确匹配就不用模糊搜索
            "tabName": "fulltext",
            "pageSize": page_size,
            "pageNum": 1,
            "column": "",
            "category": category,
            "plate": "",
            "seDate": "",
            "secid": "",
            "sortName": "",
            "sortType": "",
            "isHLtitle": "true",
        }

        resp = requests.post(search_url, data=payload, headers=headers, timeout=15)
        result = resp.json()
        announcements = result.get("announcements", []) or []

        if not announcements:
            return {
                "status": "error",
                "message": f"未找到 {company} 的 {report_type} 公告。请确认公司名称或代码是否正确。",
                "resolved_as": sec_name or company,
            }

        # ── 步骤 3：二次过滤 ──
        # 只保留 secName 匹配目标公司的结果（排除"别人公告里提到该公司"的情况）
        target_name = sec_name or company
        filtered = []
        for ann in announcements:
            ann_sec = ann.get("secName", "").replace("<em>", "").replace("</em>", "")
            # secName 包含目标公司名 或 目标公司名包含 secName（处理简称/全称差异）
            if (target_name in ann_sec) or (ann_sec in target_name) or (stock_code and stock_code in ann.get("secCode", "")):
                filtered.append(ann)
        
        # 如果过滤后为空，放宽条件用原始结果
        if not filtered:
            filtered = announcements

        # ── 步骤 3.5：年份过滤（如果用户指定了 years 参数）──
        if year_strs:
            year_filtered = []
            for ann in filtered:
                ann_title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
                # 命中标题里任意一个目标年份就保留
                if any(y in ann_title for y in year_strs):
                    year_filtered.append(ann)
            filtered = year_filtered
            
            if not filtered:
                return {
                    "status": "error",
                    "company": sec_name or company,
                    "stock_code": stock_code or "",
                    "report_type": report_type,
                    "years_requested": year_strs,
                    "message": f"未找到 {company} 在 {year_strs} 年份的 {report_type} 公告。该公司可能在这些年份未发布此类报告，或公告标题中不含年份字样。",
                }

        # ── 步骤 4：批量下载 PDF ──
        # 指定年份时，命中多少下多少；否则按 max_count 截断
        download_limit = len(filtered) if year_strs else max_count
        base_url = "http://static.cninfo.com.cn/"
        downloaded = []
        failed = []

        for ann in filtered[:download_limit]:
            title = ann.get("announcementTitle", "未知公告")
            # 清理 HTML 标签
            title = title.replace("<em>", "").replace("</em>", "")
            adj_url = ann.get("adjunctUrl", "")
            ann_sec_name = ann.get("secName", company)
            ann_sec_name = ann_sec_name.replace("<em>", "").replace("</em>", "")
            ann_date = ann.get("announcementTime", "")

            if not adj_url:
                failed.append({"title": title, "reason": "无下载链接"})
                continue

            # 构建文件名
            if ann_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(ann_date / 1000)
                    date_str = dt.strftime("%Y%m%d")
                except (ValueError, TypeError, OSError):
                    date_str = ""
            else:
                date_str = ""

            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|')[:80]
            filename = f"{ann_sec_name}_{date_str}_{safe_title}.pdf" if date_str else f"{ann_sec_name}_{safe_title}.pdf"
            filepath = out_dir / filename

            # 下载
            try:
                pdf_url = base_url + adj_url
                pdf_resp = requests.get(pdf_url, headers=headers, timeout=60)

                if pdf_resp.status_code == 200 and len(pdf_resp.content) > 1000:
                    filepath.write_bytes(pdf_resp.content)
                    downloaded.append({
                        "title": title,
                        "file": str(filepath),
                        "size_kb": len(pdf_resp.content) // 1024,
                    })
                else:
                    failed.append({"title": title, "reason": f"HTTP {pdf_resp.status_code} 或文件过小"})

            except Exception as e:
                failed.append({"title": title, "reason": str(e)})

            # 礼貌间隔，避免被封
            time.sleep(0.5)

        return {
            "status": "success" if downloaded else "error",
            "company": sec_name or company,
            "stock_code": stock_code or "",
            "report_type": report_type,
            "years_requested": year_strs if year_strs else None,
            "total_found": len(filtered),
            "downloaded": downloaded,
            "failed": failed,
            "output_dir": str(out_dir),
            "message": f"找到 {len(filtered)} 份公告，成功下载 {len(downloaded)} 份，失败 {len(failed)} 份",
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "message": "巨潮资讯网请求超时，请稍后重试"}
    except requests.exceptions.ConnectionError:
        return {"status": "error", "message": "无法连接巨潮资讯网，请检查网络"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
