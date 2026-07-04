"""
共享路径工具 — 解析 gridman-mind 目录（稳定锚点优先）。

解析顺序（第一个命中即用）：
  ① 环境变量 GRIDMAN_MIND —— 显式锁定，最高优先。安装时写进 MCP 配置的 env 即可。
  ② 主目录指针 ~/.gridman/home.json 的 gridman_mind —— "扫一次、永久记得"。
  ③ 回退：CWD 父目录下的 gridman-mind —— 仅当前两者都没有时用；结果会立刻落盘成指针，
     这样即便下次 CWD 变了（uvx + whl 部署下 CWD 由宿主 Agent 决定、不可控）也保持稳定，
     不会每次启动在不同位置重建空 mind 而"失忆"。

解析到的目录若不存在会自动重建空结构（projects/ + entities/ + README.md）。
"""
import json
import os
import time
from pathlib import Path

POINTER = Path.home() / ".gridman" / "home.json"

_README = (
    "# gridman-mind\n\n"
    "古立特的记忆空间。项目档案、企业上下文、工具产出都存放于此。\n\n"
    "- `projects/` — 项目记忆\n"
    "- `entities/` — 企业上下文（每户一份 md：工商事实自动节 + 了解与判断节）\n"
    "- `outputs/`  — 工具产出（底稿/图表/报表等）\n"
    "- `reports/`  — 下载的公告/年报\n"
    "- `feedback/` — 路由失败/踩坑/报错三反馈池\n"
    "- `temp/`     — 临时中间文件\n"
    "- `_cache/`   — 工具内部取数缓存（如工商查询，可删；删后重查重花额度）\n\n"
    "（projects/entities 启动即建，其余子目录由对应工具首次用到时按需创建。）\n\n"
    "删除此目录不会影响古立特的知识和工具，只是\"失忆\"。\n"
    "下次使用时会自动重建。\n"
)


def _ensure_structure(mind_dir: Path) -> None:
    """重建 mind 的最小空结构。失败静默（不阻断主流程）。"""
    try:
        (mind_dir / "projects").mkdir(parents=True, exist_ok=True)
        (mind_dir / "entities").mkdir(parents=True, exist_ok=True)
        readme = mind_dir / "README.md"
        if not readme.exists():
            readme.write_text(_README, encoding="utf-8")
    except Exception:
        pass


def _pointer_mind() -> Path | None:
    """读 home.json 里记着的 mind 路径；存在且有效才返回，否则 None。"""
    if not POINTER.exists():
        return None
    try:
        data = json.loads(POINTER.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    val = data.get("gridman_mind") or data.get("mind")
    if not val:
        return None
    p = Path(str(val)).expanduser()
    return p if p.exists() else None


def write_pointer_mind(mind_dir: Path, source: str = "get_mind_dir (auto)") -> None:
    """把 mind 路径合并写进 home.json（保留已有键）。失败静默。"""
    try:
        POINTER.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if POINTER.exists():
            try:
                loaded = json.loads(POINTER.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data["gridman_mind"] = str(mind_dir)
        data.setdefault("source", source)
        data["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        POINTER.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def resolve_mind_dir() -> tuple[Path, bool, str]:
    """解析 mind 目录，返回 (路径, 解析前是否已存在, 来源[env/pointer/cwd])。

    会按需重建空结构；除 pointer 命中外都会把结果落盘成指针，让位置稳定下来。
    来源同时返回，便于调用方（如 gridman_locate）把"按 CWD 兜底"这种不确定情形显式暴露出来。
    """
    # ① 环境变量显式锁定
    env = os.environ.get("GRIDMAN_MIND", "").strip()
    if env:
        mind_dir = Path(env).expanduser()
        existed = mind_dir.exists()
        _ensure_structure(mind_dir)
        write_pointer_mind(mind_dir, source="env GRIDMAN_MIND")
        return mind_dir, existed, "env"

    # ② 主目录指针（稳定锚点）
    pinned = _pointer_mind()
    if pinned is not None:
        _ensure_structure(pinned)
        return pinned, True, "pointer"

    # ③ 回退：CWD 同级扫描，并立刻把结果固化到指针
    mind_dir = Path.cwd().parent / "gridman-mind"
    existed = mind_dir.exists()
    _ensure_structure(mind_dir)
    write_pointer_mind(mind_dir, source="cwd fallback")
    return mind_dir, existed, "cwd"


def get_mind_dir() -> Path:
    """获取 gridman-mind 根目录（解析顺序见模块 docstring）。"""
    mind_dir, _, _ = resolve_mind_dir()
    return mind_dir
