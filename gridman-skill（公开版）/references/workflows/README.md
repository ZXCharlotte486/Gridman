# 端到端工作流（索引）

> 定位：跨多个 MCP 工具的完整业务流程定义
> 来源：审计实务流程设计
> 覆盖：应收审计、银行审计、固定资产审计、凭证数字化、总账分析、月结、财报分析、函证、报表勾稽、IPO尽调、审计调整、截止测试、底稿全流程、财务比率分析、现金流量表编制、纳税调整、个股排雷
> 性质：实操
>
> 拆分说明（2026-06-09 三层重构）：原 `workflows.md` 拆为本目录下 16 个独立工作流文件，按职业归类（audit/tax/finance/investment/bp）。本 README 保留索引头、通用异常升级规则、执行原则、自动选择表。

---

## 工作流索引

| 名称 | 文件 | 输入 | 输出 | 涉及工具 |
|------|------|------|------|----------|
| W1: 应收账款审计套件 | `audit/ar_audit.md` | 应收明细表 + 客户基本信息 | 账龄分析 + 函证抽样 + 函证地址 | balance_sheet_process / aging_analysis / audit_sampling / address_split |
| W2: 银行存款审计套件 | `audit/bank_audit.md` | 银行对账单 + 银行日记账 | 调节表 + 异常日记账 | bank_reconciliation / benford_law_check |
| W3: 固定资产审计套件 | `audit/fa_audit.md` | 固定资产明细表 | 折旧重算 + 抽样核实 | depreciation_check / audit_sampling |
| W4: 扫描凭证数字化 | `audit/voucher_digitize.md` | 扫描版凭证 PDF | 拆分凭证 + OCR 识别 + 结构化数据 | voucher_pdf_split / document_ocr_batch |
| W5: 总账分析与异常检测 | `audit/gl_analysis.md` | 序时账（凭证流水） | 异常分录清单 + 关键交易 | data_file_overview / benford_law_check / data_filter |
| W6: 月结闭环 | `finance/month_end.md` | 各模块业务数据 | 计提调度表 + 余额变动表 + 差异分析 | balance_sheet_process / data_group_summary / data_pivot |
| W7: 上市公司财报分析 | `investment/listed_analysis.md` | 股票代码 | 三年财务数据 + 关键指标分析 | stock_financial / stock_history / data_pivot |
| W8: 函证全流程 | `audit/confirmation_flow.md` | 客户/供应商清单 | 抽样样本 + 拆分地址 + 函证 Word + Excel 清单 | audit_sampling / address_split / confirmation_letter |
| W9: 报表勾稽校验 | `audit/statement_crosscheck.md` | 三大报表 | 各项校验结果 | data_file_overview + 知识库（statement.md） |
| W10: IPO 财务尽调 | `investment/ipo_dd.md` | 拟上市公司基础数据 + 财报 | 收入/毛利/客户分析 + 风险清单 | data_group_summary / data_pivot / benford_law_check + 知识库 |
| W11: 审计调整与底稿三栏 TB | `audit/adjustment_tb.md` | 未审 TB + 调整分录表 | 三栏 TB（未审/调整/审定） + 平衡校验 | balance_sheet_process / audit_adjustment |
| W12: 截止测试 | `audit/cutoff_test.md` | 序时账 + 截止日 | 截止日前后样本 + 可疑项清单 | data_file_overview / cutoff_test |
| W13: 底稿全流程 | `audit/full_workpaper.md` | 客户名 + 财务数据 + 各类原始文件 | 完整底稿包（含模板填充 + 各项程序结果） | workpaper_init / materiality_calculator / analytical_procedures + 全部审计工具 |
| W14: 财务比率分析 | `bp/ratio_analysis.md` | 科目余额表 或 三大报表 | 五类比率分析底稿 + 趋势图 + 异常提示 | financial_ratios / analytical_procedures |
| W15: 现金流量表编制 | `finance/cashflow.md` | 序时账（直接法）或 三大报表+TB（间接法） | 现金流量表 + 与报表勾稽校验 | cashflow_direct / cashflow_test |
| W16: 企业所得税纳税调整 | `tax/tax_adjustment.md` | 科目余额表 或 利润表 + 调整项说明 | 纳税调整明细表 + A105000系列底稿 | tax_adjustment / data_file_overview |
| W17: 个股排雷（一句话端到端） | `investment/stock_screening.md` | 公司名/股票代码 | 排雷报告（市场信号+财务硬伤+先例比对+红黄绿灯） | market_quote / stock_financial / stock_history / financial_ratios / analytical_procedures + 知识库 |

---

## 异常判定通用规则：风险持续性升级

> 类型：规则
> 来源：CSA 1315（评估错报）+ CSA 1520（分析性程序）+ 实务经验
> 置信度：实务经验

[场景：analytical_procedures / voucher_scan / cutoff_test 等工具输出"异常标记"后，按以下规则判断异常的严重性等级]

**升级规则（按持续性分级）**：

