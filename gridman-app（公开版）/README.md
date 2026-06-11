# 古立特 MCP Server（App 形态）

财税超级特工古立特的计算层。当前版本 **v2.0.0**，提供 **45 个 MCP 工具**，按 6 大功能类别（数据 / 文档 / 审计 / 财务 / 市场 / 办公）组织，覆盖底稿全流程（计划→风险→实质性程序→完成→报告）+ 文档识别 + PDF 工具 + 数据分析 + 市场数据 + 报表分析 + Office 实时协同。支持按职业**按需安装**（见下）。

基于标准 **MCP 协议**，可在任意支持 MCP 的 AI Agent 中使用：Kiro、Cursor、Claude Code、Cline、Windsurf 等。

---

## 一键安装（推荐，跨所有 Agent 通用）

### 前置：装一次 uv（每台电脑只需一次）

`uv` 是一个独立小工具，负责自动管理 Python 环境。装上它之后，古立特无需手动建虚拟环境、无需手动 pip install。

**Windows（PowerShell）：**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux：**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

装完重启终端，`uv --version` 能输出版本号即成功。

### 配置 Agent

在你的 Agent 的 MCP 配置文件里加入下面这段。把 `<WHL绝对路径>` 换成你拿到的 `gridman_mcp-2.0.0-py3-none-any.whl` 的真实路径（Windows 路径里的反斜杠在 JSON 中写成 `\\`）：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "<WHL绝对路径>", "gridman-mcp"]
    }
  }
}
```

示例（Windows）：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "D:\\gridman\\gridman_mcp-2.0.0-py3-none-any.whl", "gridman-mcp"]
    }
  }
}
```

> 当前通过**本地 whl 文件**分发（一个文件，不含 venv，跨电脑可用）。GitHub 仓库暂未公开，
> 待发布后将提供 `git+https://` 安装方式，届时只需替换 `--from` 后的地址，其余不变。

各 Agent 的配置文件位置：

| Agent | 配置文件位置 |
|-------|-------------|
| **Kiro** | `.kiro/settings/mcp.json`（工作区级）或 `~/.kiro/settings/mcp.json`（用户级） |
| **Cursor** | `~/.cursor/mcp.json` 或项目内 `.cursor/mcp.json` |
| **Claude Code** | `claude mcp add gridman -- uvx --from "<WHL绝对路径>" gridman-mcp`，或编辑 `~/.claude.json` |
| **Cline / Windsurf** | 各自的 MCP 设置面板 |

保存后重启 Agent（或在 MCP 面板点 Retry）。首次启动 uvx 会自动下载依赖（约 10–60 秒），看到 `gridman Connected (45 tools)` 即成功（默认全开 45 个；若设了 `GRIDMAN_TOOLS` 精简则为对应数量）。

### 按需安装（可选，两个独立开关）

古立特工具层可按职业/喜好精简，两个开关**互相独立**：

**开关一 · 装哪些依赖（pip extras）**——控制安装体积。按 6 大功能类别拆分：

| extra | 覆盖工具 | 额外依赖 |
|-------|---------|---------|
| 核心（默认，不带 extra） | 数据/审计/财务大部分工具 | pandas/openpyxl/mcp/requests |
| `[data]` | 图表生成 | matplotlib |
| `[document]` | PDF 合并/拆分/提取/凭证拆分 | pymupdf |
| `[audit]` | 函证/底稿 Word 生成 | python-docx |
| `[finance]` | （无额外依赖） | — |
| `[market]` | A股行情/K线/财务 | akshare |
| `[office]` | Excel/Word/PPT 实时操控（仅 Windows） | pywin32 |
| `[all]` | 全部 | 以上全部 |

多个 extra 用逗号，紧跟 whl 路径不加空格：`"<WHL绝对路径>[audit,document,market]"`。缺依赖时对应工具返回友好提示，不崩 server。

**开关二 · 开哪些工具（GRIDMAN_TOOLS 环境变量）**——控制 Agent 看到的工具清单。6 大类别：`数据 / 文档 / 审计 / 财务 / 市场 / 办公`（中英文均可：data/document/audit/finance/market/office）。写进 `env`：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "<WHL绝对路径>[audit,document]", "gridman-mcp"],
      "env": { "GRIDMAN_TOOLS": "审计,文档,数据" }
    }
  }
}
```

- 不设 / `all` / `全部` / `*` → 全部 45 个工具（向后兼容）
- 逗号分隔指定 → 只挂这些类别（无效名忽略并告警；全无效则兜底全开）

**配合使用**：装的依赖和开的工具用**同一套类别名**——做审计就 `[audit,document]` + `GRIDMAN_TOOLS=审计,文档,数据`。

### 配置 MinerU OCR（可选）

`document_ocr` / `document_ocr_batch` 调用 MinerU 云端 API，需要 Token。在配置里加 `env`：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "<WHL绝对路径>", "gridman-mcp"],
      "env": { "MINERU_API_TOKEN": "你的Token" }
    }
  }
}
```

