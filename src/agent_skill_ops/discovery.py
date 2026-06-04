"""Roster and discovery-root helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RosterSkill:
    skill_id: str
    visible: bool
    user_invocable: bool


@dataclass(frozen=True)
class Roster:
    skills: list[RosterSkill]

    @property
    def visible_ids(self) -> set[str]:
        return {s.skill_id for s in self.skills if s.visible}

    @property
    def hidden_ids(self) -> set[str]:
        return {s.skill_id for s in self.skills if not s.visible}

    @property
    def all_ids(self) -> set[str]:
        return {s.skill_id for s in self.skills}


class ConfigError(Exception):
    """Invalid CLI paths or malformed configuration files."""


def load_roster(path: Path) -> Roster:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read roster file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"malformed JSON in roster file {path}: {exc}") from exc

    if not isinstance(raw, dict) or "skills" not in raw:
        raise ConfigError(f"roster file {path} must contain a 'skills' array")
    entries = raw["skills"]
    if not isinstance(entries, list):
        raise ConfigError(f"roster file {path}: 'skills' must be an array")

    skills: list[RosterSkill] = []
    for idx, item in enumerate(entries):
        if not isinstance(item, dict) or "id" not in item:
            raise ConfigError(
                f"roster file {path}: skills[{idx}] must be an object with 'id'"
            )
        skill_id = item["id"]
        if not isinstance(skill_id, str) or not skill_id:
            raise ConfigError(
                f"roster file {path}: skills[{idx}].id must be a non-empty string"
            )
        visible = bool(item.get("visible", False))
        user_invocable = bool(
            item.get("userInvocable", item.get("user_invocable", False))
        )
        skills.append(
            RosterSkill(
                skill_id=skill_id,
                visible=visible,
                user_invocable=user_invocable,
            )
        )
    return Roster(skills=skills)


def load_settings(path: Path) -> set[str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read settings file {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"malformed JSON in settings file {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"settings file {path} must be a JSON object")
    disabled = raw.get("disabledSkills", [])
    if disabled is None:
        disabled = []
    if not isinstance(disabled, list):
        raise ConfigError(f"settings file {path}: disabledSkills must be an array")
    out: set[str] = set()
    for name in disabled:
        if not isinstance(name, str):
            raise ConfigError(
                f"settings file {path}: disabledSkills entries must be strings"
            )
        out.add(name)
    return out


def resolve_under(base: Path, target: Path) -> Path | None:
    """Return resolved target if it stays under base; else None."""
    base = base.resolve()
    try:
        resolved = target.resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(base)
    except ValueError:
        return None
    return resolved


def discovery_entries(discovery_root: Path) -> list[Path]:
    if not discovery_root.is_dir():
        return []
    return sorted(
        (p for p in discovery_root.iterdir() if not p.name.startswith(".")),
        key=lambda p: p.name,
    )
