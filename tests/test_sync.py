"""`sync` for OpenCode: a session lands in the memory of the project where it ran, with a state.db and the ports for the
viewers. The fixture is a small SQLite file with the tables of OpenCode and invented text. Run with breadcrumbs-common
and this folder on PYTHONPATH."""
import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock

from breadcrumbs import ports, scope, statedb, sync, usage

from breadcrumbs_opencode import adapter


def step(inp, read, write):
    return {"type": "step-finish", "tokens": {"input": inp, "output": 5, "reasoning": 0,
                                              "cache": {"read": read, "write": write}}}


class Sync(unittest.TestCase):
    def setUp(self):
        ports.load()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = os.path.realpath(tmp.name)
        self.base = os.path.join(self.home, "memory")
        self.repo = os.path.join(self.home, "work", "kettle")
        os.makedirs(os.path.join(self.repo, ".git"))
        self.db = os.path.join(self.home, "opencode.db")
        con = sqlite3.connect(self.db)
        con.executescript("CREATE TABLE session (id TEXT, title TEXT, directory TEXT, parent_id TEXT, time_created INTEGER);"
                          "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);"
                          "CREATE TABLE part (id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);")
        for n, (name, cwd, text) in enumerate((("kettle", self.repo, "how long to steep green tea?"),
                                               ("stray", os.path.join(self.home, "nowhere"), "an invented question"))):
            sid = "ses_" + name
            con.execute("INSERT INTO session VALUES (?, ?, ?, NULL, ?)", (sid, name, cwd, 1767323045000 + n))
            con.execute("INSERT INTO message VALUES (?, ?, 1, ?)", ("u" + name, sid, json.dumps({"role": "user"})))
            con.execute("INSERT INTO message VALUES (?, ?, 2, ?)", ("a" + name, sid, json.dumps(
                {"role": "assistant", "modelID": "demo-model", "providerID": "demo"})))
            for pid, mid, data in (("p1" + name, "u" + name, {"type": "text", "text": text}),
                                   ("p2" + name, "a" + name, {"type": "text", "text": "Two minutes."}),
                                   ("p3" + name, "a" + name, step(40, 700, 20))):
                con.execute("INSERT INTO part VALUES (?, ?, ?, 1767323045000, ?)", (pid, mid, sid, json.dumps(data)))
        con.commit()
        con.close()

    def sync(self):
        return sync.sync("opencode", self.db, self.base, exclude=(), home=self.home)

    def test_a_session_goes_to_the_memory_of_the_repository_where_it_ran(self):
        out = self.sync()
        by = {s["scope"] or "default": s for s in out["stores"]}
        self.assertEqual((out["sessions"], out["new"]), (2, 2))
        self.assertEqual(by[scope.short(self.repo)]["sessions"], 1)
        self.assertEqual(by["default"]["sessions"], 1)  # its folder is gone and nothing above it is a project
        rows = statedb.read(statedb.locate(scope.store_home(self.base, self.repo)), lambda c: c.execute(
            "SELECT id, git_repo_root, created_source FROM sessions").fetchall())
        self.assertEqual(rows, [("ses_kettle", self.repo, "opencode")])

    def test_the_usage_of_a_session_lands_beside_it_with_its_prompt_tokens(self):
        out = self.sync()
        self.assertEqual(out["usage"], {"requests": 2, "added": 2})
        store = scope.store_home(self.base, self.repo)
        with open(os.path.join(store, usage.LOG_NAME), encoding="utf-8") as f:
            lines = f.read().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("model=demo-model", lines[0])
        self.assertEqual(self.sync()["usage"]["added"], 0)  # run again: nothing added

    def test_the_ports_place_a_folder_as_sync_does(self):
        self.assertEqual(ports.get("profile")("/anywhere"), adapter.NAME)
        self.assertIsNone(ports.get("codebase")(os.path.join(self.repo, "src")))  # the test repository is in a temporary folder
        with mock.patch.object(sync, "no_project", return_value=[]):
            self.assertEqual(ports.get("codebase")(os.path.join(self.repo, "src")), self.repo)
        self.assertIsNone(ports.get("codebase")(os.path.expanduser("~")))  # the home folder: the default memory
        self.assertIs(ports.get("state"), statedb.read)


if __name__ == "__main__":
    unittest.main()
