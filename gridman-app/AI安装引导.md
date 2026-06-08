# 古立特 Gridman MCP Server — AI 自动安装引导

> 这份文档是给 **AI Agent**（Kiro / Cursor / Claude Code / Cline / Windsurf 等）读的。
> 用户只需把本文件连同 `gridman_mcp-1.9.0-py3-none-any.whl` 一起交给你，并说一句
> “帮我安装古立特”，你就照下面的步骤自动完成安装。安装过程中需要用户操作时再提示用户。

---

## 你要做的事（总览）

把古立特工具层（35 个财税审计 MCP 工具）安装到当前 AI Agent 中。整个过程分 4 步：

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

用户应该把 `gridman_mcp-1.9.0-py3-none-any.whl` 和本文件放在一起。

1. 在当前目录或用户指定目录找到这个 `.whl` 文件。
2. 记下它的**绝对路径**，例如：
   - Windows：`D:\gridman\gridman_mcp-1.9.0-py3-none-any.whl`
   - macOS/Linux：`/Users/xxx/gridman/gridman_mcp-1.9.0-py3-none-any.whl`
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
      "args": ["--from", "D:\\gridman\\gridman_mcp-1.9.0-py3-none-any.whl", "gridman-mcp"]
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

**合并规则（重要）：**
- 如果配置文件已存在且里面已有 `mcpServers`，**只新增 `gridman` 这一项**，不要覆盖用户已有的其他 server。
- 如果文件不存在，创建它，写入完整结构。
- 写之前先读一遍现有内容，保证是合法 JSON 再写回。

---

## 第 4 步：重启与验证

1. 提示用户**重启 Agent**，或在 Agent 的 MCP 面板点 **Retry / Reconnect**。
2. 首次连接时 uvx 会自动下载依赖（约 10–60 秒，取决于网速），属正常现象。
3. 连接成功的标志：MCP 面板显示 **gridman** 已连接、约 **35 个工具**。
4. 可让用户测试一句：“用古立特做一张重要性水平计算” 或调用 `materiality_calculator`。

---

## 可选功能

### A. 市场数据工具（A股行情/K线/财务）

这 4 个工具依赖 `akshare`，默认不装。需要时把 args 改成：

```json
"args": ["--from", "<WHL绝对路径>[market]", "gridman-mcp"]
```

注意：`[market]` 紧跟在 whl 路径后面，不要加空格。其余 31 个工具不需要它。

### B. OCR 文档识别（document_ocr）

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

Token 获取：https://mineru.net → 登录 → 顶部 API → 左侧“智能解析 → API 管理” → 创建 Token。
不配 Token 不影响其他 33 个工具。

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
| 报 akshare 未安装 | 用了市场数据工具但没装扩展 | 按「可选功能 A」改成 `[market]` |
| 报 MINERU_API_TOKEN 未配置 | 用了 OCR 但没配 Token | 按「可选功能 B」配，或不用 OCR |
| 连上但工具数不对 | 可能装了旧版本缓存 | 运行 `uvx --refresh --from "<whl>" gridman-mcp` 强制刷新 |

---

## 其他安装来源（同一套步骤，只换“包地址”）

古立特的 MCP 配置只有“包从哪来”这一处会变，其余完全一致：

- **本地 whl 文件**（当前方式）：
  `"args": ["--from", "<WHL绝对路径>", "gridman-mcp"]`
- **GitHub 仓库**（待发布）：
  `"args": ["--from", "git+https://github.com/ZXCharlotte486/Gridman.git", "gridman-mcp"]`

---

古立特 Gridman v1.9.0 · 35 个 MCP 工具 · 作者：真寻Charlotte
