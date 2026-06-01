# 古立特 Skill（知识层）

财税超级特工古立特的知识指引层。34 个专业模块，覆盖会计准则、税法、审计、内控、内审、投行、ESG、政府会计、财务造假识别、经济法等全领域。

配合 [gridman-app（MCP 工具层）](../gridman-app/) 使用可获得完整的"判断 + 计算"能力；单独使用时作为财税知识顾问。

## 跨平台安装

本技能遵循 AgentSkills 标准（`SKILL.md` + `references/`），可用于 OpenClaw、Claude / Claude Code、Cursor、Cherry Studio 等支持 Agent Skill 的平台，不限于 Kiro。

安装时把目标平台的 AI 指向同目录下的 **`AI适配引导.md`**——它会引导那个平台的 AI 自己完成接入（触发机制、文件读取、工具层接入），你不需要为每个平台手写适配版。核心要求只有一条：**保持 `SKILL.md` 与 `references/` 同级**。

---

## 知识来源与致谢

本知识库为基于公开准则、法规、教材及开源资源的**学习性提炼与重写**，非原文复制。各模块来源如下：

### 教材蒸馏（已重写为决策规则，非照搬原文）

| 来源 | 对应模块 |
|------|---------|
| 2026年CPA《会计》教材（中国注册会计师协会） | accounting_core.md、accounting_advanced.md |
| 2026年CPA《税法》教材 | tax_core.md、tax_advanced.md |
| 2026年CPA《审计》教材 | audit.md |
| 2026年CPA《财务成本管理》教材 | management_accounting.md、investment.md（部分） |
| 2026年CPA《经济法》教材 | economic_law.md |
| 2026年CPA《公司战略与风险管理》教材 | internal_control.md（战略部分） |
| 《政府与非营利组织会计》（陈平主编，广东高等教育出版社，2024） | government_npo_accounting.md |

### 准则、法规与官方文件（不受著作权保护）

| 来源 | 对应模块 |
|------|---------|
| 企业会计准则（CAS）及应用指南 | accounting_core/advanced、各模块准则引用 |
| 中国注册会计师审计准则（CSA） | audit.md、audit_procedures.md |
| 税收法律法规及国家税务总局公告 | tax_core.md、tax_advanced.md、tax_risk_indicators.md |
| 证监会行政处罚决定、会计监管风险提示 | financial_fraud.md、regulatory_risk_alerts.md、penalty_cases.md |
| 企业内部控制基本规范（财会〔2008〕7号） | internal_control.md |
| IIA 国际内部审计准则 | internal_audit.md |
| 中国内部审计协会《内部审计数智化转型指引（2025版）》 | internal_audit.md（第七章） |
| 资产评估法及中评协准则 | investment.md（第九章） |
| ISSB/GRI/TCFD 框架 | esg.md |

### 开源项目参考（MIT 许可证，已消化重写，非直接复制）

