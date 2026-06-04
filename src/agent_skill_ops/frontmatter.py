"""Parse supported SKILL.md frontmatter subset (stdlib only)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ParseErrorKind = Literal[
    "missing_frontmatter",
    "malformed",
    "missing_name",
    "missing_description",
    "missing_user_invocable",
    "invalid_user_invocable",
]

DESCRIPTION_MAX_LEN = 1024


@dataclass(frozen=True)
class Frontmatter:
    name: str
    description: str
    user_invocable: bool


@dataclass(frozen=True)
class FrontmatterError:
    kind: ParseErrorKind
    message: str
    detail: str | None = None


def parse_frontmatter(text: str) -> Frontmatter | FrontmatterError:
    if not text.startswith("---\n"):
        return FrontmatterError(
            kind="missing_frontmatter",
            message="SKILL.md must start with a frontmatter block (---)",
        )
    end = text.find("\n---\n", 4)
    if end < 0:
        return FrontmatterError(
            kind="malformed",
            message="frontmatter block is not closed with ---",
        )
    block = text[4:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            return FrontmatterError(
                kind="malformed",
                message=f"invalid frontmatter line: {line!r}",
            )
        key, _, raw_val = line.partition(":")
        key = key.strip()
        val = raw_val.strip()
        if key in fields:
            return FrontmatterError(
                kind="malformed",
                message=f"duplicate frontmatter key: {key!r}",
            )
        fields[key] = val

    if "name" not in fields:
        return FrontmatterError(
            kind="missing_name",
            message="frontmatter is missing required field name",
        )
    if "description" not in fields:
        return FrontmatterError(
            kind="missing_description",
            message="frontmatter is missing required field description",
        )
    if "user-invocable" not in fields:
        return FrontmatterError(
            kind="missing_user_invocable",
            message="frontmatter is missing required field user-invocable",
        )

    ui_raw = fields["user-invocable"]
    if ui_raw in ("true", "True"):
        user_invocable = True
    elif ui_raw in ("false", "False"):
        user_invocable = False
    else:
        return FrontmatterError(
            kind="invalid_user_invocable",
            message="user-invocable must be boolean true or false",
            detail=ui_raw,
        )

    return Frontmatter(
        name=fields["name"],
        description=fields["description"],
        user_invocable=user_invocable,
    )


def validate_parsed_for_visible_skill(
    parsed: Frontmatter | FrontmatterError,
    *,
    skill_dir_name: str,
) -> list[str]:
    """Return human-readable invariant messages (empty if ok)."""
    if isinstance(parsed, FrontmatterError):
        if parsed.detail:
            return [f"{parsed.message} ({parsed.detail})"]
        return [parsed.message]

    issues: list[str] = []
    if parsed.name != skill_dir_name:
        issues.append(
            f"name mismatch: directory {skill_dir_name!r} but frontmatter name: {parsed.name!r}"
        )
    if not parsed.description:
        issues.append("missing description")
    elif len(parsed.description) > DESCRIPTION_MAX_LEN:
        issues.append(
            f"description exceeds maximum length of {DESCRIPTION_MAX_LEN} characters "
            f"(got {len(parsed.description)})"
        )
    if not parsed.user_invocable:
        issues.append("visible skills must have user-invocable: true")
    return issues