获取 Token：见文末「MinerU Token」一节。不配只影响这 2 个 OCR 工具，其余工具照常用。

---

## 开发者本地安装（改代码用）

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. 安装（可编辑模式，国内用户加清华镜像）
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
# 需要某类别的额外依赖时按需加 extra（多个用逗号）：
pip install -e ".[audit,document,market]" -i https://pypi.tuna.tsinghua.edu.cn/simple
# 或全功能：
pip install -e ".[all]" -i https://pypi.tuna.tsinghua.edu.cn/simple
```

本地开发时的 MCP 配置（指向 venv 里的 python）：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "你的路径/.venv/Scripts/python.exe",
      "args": ["-m", "gridman_mcp.server"],
      "cwd": "你的路径/gridman-app"
    }
  }
}
```

---

## 构建与分发（维护者）

```bash
# 构建（产物在 dist/，含 .whl 和 .tar.gz）
uv build
```

构建出的 `dist/gridman_mcp-<版本>-py3-none-any.whl` 就是完整的工具层，可直接分发：

- **发 whl 文件**（当前方式）：把这个 `.whl` 连同 `AI安装引导.md` 发给用户，
  用户配置用 `--from "<WHL绝对路径>" gridman-mcp`。
- **推到 GitHub**（待发布）：仓库公开后，用户配置改成
  `--from "git+https://github.com/ZXCharlotte486/Gridman.git" gridman-mcp`，更新自动生效，无需重发文件。

每次改完代码，记得同步更新 `pyproject.toml` 和 `gridman_mcp/__init__.py` 里的版本号。

---

## 工具列表（45 个）

> 按 6 大功能类别组织，与 `GRIDMAN_TOOLS` 门控类别一致。标注的 pip extra 为该类别部分工具所需。

### 数据（8 个）

| 工具 | 功能 |
|------|------|
| `balance_sheet_process` | 科目余额表处理（删非末级、拆层级） |
| `address_split` | 地址拆分省市区（函证用） |
| `data_file_overview` | 数据概览（行列/类型/缺失/统计） |
| `data_group_summary` | 分组汇总（sum/mean/count/max/min/std/median） |
| `data_filter` | 数据筛选（>/</>=/<=/==/!=/contains/startswith） |
| `data_pivot` | 透视表生成 |
| `fuzzy_match` | 名称模糊匹配（应收应付对账、关联方识别） |
| `chart_generate` | 统计图表生成（折线/柱状/饼/散点/热力/堆积/瀑布，PNG/Excel；需 `[data]`） |

### 文档（6 个，PDF 工具需 `[document]`）

| 工具 | 功能 |
|------|------|
| `document_ocr` | 文档识别（PDF/图片/Office → Markdown，MinerU 云端） |
| `document_ocr_batch` | 批量文档识别（≤ 200 文件，自动分批并行） |
| `pdf_merge` | PDF 合并 |
| `pdf_split` | PDF 按页码范围拆分 |
| `pdf_extract` | PDF 提取指定页面 |
| `voucher_pdf_split` | 记账凭证 PDF 按凭证号自动拆分 |

### 审计（13 个，函证/底稿需 `[audit]`）

| 工具 | 功能 |
|------|------|
| `workpaper_init` | 底稿框架初始化（自动建文件夹 + 模板） |
| `materiality_calculator` | 重要性计算（CSA 1320，自动选基准 + 三档计算） |
| `analytical_procedures` | 分析性程序（本期 vs 上期波动 + 异常标记） |
| `bank_reconciliation` | 银行余额调节表（置信度分层匹配 + 重复流水检测 + 未匹配项性质判断） |
| `aging_analysis` | 往来账龄分析（先进先出法） |
| `benford_law_check` | 本福特定律检验 |
| `depreciation_check` | 固定资产折旧重算（直线/双倍余额递减/年数总和） |
| `audit_sampling` | 审计抽样（随机/系统/MUS 货币单位抽样） |
| `audit_adjustment` | 审计调整三栏 TB（未审 + 调整 = 审定，借贷平衡校验） |
| `cutoff_test` | 截止测试（前后窗口筛选 + 自动标记可疑项） |
| `confirmation_letter` | 函证生成（银行/应收/应付/律师 → Word + Excel 清单） |
| `reclassification` | 往来款重分类（CAS 30，按余额方向列报） |
| `voucher_scan` | 凭证巡检（七大类高风险业务模式，自动标记可疑项） |

