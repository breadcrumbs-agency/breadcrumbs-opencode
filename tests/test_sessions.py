"""The sessions of OpenCode as a source of the ingest. The fixture is a small SQLite file with the tables of OpenCode
(session, message, part) and invented text. Run with breadcrumbs-common and this folder on PYTHONPATH."""
import json
import os
import sqlite3
import unittest

from breadcrumbs import harness_case


def tool(state):
    return {"type": "tool", "callID": "c1", "tool": "bash", "state": state}


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
            ("msg_1", 1, json.dumps({"role": "user"})), ("msg_2", 2, json.dumps({"role": "assistant"})), ("msg_3", 3, "{broken")])
        db.executemany("INSERT INTO part VALUES (?, ?, 'ses_1', 1767323045000, ?)", [
            ("prt_1", "msg_1", json.dumps({"type": "text", "text": "how long to boil an egg?"})),
            ("prt_2", "msg_1", json.dumps({"type": "text", "text": "an injected note", "synthetic": True})),
            ("prt_3", "msg_2", json.dumps({"type": "reasoning", "text": "hmm"})),
            ("prt_4", "msg_2", json.dumps({"type": "text", "text": "Let me look at the clock."})),
            ("prt_5", "msg_2", json.dumps(tool({"status": "completed", "input": {"command": "date"}, "output": "Fri 03:04"}))),
            ("prt_6", "msg_2", json.dumps({"type": "text", "text": "About ten minutes."})),
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

    def test_a_broken_row_is_skipped_and_counted(self):
        (_sid, _title, meta, rows), = self.sessions()
        self.assertEqual((meta["skipped"], len(rows)), ("1", 4))


if __name__ == "__main__":
    unittest.main()
