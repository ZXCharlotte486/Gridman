# 古立特 Gridman MCP Server — AI 自动安装引导

> 这份文档是给 **AI Agent**（Kiro / Cursor / Claude Code / Cline / Windsurf 等）读的。
> 用户只需把本文件连同 `gridman_mcp-2.0.0-py3-none-any.whl` 一起交给你，并说一句
> “帮我安装古立特”，你就照下面的步骤自动完成安装。安装过程中需要用户操作时再提示用户。

---

## 你要做的事（总览）

把古立特工具层（45 个财税审计 MCP 工具）安装到当前 AI Agent 中。整个过程分 4 步：

1. 确认 `uv` 是否已安装，没有就装
2. 确定 `.whl` 包文件的位置
3. 把 MCP 配置写进当前 Agent 的配置文件
4. 让用户重启 Agent 并验证

**重要原则：**
- 全程不要让用户手动建 Python 虚拟环境（venv），不要手动 `pip install`。uvx 会自动处理。
- 不要让用户手填路径。你来探测路径并写进配置。
- 每一步执行前用一句话告诉用户你在做什么。涉及联网下载/写系统配置时，先说明再执行。

---

## 第 1 步：确认并安装 uv

`uv` 是 Astral 出品的 Python 环境管理工具，uvx 是它的运行器。古立特用它一键启动。

**先检测是否已安装**（按当前操作系统选一条执行）：

```bash
# 通用
uv --version
```

- 如果输出了版本号 → 已安装，跳到第 2 步。
- 如果报“命令找不到” → 按下面安装。

**安装 uv：**

Windows（PowerShell）：
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS / Linux：
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

安装后 `uv` 可能还不在当前终端的 PATH 里。处理方式：
- 提示用户**重启终端**（或重启 Agent）后再验证 `uv --version`；
- 或在本次会话里用其默认安装路径直接调用：
  - Windows：`%USERPROFILE%\.local\bin\uv.exe`（旧版本可能在 `%USERPROFILE%\.cargo\bin\uv.exe`）
  - macOS/Linux：`~/.local/bin/uv`

---

## 第 2 步：确定 .whl 包的位置

用户应该把 `gridman_mcp-2.0.0-py3-none-any.whl` 和本文件放在一起。

1. 在当前目录或用户指定目录找到这个 `.whl` 文件。
2. 记下它的**绝对路径**，例如：
   - Windows：`D:\gridman\gridman_mcp-2.0.0-py3-none-any.whl`
   - macOS/Linux：`/Users/xxx/gridman/gridman_mcp-2.0.0-py3-none-any.whl`
3. 如果找不到，提示用户告诉你这个文件放在哪。

> 提示：如果将来古立特推到了 GitHub，这一步的“包地址”会变（见文末「其他安装来源」），其余步骤不变。

---

## 第 3 步：写入 MCP 配置

根据**当前正在运行的 AI Agent**，找到对应配置文件并合并写入下面的配置。

### 配置内容（把 `<WHL绝对路径>` 换成第 2 步的真实路径）

Windows 路径里的反斜杠在 JSON 中要写成双反斜杠 `\\`。

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

### 各 Agent 的配置文件位置

| Agent | 配置文件 |
|-------|---------|
| **Kiro** | 工作区 `.kiro/settings/mcp.json`，或用户级 `~/.kiro/settings/mcp.json` |
| **Cursor** | `~/.cursor/mcp.json`，或项目内 `.cursor/mcp.json` |
| **Claude Code** | 运行 `claude mcp add gridman -- uvx --from "<WHL绝对路径>" gridman-mcp`，或编辑 `~/.claude.json` |
| **Cline** | VS Code 里 Cline 的 MCP Servers 设置（`cline_mcp_settings.json`） |
| **Windsurf** | Cascade 的 MCP 配置文件 |
| **WorkBuddy** | 用户级 `~/.workbuddy/mcp.json`，**通过 GUI 编辑**（见下方专属步骤） |

> **WorkBuddy 专属步骤（图形界面操作）**：WorkBuddy 的 MCP 配置通过 GUI 管理，你（AI）通常无法直接写该文件，需引导用户手动操作：
>
> 1. 主界面底部点「连接器 ▾」→ 选「管理连接器」
> 2. 进入「专家 / 连接器」页，点右上角「＋ 自定义连接器」
> 3. 弹出「MCP 服务管理」窗口 → 点「配置」（或右上「配置 MCP」）
> 4. 编辑打开的 `mcp.json`（路径形如 `C:\Users\<用户名>\.workbuddy\mcp.json`），在 `"mcpServers": {}` 的花括号内粘入上面的 gridman 配置
> 5. 点「保存」→ 返回 MCP 列表
> 6. **首次需信任**：关闭「MCP 服务管理」窗口再重新打开，gridman 会显示"首次连接此 MCP 服务需要您的信任确认"，点右侧「信任」
> 7. **再启用**：信任后仍显示"0 启用"——再次关闭窗口重新打开，把 gridman 右侧的开关拨到「开」，状态变为已启用才可用

