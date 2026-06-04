"""Visible-only discovery symlink sync (dry-run by default)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from agent_skill_ops.discovery import ConfigError, Roster, load_roster, resolve_under

MANIFEST_NAME = ".agent-skill-ops-sync-manifest.json"
MANIFEST_VERSION = 1

EXIT_OK = 0
EXIT_OPERATION = 1
EXIT_CONFIG = 2


class ActionKind(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE_STALE = "remove_stale"
    REPAIR = "repair"
    NOOP = "noop"
    SKIP_CONFLICT = "skip_conflict"
    ERROR_MISSING_SOURCE = "error_missing_source"


@dataclass(frozen=True)
class PlannedAction:
    kind: ActionKind
    name: str
    detail: str


def _manifest_path(discovery_root: Path) -> Path:
    return discovery_root / MANIFEST_NAME


def _load_manifest(discovery_root: Path) -> set[str]:
    path = _manifest_path(discovery_root)
    if not path.is_file():
        return set()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(raw, dict):
        return set()
    names = raw.get("managed", [])
    if not isinstance(names, list):
        return set()
    return {n for n in names if isinstance(n, str)}


def _write_manifest(discovery_root: Path, managed: set[str]) -> None:
    payload = {"version": MANIFEST_VERSION, "managed": sorted(managed)}
    _manifest_path(discovery_root).write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def _relative_link_target(source_skill: Path, discovery_root: Path) -> str:
    return os.path.relpath(source_skill.resolve(), discovery_root.resolve())


def _expected_target(source: Path, skill_id: str, discovery_root: Path) -> Path:
    rel = _relative_link_target(source / skill_id, discovery_root)
    return (discovery_root / rel).resolve()


def _is_managed_symlink_to_source(
    entry: Path,
    *,
    source: Path,
    managed_names: set[str],
) -> bool:
    if not entry.is_symlink():
        return False
    name = entry.name
    if name in managed_names:
        return True
    if not entry.exists():
        return name in managed_names
    raw = entry.readlink()
    target = (entry.parent / raw).resolve() if not raw.is_absolute() else raw.resolve()
    return resolve_under(source.resolve(), target) is not None


def _public_detail(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def _source_skill_public(root: Path, source: Path, skill_id: str) -> str:
    try:
        rel = source.resolve().relative_to(root.resolve())
        return f"{rel}/{skill_id}"
    except ValueError:
        return skill_id


def _plan_detail(
    root: Path,
    source: Path,
    skill_id: str,
    *,
    suffix: str,
) -> str:
    pub = _source_skill_public(root, source, skill_id)
    return f"{suffix} (source {pub})"


def plan_sync(
    *,
    root: Path,
    roster: Roster,
    source: Path,
    discovery_root: Path,
) -> tuple[list[PlannedAction], list[str]]:
    messages: list[str] = []
    actions: list[PlannedAction] = []
    visible = sorted(roster.visible_ids)
    managed_prev = _load_manifest(discovery_root)

    if discovery_root.exists() and not discovery_root.is_dir():
        messages.append(
            "configuration error: discovery root is not a directory: "
            + _public_detail(root, discovery_root)
        )
        return actions, messages

    if not discovery_root.exists():
        messages.append(
            "plan: discovery root will be created: "
            + _public_detail(root, discovery_root)
        )

    for skill_id in visible:
        src_dir = source / skill_id
        if not src_dir.is_dir():
            actions.append(
                PlannedAction(
                    kind=ActionKind.ERROR_MISSING_SOURCE,
                    name=skill_id,
                    detail=_plan_detail(root, source, skill_id, suffix="visible skill missing from source"),
                )
            )
            continue

        entry = discovery_root / skill_id
        rel = _relative_link_target(src_dir, discovery_root)
        expected = _expected_target(source, skill_id, discovery_root)

        if entry.exists() or entry.is_symlink():
            if entry.is_dir() and not entry.is_symlink():
                actions.append(
                    PlannedAction(
                        kind=ActionKind.SKIP_CONFLICT,
                        name=skill_id,
                        detail="discovery entry is an unrelated directory",
                    )
                )
                continue
            if entry.is_file() and not entry.is_symlink():
                actions.append(
                    PlannedAction(
                        kind=ActionKind.SKIP_CONFLICT,
                        name=skill_id,
                        detail="discovery entry is an unrelated file",
                    )
                )
                continue
            if entry.is_symlink():
                if not entry.exists():
                    actions.append(
                        PlannedAction(
                            kind=ActionKind.REPAIR,
                            name=skill_id,
                            detail=_plan_detail(root, source, skill_id, suffix="repair broken symlink"),
                        )
                    )
                    continue
                try:
                    current = entry.resolve()
                except OSError:
                    actions.append(
                        PlannedAction(
                            kind=ActionKind.REPAIR,
                            name=skill_id,
                            detail=_plan_detail(root, source, skill_id, suffix="repair broken symlink"),
                        )
                    )
                    continue
                if current == expected:
                    actions.append(
                        PlannedAction(
                            kind=ActionKind.NOOP,
                            name=skill_id,
                            detail="symlink already correct",
                        )
                    )
                    continue
                if _is_managed_symlink_to_source(
                    entry, source=source, managed_names=managed_prev | {skill_id}
                ):
                    actions.append(
                        PlannedAction(
                            kind=ActionKind.UPDATE,
                            name=skill_id,
                            detail=_plan_detail(root, source, skill_id, suffix="update symlink"),
                        )
                    )
                    continue
                actions.append(
                    PlannedAction(
                        kind=ActionKind.SKIP_CONFLICT,
                        name=skill_id,
                        detail="non-generated symlink already present",
                    )
                )
                continue

        actions.append(
            PlannedAction(
                kind=ActionKind.CREATE,
                name=skill_id,
                detail=_plan_detail(root, source, skill_id, suffix="create symlink"),
            )
        )

    if discovery_root.is_dir():
        for entry in sorted(discovery_root.iterdir(), key=lambda p: p.name):
            if entry.name.startswith(".") or entry.name == MANIFEST_NAME:
                continue
            name = entry.name
            if name in roster.visible_ids:
                continue
            stale = False
            if name in roster.hidden_ids or name in roster.all_ids:
                if entry.is_symlink() and (
                    name in managed_prev
                    or _is_managed_symlink_to_source(
                        entry, source=source, managed_names=managed_prev
                    )
                ):
                    stale = True
            elif name in managed_prev:
                stale = True
            elif entry.is_symlink() and _is_managed_symlink_to_source(
                entry, source=source, managed_names=managed_prev
            ):
                if name not in roster.all_ids:
                    stale = True
            elif entry.is_symlink() and not entry.exists() and name in managed_prev:
                stale = True
            elif entry.is_symlink() and not entry.exists():
                messages.append(
                    "warning: broken symlink (unmanaged): "
                    + _public_detail(root, entry)
                )
            if stale:
                actions.append(
                    PlannedAction(
                        kind=ActionKind.REMOVE_STALE,
                        name=name,
                        detail="stale generated symlink",
                    )
                )

    return actions, messages


def apply_sync(
    *,
    root: Path,
    roster: Roster,
    source: Path,
    discovery_root: Path,
) -> tuple[int, list[str]]:
    root = root.resolve()
    discovery_root = discovery_root.resolve()
    source = source.resolve()
    if resolve_under(root, discovery_root) is None:
        return EXIT_CONFIG, [
            "configuration error: --apply requires --discovery-root inside --root "
            f"(got {_public_detail(root, discovery_root)})"
        ]
    if resolve_under(root, source) is None:
        return EXIT_CONFIG, [
            "configuration error: --source must be inside --root for symlink apply"
        ]

    actions, extra = plan_sync(
        root=root, roster=roster, source=source, discovery_root=discovery_root
    )
    lines = list(extra)
    errors = [a for a in actions if a.kind == ActionKind.ERROR_MISSING_SOURCE]
    if errors:
        for a in errors:
            lines.append(f"error: {a.detail}")
        lines.insert(0, f"sync-skills: {len(errors)} missing source error(s)")
        return EXIT_OPERATION, lines

    discovery_root.mkdir(parents=True, exist_ok=True)
    managed: set[str] = set()

    for action in actions:
        if action.kind == ActionKind.SKIP_CONFLICT:
            lines.append(f"conflict: {action.name}: {action.detail}")
            continue
        if action.kind == ActionKind.NOOP:
            managed.add(action.name)
            lines.append(f"noop: {action.name}: {action.detail}")
            continue

        entry = discovery_root / action.name
        if action.kind == ActionKind.REMOVE_STALE:
            if entry.is_symlink() or entry.exists():
                entry.unlink(missing_ok=True)
            lines.append(f"removed: {action.name}: {action.detail}")
            continue

        if action.kind in (ActionKind.CREATE, ActionKind.UPDATE, ActionKind.REPAIR):
            src_dir = source / action.name
            rel = _relative_link_target(src_dir, discovery_root)
            if entry.exists() or entry.is_symlink():
                entry.unlink(missing_ok=True)
            entry.symlink_to(rel)
            managed.add(action.name)
            lines.append(f"applied: {action.name}: {action.detail}")

    for skill_id in roster.visible_ids:
        p = discovery_root / skill_id
        if p.is_symlink():
            managed.add(skill_id)

    _write_manifest(discovery_root, managed)
    lines.insert(0, "sync-skills: apply complete")
    return EXIT_OK, lines


def run_sync(
    *,
    root: Path,
    roster_path: Path,
    source: Path,
    discovery_root: Path,
    apply: bool,
    dry_run_explicit: bool,
) -> tuple[int, list[str]]:
    _ = dry_run_explicit
    try:
        roster = load_roster(roster_path.resolve())
    except ConfigError as exc:
        return EXIT_CONFIG, [f"configuration error: {exc}"]

    source = source.resolve()
    if not source.is_dir():
        return EXIT_CONFIG, [f"configuration error: source is not a directory: {source}"]

    discovery_root = discovery_root.resolve()
    actions, messages = plan_sync(
        root=root.resolve(),
        roster=roster,
        source=source,
        discovery_root=discovery_root,
    )

    errors = [a for a in actions if a.kind == ActionKind.ERROR_MISSING_SOURCE]
    if apply:
        return apply_sync(
            root=root.resolve(),
            roster=roster,
            source=source,
            discovery_root=discovery_root,
        )

    lines = ["sync-skills: dry-run (no changes applied)"]
    lines.extend(messages)
    for action in actions:
        lines.append(f"plan: {action.name}: [{action.kind.value}] {action.detail}")
    if errors:
        lines.append(f"sync-skills: {len(errors)} missing source error(s)")
        return EXIT_OPERATION, lines
    return EXIT_OK, lines