| 触发情况 | 风险等级 | 含义 | 行动 |
|---|---|---|---|
| 单期触发阈值 | 单期异常 | 可能是噪音或一次性事件 | 标记观察，不单独下结论 |
| 持续 2 期及以上触发 | 高风险异常 | 系统性问题信号 | 深入核查，纳入审计发现 |
| 持续 3-4 期（全周期）触发 | 极高风险异常 | 管理层行为模式 | 舞弊/重大错报/盈余管理高度可能 |

**"期"的定义与严重性区分**：

| 分析周期 | "持续 2 期" 的含义 | 严重性 |
|---|---|---|
| 年度报表 | 连续 2 个年度 | 高——年度数据已消化季节性波动，连续异常是强信号 |
| 季度报表 | 连续 2 个季度 | 中——需排除季节性因素后再判断 |
| 月度数据 | 连续 2 个月 | 低——月度波动大，至少 3 个月才是信号 |

**使用规则**：

1. analytical_procedures 工具输出的"异常"标记 → 按此规则判断是否升级
2. 单期异常不单独下结论，必须结合历史趋势
3. 风险升级后，需在底稿/报告中说明"该异常已持续 X 期"作为判断依据
4. 不同指标的升级规则互相独立——A 指标持续异常不影响 B 指标的判定

⚠️ 来源依据：CSA 1315 要求评估错报时考虑"性质"维度，包括"是否系统性出现"；CSA 1520 要求分析性程序偏差评估时考虑"趋势方向与持续性"。持续性升级是这两条准则要求的操作落地。

---

## 工作流执行原则

### 执行前

1. **先看数据再动手**：每个工作流第一步都应该用 data_file_overview 看数据结构，避免列名错误
2. **保留原始文件**：所有工具输出都用新文件，不覆盖原始数据
3. **统一命名规范**：`{业务}_{工序}_{日期}.xlsx`，如 `应收账款_账龄分析_20260521.xlsx`

### 执行中

1. **每一步报告进度**：完成 Step N，告诉用户当前结果，再问要不要继续
2. **遇到错误立即停止**：不强行继续，让用户决定是修数据还是换路径
3. **关键判断需要确认**：抽样比例、容差阈值、筛选关键词等参数，确认一次再执行

### 执行后

1. **汇总输出**：列出所有生成的文件路径
2. **结果解读**：不只是给文件，要给一段"业务结论"（比如"长账龄占比 30%，需重点关注"）
3. **下一步建议**：基于结果给出后续动作（如"建议对前 5 大客户实地访谈"）

---

## 自动选择工作流

当用户说"帮我做XX审计/月结/分析"时，按以下规则自动判断走哪个工作流：

| 用户关键词 | 触发工作流 | 文件 |
|-----------|-----------|------|
| 应收账款、客户、欠款、账龄 | W1 | `audit/ar_audit.md` |
| 银行、对账、调节表、未达账项 | W2 | `audit/bank_audit.md` |
| 固定资产、折旧、累计折旧 | W3 | `audit/fa_audit.md` |
| 扫描凭证、PDF 凭证、纸质凭证 | W4 | `audit/voucher_digitize.md` |
| 序时账、总账、异常分录、舞弊检测 | W5 | `audit/gl_analysis.md` |
| 月结、关账、月度报表 | W6 | `finance/month_end.md` |
| 股票、上市公司、财报分析 | W7 | `investment/listed_analysis.md` |
| 函证、询证函 | W8 | `audit/confirmation_flow.md` |
| 三表勾稽、报表校验 | W9 | `audit/statement_crosscheck.md` |
| IPO、上市尽调、财务尽调 | W10 | `investment/ipo_dd.md` |
| 底稿、调整分录、未审/审定、三栏 TB、试算平衡表 | W11 | `audit/adjustment_tb.md` |
| 截止测试、跨期、提前确认、延后确认 | W12 | `audit/cutoff_test.md` |
| 全套底稿、底稿框架、新项目底稿、从计划到报告 | W13 | `audit/full_workpaper.md` |
| 财务比率、ROE/ROA/流动比率/资产周转、比率分析、财务指标、五类比率 | W14 | `bp/ratio_analysis.md` |
| 现金流量表、间接法、直接法、现金流编制、序时账归类 | W15 | `finance/cashflow.md` |
| 纳税调整、企业所得税、税会差异、A105000、汇算清缴底稿、调增调减 | W16 | `tax/tax_adjustment.md` |
| 排雷、排雷XX、有没有雷、会不会暴雷、这股靠不靠谱、XX财报有没有问题 | W17 | `investment/stock_screening.md` |

如果用户的需求不属于任何已定义工作流，但跨越多个工具，AI 应主动设计一个临时工作流，向用户确认后执行。

---

> 末次更新：2026-06-10 [新增工作流] W17 个股排雷（investment/stock_screening.md）——一句话端到端排雷，串 market_quote + stock_financial + financial_fraud Red Flags，配套新增 market_quote 多市场行情工具
> 末次更新：2026-06-09 [三层重构] 由 workflows.md 拆分为 16 个独立工作流文件 + 本索引
> 原始内容来源：workflows.md 末次更新 2026-06-03（新增 W14/W15/W16；W6 接入 cashflow_test；W7 接入 financial_ratios + non_recurring_items）
