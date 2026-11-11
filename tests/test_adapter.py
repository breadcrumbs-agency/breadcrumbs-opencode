"""The adapter of breadcrumbs_opencode: it gives the entry 'opencode' of the harness table of core.py (identify and setup).
Run with breadcrumbs-common and this folder on PYTHONPATH."""
import json
import unittest

from breadcrumbs import core, ports


class Adapter(unittest.TestCase):
    CMD = ["env", "PYTHONPATH=/x", "python", "-m", "breadcrumbs", "core", "mcp"]

    def setUp(self):
        self.entry = ports.harnesses()['opencode']

    def test_the_package_gives_one_entry_to_the_table(self):
        self.assertEqual(self.entry["label"], 'OpenCode')
        self.assertEqual(ports.layer("opencode", __file__), False)  # the adapter announced its layer once

    def test_identify_tells_the_client_names_apart(self):
        for name in ['opencode']:
            self.assertEqual(core.identify(name), 'opencode', name)
        for name in ("curl", "", None):
            self.assertEqual(core.identify(name), "unknown", name)

    def test_the_table_lists_it_in_its_place(self):
        self.assertIn('opencode', core.harnesses())

    def test_setup_is_the_json_entry_for_opencode_json(self):
        text = self.entry["setup"](self.CMD)
        head, _, body = text.partition("\n")
        self.assertEqual(head, "# opencode.json")
        self.assertEqual(json.loads(body), {"mcp": {"breadcrumbs": {"type": "local", "command": self.CMD, "enabled": True}}})

    def test_health_counts_the_calls_of_this_harness(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            c = core.Core(core.Stores(root=tmp))
            try:
                c.call("stores", harness='opencode')
                self.assertEqual(c.call("health")["calls"], {'opencode': 1, "unknown": 1})
            finally:
                c.close()


if __name__ == "__main__":
    unittest.main()
