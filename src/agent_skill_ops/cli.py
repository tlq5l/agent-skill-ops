"""CLI entrypoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_skill_ops.doctor import EXIT_CONFIG, EXIT_INVARIANT, EXIT_OK, run_doctor


def _doctor_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="skills-doctor",
        description=(
            "Read-only checks for agent skill roster, source metadata, and discovery roots."
        ),
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root (default: .)",
    )
    p.add_argument(
        "--roster",
        type=Path,
        required=True,
        help="Path to roster JSON (visible skills)",
    )
    p.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Canonical skill source directory (default: <root>/examples/skills)",
    )
    p.add_argument(
        "--discovery-root",
        type=Path,
        action="append",
        dest="discovery_roots",
        default=None,
        help="Discovery root to scan (repeatable)",
    )
    p.add_argument(
        "--settings",
        type=Path,
        default=None,
        help="Optional harness settings JSON (disabledSkills)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Report checks only; never mutates files (default behavior)",
    )
    return p


def main_doctor(argv: list[str] | None = None) -> None:
    parser = _doctor_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise SystemExit(exc.code if exc.code is not None else 2) from exc

    root = args.root.resolve()
    roster_path = args.roster if args.roster.is_absolute() else (root / args.roster)
    source = args.source
    if source is None:
        source = root / "examples" / "skills"
    elif not source.is_absolute():
        source = root / source

    discovery_roots = args.discovery_roots or []
    resolved_roots: list[Path] = []
    for dr in discovery_roots:
        resolved_roots.append(dr if dr.is_absolute() else (root / dr))

    if not roster_path.is_file():
        print(f"configuration error: roster file not found: {roster_path}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG)

    settings_path = args.settings
    if settings_path is not None and not (
        settings_path if settings_path.is_absolute() else (root / settings_path)
    ).is_file():
        sp = settings_path if settings_path.is_absolute() else (root / settings_path)
        print(f"configuration error: settings file not found: {sp}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG)
    if settings_path is not None and not settings_path.is_absolute():
        settings_path = root / settings_path

    code, lines = run_doctor(
        root=root,
        roster_path=roster_path,
        source=source,
        discovery_roots=resolved_roots,
        settings_path=settings_path,
        dry_run=args.dry_run,
    )
    stream = sys.stdout if code == EXIT_OK else sys.stderr
    for line in lines:
        print(line, file=stream)
    raise SystemExit(code)


def _sync_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="sync-skills",
        description="Plan or apply visible-only discovery symlinks from roster and source.",
    )
    p.add_argument("--root", type=Path, default=Path("."), help="Repository root")
    p.add_argument("--roster", type=Path, required=True, help="Roster JSON path")
    p.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Canonical skill source directory",
    )
    p.add_argument(
        "--discovery-root",
        type=Path,
        required=True,
        help="Discovery root for symlink farm",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Report plan only (default when --apply omitted)",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Create or update managed symlinks",
    )
    return p


def main_sync(argv: list[str] | None = None) -> None:
    from agent_skill_ops.sync import EXIT_CONFIG, EXIT_OK, EXIT_OPERATION, run_sync

    parser = _sync_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise SystemExit(exc.code if exc.code is not None else 2) from exc

    root = args.root.resolve()
    roster_path = args.roster if args.roster.is_absolute() else (root / args.roster)
    source = args.source if args.source.is_absolute() else (root / args.source)
    discovery_root = (
        args.discovery_root
        if args.discovery_root.is_absolute()
        else (root / args.discovery_root)
    )

    if not roster_path.is_file():
        print(f"configuration error: roster file not found: {roster_path}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG)

    code, lines = run_sync(
        root=root,
        roster_path=roster_path,
        source=source,
        discovery_root=discovery_root,
        apply=args.apply,
        dry_run_explicit=args.dry_run,
    )
    stream = sys.stdout if code == EXIT_OK else sys.stderr
    for line in lines:
        print(line, file=stream)
    raise SystemExit(code)


def _audit_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="audit-public-safety",
        description="Scan the repository for private paths, corpus leaks, and obvious secrets.",
    )
    p.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root to scan (default: .)",
    )
    return p


def main_audit(argv: list[str] | None = None) -> None:
    from agent_skill_ops.audit import EXIT_CONFIG, EXIT_FINDINGS, EXIT_OK, run_audit

    parser = _audit_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise SystemExit(exc.code if exc.code is not None else 2) from exc

    code, lines = run_audit(root=args.root.resolve())
    stream = sys.stdout if code == EXIT_OK else sys.stderr
    for line in lines:
        print(line, file=stream)
    raise SystemExit(code)
