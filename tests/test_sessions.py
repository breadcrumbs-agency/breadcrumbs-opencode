"""The sessions of OpenCode as a source of the ingest. The fixture is a small SQLite file with the tables of OpenCode
(session, message, part) and invented text. Run with breadcrumbs-common and this folder on PYTHONPATH."""
import json
import os
import sqlite3
import unittest

from breadcrumbs import harness_case, ports


def tool(state):
    return {"type": "tool", "callID": "c1", "tool": "bash", "state": state}


def step(inp, out, rsn, read, write):  # a step-finish part, made-up counts (input: without the cache, as OpenCode keeps it)
    return {"type": "step-finish", "reason": "stop", "cost": 0,
            "tokens": {"input": inp, "output": out, "reasoning": rsn, "cache": {"read": read, "write": write}}}


class Sessions(harness_case.SourceCase):
    KEY = "opencode"

    def fixture(self, folder):
        path = os.path.join(folder, "opencode.db")
        db = sqlite3.connect(path)
        db.executescript("CREATE TABLE session (id TEXT, title TEXT, directory TEXT, parent_id TEXT, time_created INTEGER);"
                         "CREATE TABLE message (id TEXT, session_id TEXT, time_created INTEGER, data TEXT);"
                         "CREATE TABLE part (id TEXT, message_id TEXT, session_id TEXT, time_created INTEGER, data TEXT);")
        db.execute("INSERT INTO session VALUES ('ses_1', 'Boil an egg', '/work/demo', 'ses_0', 1767323045000)")
        db.executemany("INSERT INTO message VALUES (?, 'ses_1', ?, ?)", [
            ("msg_1", 1, json.dumps({"role": "user"})), ("msg_3", 3, "{broken"),
            ("msg_2", 2, json.dumps({"role": "assistant", "modelID": "demo-model", "providerID": "demo",
                                     "tokens": {"input": 1, "output": 1, "reasoning": 0, "cache": {"read": 0, "write": 0}}}))])
        db.executemany("INSERT INTO part VALUES (?, ?, 'ses_1', 1767323045000, ?)", [
            ("prt_1", "msg_1", json.dumps({"type": "text", "text": "how long to boil an egg?"})),
            ("prt_2", "msg_1", json.dumps({"type": "text", "text": "an injected note", "synthetic": True})),
            ("prt_3", "msg_2", json.dumps({"type": "reasoning", "text": "hmm"})),
            ("prt_4", "msg_2", json.dumps({"type": "text", "text": "Let me look at the clock."})),
            ("prt_5", "msg_2", json.dumps(tool({"status": "completed", "input": {"command": "date"}, "output": "Fri 03:04"}))),
            ("prt_6", "msg_2", json.dumps({"type": "text", "text": "About ten minutes."})),
            ("prt_8", "msg_2", json.dumps(step(40, 5, 2, 0, 700))),  # the step of each request: two requests
            ("prt_9", "msg_2", json.dumps(step(30, 4, 0, 700, 20))),
            ("prt_99", "msg_2", json.dumps(step(20_000, 4, 0, 90_000, 500))),  # a request over 100,000 prompt tokens
            ("prt_7", "msg_3", json.dumps({"type": "text", "text": "never read"}))])
        db.commit()
        db.close()
        return path

    def test_a_fixture_becomes_turns_and_tool_rows(self):
        (sid, _title, _meta, rows), = self.sessions()
        self.assertEqual(sid, "ses_1")
        self.assertEqual([(r["role"], r["content"]) for r in rows], [
            ("user", "how long to boil an egg?"), ("assistant", "Let me look at the clock."), ("tool", "Fri 03:04"),
            ("assistant", "About ten minutes.")])
        self.assertEqual(rows[1]["tool_calls"], [{"id": "c1", "function": {"name": "bash", "arguments": {"command": "date"}}}])
        self.assertEqual((rows[2]["tool_name"], rows[2]["tool_call_id"]), ("bash", "c1"))
        self.assertEqual({r["ts"] for r in rows}, {1767323045})  # OpenCode counts milliseconds

    def test_the_session_keeps_its_title_folder_and_parent(self):
        (_sid, title, meta, _rows), = self.sessions()
        self.assertEqual((title, meta["cwd"], meta["parent_session_id"]), ("Boil an egg", "/work/demo", "ses_0"))

    def test_each_step_is_a_request_with_the_model_of_its_message(self):
        got = list(ports.harnesses()[self.KEY]["usage"](self.path))
        self.assertEqual([(r["req"], r["sess"], r["model"], r["prov"], r["src"], r["ts"]) for r in got],
                         [("prt_8", "ses_1", "demo-model", "demo", "opencode", 1767323045),
                          ("prt_9", "ses_1", "demo-model", "demo", "opencode", 1767323045),
                          ("prt_99", "ses_1", "demo-model", "demo", "opencode", 1767323045)])
        self.assertEqual([(r["in"], r["cr"], r["cw"], r["out"], r["rsn"], r["prompt"]) for r in got],
                         [(40, 0, 700, 5, 2, 740), (30, 700, 20, 4, 0, 750),
                          (20_000, 90_000, 500, 4, 0, 110_500)])

    def test_the_prompt_counts_the_cache_so_a_request_over_100000_shows(self):
        # Haiku 5.5 steps up at 100,000 prompt tokens, and cache reads count toward them (context-bench README)
        got = list(ports.harnesses()[self.KEY]["usage"](self.path))
        self.assertEqual([r["req"] for r in got if r["prompt"] > 100_000], ["prt_99"])

    def test_a_broken_row_is_skipped_and_counted(self):
        (_sid, _title, meta, rows), = self.sessions()
        self.assertEqual((meta["skipped"], len(rows)), ("1", 4))


@unittest.skipUnless(os.path.isfile(os.path.expanduser("~/.local/share/opencode/opencode.db")), "no OpenCode database here")
class RealDatabase(unittest.TestCase):
    """The database of this machine, read-only: whatever it holds, every record is whole."""

    def test_every_request_has_a_model_and_a_prompt_that_is_the_sum_of_its_inputs(self):
        for r in ports.harnesses()["opencode"]["usage"](None):
            self.assertTrue(r["model"], r["req"])
            self.assertEqual(r["prompt"], r["in"] + r["cr"] + r["cw"], r["req"])
            self.assertEqual(r["src"], "opencode")

    def test_every_session_has_an_id_and_rows(self):
        for sid, _title, meta, rows in ports.harnesses()["opencode"]["source"](None):
            self.assertTrue(sid)
            self.assertIn("cwd", meta)


if __name__ == "__main__":
    unittest.main()
