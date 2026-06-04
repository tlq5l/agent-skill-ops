import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import unittest

from agent_skill_ops.frontmatter import (
    DESCRIPTION_MAX_LEN,
    parse_frontmatter,
    validate_parsed_for_visible_skill,
)


class TestFrontmatter(unittest.TestCase):
    def test_valid_block(self):
        text = """---
name: alpha
description: Short desc.
user-invocable: true
---

# Body
"""
        parsed = parse_frontmatter(text)
        self.assertFalse(hasattr(parsed, "kind"))
        self.assertEqual(parsed.name, "alpha")
        self.assertTrue(parsed.user_invocable)

    def test_missing_frontmatter(self):
        err = parse_frontmatter("# no frontmatter\n")
        self.assertEqual(err.kind, "missing_frontmatter")

    def test_missing_description(self):
        text = """---
name: alpha
user-invocable: true
---
"""
        err = parse_frontmatter(text)
        self.assertEqual(err.kind, "missing_description")

    def test_invalid_user_invocable_string(self):
        text = """---
name: alpha
description: ok
user-invocable: "yes"
---
"""
        err = parse_frontmatter(text)
        self.assertEqual(err.kind, "invalid_user_invocable")

    def test_name_mismatch_message(self):
        text = """---
name: wrong-name
description: ok
user-invocable: true
---
"""
        parsed = parse_frontmatter(text)
        msgs = validate_parsed_for_visible_skill(parsed, skill_dir_name="alpha-skill")
        self.assertTrue(any("name mismatch" in m for m in msgs))

    def test_description_too_long(self):
        long_desc = "x" * (DESCRIPTION_MAX_LEN + 1)
        text = f"""---
name: alpha
description: {long_desc}
user-invocable: true
---
"""
        parsed = parse_frontmatter(text)
        msgs = validate_parsed_for_visible_skill(parsed, skill_dir_name="alpha")
        self.assertTrue(any("1024" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
