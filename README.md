# agent-skill-ops

Small Python toolkit for checking agent skill folders before your harness tries to load them.

It is stdlib-only, dry-run by default, and built around plain files: a roster, a skill source directory, discovery roots, and optional harness settings.

## What it catches

- Broken discovery symlinks.
- Hidden skills accidentally exposed in discovery roots.
- Visible roster skills missing from the source tree.
- `SKILL.md` frontmatter problems:
  - `name:` does not match the directory name
  - missing `description` or one longer than 1024 characters
  - missing or invalid `user-invocable`
- Visible skills disabled in harness settings.
- Hidden skill names leaking into `disabledSkills`.

## Quickstart

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/skills-doctor --root . --roster examples/roster.json --discovery-root examples/discovery --settings examples/harness-settings.json
python3 scripts/sync-skills --root . --roster examples/roster.json --source examples/skills --discovery-root /tmp/agent-skill-ops-discovery --dry-run
python3 scripts/audit-public-safety --root .
```

Optional install:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
skills-doctor --root . --roster examples/roster.json --discovery-root examples/discovery --settings examples/harness-settings.json
```

## Commands

| Command | Use it for |
|---|---|
| `skills-doctor` | Read-only checks for roster, source skills, discovery roots, symlinks, frontmatter, and disabled-skill drift. |
| `sync-skills` | Dry-run or apply a visible-only symlink farm from a roster. |
| `audit-public-safety` | Scan this repository for unsafe path, account, repository-marker, or obvious secret leaks. |

## Dry-run vs apply

`sync-skills` is a dry-run unless you pass `--apply`.

| Mode | Discovery root | Notes |
|---|---|---|
| Dry-run | Any scratch path, such as `/tmp/agent-skill-ops-discovery` | Prints the planned changes only. |
| Apply | A path under the configured `--root`, such as `examples/discovery` | Creates or updates visible-skill symlinks. |

Example apply + verify:

```sh
python3 scripts/sync-skills --root . --roster examples/roster.json --source examples/skills --discovery-root examples/discovery --apply
python3 scripts/skills-doctor --root . --roster examples/roster.json --discovery-root examples/discovery --settings examples/harness-settings.json
```

## Example layout

```text
examples/
  roster.json
  harness-settings.json
  skills/
    explain-error/SKILL.md
    plan-task/SKILL.md
    review-diff/SKILL.md
    summarize-notes/SKILL.md
    internal-only-skill/SKILL.md
  discovery/
```

The bundled examples are synthetic fixtures. Replace them with your own roster, source directory, discovery root, and settings file.

## What it does not do

- It does not install or configure an agent harness.
- It does not manage credentials, accounts, browsers, databases, web apps, or hosted services.
- It does not copy skill bodies into discovery roots; `sync-skills` creates symlinks.
- It does not rewrite files unless you explicitly run `sync-skills --apply`.
- It does not validate every possible YAML feature; frontmatter support is intentionally small.

## Feedback

If the checker misses a skill-loading failure mode, open an issue with:

1. A minimal redacted fixture.
2. The command you ran.
3. The expected result.
4. The actual result.

Do not include tokens, API keys, customer data, proprietary harness configuration, or copied non-public `SKILL.md` bodies.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
