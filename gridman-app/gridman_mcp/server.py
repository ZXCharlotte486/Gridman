"""古立特 MCP Server 主入口"""
import json
import math
from mcp.server.fastmcp import FastMCP
from gridman_mcp import __version__


def _sanitize(obj):
    """递归清洗：把 inf/nan/numpy 标量等转换为 JSON 可序列化形式。"""
    # numpy 标量
    if hasattr(obj, "item") and callable(getattr(obj, "item", None)):
        try:
            obj = obj.item()
        except Exception:
            return str(obj)
    # 浮点 inf/nan
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    # 容器递归
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    # pandas Timestamp / 日期
    if hasattr(obj, "isoformat") and callable(getattr(obj, "isoformat", None)):
        try:
            return obj.isoformat()
        except Exception:
            return str(obj)
    return obj


def _dumps(result) -> str:
    """统一 JSON 序列化：先 sanitize 再 dumps，保证严格 JSON 兼容。"""
    return json.dumps(_sanitize(result), ensure_ascii=False, indent=2)


from gridman_mcp.tools.data.balance_sheet_processor import process_balance_sheet
from gridman_mcp.tools.audit.bank_reconciliation import reconcile_bank
from gridman_mcp.tools.audit.aging_analysis import analyze_aging
from gridman_mcp.tools.audit.benford_law import check_benford
from gridman_mcp.tools.data.address_split import split_address
from gridman_mcp.tools.document.document_ocr import convert_document, convert_documents_batch
from gridman_mcp.tools.document.pdf_tools import merge_pdfs, split_pdf, extract_pages
from gridman_mcp.tools.document.voucher_split import split_vouchers
from gridman_mcp.tools.market.stock_data import get_stock_quote, get_stock_history, get_financial_data
from gridman_mcp.tools.data.data_analyst import data_overview, group_summary, filter_data, pivot_table
from gridman_mcp.tools.audit.depreciation_check import check_depreciation
from gridman_mcp.tools.audit.audit_sampling import generate_sample
from gridman_mcp.tools.audit.audit_adjustment import run_audit_adjustment
from gridman_mcp.tools.audit.cutoff_test import generate_cutoff_test
from gridman_mcp.tools.audit.confirmation_letter import generate_confirmation_letters
from gridman_mcp.tools.audit.workpaper_init import init_workpaper
from gridman_mcp.tools.audit.materiality_calculator import calculate_materiality
from gridman_mcp.tools.audit.analytical_procedures import run_analytical_procedures
from gridman_mcp.tools.market.report_download import download_reports
from gridman_mcp.tools.finance.cashflow_test import test_cashflow
from gridman_mcp.tools.finance.cashflow_direct import generate_cashflow_direct
from gridman_mcp.tools.finance.non_recurring_items import calculate_non_recurring
from gridman_mcp.tools.finance.financial_ratios import calculate_ratios
from gridman_mcp.tools.finance.tax_adjustment import generate_tax_adjustment
from gridman_mcp.tools.audit.reclassification import run_reclassification
from gridman_mcp.tools.audit.voucher_scan import scan_vouchers
from gridman_mcp.tools.data.fuzzy_match import fuzzy_match as run_fuzzy_match

mcp = FastMCP("gridman")


