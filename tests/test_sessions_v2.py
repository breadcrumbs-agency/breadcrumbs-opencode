"""The sessions of the OpenCode 2 layout (session_v2, session_message): the rows of a session, its usage per assistant
message, and that the layout is chosen by its tables. The fixture is a small SQLite file with the key names of the
OpenCode 2 store and invented text. Run with breadcrumbs-common and this folder on PYTHONPATH."""
import json
import os
import sqlite3
import tempfile
import unittest

from breadcrumbs import ports
from breadcrumbs_opencode import sessions

V2_SCHEMA = (
    "CREATE TABLE session_v2 (id TEXT PRIMARY KEY, project_id TEXT, parent_id TEXT, directory TEXT NOT NULL,"
    " title TEXT, time_created INTEGER NOT NULL);"
    "CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, type TEXT NOT NULL,"
    " seq INTEGER NOT NULL, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL);"
    "CREATE TABLE session_part (message_id TEXT NOT NULL, session_id TEXT NOT NULL, ordinal INTEGER NOT NULL,"
    " type TEXT NOT NULL, call_id TEXT, time_created INTEGER NOT NULL, time_updated INTEGER NOT NULL, data TEXT NOT NULL);"
)


class SessionsV2(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = os.path.join(tmp.name, "opencode.db")
        con = sqlite3.connect(self.path)
        con.executescript(V2_SCHEMA)
        con.execute("INSERT INTO session_v2 VALUES ('ses_v2', 'prj', 'ses_parent', '/work/demo', 'Boil an egg', 1767323045000)")
        msgs = [
            ("m1", "user", 1, 1767323045000, {"text": "how long to boil an egg?", "time": {"created": 1767323045000}}),
            ("m2", "model-switched", 2, 1767323046000, {"model": {"id": "x"}, "previous": {"id": "y"}}),
            ("m3", "assistant", 3, 1767323047000, {
                "agent": "build",
                "content": [
                    {"type": "reasoning", "text": "hmm", "time": {}},
                    {"type": "text", "text": "Let me look at the clock."},
                    {"type": "tool", "id": "call_1", "name": "bash", "executed": True,
                     "state": {"status": "completed", "input": {"command": "date"},
                               "content": [{"type": "text", "text": "Fri 03:04"}], "metadata": {}},
                     "time": {"created": 1767323047000, "ran": 1767323047100, "completed": 1767323047200}},
                ],
                "model": {"id": "demo-model", "providerID": "demo", "variant": None},
                "tokens": {"input": 40, "output": 5, "reasoning": 2, "cache": {"read": 700, "write": 20}},
                "cost": 0, "finish": "tool-calls", "time": {"created": 1767323047000, "completed": 1767323047300}}),
            ("m4", "assistant", 4, 1767323048000, {
                "agent": "build", "content": [{"type": "text", "text": "About ten minutes."}],
                "model": {"id": "demo-model", "providerID": "demo"},
                "tokens": {"input": 30, "output": 4, "reasoning": 0, "cache": {"read": 700, "write": 0}},
                "finish": "stop", "time": {"created": 1767323048000}}),
            ("m5", "idle", 5, 1767323049000, {"outcome": "done", "time": {"created": 1767323049000}}),
        ]
        for mid, mtype, seq, made, data in msgs:
            con.execute("INSERT INTO session_message VALUES (?, 'ses_v2', ?, ?, ?, ?, ?)",
                        (mid, mtype, seq, made, made, json.dumps(data)))
        con.commit()
        con.close()

    def test_the_layout_is_chosen_by_its_tables(self):
        with sessions.database(self.path) as con:
            self.assertTrue(sessions.is_v2(con))

    def test_a_session_becomes_its_turns_and_its_tool_rows(self):
        (sid, title, meta, rows), = list(sessions.sessions(self.path))
        self.assertEqual((sid, title), ("ses_v2", "Boil an egg"))
        self.assertEqual((meta["cwd"], meta["parent_session_id"]), ("/work/demo", "ses_parent"))
        self.assertEqual([(r["role"], r["content"]) for r in rows], [
            ("user", "how long to boil an egg?"), ("assistant", "Let me look at the clock."),
            ("tool", "Fri 03:04"), ("assistant", "About ten minutes.")])
        self.assertEqual(rows[1]["tool_calls"], [{"id": "call_1", "function": {"name": "bash", "arguments": {"command": "date"}}}])
        self.assertEqual((rows[2]["tool_name"], rows[2]["tool_call_id"]), ("bash", "call_1"))
        self.assertEqual({r["ts"] for r in rows}, {1767323045, 1767323047, 1767323048}, "OpenCode counts milliseconds")

    def test_each_assistant_message_with_tokens_is_one_request(self):
        ports.load()
        got = list(sessions.usage(self.path))
        self.assertEqual([(r["req"], r["sess"], r["model"], r["prov"], r["src"]) for r in got],
                         [("m3", "ses_v2", "demo-model", "demo", "opencode"), ("m4", "ses_v2", "demo-model", "demo", "opencode")])
        self.assertEqual((got[0]["in"], got[0]["cr"], got[0]["cw"], got[0]["out"], got[0]["rsn"]), (40, 700, 20, 5, 2))


if __name__ == "__main__":
    unittest.main()
