"""古立特 Gridman MCP Server — 财税审计计算工具"""
from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("gridman-mcp")
except PackageNotFoundError:
    # 开发环境未安装包时的兜底
    __version__ = "0.0.0.dev"