@mcp.tool()
def balance_sheet_process(
    file_path: str,
    code_column: str = "科目代码",
    name_column: str = "科目名称",
    output_path: str = None,
) -> str:
    """科目余额表处理：删除非末级科目行、拆分科目层级、标准化输出。"""
    result = process_balance_sheet(
        file_path=file_path,
        code_column=code_column,
        name_column=name_column,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def bank_reconciliation(
    bank_statement_path: str,
    ledger_path: str,
    date_tolerance_days: int = 3,
    output_path: str = None,
) -> str:
    """银行余额调节表：将银行对账单与企业账面日记账逐笔匹配，识别未达账项，生成调节表。"""
    result = reconcile_bank(
        bank_statement_path=bank_statement_path,
        ledger_path=ledger_path,
        date_tolerance_days=date_tolerance_days,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def aging_analysis(
    file_path: str,
    base_date: str,
    aging_brackets_months: list = None,
    output_path: str = None,
) -> str:
    """往来账龄分析：按先进先出法计算各客商账龄分布，生成账龄分析表。base_date 格式：YYYY-MM-DD"""
    result = analyze_aging(
        file_path=file_path,
        base_date=base_date,
        aging_brackets_months=aging_brackets_months,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def benford_law_check(
    file_path: str,
    amount_column: str,
    output_path: str = None,
) -> str:
    """本福特定律检验：对财务数据进行首位数字分布检验，识别可能的数据异常或造假信号。"""
    result = check_benford(
        file_path=file_path,
        amount_column=amount_column,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def address_split(
    file_path: str,
    address_column: str = "地址",
    output_path: str = None,
    add_zipcode: bool = True,
) -> str:
    """地址拆分：将完整地址拆分为省、市、区三级信息，用于函证发送。

    add_zipcode=True（默认）时按行政区划匹配邮政编码列（数据源：tombcato/china-zipcode-data，
    MIT，2023版行政区划），邮编由区县级精确匹配，匹配不到时退到市级近似。
    """
    result = split_address(
        file_path=file_path,
        address_column=address_column,
        output_path=output_path,
        add_zipcode=add_zipcode,
    )
    return _dumps(result)


@mcp.tool()
def document_ocr(
    file_path: str,
    langs: str = "zh,en",
    output_path: str = None,
) -> str:
    """文档识别：将 PDF/图片/Office 文件转换为 Markdown 文本。

    调用 MinerU 云端精准解析 API（vlm 模型），支持复杂排版、表格、公式识别。
    适合年报、招股书、扫描件、研究报告等。需在 env 中配置 MINERU_API_TOKEN。
    """
    result = convert_document(
        file_path=file_path,
        output_path=output_path,
        langs=langs,
    )
    return _dumps(result)


@mcp.tool()
def document_ocr_batch(
    file_paths: list,
    output_dir: str = None,
    langs: str = "zh,en",
) -> str:
    """批量文档识别：将多个 PDF/图片/Office 文件批量转换为 Markdown。

    单次最多 200 个文件（内部自动按 50 个一批提交），所有文件并行解析。
    结果按文件名保存到 output_dir（如指定）。需在 env 中配置 MINERU_API_TOKEN。
    """
    result = convert_documents_batch(
        file_paths=file_paths,
        output_dir=output_dir,
        langs=langs,
    )
    return _dumps(result)


@mcp.tool()
def pdf_merge(
    file_paths: list,
    output_path: str,
) -> str:
    """PDF 合并：将多个 PDF 文件合并为一个。按列表顺序拼接。"""
    result = merge_pdfs(file_paths=file_paths, output_path=output_path)
    return _dumps(result)


@mcp.tool()
def pdf_split(
    file_path: str,
    ranges: str,
    output_dir: str,
) -> str:
    """PDF 拆分：按页码范围拆分 PDF。ranges 格式如 "1-5,6-10,11-20"。"""
    result = split_pdf(file_path=file_path, ranges=ranges, output_dir=output_dir)
    return _dumps(result)


@mcp.tool()
def pdf_extract(
    file_path: str,
    pages: str,
    output_path: str,
) -> str:
    """PDF 提取页面：从 PDF 中提取指定页面。pages 格式如 "1,3,5,7-10"。"""
    result = extract_pages(file_path=file_path, pages=pages, output_path=output_path)
    return _dumps(result)


@mcp.tool()
def voucher_pdf_split(
    file_path: str,
    output_dir: str,
    prefix: str = "记",
) -> str:
    """记账凭证拆分：将包含多份记账凭证的扫描 PDF 按凭证自动拆分为独立文件。

    自动识别凭证边界，按"记{月份}-{编号}.pdf"格式命名。
    """
    result = split_vouchers(file_path=file_path, output_dir=output_dir, prefix=prefix)
    return _dumps(result)


@mcp.tool()
def stock_quote(symbol: str) -> str:
    """A股实时行情：获取个股最新价、涨跌幅、成交量、市盈率等。symbol 为股票代码如 "000001"。"""
    result = get_stock_quote(symbol=symbol)
    return _dumps(result)


@mcp.tool()
def stock_history(
    symbol: str,
    period: str = "daily",
    start_date: str = "",
    end_date: str = "",
    adjust: str = "qfq",
) -> str:
    """A股历史K线：获取个股历史行情数据。period 可选 daily/weekly/monthly，adjust 可选 qfq/hfq/空。"""
    result = get_stock_history(
        symbol=symbol, period=period, start_date=start_date, end_date=end_date, adjust=adjust
    )
    return _dumps(result)


@mcp.tool()
def stock_financial(symbol: str, report_type: str = "income") -> str:
    """A股财务数据：获取个股利润表/资产负债表/现金流量表。report_type 可选 income/balance/cashflow。"""
    result = get_financial_data(symbol=symbol, report_type=report_type)
    return _dumps(result)


@mcp.tool()
def data_file_overview(file_path: str, sheet_name: str = None) -> str:
    """数据概览：查看 CSV/Excel 文件的行列数、列名、数据类型、缺失值和基本统计。"""
    result = data_overview(file_path=file_path, sheet_name=sheet_name)
    return _dumps(result)


@mcp.tool()
def data_group_summary(
    file_path: str,
    group_by: str,
    agg_column: str,
    agg_func: str = "sum",
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """分组汇总：按指定列分组聚合。agg_func 可选 sum/mean/count/max/min/std/median。"""
    result = group_summary(
        file_path=file_path, group_by=group_by, agg_column=agg_column,
        agg_func=agg_func, sheet_name=sheet_name, output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def data_filter(
    file_path: str,
    column: str,
    operator: str,
    value: str,
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """数据筛选：按条件过滤。operator 支持 >/</>=/<=/==/!=/contains/startswith。"""
    result = filter_data(
        file_path=file_path, column=column, operator=operator,
        value=value, sheet_name=sheet_name, output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def data_pivot(
    file_path: str,
    index: str,
    columns: str = None,
    values: str = None,
    agg_func: str = "sum",
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """透视表：生成数据透视表。指定行标签(index)、列标签(columns)、值(values)和聚合函数。"""
    result = pivot_table(
        file_path=file_path, index=index, columns=columns,
        values=values, agg_func=agg_func, sheet_name=sheet_name, output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def depreciation_check(
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
) -> str:
    """固定资产折旧重算：根据折旧方法（直线/双倍余额递减/年数总和）重算累计折旧并与账面比对。

    支持：straight_line（直线法）/ double_declining（双倍余额递减法）/ sum_of_years（年数总和法）。
    输出每项资产的重算累计折旧、账面累计折旧、差异及差异方向。check_date 格式：YYYY-MM-DD。
    """
    result = check_depreciation(
        file_path=file_path, check_date=check_date,
        method_column=method_column, cost_column=cost_column,
        salvage_rate_column=salvage_rate_column, useful_life_column=useful_life_column,
        start_date_column=start_date_column, book_accumulated_column=book_accumulated_column,
        name_column=name_column, sheet_name=sheet_name, output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def audit_sampling(
    file_path: str,
    method: str = "random",
    sample_size: int = None,
    amount_column: str = None,
    risk_level: str = "medium",
    sheet_name: str = None,
    output_path: str = None,
    random_seed: int = None,
) -> str:
    """审计抽样：从总体中按指定方法抽取样本。

    method 可选：
    - random：随机抽样（每个项目等概率）
    - systematic：系统抽样（等距抽取）
    - mus：货币单位抽样（金额越大被抽中概率越高，需指定 amount_column）

    risk_level（low/medium/high）用于在 sample_size 未指定时自动估算样本量。
    输出包含抽样样本、抽样记录表（含选取标准、金额覆盖率、随机种子）。
    """
    result = generate_sample(
        file_path=file_path, method=method, sample_size=sample_size,
        amount_column=amount_column, risk_level=risk_level,
        sheet_name=sheet_name, output_path=output_path, random_seed=random_seed,
    )
    return _dumps(result)


@mcp.tool()
def audit_adjustment(
    tb_path: str,
    adjustments_path: str,
    code_column: str = "科目代码",
    name_column: str = "科目名称",
    debit_column: str = "借方余额",
    credit_column: str = "贷方余额",
    adj_entry_column: str = "分录号",
    adj_code_column: str = "科目代码",
    adj_debit_column: str = "借方",
    adj_credit_column: str = "贷方",
    adj_memo_column: str = "摘要",
    output_path: str = None,
    tb_sheet: str = None,
    adj_sheet: str = None,
) -> str:
    """审计调整分录汇总 — 底稿核心逻辑：未审 + 调整 = 审定。

    输入未审 TB（科目代码/科目名称/借方余额/贷方余额）和调整分录表（分录号/科目代码/借方/贷方/摘要），
    输出三栏 TB（未审借/贷、调整借/贷、审定借/贷）+ 调整分录平衡校验 + 总借贷平衡校验。
    采用古立特统一配色（深灰紫表头、浅灰紫小计、隔行变色）。
    """
    result = run_audit_adjustment(
        tb_path=tb_path, adjustments_path=adjustments_path,
        code_column=code_column, name_column=name_column,
        debit_column=debit_column, credit_column=credit_column,
        adj_entry_column=adj_entry_column, adj_code_column=adj_code_column,
        adj_debit_column=adj_debit_column, adj_credit_column=adj_credit_column,
        adj_memo_column=adj_memo_column,
        output_path=output_path, tb_sheet=tb_sheet, adj_sheet=adj_sheet,
    )
    return _dumps(result)


@mcp.tool()
def cutoff_test(
    file_path: str,
    cutoff_date: str,
    window_days: int = 7,
    date_column: str = "凭证日期",
    amount_column: str = "金额",
    voucher_column: str = "凭证号",
    summary_column: str = "摘要",
    account_column: str = "科目",
    test_type: str = "general",
    keywords: list = None,
    amount_threshold: float = None,
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """截止测试：从序时账中筛选出截止日前后 N 天的交易，识别跨期风险。

    test_type 可选：
    - general：通用截止测试（不限科目）
    - revenue：收入截止（自动筛选含"收入"的科目）
    - purchase：采购截止（采购/原材料/库存商品）
    - expense：费用截止（管理费用/销售费用/财务费用）
    - receivable：应收账款截止
    - payable：应付账款截止

    输出三个 Sheet：可疑项 / 截止日前样本 / 截止日后样本。
    自动标记可疑项（临近截止日、大额、整数、月末月初），按古立特配色输出。
    """
    result = generate_cutoff_test(
        file_path=file_path, cutoff_date=cutoff_date, window_days=window_days,
        date_column=date_column, amount_column=amount_column,
        voucher_column=voucher_column, summary_column=summary_column,
        account_column=account_column, test_type=test_type,
        keywords=keywords, amount_threshold=amount_threshold,
        sheet_name=sheet_name, output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def confirmation_letter(
    sample_path: str,
    confirmation_type: str,
    entity_name: str,
    cutoff_date: str,
    return_address: str = "",
    return_email: str = "",
    counterparty_column: str = "对方名称",
    amount_column: str = "金额",
    address_column: str = "地址",
    contact_column: str = "联系人",
    extra_columns: list = None,
    sheet_name: str = None,
    output_dir: str = None,
) -> str:
    """函证生成：批量生成 Word 询证函 + Excel 函证清单。

    confirmation_type 可选：
    - bank：银行存款及借款询证函（询余额/借款/未结算/保证金/授信）
    - receivable：应收账款询证函
    - payable：应付账款询证函
    - lawyer：律师函证（询诉讼/或有事项）

    输入：函证样本表（通常是 audit_sampling 的输出）+ 项目基础信息。
    输出：每个对象一页的 Word 函证（含回函栏）+ 函证清单 Excel。
    各所封面/抬头/装订格式由用户自行处理，古立特只生成核心内容。
    """
    result = generate_confirmation_letters(
        sample_path=sample_path,
        confirmation_type=confirmation_type,
        entity_name=entity_name,
        cutoff_date=cutoff_date,
        return_address=return_address,
        return_email=return_email,
        counterparty_column=counterparty_column,
        amount_column=amount_column,
        address_column=address_column,
        contact_column=contact_column,
        extra_columns=extra_columns,
        sheet_name=sheet_name,
        output_dir=output_dir,
    )
    return _dumps(result)


@mcp.tool()
def workpaper_init(
    client_name: str,
    audit_year: int,
    output_dir: str = None,
    is_group_audit: bool = False,
    perform_control_test: bool = False,
) -> str:
    """审计底稿初始化：自动生成完整目录结构 + 12 份空白模板。

    按《审计底稿全流程操作手册》标准 7 大文件夹结构（计划/控制测试/实质性程序/
    准则合规/职业判断/完成阶段/备查类）+ 索引 + README。

    模板含古立特统一灰紫配色（可改），用户只需填充内容。
    is_group_audit=True 时增加集团审计相关模板。
    """
    result = init_workpaper(
        client_name=client_name, audit_year=audit_year,
        output_dir=output_dir, is_group_audit=is_group_audit,
        perform_control_test=perform_control_test,
    )
    return _dumps(result)


@mcp.tool()
def materiality_calculator(
    profit_before_tax: float = None,
    total_assets: float = None,
    revenue: float = None,
    base: str = "auto",
    base_rate: float = None,
    performance_ratio: float = 0.60,
    trivial_ratio: float = 0.05,
    is_group_audit: bool = False,
    group_component_ratio: float = 0.80,
    output_path: str = None,
) -> str:
    """重要性水平计算（CSA 1320）：自动选择基准并计算三档重要性。

    base 可选：profit_before_tax / total_assets / revenue / auto（自动选择）。
    auto 模式优先用税前利润，亏损或微利时改用总资产/营业收入。

    输出整体重要性 / 实际执行重要性 / 明显微小错报 + 可直接复制到底稿的职业判断说明。
    集团审计 (is_group_audit=True) 自动应用双限值规则。
    """
    result = calculate_materiality(
        profit_before_tax=profit_before_tax, total_assets=total_assets,
        revenue=revenue, base=base, base_rate=base_rate,
        performance_ratio=performance_ratio, trivial_ratio=trivial_ratio,
        is_group_audit=is_group_audit, group_component_ratio=group_component_ratio,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def analytical_procedures(
    file_path: str,
    current_column: str = "本期",
    prior_column: str = "上期",
    account_column: str = "科目",
    threshold: float = 0.10,
    sheet_name: str = None,
    output_path: str = None,
    structural_threshold: float = None,
    total_base_account: str = None,
) -> str:
    """分析性程序：本期 vs 上期科目对比，标记异常波动。

    输入：含本期、上期金额的对比表（科目余额表的"本期/上期"列）。
    输出 4 个 Sheet：摘要 / 异常波动 / 重要科目变动 / 全部对比。

    判定模式：
    - 默认（structural_threshold=None）：单条件，仅按 threshold 判变动率异常
    - 双条件（传 structural_threshold，如 0.04 表示 4%）：必须同时满足
      结构比 ≥ structural_threshold 且 变动率 ≥ threshold 才标"重大异常"。
      推荐用于风险评估阶段的实质性程序，符合 CSA 1313 重要性原则。
    - total_base_account：双条件模式的结构比基准科目名（如"资产总计""营业收入"），
      未找到时降级到全表本期合计。

    "从无到有/从有到无"在两种模式下都强制标记。
    """
    result = run_analytical_procedures(
        file_path=file_path, current_column=current_column,
        prior_column=prior_column, account_column=account_column,
        threshold=threshold, sheet_name=sheet_name, output_path=output_path,
        structural_threshold=structural_threshold,
        total_base_account=total_base_account,
    )
    return _dumps(result)


@mcp.tool()
def report_download(
    company: str,
    report_type: str = "年报",
    output_dir: str = None,
    max_count: int = 10,
    years: list = None,
) -> str:
    """公告下载：从巨潮资讯网批量下载上市公司年报/半年报/季报等公告 PDF。

    输入公司简称或股票代码，选择报告类型，自动下载到指定目录。
    report_type 可选：年报/半年报/一季报/三季报/IPO/配股/增发/债券/全部。

    默认按发布时间倒序拉取最近 max_count 份；若指定 years（如 [2015, 2023]），
    则只下载标题命中这些年份的公告，max_count 失效。无需 API Key。
    """
    result = download_reports(
        company=company, report_type=report_type,
        output_dir=output_dir, max_count=max_count,
        years=years,
    )
    return _dumps(result)


@mcp.tool()
def cashflow_test(
    tb_path: str,
    profit_data: dict = None,
    report_cashflow: dict = None,
    output_path: str = None,
) -> str:
    """现金流量表测算：从审定TB和利润表数据间接法倒推现金流量表各项目，与报表对比识别差异。

    输入审定后的试算平衡表（含科目名称、期初余额、期末余额）和利润表关键数据。
    输出各经营活动项目测算值 + 间接法验证 + 差异分析。
    profit_data 键包括：revenue、cost、depreciation、finance_expense 等。
    """
    result = test_cashflow(
        tb_path=tb_path,
        profit_data=profit_data,
        report_cashflow=report_cashflow,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def cashflow_direct(
    file_path: str,
    cash_column: str = "科目名称",
    debit_column: str = "借方金额",
    credit_column: str = "贷方金额",
    summary_column: str = "摘要",
    voucher_column: str = "凭证号",
    date_column: str = "日期",
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """直接法现金流量表：穿透序时账逐笔识别现金流项目，生成直接法现金流量表。

    从序时账中筛选涉及现金类科目（库存现金/银行存款/其他货币资金）的分录，
    根据对方科目+摘要关键词自动归类到经营/投资/筹资三大类现金流项目。
    输出：现金流量表（直接法）+ 每笔分录的归类明细。
    未能自动归类的分录标记为"未归类"，需人工判断。
    """
    result = generate_cashflow_direct(
        file_path=file_path,
        cash_column=cash_column,
        debit_column=debit_column,
        credit_column=credit_column,
        summary_column=summary_column,
        voucher_column=voucher_column,
        date_column=date_column,
        sheet_name=sheet_name,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def non_recurring_items(
    items: dict,
    income_tax_rate: float = 0.25,
    minority_share: float = 0.0,
    net_profit: float = None,
    output_path: str = None,
) -> str:
    """非经常性损益计算：根据证监会定义计算非经常性损益合计、所得税影响、扣非净利润。

    items 为各非经常性损益项目金额（dict），键为项目名称，值为金额（收益正、损失负）。
    自动计算：税前合计 → 所得税影响 → 少数股东影响 → 归母非经常性损益净额 → 扣非净利润。
    """
    result = calculate_non_recurring(
        items=items,
        income_tax_rate=income_tax_rate,
        minority_share=minority_share,
        net_profit=net_profit,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def financial_ratios(
    balance_data: dict,
    profit_data: dict,
    prior_balance_data: dict = None,
    prior_profit_data: dict = None,
    shares: float = None,
    cashflow_operating: float = None,
    output_path: str = None,
) -> str:
    """财务比率分析：从资产负债表和利润表数据计算常用财务比率，生成分析底稿。

    覆盖：变现能力（流动/速动比率）、资产管理效率（周转率/周转天数）、
    负债比率（资产负债率/产权比率/利息保障倍数）、盈利能力（毛利率/净利率/ROA/ROE）、
    每股指标（EPS/BVPS/每股经营现金流）。
    balance_data 键：current_assets、inventory、current_liabilities、total_assets、
    total_liabilities、equity、accounts_receivable 等。
    """
    result = calculate_ratios(
        balance_data=balance_data,
        profit_data=profit_data,
        prior_balance_data=prior_balance_data,
        prior_profit_data=prior_profit_data,
        shares=shares,
        cashflow_operating=cashflow_operating,
        output_path=output_path,
    )
    return _dumps(result)



@mcp.tool()
def tax_adjustment(
    file_path: str,
    revenue: float = None,
    salary_total: float = None,
    profit_total: float = None,
    rd_expense: float = None,
    account_column: str = "科目名称",
    amount_column: str = "发生额",
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """纳税调整明细：从科目余额表自动识别税会差异，计算调增/调减，生成纳税调整明细表。

    自动识别的调整项目：职工福利费(14%)、工会经费(2%)、职工教育经费(8%)、
    业务招待费(60%且≤收入5‰)、广告宣传费(15%)、捐赠支出(12%)、
    罚款滞纳金(全额调增)、资产减值准备(全额调增)、研发加计扣除(100%)等。
    需要人工确认的项目会标记出来。
    """
    result = generate_tax_adjustment(
        file_path=file_path,
        revenue=revenue,
        salary_total=salary_total,
        profit_total=profit_total,
        rd_expense=rd_expense,
        account_column=account_column,
        amount_column=amount_column,
        sheet_name=sheet_name,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def reclassification(
    file_path: str,
    counterparty_column: str = None,
    account_column: str = None,
    debit_column: str = None,
    credit_column: str = None,
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """往来款重分类：按CAS 30要求，将往来科目明细按余额方向分别列报为资产和负债。

    输入往来科目余额表（对方名称+科目+借方余额+贷方余额），自动识别需重分类的项目。
    支持两种输入格式：①借方余额+贷方余额两列 ②方向+金额两列。
    输出三个Sheet：重分类明细表 / 调整分录 / 报表项目汇总。
    覆盖科目：应收账款、应付账款、预收账款、预付账款、其他应收款、其他应付款、合同负债。
    """
    result = run_reclassification(
        file_path=file_path,
        counterparty_column=counterparty_column,
        account_column=account_column,
        debit_column=debit_column,
        credit_column=credit_column,
        sheet_name=sheet_name,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def voucher_scan(
    file_path: str,
    revenue: float = None,
    date_column: str = "凭证日期",
    amount_column: str = "金额",
    voucher_column: str = "凭证号",
    summary_column: str = "摘要",
    account_column: str = "科目",
    counterparty_column: str = "对方名称",
    travel_ratio_threshold: float = 0.03,
    vendor_freq_threshold: int = 5,
    sheet_name: str = None,
    output_path: str = None,
) -> str:
    """凭证巡检：扫描序时账识别七大类高风险业务模式，自动标记可疑项。

    扫描类别：
    - 差旅费占比超标（默认 > 3% 营业收入）
    - 供应商付款异常（同一供应商单月多笔零散付款，疑似拆分付款）
    - 大额整数（金额尾数 4 个 0，疑似估计/虚列）
    - 周末凭证（非工作日记账）
    - 红字冲销（频繁冲销/跨期冲销）
    - 现金大额（≥ 5 万的现金类科目支出）
    - 费用占比异动（管理/销售/财务费用占营收比超标）

    输出按风险等级排序（高/中/低），每条带依据和建议。提供 revenue 后扫描更精准。
    """
    result = scan_vouchers(
        file_path=file_path,
        revenue=revenue,
        date_column=date_column,
        amount_column=amount_column,
        voucher_column=voucher_column,
        summary_column=summary_column,
        account_column=account_column,
        counterparty_column=counterparty_column,
        travel_ratio_threshold=travel_ratio_threshold,
        vendor_freq_threshold=vendor_freq_threshold,
        sheet_name=sheet_name,
        output_path=output_path,
    )
    return _dumps(result)


@mcp.tool()
def fuzzy_match(
    left_path: str,
    right_path: str,
    left_column: str,
    right_column: str,
    threshold: int = 70,
    left_sheet: str = None,
    right_sheet: str = None,
    output_path: str = None,
) -> str:
    """名称模糊匹配：两份名单按字符串相似度+中文公司名标准化进行匹配。

    适用场景：应收应付对账（台账 vs 回款单）、关联方识别、函证地址核对、数据清洗。

    匹配策略（分数从高到低）：
    - 完全相等 → 100 分
    - 标准化等（去"有限公司/集团/地区前缀"等通用词后相等） → 95 分
    - 包含关系（短名包含于长名） → 80-90 分
    - Levenshtein 字符相似度 → 0-100 分

    threshold 默认 70 分及以上视为匹配。输出：匹配清单 + 左右两侧未匹配项。
    """
    result = run_fuzzy_match(
        left_path=left_path,
        right_path=right_path,
        left_column=left_column,
        right_column=right_column,
        threshold=threshold,
        left_sheet=left_sheet,
        right_sheet=right_sheet,
        output_path=output_path,
    )
    return _dumps(result)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
