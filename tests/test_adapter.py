"""The adapter of breadcrumbs_opencode: it gives the entry 'opencode' of the harness table of core.py (identify and setup).
Run with breadcrumbs-common and this folder on PYTHONPATH."""
import unittest

from breadcrumbs import harness_case


class Adapter(harness_case.HarnessCase):
    KEY, LABEL, LAYER = "opencode", "OpenCode", "opencode"
    NAMES = ['opencode']
    SETUP = '''# opencode.json
{
  "mcp": {
    "breadcrumbs": {
      "type": "local",
      "command": [
        "env",
        "PYTHONPATH=/x",
        "python",
        "-m",
        "breadcrumbs",
        "core",
        "mcp"
      ],
      "enabled": true
    }
  }
}'''


if __name__ == "__main__":
    unittest.main()