**合并规则（重要）：**
- 如果配置文件已存在且里面已有 `mcpServers`，**只新增 `gridman` 这一项**，不要覆盖用户已有的其他 server。
- 如果文件不存在，创建它，写入完整结构。
- 写之前先读一遍现有内容，保证是合法 JSON 再写回。

---

## 第 4 步：重启与验证

1. 提示用户**重启 Agent**，或在 Agent 的 MCP 面板点 **Retry / Reconnect**。
2. 首次连接时 uvx 会自动下载依赖（约 10–60 秒，取决于网速），属正常现象。
3. 连接成功的标志：MCP 面板显示 **gridman** 已连接、约 **45 个工具**（默认全开；可用 GRIDMAN_TOOLS 精简，见「按需安装」）。
4. 可让用户测试一句：“用古立特做一张重要性水平计算” 或调用 `materiality_calculator`。

---

## 按需安装（两个独立开关）

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

---

## 可选：OCR 文档识别（document_ocr）

`document_ocr` / `document_ocr_batch` 调用 MinerU 云端 API，需要 Token。在配置里加 `env`：

```json
{
  "mcpServers": {
    "gridman": {
      "command": "uvx",
      "args": ["--from", "<WHL绝对路径>", "gridman-mcp"],
      "env": { "MINERU_API_TOKEN": "用户的Token" }
    }
  }
}
```

Token 获取：https://mineru.net → 登录 → 顶部 API → 左侧"智能解析 → API 管理" → 创建 Token。
不配 Token 只影响这 2 个 OCR 工具，其余工具照常用。

---

## 可选：修改 uv 缓存位置

uvx 运行时会在 C 盘默认路径缓存依赖包，长期使用后会积累几 GB。如果 C 盘空间紧张，可以在安装前设置以下环境变量，把缓存和工具目录迁到其他位置。

**Windows（PowerShell，永久生效）：**

```powershell
# 缓存目录（下载的包）
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\APP\uv\cache", "User")
# 工具环境目录
[Environment]::SetEnvironmentVariable("UV_TOOL_DIR", "D:\APP\uv\tools", "User")
# 可执行文件目录（gridman-mcp.exe 等）
[Environment]::SetEnvironmentVariable("UV_TOOL_BIN_DIR", "D:\APP\uv\bin", "User")
# 把可执行文件目录加入 PATH
$p = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("Path", "$p;D:\APP\uv\bin", "User")
```

把 `D:\APP\uv\` 换成你想要的任意路径。设完后**重启终端**再继续安装。

**macOS / Linux（写入 shell 配置文件如 `~/.zshrc`）：**

```bash
export UV_CACHE_DIR="$HOME/uv-cache"
export UV_TOOL_DIR="$HOME/uv-tools"
export UV_TOOL_BIN_DIR="$HOME/uv-tools/bin"
export PATH="$HOME/uv-tools/bin:$PATH"
```

> 不设置也能正常用，只是缓存在默认位置（Windows：`C:\Users\{用户名}\AppData\Local\uv\`）。

---

## 故障排查

| 现象 | 原因 | 处理 |
|------|------|------|
| Connection Failed / closed | uv 没装好，或不在 PATH | `uv --version` 验证；没装就装；装了就重启终端/Agent |
| 第一次连很久才成功或超时 | 首次下载依赖 | 等 10–60 秒；网络差可重试 Retry |
| 找不到 whl / No such file | 路径写错 | 用绝对路径；Windows 用 `\\` |
| 报 akshare 未安装 | 用了市场工具但没装扩展 | 按「按需安装」给 whl 加 `[market]` |
| 报缺 matplotlib / pymupdf / python-docx | 用了对应类别工具但没装该扩展 | 按「按需安装」加 `[data]` / `[document]` / `[audit]` |
| 报 MINERU_API_TOKEN 未配置 | 用了 OCR 但没配 Token | 按「可选：OCR」配，或不用 OCR |
| 工具数比预期少 | GRIDMAN_TOOLS 限定了类别（正常现象） | 想全开就删掉该环境变量或设为 `all` |
| 连上但工具数不对 | 可能装了旧版本缓存 | 运行 `uvx --refresh --from "<whl>" gridman-mcp` 强制刷新 |

---

## 其他安装来源（同一套步骤，只换“包地址”）

古立特的 MCP 配置只有“包从哪来”这一处会变，其余完全一致：

- **本地 whl 文件**（当前方式）：
  `"args": ["--from", "<WHL绝对路径>", "gridman-mcp"]`
- **GitHub 仓库**（待发布）：
  `"args": ["--from", "git+https://github.com/ZXCharlotte486/Gridman.git", "gridman-mcp"]`

---

古立特 Gridman v2.0.0 · 45 个 MCP 工具 · 作者：真寻Charlotte
