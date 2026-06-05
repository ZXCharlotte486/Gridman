"""
共享路径工具 — 获取 gridman-mind 目录。

gridman-mind 与 gridman-app 同级（即 CWD 的父目录下）。
如果不存在，自动创建空目录结构（projects/ + entities/ + README.md）。
"""
from pathlib import Path


def get_mind_dir() -> Path:
    """
    获取 gridman-mind 根目录。

    逻辑：CWD（MCP server 启动目录，即 gridman-app/）的父目录下找 gridman-mind/。
    不存在时自动重建空结构。
    """
    app_dir = Path.cwd()
    mind_dir = app_dir.parent / "gridman-mind"

    if not mind_dir.exists():
        # 自动重建空目录结构
        (mind_dir / "projects").mkdir(parents=True, exist_ok=True)
        (mind_dir / "entities").mkdir(parents=True, exist_ok=True)
        readme = mind_dir / "README.md"
        content = (
            "# gridman-mind\n\n"
            "古立特的记忆空间。项目档案和企业上下文存放于此。\n\n"
            "- `projects/` — 项目记忆\n"
            "- `entities/` — 企业上下文\n"
            "- `reports/`  — 下载的公告/年报\n\n"
            "删除此目录不会影响古立特的知识和工具，只是\"失忆\"。\n"
            "下次使用时会自动重建。\n"
        )
        readme.write_text(content, encoding="utf-8")

    return mind_dir
