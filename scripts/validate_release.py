#!/usr/bin/env python3
"""Gridman Skill 发布质检脚本（维护者工具，非古立特运行时的一部分）。

用途
    在改完 Skill、准备发布新版本前跑一次自动体检，把低级错误挡在发布之前。
    古立特回答财税问题时不会读取或依赖本脚本。

检查项
    - 核心文件是否齐全（SKILL.md、INSTALL.md、operations 规则、能力表、workflows README 等）
    - SKILL.md frontmatter 的 name 与 version（version 必须是 x.y.z）
    - 每个 Workflow 的 frontmatter 字段、必备章节、profession/risk_level 取值，
      以及引用的能力 ID 是否都在 capability_registry.md 注册
    - 能力 ID 命名格式
    - 文件编码与乱码标记
    - 文档内部引用的相对路径是否真实存在（死链检查）
    - 知识文件的标题、文件头元数据与“准则原文”类知识点的来源
    - SKILL.md / source_directory.md 的权威层级断言，及是否残留旧冲突表述

边界
    仅服务发布质量，不是第二套运行架构，也不校验具体工具/provider/schema。
    只用 Python 标准库，不联网、不安装依赖。

用法
    python scripts/validate_release.py            # 常规检查
    python scripts/validate_release.py --strict   # 警告也视为发布阻断
    通过时输出 "Release gate: PASS"。
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
WORKFLOW_VERSION = re.compile(r"^\d+\.\d+(?:\.\d+)?$")
CAPABILITY_ID = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+$")
MOJIBAKE = ("\ufffd", "\u951f\u65a4\u62f7", "\u00ef\u00bf\u00bd", "\u00e2\u20ac\u2122")
CORE_FILES = (
    "SKILL.md",
    "INSTALL.md",
    "CHANGELOG.md",
    "_format_standard.md",
    "operations/behavior_rules.md",
    "operations/private_resources_rules.md",
    "operations/user_prefs_rules.md",
    "operations/routing_index.md",
    "operations/routing_flow.md",
    "operations/source_directory.md",
    "operations/capability_registry.md",
    "references/workflows/README.md",
)
INTERNAL_ROOTS = ("operations/", "references/", "gridman-character/", "scripts/")
INTERNAL_FILES = {"SKILL.md", "INSTALL.md", "CHANGELOG.md", "_format_standard.md"}
WORKFLOW_FIELDS = (
    "workflow",
    "version",
    "profession",
    "output_type",
    "risk_level",
    "required_inputs",
    "required_capabilities",
    "optional_capabilities",
    "external_write",
    "mind_write",
)
WORKFLOW_SECTIONS = (
    "触发条件",
    "前置条件",
    "专业知识绑定",
    "执行步骤",
    "工具选择与授权",
    "异常处理",
    "复核检查点",
    "产出物",
    "Mind 写入规则",
)
PROFESSIONS = {"审计", "财务", "税务", "投行", "分析"}
RISK_LEVELS = {"low", "medium", "high"}


@dataclass(frozen=True)
class Finding:
    level: str
    path: str
    line: int
    code: str
    message: str


class Validator:
    def __init__(self, root: Path, exclude_workflow_audit: bool = False) -> None:
        self.root = root.resolve()
        self.exclude_workflow_audit = exclude_workflow_audit
        self.findings: list[Finding] = []
        self.text_cache: dict[Path, str] = {}

    def add(self, level: str, path: Path, line: int, code: str, message: str) -> None:
        try:
            display = path.resolve().relative_to(self.root).as_posix()
        except ValueError:
            display = str(path)
        self.findings.append(Finding(level, display, line, code, message))

    def error(self, path: Path, line: int, code: str, message: str) -> None:
        self.add("ERROR", path, line, code, message)

    def warn(self, path: Path, line: int, code: str, message: str) -> None:
        self.add("WARN", path, line, code, message)

    def read(self, path: Path) -> str | None:
        if path in self.text_cache:
            return self.text_cache[path]
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError as exc:
            self.error(path, exc.start + 1, "ENCODING", "文件不是有效 UTF-8")
            return None
        except OSError as exc:
            self.error(path, 1, "READ", f"无法读取：{exc}")
            return None
        self.text_cache[path] = text
        return text

    def markdown_files(self) -> list[Path]:
        files = sorted(self.root.rglob("*.md"))
        if self.exclude_workflow_audit:
            audit_root = self.root / "references" / "workflows" / "audit"
            files = [path for path in files if audit_root not in path.parents]
        return files

    def workflow_files(self) -> list[Path]:
        root = self.root / "references" / "workflows"
        files = sorted(path for path in root.rglob("*.md") if path.name != "README.md")
        if self.exclude_workflow_audit:
            audit_root = root / "audit"
            files = [path for path in files if audit_root not in path.parents]
        return files

    @staticmethod
    def parse_frontmatter(text: str) -> tuple[dict[str, Any], int] | None:
        lines = text.splitlines()
        if not lines or lines[0].strip() != "---":
            return None
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            return None
        data: dict[str, Any] = {}
        current_list: str | None = None
        for raw in lines[1:end]:
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("-") and current_list:
                data[current_list].append(stripped[1:].strip().strip('"\''))
                continue
            match = re.match(r"^(?:\s*)([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$", raw)
            if not match:
                continue
            key, value = match.groups()
            value = value.strip().strip('"\'')
            if not value:
                data[key] = []
                current_list = key
            else:
                if value == "true":
                    parsed: Any = True
                elif value == "false":
                    parsed = False
                else:
                    parsed = value
                data[key] = parsed
                current_list = None
        return data, end + 1

    def check_core_files(self) -> None:
        for relative in CORE_FILES:
            path = self.root / relative
            if not path.is_file():
                self.error(path, 1, "CORE_MISSING", "核心发布文件不存在")

    def check_skill_frontmatter(self) -> None:
        path = self.root / "SKILL.md"
        text = self.read(path)
        if text is None:
            return
        parsed = self.parse_frontmatter(text)
        if parsed is None:
            self.error(path, 1, "SKILL_FRONTMATTER", "缺少完整 frontmatter")
            return
        data, _ = parsed
        if not data.get("name"):
            self.error(path, 1, "SKILL_NAME", "frontmatter 缺少 name")
        version = data.get("version")
        if not isinstance(version, str) or not SEMVER.fullmatch(version):
            self.error(path, 1, "SKILL_VERSION", "metadata.version 必须是 SemVer（x.y.z）")

    def load_capabilities(self) -> set[str]:
        path = self.root / "operations" / "capability_registry.md"
        text = self.read(path)
        if text is None:
            return set()
        capabilities = set(re.findall(r"^\|\s*`([a-z][a-z0-9]*(?:\.[a-z][a-z0-9]*)+)`\s*\|", text, re.MULTILINE))
        if not capabilities:
            self.error(path, 1, "CAPABILITY_REGISTRY", "注册表中未找到能力 ID")
        for capability in capabilities:
            if not CAPABILITY_ID.fullmatch(capability):
                self.error(path, 1, "CAPABILITY_ID", f"无效能力 ID：{capability}")
        return capabilities

    def check_workflows(self, capabilities: set[str]) -> None:
        for path in self.workflow_files():
            text = self.read(path)
            if text is None:
                continue
            parsed = self.parse_frontmatter(text)
            if parsed is None:
                self.error(path, 1, "WORKFLOW_FRONTMATTER", "缺少完整 frontmatter")
                continue
            data, end_line = parsed
            for field in WORKFLOW_FIELDS:
                if field not in data:
                    self.error(path, 1, "WORKFLOW_FIELD", f"缺少 frontmatter 字段：{field}")
            version = data.get("version")
            if not isinstance(version, str) or not WORKFLOW_VERSION.fullmatch(version):
                self.error(path, 1, "WORKFLOW_VERSION", "version 必须是 x.y 或 x.y.z")
            profession = data.get("profession")
            if profession not in PROFESSIONS:
                self.error(path, 1, "WORKFLOW_PROFESSION", f"profession 不在允许值中：{profession}")
            risk = data.get("risk_level")
            if risk not in RISK_LEVELS:
                self.error(path, 1, "WORKFLOW_RISK", f"risk_level 不在允许值中：{risk}")
            for field in ("external_write", "mind_write"):
                if not isinstance(data.get(field), bool):
                    self.error(path, 1, "WORKFLOW_BOOLEAN", f"{field} 必须是 true 或 false")
            for field in ("required_inputs", "required_capabilities", "optional_capabilities"):
                value = data.get(field)
                if not isinstance(value, list):
                    self.error(path, 1, "WORKFLOW_LIST", f"{field} 必须是 YAML 列表")
            required_inputs = data.get("required_inputs")
            if isinstance(required_inputs, list) and not required_inputs:
                self.error(path, 1, "WORKFLOW_INPUTS", "required_inputs 不得为空")
            for field in ("required_capabilities", "optional_capabilities"):
                value = data.get(field)
                if not isinstance(value, list):
                    continue
                for capability in value:
                    if capability not in capabilities:
                        self.error(path, 1, "UNKNOWN_CAPABILITY", f"{field} 使用未注册能力：{capability}")
            if isinstance(data.get("required_capabilities"), list) and isinstance(data.get("optional_capabilities"), list):
                overlap = set(data["required_capabilities"]) & set(data["optional_capabilities"])
                if overlap:
                    self.error(path, 1, "CAPABILITY_OVERLAP", f"必需与可选能力重复：{', '.join(sorted(overlap))}")
            body = "\n".join(text.splitlines()[end_line:])
            for section in WORKFLOW_SECTIONS:
                if not re.search(rf"^##\s+{re.escape(section)}\s*$", body, re.MULTILINE | re.IGNORECASE):
                    self.error(path, end_line + 1, "WORKFLOW_SECTION", f"缺少正文二级章节：{section}")

    def check_encoding_and_mojibake(self, files: list[Path]) -> None:
        for path in files:
            text = self.read(path)
            if text is None:
                continue
            for marker in MOJIBAKE:
                for match in re.finditer(re.escape(marker), text):
                    line = text.count("\n", 0, match.start()) + 1
                    self.error(path, line, "MOJIBAKE", f"发现疑似乱码标记：{marker}")

    def check_paths(self, files: list[Path]) -> None:
        basename_index: dict[str, list[Path]] = defaultdict(list)
        for file_path in self.root.rglob("*"):
            if file_path.is_file():
                basename_index[file_path.name].append(file_path)
        for name, paths in basename_index.items():
            knowledge_paths = [path for path in paths if self.root / "references" / "knowledge" in path.parents]
            if len(knowledge_paths) > 1:
                self.error(knowledge_paths[0], 1, "DUPLICATE_KNOWLEDGE_NAME", f"knowledge 裸文件名不唯一：{name}")

        # This is a maintainer-facing specification containing deliberately
        # invalid examples and placeholders, not a runtime routing document.
        excluded_runtime_path_docs = {self.root / "_format_standard.md"}
        knowledge_root = self.root / "references" / "knowledge"
        extra_root = self.root / "references" / "extra"
        character_root = self.root / "gridman-character"

        for path in files:
            if path in excluded_runtime_path_docs:
                continue
            text = self.read(path)
            if text is None:
                continue
            lines = text.splitlines()
            for number, line in enumerate(lines, 1):
                if re.search(r"(?<!references/)\b(?:knowledge|workflows)/", line):
                    self.error(path, number, "SHORT_PATH", "运行时路径缺少 references/ 前缀")
                tokens = re.findall(r"(?<!`)`([^`\n]+)`(?!`)", line)
                links = re.findall(r"\]\((?!https?://|mailto:)([^)#]+)(?:#[^)]+)?\)", line)
                for raw in tokens + links:
                    token = raw.strip().replace("\\", "/")
                    if not token or " " in token or token.startswith(("http://", "https://", "~/", "~\\")):
                        continue
                    token = token.rstrip(".,;:，。；：")
                    if "#" in token:
                        token = token.split("#", 1)[0]
                    if token in INTERNAL_FILES or token.startswith(INTERNAL_ROOTS):
                        self.check_internal_path(path, number, line, token)
                        continue
                    if "/" not in token and token.endswith(".md") and token in basename_index:
                        targets = basename_index[token]
                        allowed_knowledge_link = (
                            knowledge_root in path.parents
                            and re.match(r"^\s*>\s*(?:详见|关联)：", line) is not None
                            and all(knowledge_root in target.parents for target in targets)
                        )
                        allowed_extra_link = (
                            extra_root in path.parents
                            and all(extra_root in target.parents for target in targets)
                        )
                        allowed_character_link = (
                            character_root in path.parents
                            and (path.parent / token).is_file()
                        )
                        if not (allowed_knowledge_link or allowed_extra_link or allowed_character_link):
                            self.error(path, number, "BARE_INTERNAL_PATH", f"内部文件必须使用 skill 根相对路径：{token}")

    def check_internal_path(self, source: Path, line_number: int, line: str, token: str) -> None:
        if any(symbol in token for symbol in ("*", "?", "[")):
            return
        if "{" in token:
            prefix = token.split("{", 1)[0].rstrip("/")
            if prefix and not (self.root / prefix).exists():
                self.error(source, line_number, "PATH_PREFIX_MISSING", f"路径占位符前缀不存在：{token}")
            return
        target = self.root / token
        if target.exists():
            return
        is_workflow_convention = (
            source == self.root / "references" / "workflows" / "README.md"
            and token.startswith("references/workflows/")
            and token.endswith("/")
        )
        is_optional_route = (
            source == self.root / "operations" / "routing_index.md"
            and token.startswith("references/workflows/")
            and token.endswith("/")
            and "实际存在" in line
        )
        if not (is_workflow_convention or is_optional_route):
            self.error(source, line_number, "BROKEN_PATH", f"内部引用不存在：{token}")

    def check_knowledge_metadata(self) -> None:
        root = self.root / "references" / "knowledge"
        for path in sorted(root.rglob("*.md")):
            text = self.read(path)
            if text is None:
                continue
            lines = text.splitlines()
            first_nonempty = next((line for line in lines if line.strip()), "")
            if not first_nonempty.startswith("# "):
                self.warn(path, 1, "KNOWLEDGE_TITLE", "知识文件首个非空行应为一级标题")
            header = "\n".join(lines[:35])
            for field in ("定位", "来源", "覆盖", "性质"):
                if not re.search(rf"^>\s*{field}：", header, re.MULTILINE):
                    self.warn(path, 1, "KNOWLEDGE_HEADER", f"文件头缺少字段：{field}")
            for index, line in enumerate(lines):
                if re.match(r"^>\s*置信度：准则原文\s*$", line):
                    section_start = index
                    while section_start >= 0 and not lines[section_start].startswith("### "):
                        section_start -= 1
                    context = lines[max(section_start, 0):index]
                    if not any(re.match(r"^>\s*来源：\s*\S+", item) for item in context):
                        self.error(path, index + 1, "PRIMARY_SOURCE_MISSING", "“准则原文”知识点缺少具体来源字段")

    def check_authority_contract(self) -> None:
        skill = self.root / "SKILL.md"
        source = self.root / "operations" / "source_directory.md"
        skill_text = self.read(skill) or ""
        source_text = self.read(source) or ""
        required_skill = (
            "现行法规、准则、税率、文号与效力状态",
            "官方原文为最高权威",
            "不得覆盖更新后的官方事实",
        )
        for phrase in required_skill:
            if phrase not in skill_text:
                self.error(skill, 1, "AUTHORITY_CONTRACT", f"缺少权威层级断言：{phrase}")
        if "现行法规、准则、税率、文号与效力状态以核实后的官方原文为最高权威" not in source_text:
            self.error(source, 1, "AUTHORITY_CONTRACT", "来源目录未声明官方现行原文优先")
        forbidden = ("`references/` 是主源、最高权威", "冲突时以 `references/` 为准", "冲突时 `references/` 优先")
        for path in (skill, self.root / "operations" / "behavior_rules.md"):
            text = self.read(path) or ""
            for phrase in forbidden:
                if phrase in text:
                    line = text[: text.index(phrase)].count("\n") + 1
                    self.error(path, line, "AUTHORITY_CONFLICT", f"发现旧权威冲突表述：{phrase}")

    def run(self) -> None:
        self.check_core_files()
        files = self.markdown_files()
        self.check_skill_frontmatter()
        capabilities = self.load_capabilities()
        self.check_workflows(capabilities)
        self.check_encoding_and_mojibake(files)
        self.check_paths(files)
        self.check_knowledge_metadata()
        self.check_authority_contract()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Gridman Skill before release")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="gridman-skill root")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as release-blocking")
    parser.add_argument("--exclude-workflow-audit", action="store_true", help="Temporarily exclude references/workflows/audit")
    args = parser.parse_args()

    validator = Validator(args.root, exclude_workflow_audit=args.exclude_workflow_audit)
    validator.run()
    findings = sorted(validator.findings, key=lambda item: (item.level != "ERROR", item.path, item.line, item.code))
    for item in findings:
        print(f"{item.level} {item.code} {item.path}:{item.line} - {item.message}")
    errors = sum(item.level == "ERROR" for item in findings)
    warnings = sum(item.level == "WARN" for item in findings)
    print(f"\nValidated: {args.root.resolve()}")
    print(f"Result: {errors} error(s), {warnings} warning(s)")
    if errors or (args.strict and warnings):
        return 1
    print("Release gate: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
