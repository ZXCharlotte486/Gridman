# 古立特 Gridman — MCP 工具层安装（BIOS 固件）

> **读者：AI Agent。** 无论你是 Kiro、Cursor、Claude Code、Codex、OpenClaw、Workbuddy 还是其他任何 AI 助手——读到这份文件，就按步骤执行安装。
>
> 用户只需说一句"装古立特"或"安装 MCP"，你就启动这个流程。

---

## POST 自检（第 1 步）

检测当前环境是否已有 `uv`：

```bash
uv --version
```

- ✅ 输出版本号 → 跳到第 2 步
- ❌ 命令不存在 → 安装 uv：

**Windows（PowerShell）：**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux：**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后若 `uv --version` 仍报错，提示用户重启终端后再继续。

---

## 找启动盘（第 2 步）

**你（AI）自己探测 whl 的绝对路径，不要让用户手填。**

whl 文件在本文件同级的 `payload/` 目录下：

```
payload/gridman_mcp-*.whl
```

你知道自己正在读的这份 INSTALL.md 所在的目录路径，往下拼 `payload/gridman_mcp-2.0.0-py3-none-any.whl` 即可。

如果找不到 payload/ 或里面没有 whl 文件，问用户："whl 安装包放在哪了？告诉我路径。"

---

## 写入引导配置（第 3 步）

根据**当前 AI Agent 平台**，把下面的配置写入对应位置。

### 配置内容

将 `<WHL路径>` 替换为第 2 步的绝对路径（Windows 路径用 `\\` 转义）：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "<WHL路径>", "gridman-mcp"]
    }
  }
}
```

### 各平台配置位置

| 平台 | 配置文件 |
|------|---------|
| **Kiro** | `.kiro/settings/mcp.json`（工作区）或 `~/.kiro/settings/mcp.json`（用户级） |
| **Cursor** | `~/.cursor/mcp.json` 或项目内 `.cursor/mcp.json` |
| **Claude Code** | 执行 `claude mcp add gridman -- uvx --from "<WHL路径>" gridman-mcp`，或编辑 `~/.claude.json` |
| **Codex** | 项目内 `.codex/mcp.json` 或平台约定的 MCP 配置入口 |
| **OpenClaw** | 平台 MCP 设置面板 |
| **WorkBuddy** | `~/.workbuddy/mcp.json`（用户级；通过 GUI 编辑，见下方「WorkBuddy 专属步骤」） |
| **Cline** | VS Code Cline 的 `cline_mcp_settings.json` |
| **Windsurf** | Cascade 的 MCP 配置文件 |

> **WorkBuddy 专属步骤（图形界面操作）**：WorkBuddy 的 MCP 配置通过 GUI 管理，AI 通常无法直接写该文件，需引导用户手动操作：
>
> 1. 主界面底部点「连接器 ▾」→ 选「管理连接器」
> 2. 进入「专家 / 连接器」页，点右上角「＋ 自定义连接器」
> 3. 弹出「MCP 服务管理」窗口 → 点「配置」（或右上「配置 MCP」）
> 4. 编辑打开的 `mcp.json`（路径形如 `C:\Users\<用户名>\.workbuddy\mcp.json`），在 `"mcpServers": {}` 的花括号内粘入上面的 gridman 配置
> 5. 点「保存」→ 返回 MCP 列表
> 6. **首次需信任**：关闭「MCP 服务管理」窗口再重新打开，gridman 会显示"首次连接此 MCP 服务需要您的信任确认"，点右侧「信任」
> 7. **再启用**：信任后仍显示"0 启用"——再次关闭窗口重新打开，把 gridman 右侧的开关拨到「开」，状态变为已启用才可用

### 合并规则

- 配置文件已存在且有 `mcpServers` → **只新增 `gridman` 这一项**，不覆盖其他 server
- 文件不存在 → 创建并写入完整结构
- 写之前先读现有内容，确保合法 JSON

---

## 启动验证（第 4 步）

1. 提示用户**重启 Agent**（或在 MCP 面板点 Reconnect）
2. 首次连接 uvx 会自动下载依赖（10–60 秒），正常现象
3. 成功标志：MCP 面板显示 **gridman** 已连接，约 **45 个工具**（默认全开；可用 GRIDMAN_TOOLS 精简，见下方"按需安装"）
4. 快速验证：调用 `materiality_calculator` 或问"帮我算重要性水平"

---

## 按需安装（两个独立开关）

古立特工具层支持按职业/喜好精简，两个开关**互相独立**：

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

多个 extra 用逗号：`"<WHL路径>[audit,document,market]"`。缺依赖时对应工具返回友好提示，不崩 server。

**开关二 · 开哪些工具（GRIDMAN_TOOLS 环境变量）**——控制 Agent 看到的工具清单。6 大类别：`数据 / 文档 / 审计 / 财务 / 市场 / 办公`（中英文均可：data/document/audit/finance/market/office）。

```json
"env": { "GRIDMAN_TOOLS": "审计,数据,文档" }
```

- 不设 / `all` / `全部` / `*` → 全部 45 个工具（向后兼容）
- 逗号分隔指定 → 只挂这些类别（无效名忽略并告警；全无效则兜底全开）

**配合使用**：装的依赖和开的工具用**同一套类别名**。做审计 → `"<WHL路径>[audit,document]"` + `GRIDMAN_TOOLS=审计,文档,数据`。

---

## 可选扩展

### A. OCR 文档识别

需要 MinerU API Token。加 env：
```json
"env": { "MINERU_API_TOKEN": "你的Token" }
```
Token 获取：https://mineru.net → 登录 → API → 智能解析 → API 管理 → 创建

### B. uv 缓存迁移（C 盘空间紧张时）

Windows PowerShell：
```powershell
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\uv\cache", "User")
[Environment]::SetEnvironmentVariable("UV_TOOL_DIR", "D:\uv\tools", "User")
```

---

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| Connection Failed / closed | uv 没装好或不在 PATH | 验证 `uv --version`；重启终端 |
| 首次连接超时 | 下载依赖中 | 等待或重试 |
| No such file | whl 路径错 | 用绝对路径；Windows 用 `\\` |
| 工具数不对 | 旧版缓存 | `uvx --refresh --from "<whl>" gridman-mcp` |
| akshare 未安装 | 没加 `[market]` | 按扩展 A 修改 |

---

## 安装来源说明

当前用本地 whl 文件安装。未来 GitHub 上线后可改为远程源，其余步骤完全不变：

```json
"args": ["--from", "git+https://github.com/ZXCharlotte486/Gridman.git", "gridman-mcp"]
```

---

*古立特 Gridman v2.0.0 · 45 个 MCP 工具 · Access Flash.*
