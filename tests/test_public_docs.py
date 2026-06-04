"""VAL-DOCS contract checks for README and LICENSE."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
LICENSE = ROOT / "LICENSE"

PRIVATE_OR_GTM = re.compile(
    r"@[a-z0-9.-]+\.[a-z]{2,}|you@example\.com|greenapple|Terry|"
    r"7-day|demand test|concierge|\bpaid\b|\$99|\$499|CTA|sales page",
    re.I,
)


class TestPublicDocs(unittest.TestCase):
    def setUp(self) -> None:
        self.readme = README.read_text(encoding="utf-8")
        self.license = LICENSE.read_text(encoding="utf-8")

    def test_readme_exists(self):
        self.assertTrue(README.is_file())

    def test_quickstart_section_with_copy_pastable_commands(self):
        self.assertRegex(self.readme, r"(?i)##\s*Quickstart")
        for snippet in (
            "python3 -m unittest discover -s tests -v",
            "python3 scripts/skills-doctor",
            "python3 scripts/sync-skills",
            "python3 scripts/audit-public-safety",
        ):
            self.assertIn(snippet, self.readme)

    def test_what_this_checks_covers_doctor_invariants(self):
        self.assertRegex(self.readme, r"(?i)what this checks")
        for topic in (
            "frontmatter",
            "name:",
            "description",
            "1024",
            "user-invocable",
            "symlink",
            "disabled",
        ):
            self.assertIn(topic, self.readme, msg=f"missing topic: {topic}")

    def test_intentional_exclusions_section(self):
        self.assertRegex(self.readme, r"(?i)intentionally does not include")
        for item in (
            "private",
            "memories",
            "credentialed",
            "database",
            "web",
        ):
            self.assertIn(item, self.readme, msg=f"missing exclusion hint: {item}")

    def test_private_corpus_stays_private_statement(self):
        self.assertRegex(self.readme, r"(?i)private corpus")
        self.assertRegex(self.readme, r"(?i)stays private|stay private")

    def test_no_gtm_or_sales_strategy_in_readme(self):
        self.assertIsNone(PRIVATE_OR_GTM.search(self.readme))

    def test_feedback_section_without_private_contacts(self):
        self.assertRegex(self.readme, r"(?i)feedback")
        self.assertRegex(self.readme, r"(?i)minimal redacted fixture")
        self.assertIsNone(PRIVATE_OR_GTM.search(self.readme))

    def test_dry_run_uses_tmp_apply_uses_in_repo_discovery(self):
        self.assertIn("/tmp/agent-skill-ops-discovery", self.readme)
        self.assertIn("examples/discovery", self.readme)
        self.assertRegex(self.readme, r"(?i)dry-run")

    def test_license_apache_attribution_no_overclaim(self):
        self.assertTrue(LICENSE.is_file())
        self.assertIn("Apache License", self.license)
        self.assertIn("Version 2.0", self.license)
        self.assertIn("2026 agent-skill-ops contributors", self.license)
        self.assertNotIn("[yyyy]", self.license)
        self.assertNotIn("[name of copyright owner]", self.license)
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("agent-skill-ops contributors", pyproject)
        self.assertNotRegex(
            self.readme,
            r"(?i)legal review complete|reviewed by counsel|attorney-approved",
        )
        self.assertRegex(
            self.readme,
            r"(?i)not a substitute for your own legal review",
        )
        self.assertRegex(
            self.readme,
            r"(?i)2026 agent-skill-ops contributors",
        )


if __name__ == "__main__":
    unittest.main()