| 项目 | 作者 | 参考内容 |
|------|------|---------|
| [nigo-skills](https://github.com/nigo81/nigo-skills) | nigo81 | 陈奕蔚准则判断框架、田川审计方法论 → 融入 accounting_core.md、audit.md |
| [tools-for-auditor](https://github.com/nigo81/tools-for-auditor) | nigo81 | 审计工具核心算法逻辑 → 融入 audit.md |
| [anthropics/financial-services](https://github.com/anthropics/anthropic-cookbook) | Anthropic | 投行尽调/估值框架（Apache 2.0）→ 融入 investment.md |

### 其他来源

| 来源 | 对应模块 |
|------|---------|
| 来也科技 ADP 公开 Skill 字段规范 | invoice_templates.md |
| 聂辉华《基层中国的运行逻辑》 | governance_logic.md |
| 真实企业账务数据提炼（已脱敏） | business_patterns.md |
| 证监会处罚决定 + 公开报道 | financial_fraud.md（案例库） |
| 审计文库 MaoDocs（docs.maoyanqing.com） | 准则原文核实来源 |
| 国家税务总局法规库（fgk.chinatax.gov.cn） | 税法时效性核实来源 |

---

## 免责声明

本知识库提供专业知识指引和学习参考，**不构成正式的审计意见、税务建议或法律意见**。所有判断结论需使用者以专业胜任能力复核确认。相关准则、法规、教材的版权归原制定/出版机构所有。如认为某处内容涉及您的权益，请联系作者处理。

---

## 关于"古立特 / Gridman"角色（重要声明）

本项目以"古立特 / Gridman"作为 AI 助手的人格形象，是出于个人对圆谷制作（Tsuburaya Productions）《电光超人 Gridman》《SSSS.GRIDMAN》《SSSS.DYNAZENON》《GRIDMAN UNIVERSE》等作品的**喜爱与致敬**。

- **角色 IP 归属**："古立特 / Gridman / グリッドマン / 电光超人 / SSSS / Dynazenon / Access Flash" 等名称、形象、设定、台词的著作权与商标权，**全部归圆谷制作（Tsuburaya Productions）所有**。本项目与圆谷制作没有任何关联、合作或授权关系。
- **非商业、粉丝向**：本项目是个人非营利的学习与实践项目，不收费、不用于任何商业目的，借用该角色仅为赋予工具一个有温度的人格外观，无意冒犯或侵害原作权益。
- **核心价值在财税能力**：本项目的实质内容是财税知识库与工具，角色形象是外壳。使用者获得的价值来自财税专业能力，而非角色本身。
- **侵权即删**：若圆谷制作或相关权利方认为本项目对角色的使用不当，请联系作者，将**立即移除全部相关角色元素或下架本项目**。

> 一句话：财税能力是我自己的，"古立特"这个名字和灵魂是借圆谷的——心怀感激，绝不冒犯，权利方有异议随时撤。

---

## 目录结构

```
gridman-skill/
├── SKILL.md                    ← 主入口（人格、路由、工作协议）
├── README.md                   ← 本文件
├── AI适配引导.md                ← 跨平台安装：引导目标平台 AI 自行接入
└── references/                 ← 34 个知识模块
    ├── accounting_core.md          会计准则（第1-17章）
    ├── accounting_advanced.md      会计准则（第18-29章）
    ├── audit.md                    审计准则与程序
    ├── audit_procedures.md         审计程序详细操作
    ├── tax_core.md                 增值税/企业所得税/个税
    ├── tax_advanced.md             小税种/国际税收/征管
    ├── tax_risk_indicators.md      金税四期/税务风险
    ├── investment.md               投行/估值/资产评估
    ├── financial_fraud.md          财务造假识别（16案例）
    ├── financial_bp.md             财务BP/经营分析
    ├── management_accounting.md    管理会计
    ├── internal_control.md         内控/战略
    ├── internal_audit.md           内部审计/数智化转型
    ├── economic_law.md             经济法
    ├── government_npo_accounting.md 政府/非营利组织会计
    ├── esg.md                      ESG
    ├── consulting.md               结构化思维
    ├── statement.md                报表勾稽/异常识别
    ├── finance.md                  财务数字化/凭证
    ├── business_patterns.md        多步业务模式识别
    ├── forensic_accounting.md      司法会计/验资
    ├── shared_services_rpa.md      财务共享/RPA
    ├── equity_research.md          上市公司财报研究
    ├── regulatory_risk_alerts.md   监管风险提示
    ├── penalty_cases.md            处罚案例
    ├── cas_application_cases.md    准则应用案例
    ├── cas_practical_judgments.md   准则实务判断
    ├── invoice_templates.md        发票字段模板
    ├── workflows.md                端到端工作流
    ├── mpacc_case_template.md      MPAcc案例模板
    ├── empirical_research.md       实证研究方法
    ├── political_economy.md        政治经济学
    ├── governance_logic.md         基层治理逻辑
    └── songs.md                    古立特主题曲
```
