# 古立特 Gridman — Hyper Agent for Chinese Finance & Tax

财税超级特工古立特。一个入口覆盖中国会计准则（CAS）、税法、审计、投行估值、内控、内审、ESG、政府会计、财务造假识别、经济法、财务BP等全领域，34个专业知识模块。

从底稿编制、分录判断、准则应用，到税务筹划、报表勾稽、财报研究、IPO尽调——处理中国财税场景时的并肩伙伴。

## 项目结构

```
Gridman/
├── gridman-skill/       ← 知识层（34模块 + BIOS安装 + 使用说明）
│   ├── SKILL.md         ← 主文件
│   ├── INSTALL.md       ← 工具层自动安装固件
│   ├── references/      ← 34个知识模块
│   └── payload/         ← 工具层安装包（whl）
└── gridman-app/         ← 工具层（35个MCP计算工具）
    ├── dist/            ← whl安装包
    └── gridman_mcp/     ← 源码
```

## 快速开始

1. 把 `gridman-skill/` 文件夹放到你的 AI Agent 能读到的位置（Kiro 放 `.kiro/skills/gridman/`，Cursor/Claude Code 放项目根目录）
2. 对 AI 说"装古立特"——AI 自动完成工具层安装
3. 开始用

详细说明见 [`gridman-skill/README.md`](gridman-skill/README.md) 和 [`gridman-skill/使用说明.txt`](gridman-skill/使用说明.txt)

## 适配环境

| 环境 | 适配程度 |
|------|---------|
| Kiro / Cursor / Claude Code | ⭐⭐⭐ 最佳 |
| Codex / Windsurf / Cline | ⭐⭐ 可用 |
| OpenClaw / LobeChat / Cherry Studio | ⭐ 基本可用 |

## 许可证

- **知识层**（gridman-skill/）：[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/deed.zh-hans)
- **工具层**（gridman-app/）：MIT

## 角色声明

"古立特 / Gridman / グリッドマン"等角色 IP 的著作权与商标权归**圆谷制作株式会社**（Tsuburaya Productions Co., Ltd.）所有。动画作品制作权归**株式会社 TRIGGER**（Studio TRIGGER Inc.）。本项目为个人非商业粉丝向学习项目，与上述公司无任何关联。权利方有异议请联系作者，将立即移除。

---

*v1.9.0 · 作者：真寻Charlotte*
