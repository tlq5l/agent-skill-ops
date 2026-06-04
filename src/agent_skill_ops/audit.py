"""Public-safety audit: scan repository files for unsafe content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SCAN_SUFFIXES = {".md", ".json", ".toml", ".py", ".txt", ".yaml", ".yml", ".sh"}
_SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules", "tests"}


@dataclass(frozen=True)
class AuditFinding:
    rule: str
    path: str
    detail: str

    def format_line(self) -> str:
        return f"[{self.rule}] {self.path}: {self.detail}"


EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_CONFIG = 2


def rule_catalog() -> list[tuple[str, str]]:
    """Human-readable rule ids and categories for success output."""
    return [(rule_id, detail) for rule_id, _pattern, detail in _rules()]


def _iter_scan_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.suffix.lower() not in _SCAN_SUFFIXES and path.name not in {"LICENSE", "README"}:
            continue
        rel = path.relative_to(root)
        if rel.as_posix() == "src/agent_skill_ops/audit.py":
            continue
        out.append(path)
    return out


def _rules() -> list[tuple[str, re.Pattern[str], str]]:
    return [
        ("PRIVATE_PATH", re.compile(r"/Users/greenapple(?:/\.agents)?"), "private absolute path reference"),
        ("PRIVATE_CORPUS", re.compile(r"\.agents/skill-db"), "private corpus reference"),
        ("MEMORIES", re.compile(r"\.agents/memories|(?:^|/)MEMORY\.md$", re.I), "memories category reference"),
        ("SECURE_BACKUPS", re.compile(r"secure-backups", re.I), "secure-backups reference"),
        ("ACCOUNT_ROTATION", re.compile(r"account[-_ ]?rotation[-_ ]?script", re.I), "account rotation script reference"),
        ("RAW_TRANSCRIPTS", re.compile(r"raw[-_ ]?transcripts?/|transcript-derived[-_ ]content", re.I), "raw transcript reference"),
        ("PROVIDER_CONFIG", re.compile(r"(?:provider[-_ ]?config|openai\.yaml|anthropic\.yaml)", re.I), "provider config reference"),
        ("MISSION_INTERNALS", re.compile(r"(?:\.factory/missions|mission-internal)", re.I), "mission internals reference"),
        ("PRIVATE_ACCOUNT", re.compile(r"\b(?:tcvictory123|greenapple@)\b", re.I), "private account identifier"),
        (
            "PUBLIC_GTM_LEAK",
            re.compile(r"\b(?:7-day|demand[- ]test|concierge|paid support|sales page|cta)\b|\$(?:99|499)\b", re.I),
            "internal launch or sales strategy language",
        ),
        (
            "OBVIOUS_SECRET",
            re.compile(
                r"(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
                r"xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|"
                r"-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)"
            ),
            "obvious secret or token pattern",
        ),
    ]


def run_audit(*, root: Path) -> tuple[int, list[str]]:
    root = root.resolve()
    if not root.is_dir():
        return EXIT_CONFIG, [f"configuration error: root is not a directory: {root}"]

    findings: list[AuditFinding] = []
    rules = _rules()

    for path in _iter_scan_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            findings.append(AuditFinding(rule="READ_ERROR", path=str(path.relative_to(root)), detail=str(exc)))
            continue
        rel = str(path.relative_to(root))
        for rule_id, pattern, detail in rules:
            if pattern.search(text):
                findings.append(AuditFinding(rule=rule_id, path=rel, detail=detail))

    if not findings:
        lines = ["audit-public-safety: no unsafe findings", "categories checked:"]
        for rule_id, detail in rule_catalog():
            lines.append(f"  - {rule_id}: {detail}")
        return EXIT_OK, lines

    lines = [f.format_line() for f in findings]
    lines.insert(0, f"audit-public-safety: {len(findings)} finding(s)")
    return EXIT_FINDINGS, lines
