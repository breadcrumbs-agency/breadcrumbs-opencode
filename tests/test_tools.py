"""The model-facing verbs of OpenCode (tools.py): find and zoom over the memory of the project of a folder, the scope line,
and the launcher (bin/bc-python) that every command of the plugin runs. Run with breadcrumbs-common and this folder on
PYTHONPATH."""
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from breadcrumbs_opencode import tools

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Verbs(unittest.TestCase):
    def setUp(self):
        parent = os.path.join(os.path.expanduser("~"), ".cache", "breadcrumbs-opencode-tests")  # not a system temp folder
        os.makedirs(parent, exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(tmp.cleanup)
        self.base = os.path.join(tmp.name, "opencode", "breadcrumbs")
        os.makedirs(self.base)
        self.home = os.path.expanduser("~")
        env = mock.patch.dict(os.environ, {"BREADCRUMBS_HOME": self.base, "BREADCRUMBS_SCOPE": "auto"})
        env.start()
        self.addCleanup(env.stop)

    def test_the_home_folder_uses_the_default_memory(self):
        s = tools.stores(self.home)
        self.assertFalse(s.here)
        self.assertEqual(os.path.realpath(s.base), os.path.realpath(self.base))

    def test_a_folder_uses_its_own_scope_store(self):
        project = os.path.join(os.path.dirname(self.base), "kettle")
        os.makedirs(os.path.join(project, ".git"))
        s = tools.stores(project)
        self.assertTrue(s.here)
        self.assertIn(os.sep + "scopes" + os.sep, s.local)

    def test_find_on_an_empty_memory_answers_no_groups(self):
        out = tools.call("find", {"q": "green tea"}, self.home)
        self.assertEqual(out, {"ok": True, "result": {"q": "green tea", "groups": []}})

    def test_zoom_of_an_unknown_id_is_a_refusal_not_an_exception(self):
        out = tools.call("zoom", {"id": "deadbeef", "level": 1.0}, self.home)
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"], "not_found")

    def test_an_unknown_verb_is_a_refusal(self):
        self.assertEqual(tools.call("write", {}, self.home)["error"], "unknown_verb")

    def test_the_scope_line_names_the_default_memory_of_the_home_folder(self):
        text = tools.scope_text(self.home)
        self.assertIn("memory: default memory", text)

    def test_the_command_line_prints_json(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = tools.main(["call", "find", json.dumps({"q": "tea"}), self.home])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(buf.getvalue())["ok"])


class Launcher(unittest.TestCase):
    def test_bc_python_runs_python_with_the_layers_and_the_default_memory(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("BREADCRUMBS_HOME", None)
        env["XDG_DATA_HOME"] = "/nonexistent-xdg"
        script = "import os,breadcrumbs;print(os.environ['BREADCRUMBS_HOME']);print(breadcrumbs.__file__)"
        out = subprocess.run(["sh", os.path.join(ROOT, "bin", "bc-python"), "-c", script], env=env,
                             capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        home, module = out.stdout.splitlines()
        self.assertEqual(home, "/nonexistent-xdg/opencode/breadcrumbs")
        self.assertTrue(module.endswith("breadcrumbs/__init__.py"), module)

    def test_bc_python_honours_a_given_memory(self):
        env = dict(os.environ, BREADCRUMBS_HOME="/tmp/x/breadcrumbs")
        out = subprocess.run(["sh", os.path.join(ROOT, "bin", "bc-python"), "-c",
                              "import os;print(os.environ['BREADCRUMBS_HOME'])"], env=env, capture_output=True,
                             text=True, timeout=60)
        self.assertEqual(out.stdout.strip(), "/tmp/x/breadcrumbs")


if __name__ == "__main__":
    unittest.main()
