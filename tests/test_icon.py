"""The icon that OpenCode gives to the harness table: the explorer draws it beside the brand. Run with breadcrumbs-common
and this folder on PYTHONPATH."""
import base64
import os
import struct
import tomllib
import unittest

from breadcrumbs import ports


class OpenCodeIcon(unittest.TestCase):
    def test_opencode_gives_a_small_png_icon(self):
        ports.load()
        entry = ports.harnesses()["opencode"]
        head, _, body = entry["icon"].partition(",")
        self.assertEqual(head, "data:image/png;base64")
        png = base64.b64decode(body)
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", png[16:24]), (96, 96))
        self.assertLess(len(png), 20_000, "it travels in the answer of a route, so it stays small")

    def test_the_package_lists_the_icon_as_data(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "pyproject.toml"), "rb") as f:
            data = tomllib.load(f)
        self.assertIn("icon.png", data["tool"]["setuptools"]["package-data"]["breadcrumbs_opencode"])


if __name__ == "__main__":
    unittest.main()
