# MCP 工具明细清单

> 定位：gridman-mcp 工具层（MCP Server）的完整工具清单与调用说明（操作参考，非知识内容、非 roster）
> 来源：gridman-mcp/gridman_mcp（以 server.py 的 @tool 装饰器为准）
> 覆盖：数据/审计/文档/财务/市场/办公 6 大功能类别
> 性质：操作参考
> 加载：按需——SKILL.md 已含"MCP配置则调/未配则降级 + 6 类门控"决策规则；**要调具体工具、需要确切工具名/参数时**读本表；判断"该不该用工具"不必读本表

---

当 MCP Server（gridman）已配置时，对"帮我做/帮我算/帮我生成"类请求调用计算工具：

> ⚠️ **工具只产数据、不产判断**：凡工具产出要作为财税结论/判断交付（账龄、报表、税额、比率、勾稽、异常等），交付前先回知识库做财税判断（口径/正常区间/雷区/勾稽规则），别把原始输出当结论直接交。纯机械操作（PDF 合并/拆分、地址拆分、格式转换）不在此列。详见 SKILL.md「工作行为规则 · 财税文件分析规则」②④步。

**工具规模**：44 个业务工具（按下方 6 类门控）+ `gridman_locate` 1 个常驻 meta 工具（不受 GRIDMAN_TOOLS 门控，任何配置下都在）。类别名与 server.py 的 `@tool("类别")` 装饰器、INSTALL.md 门控、SKILL.md 完全对齐：数据 / 审计 / 文档 / 财务 / 市场 / 办公（中英文均可：data / audit / document / finance / market / office）。

> **MCP 面板显示的数字 = 45**（默认全开时）= 44 业务工具 + 1 meta。面板统计的是全部已注册工具、不区分业务与 meta。用户用 `GRIDMAN_TOOLS` 精简后这个数字会随业务工具减少而变小，但 `gridman_locate` 始终保留——所以最小也是 1。看到面板数字与"44"对不上属正常。

### 数据（data，8 个）

| 工具 | 功能 |
| --- | --- |
| `balance_sheet_process` | 科目余额表处理（删非末级行、拆科目层级、标准化输出） |
| `address_split` | 地址拆分省市区（含邮编匹配，用于函证发送） |
| `data_file_overview` | 数据概览（行列/类型/缺失/统计） |
| `data_group_summary` | 分组汇总（sum/mean/count/max/min/std/median） |
| `data_filter` | 数据筛选（>/</>=/<=/==/!=/contains/startswith） |
| `data_pivot` | 透视表 |
| `fuzzy_match` | 名称模糊匹配（相似度+中文公司名标准化，对账/关联方识别/数据清洗） |
| `chart_generate` | 统计图表生成（折线/柱状/饼/散点/热力/堆积柱状/瀑布；png 静态 或 xlsx 内嵌交互） |

### 审计（audit，13 个）

| 工具 | 功能 |
| --- | --- |
| `bank_reconciliation` | 银行余额调节表自动编制 |
| `aging_analysis` | 往来账龄分析（生成 + 四步复核 mode=verify） |
| `benford_law_check` | 本福特定律检验 |
| `depreciation_check` | 固定资产折旧重算（直线/双倍余额递减/年数总和） |
| `audit_sampling` | 审计抽样（随机/系统/MUS货币单位抽样） |
| `audit_adjustment` | 审计调整三栏 TB（未审+调整=审定，借贷平衡校验，古立特配色） |
| `cutoff_test` | 截止测试（前后窗口筛选 + 自动标记可疑项：临近截止日/大额/整数/月末月初） |
| `confirmation_letter` | 函证生成（银行/应收/应付/律师 → Word + Excel 清单，每对象一页含回函栏） |
| `workpaper_init` | 底稿框架初始化（7 大文件夹 + 全套空白模板，含计划/风险/完成阶段/职业判断） |
| `materiality_calculator` | 重要性计算（CSA 1320，自动选基准 + 三档计算 + 职业判断说明） |
| `analytical_procedures` | 分析性程序（本期 vs 上期波动分析，单条件/双条件，自动标记异常项） |
| `reclassification` | 往来款重分类（按 CAS 30 按明细余额方向分别列报，明细表+调整分录+报表汇总） |
| `voucher_scan` | 凭证巡检（七大类高风险扫描：差旅占比/供应商付款/大额整数/周末/冲销/现金/费用占比） |

### 文档（document，3 个）

| 工具 | 功能 |
| --- | --- |
| `document_ocr` | 文档识别（PDF/图片/Office → Markdown，MinerU 云端）；单文件传 `file_path`、多文件传 `file_paths`（最多 200 个，自动分批并行） |
| `pdf_pages` | PDF 页面操作（`action=merge` 合并 / `split` 按范围拆 / `extract` 提取页） |
| `voucher_pdf_split` | 记账凭证 PDF 按凭证号自动拆分 |

### 财务（finance，9 个）