### 财务（5 个）

| 工具 | 功能 |
|------|------|
| `cashflow_test` | 现金流量表测算（间接法倒推 + 与报表对比差异） |
| `cashflow_direct` | 现金流量表（直接法，穿透序时账逐笔归类） |
| `non_recurring_items` | 非经常性损益计算（证监会定义，扣非净利润） |
| `financial_ratios` | 财务比率分析（变现/周转/负债/盈利/每股） |
| `tax_adjustment` | 纳税调整明细（税会差异，对应 A105000） |

### 市场（4 个，需 `[market]` 扩展）

| 工具 | 功能 |
|------|------|
| `market_quote` | 多市场实时行情（A股/港股/美股/指数，批量 + 异动信号） |
| `stock_history` | 历史 K 线（A股/港股/美股，日/周/月，前复权/后复权） |
| `stock_financial` | A 股财务数据（利润表/资产负债表/现金流量表） |
| `report_download` | 上市公司年报/公告批量下载（巨潮资讯网，无需 API Key） |

### 办公（9 个，需 `[office]` 扩展，仅 Windows）

| 工具 | 功能 |
|------|------|
| `office_list_apps` | 检测运行中的办公应用（M365 / WPS 的 Excel/Word/PPT） |
| `office_excel_read` | 读取打开的 Excel/WPS 表格区域 |
| `office_excel_write` | 写入数据到打开的表格（实时显示） |
| `office_excel_formula` | 在打开的表格设置公式 |
| `office_word_read` | 读取打开的 Word/WPS 文字文档 |
| `office_word_append` | 在打开的文档末尾追加文本 |
| `office_save_as` | 当前文档另存为（含 WPS 私有格式转标准格式/PDF） |
| `office_ppt_info` | 获取打开的演示文稿信息（幻灯片列表） |
| `office_ppt_add_slide` | 在演示文稿末尾添加幻灯片 |

---

## MinerU Token（OCR 用）

1. 打开 <https://mineru.net>
2. 右上角**登录**（微信/GitHub/手机号，免费）
3. 点顶部导航栏 **API**
4. 左侧 **智能解析** → **API 管理**
5. **+ 创建 Token**，复制
6. 粘贴到 MCP 配置的 `env.MINERU_API_TOKEN`

注意：Token 有效期 **90 天**；每天 **1000 页**免费额度；单文件 ≤ 200MB / 600 页。

---

## 维护脚本

项目根目录（`Gridman古立特/`）下：

- `sync_skill.ps1`：把 `.kiro/skills/gridman/` 单向镜像到 `gridman-skill/`，保持两个 Skill 副本一致。每次改 Skill 后跑一次。

---

## 许可与声明

### 版权与使用

本项目（古立特 MCP 工具层）的原创代码遵循 MIT 许可证开放使用。

知识库部分（古立特 Skill）为**基于公开会计准则、税法法规、审计准则及公开教材的学习性提炼与重写**，是面向 AI 的决策规则与判断框架，**非原文复制**。相关准则、法规、教材的版权归原制定/出版机构所有。如认为某处内容涉及您的权益，请联系作者删除或修改。

### 免责声明

古立特提供专业知识指引和工作辅助，**不构成正式的审计意见、税务建议或法律意见**。所有计算结果、判断结论、生成的底稿与报告，均需使用者本人以专业胜任能力复核确认。涉及签字责任、重大判断、对外报送的事项，请以持证专业人士的最终判断为准。因使用本工具产生的任何后果，由使用者自行承担。

### 数据与隐私

- 除显式调用云端服务（如 MinerU OCR）外，工具在本地运行，数据不外传。
- `document_ocr` / `document_ocr_batch` 会将文件上传至 MinerU 云端解析，**请勿对涉密或高度敏感文件使用**，或先行脱敏。
- 使用者自带 MinerU Token 与 AI 模型 Key，本项目不收集、不存储任何凭证。

### 第三方致谢

本项目在构建过程中参考/集成了以下开源资源与公开服务，谨致谢意：

- 审计方法论与工具逻辑：参考 nigo81/nigo-skills、nigo81/tools-for-auditor（MIT 许可证），已消化重写，非直接复制。
- 法规/准则原文核实：审计文库 MaoDocs（docs.maoyanqing.com）、国家税务总局法规库、中国会计视野法规库。
- 依赖库：pandas、openpyxl、python-docx、PyMuPDF、akshare（可选）、mcp 等开源项目。
- 云端 OCR：MinerU（mineru.net）。
- 市场数据：akshare、巨潮资讯网公开接口。
