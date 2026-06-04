# agent-skill-ops

Public-safe, **Python 3 stdlib-only** toolkit for auditing agent skill loading across harnesses. It helps you catch roster/discovery drift, broken symlinks, and metadata mistakes **before** they break an agent session.

All bundled examples are **synthetic teaching fixtures**. They are not copied from any private skill corpus, non-public source material, or operational memory stores.

## Quickstart

From the repository root (no install step required beyond Python 3.11+):

```sh
python3 -m unittest discover -s tests -v
python3 scripts/skills-doctor --root . --roster examples/roster.json --discovery-root examples/discovery --settings examples/harness-settings.json
python3 scripts/sync-skills --root . --roster examples/roster.json --source examples/skills --discovery-root /tmp/agent-skill-ops-discovery --dry-run
python3 scripts/audit-public-safety --root .
```

Optional: install entrypoints in a venv with `pip install -e .`, then call `skills-doctor`, `sync-skills`, and `audit-public-safety` the same way.

### Discovery roots: dry-run vs apply

| Mode | Discovery root | Why |
|------|----------------|-----|
| **Dry-run** (default) | Any empty or scratch directory, e.g. `/tmp/agent-skill-ops-discovery` | Plans changes without touching your real harness; safe for docs and CI snippets. |
| **Apply** (`--apply`) | A directory **under this repo root**, e.g. `examples/discovery` or `./discovery/` | Keeps generated symlink targets public-safe and inside the configured `--root`; avoids embedding private home paths in links. |

Example apply + verify (uses in-repo discovery, not `/tmp`):

```sh
python3 scripts/sync-skills --root . --roster examples/roster.json --source examples/skills --discovery-root examples/discovery --apply
python3 scripts/skills-doctor --root . --roster examples/roster.json --discovery-root examples/discovery --settings examples/harness-settings.json
```

## What this checks

### `skills-doctor` (read-only)

- Leading **frontmatter** on each visible `SKILL.md` (supported subset only).
- **`name:`** matches the skill directory name.
- **`description:`** present and within the **1024-character** limit.
- **`user-invocable:`** present, boolean, and **`true`** for visible roster skills.
- **Visible roster** entries exist in the configured canonical source tree.
- **Discovery roots** expose only visible, rostered skills (no hidden-corpus leakage).
- **Symlink health** (broken links, targets outside the configured public source).
- **Disabled-skills drift** when you pass `--settings` (visible skills must not be disabled; hidden names must not appear in `disabledSkills`).

Doctor does not rewrite files by default. Use `--dry-run` for explicit read-only reporting (same as the default).

### `sync-skills`

- **Dry-run by default** — prints a plan only.
- **`--apply`** — creates or updates **symlinks** (not copies) for **visible** roster entries only.
- Reports stale or broken managed links; does not silently ignore conflicts with unrelated files.

### `audit-public-safety`

- Scans the repo for private absolute paths, copied corpus markers, obvious secrets, and other categories documented in the validation contract.

## What this intentionally does not include

This repository is a **narrow diagnostic wedge**, not a full agent platform:

- No **private skill corpus**, private workflows, private rules, or operational playbooks.
- No **memories**, secure backups, account rotation, or harness-specific private state.
- No **credentialed integrations**, hosted APIs, databases, browsers, or web UI.
- No **mission internals**, third-party API configuration files, raw transcripts, or private operational material.
- No guarantee of **legal compliance** beyond what you adopt from the [License](#license) (Apache-2.0; not a substitute for your own legal review).

If you are unsure whether content belongs in a public repo, **exclude it**.

## Private corpus stays private

**Private corpus and private operational material stay private.** This project demonstrates *patterns* for skill loading invariants using **generic** example skills under `examples/skills/`. Do not treat this repo as a mirror of any private agent-skills tree or non-public skill library. Never commit real customer data, real account identifiers, or copied private `SKILL.md` bodies into this slice.

## Feedback

If this toolkit misses a skill-loading failure mode, open an issue with a minimal redacted fixture and the command you ran. Do not include private paths, customer data, tokens, API keys, copied private `SKILL.md` bodies, or proprietary harness configuration.

## License

This project is licensed under the **Apache License 2.0**; see [`LICENSE`](LICENSE) (Copyright 2026 agent-skill-ops contributors). Package metadata in `pyproject.toml` uses the same attribution. This is **not a substitute for your own legal review**. Do not claim that license text has been vetted by counsel unless you have actually done so.

## Contributing (public slice)

- Keep runtime and tests **stdlib-only** (`dependencies = []` in `pyproject.toml`).
- Add tests for new invariants; run the Quickstart commands before opening any public PR (when you choose to publish elsewhere).