| 工具 | 功能 |
| --- | --- |
| `cashflow_test` | 现金流量表测算（间接法倒推，与报表对比识别差异） |
| `cashflow_direct` | 直接法现金流量表（穿透序时账逐笔归类经营/投资/筹资） |
| `non_recurring_items` | 非经常性损益计算（证监会定义，税前→税后→扣非净利润） |
| `financial_ratios` | 财务比率分析（变现/效率/负债/盈利/每股，生成分析底稿） |
| `tax_adjustment` | 纳税调整明细（自动识别税会差异，计算调增/调减） |
| `pvm_decompose` | 完整 PVM 五效应分解（量/价/Mix/成本/交叉，多产品两期毛利精确归因，回答"卖少了还是卖错结构了"，补全老版残差法缺口） |
| `structure_rate_attribution` | 单位指标变动归因（结构 vs 费率，精确闭合，回答"是组合变了还是水平真变了"） |
| `dimension_explainer` | 多维利润质量诊断（η²/ω² 解释力排序+规模质量矩阵+拖累贡献，含高基数偏误修正） |
| `concentration_hhi` | HHI 赫芬达尔集中度（单期+多期趋势，客户/区域/产品/供应商集中度风险评估） |

### 市场（market，6 个）

| 工具 | 功能 |
| --- | --- |
| `market_quote` | 多市场实时行情（A股/港股/美股/指数）+ 批量 + 异动信号 |
| `company_search` | 企业模糊搜索（工商查询第一步，主体消歧，返回候选 entid，需 RISKBIRD_API_KEY） |
| `company_query` | 企业工商+风险画像取数（basic/股东/董监高/被执行/失信/经营异常等维度，带往来单位缓存，需 RISKBIRD_API_KEY） |
| `stock_history` | 历史 K 线（A股/港股/美股，daily/weekly/monthly，qfq/hfq） |
| `stock_financial` | A股财务数据（利润表/资产负债表/现金流量表） |
| `report_download` | 上市公司年报/公告批量下载（巨潮资讯网，无需 API Key） |

### 办公（office，5 个，仅 Windows，需 pywin32）

| 工具 | 功能 |
| --- | --- |
| `office_list_apps` | 检测运行中的办公应用（M365 / WPS 的 Excel/Word/PPT） |
| `excel_op` | 当前打开表格操作（`action=read` 读值/读公式 / `write` 写数据 / `formula` 设公式） |
| `word_op` | 当前打开文字文档操作（`action=read` 读全文 / `append` 末尾追加文本） |
| `ppt_op` | 当前打开演示文稿操作（`action=info` 看幻灯片列表 / `add_slide` 末尾加页） |
| `office_save_as` | 当前文档另存为（可把 WPS 私有/加密格式转标准 docx/xlsx/pptx/pdf） |

> office 协同类 5 个工具的行为约束（先看清引擎、先问后动、可被教记进 mind 等）见 SKILL.md「实时协同办公规则」，本表不重复。

### 常驻 meta 工具（不受门控）

| 工具 | 功能 |
| --- | --- |
| `gridman_locate` | 定位记忆区 gridman-mind 绝对路径并写主目录指针 `~/.gridman/home.json`（仅在确实要读写 mind 时调） |

> 它是"基础设施"不是"业务功能"，所以 server.py 在 `_register_selected()` 里把它放最前面无条件注册、跳过 GRIDMAN_TOOLS 门控。
> - `gridman_locate`：mind 记忆体系的指南针。server 跑在 gridman-mcp 目录里，能可靠算出 `gridman-mind/` 绝对路径（不靠猜），并写指针 `~/.gridman/home.json` 实现"扫一次、之后新对话都记得"（连纯 Skill 无 MCP 场景也能读这指针找 mind）。返回各子目录路径 + mind 是否已存在 + 当前启用的工具类别。再怎么精简工具都不关它——否则古立特会"失忆"。

## 附：report_download 行为规则

用户要求下载报告/年报时，不要预判报告是否已发布，直接调用工具查询。巨潮接口会返回实际存在的公告列表，以接口返回结果为准。

- 默认模式（`max_count`）：按发布时间倒序拉最近 N 份。
- 指定年份模式（`years=[2015, 2023]`）：只下标题命中目标年份的公告，`max_count` 失效。**当用户明确说"取 XX 年的报告"时，必须用 years 参数，不要用 max_count 估算**。

## 附：document_ocr 配置说明

`document_ocr` 工具调用 MinerU 云端精准解析 v4 API（vlm 模型），需要用户在 MCP 配置的 env 中填入自己的 `MINERU_API_TOKEN`。

**当前能力**：
- 单文件 ≤ 200MB / 600 页
- 每个账号每天 1000 页免费额度
- Token 有效期 90 天，到期需重新创建

Token 免费获取，详细步骤见 gridman-app 中的 README.md。当用户调用 `document_ocr` 未配置 Token 或 Token 过期时，工具会返回带有完整操作指引的错误提示，无需古立特额外解释。

## 附：company_search / company_query 配置说明

工商查询两件套调用风鸟（Riskbird）云端 API，需要用户在 MCP 配置的 env 中填入 `RISKBIRD_API_KEY`。

- 主体消歧先用 `company_search` 拿候选 entid，确认后再调 `company_query` 取数；已知 entid 时可直接传给 `company_query` 省一次搜索。
- 每个维度 = 1 次 API 调用、模糊搜索 = 1 次；部分 Key 有每日上限。`company_query` 自带往来单位缓存（gridman-mind/entities/），查过的企业零消耗复用，`refresh=True` 强制重查。
- 风鸟数据非法定权威，关键户建议人工到国家企业信用信息公示系统（gsxt.gov.cn）终审。

MCP 不可用时：退回知识指引模式，提供手动步骤和模板，告知用户可配置 MCP 获得自动化能力。
