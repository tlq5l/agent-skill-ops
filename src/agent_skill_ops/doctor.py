"""Skills doctor: read-only invariant checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_skill_ops.discovery import (
    ConfigError,
    discovery_entries,
    load_roster,
    load_settings,
    resolve_under,
)
from agent_skill_ops.frontmatter import (
    parse_frontmatter,
    validate_parsed_for_visible_skill,
)


@dataclass(frozen=True)
class DoctorIssue:
    code: str
    message: str

    def format_line(self) -> str:
        return f"[{self.code}] {self.message}"


EXIT_OK = 0
EXIT_INVARIANT = 1
EXIT_CONFIG = 2


def _check_skill_md(skill_id: str, skill_md: Path, *, prefix: str) -> list[DoctorIssue]:
    out: list[DoctorIssue] = []
    if not skill_md.is_file():
        out.append(
            DoctorIssue(
                code=f"{prefix}_SKILL_MD",
                message=f"skill {skill_id!r} has no SKILL.md at {skill_md.parent}",
            )
        )
        return out
    text = skill_md.read_text(encoding="utf-8")
    parsed = parse_frontmatter(text)
    for msg in validate_parsed_for_visible_skill(parsed, skill_dir_name=skill_id):
        out.append(
            DoctorIssue(
                code=f"{prefix}_METADATA",
                message=f"skill {skill_id!r}: {msg}",
            )
        )
    return out


def run_doctor(
    *,
    root: Path,
    roster_path: Path,
    source: Path,
    discovery_roots: list[Path],
    settings_path: Path | None,
    dry_run: bool,
) -> tuple[int, list[str]]:
    _ = dry_run  # doctor is always read-only; flag for CLI contract only

    try:
        roster = load_roster(roster_path.resolve())
    except ConfigError as exc:
        return EXIT_CONFIG, [f"configuration error: {exc}"]

    source = source.resolve()
    if not source.is_dir():
        return EXIT_CONFIG, [f"configuration error: source is not a directory: {source}"]

    disabled: set[str] | None = None
    if settings_path is not None:
        try:
            disabled = load_settings(settings_path.resolve())
        except ConfigError as exc:
            return EXIT_CONFIG, [f"configuration error: {exc}"]

    visible = roster.visible_ids
    issues: list[DoctorIssue] = []

    for skill_id in sorted(visible):
        skill_dir = source / skill_id
        if not skill_dir.is_dir():
            issues.append(
                DoctorIssue(
                    code="ROSTER_SOURCE_MISSING",
                    message=(
                        f"visible roster skill {skill_id!r} is missing from source {source}"
                    ),
                )
            )
            continue
        issues.extend(
            _check_skill_md(skill_id, skill_dir / "SKILL.md", prefix="SOURCE")
        )

    for discovery_root in discovery_roots:
        discovery_root = discovery_root.resolve()
        if not discovery_root.exists():
            issues.append(
                DoctorIssue(
                    code="DISCOVERY_ROOT",
                    message=f"discovery root does not exist: {discovery_root}",
                )
            )
            continue
        if not discovery_root.is_dir():
            issues.append(
                DoctorIssue(
                    code="DISCOVERY_ROOT",
                    message=f"discovery root is not a directory: {discovery_root}",
                )
            )
            continue

        for entry in discovery_entries(discovery_root):
            name = entry.name
            if entry.is_file() and not entry.is_symlink():
                issues.append(
                    DoctorIssue(
                        code="DISCOVERY_UNEXPECTED",
                        message=f"unexpected file in discovery root {discovery_root}: {name}",
                    )
                )
                continue

            if entry.is_dir() and not entry.is_symlink():
                issues.append(
                    DoctorIssue(
                        code="DISCOVERY_COPIED_DIR",
                        message=(
                            f"discovery entry {name!r} in {discovery_root} is a copied "
                            f"directory; expected symlink into source"
                        ),
                    )
                )
                continue

            if entry.is_symlink():
                if not entry.exists():
                    issues.append(
                        DoctorIssue(
                            code="DISCOVERY_BROKEN_SYMLINK",
                            message=(
                                f"broken symlink in discovery root {discovery_root}: {entry}"
                            ),
                        )
                    )
                    continue
                raw_target = entry.readlink()
                if not raw_target.is_absolute():
                    target = (entry.parent / raw_target).resolve()
                else:
                    target = raw_target.resolve()

                if resolve_under(source, target) is None:
                    issues.append(
                        DoctorIssue(
                            code="DISCOVERY_EXTERNAL_TARGET",
                            message=(
                                f"discovery symlink {name!r} points outside source "
                                f"({target}); expected under {source}"
                            ),
                        )
                    )
                    continue

                if name not in visible:
                    issues.append(
                        DoctorIssue(
                            code="DISCOVERY_LEAK",
                            message=(
                                f"discovery entry {name!r} in {discovery_root} is not a "
                                f"visible roster skill"
                            ),
                        )
                    )
                    continue

                issues.extend(
                    _check_skill_md(name, target / "SKILL.md", prefix="DISCOVERY")
                )
                continue

            if name not in visible:
                issues.append(
                    DoctorIssue(
                        code="DISCOVERY_LEAK",
                        message=(
                            f"hidden or unrostered entry {name!r} in discovery root "
                            f"{discovery_root}"
                        ),
                    )
                )

    if disabled is not None:
        for skill_id in sorted(disabled):
            if skill_id in visible:
                issues.append(
                    DoctorIssue(
                        code="DISABLED_VISIBLE",
                        message=f"settings disable visible roster skill {skill_id!r}",
                    )
                )
            elif skill_id in roster.hidden_ids or skill_id not in roster.all_ids:
                issues.append(
                    DoctorIssue(
                        code="DISABLED_HIDDEN_LEAK",
                        message=(
                            f"settings disabledSkills includes hidden or non-rostered "
                            f"entry {skill_id!r} (possible hidden-corpus drift)"
                        ),
                    )
                )

    if not issues:
        return EXIT_OK, ["skills-doctor: no issues found"]

    lines = [f"skills-doctor: found {len(issues)} issue(s)"]
    lines.extend(i.format_line() for i in issues)
    return EXIT_INVARIANT, lines

