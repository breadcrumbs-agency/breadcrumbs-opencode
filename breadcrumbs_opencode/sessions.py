"""The sessions of OpenCode as a source of the ingest (`python -m breadcrumbs ingest opencode [PATH]`).

OpenCode keeps its sessions in one SQLite file, $XDG_DATA_HOME/opencode/opencode.db (default ~/.local/share/opencode/
opencode.db). This reads it read-only. The layout is the one of the tables in the source of OpenCode v1.18.30,
packages/core/src/session/sql.ts (the types of the JSON in packages/schema/src/v1/session.ts):

    session   id, title, directory, parent_id, time_created
    message   id, session_id, time_created, data (JSON: role "user" or "assistant")
    part      id, message_id, time_created, data (JSON: type "text" (text, synthetic, ignored) and "tool" (callID,
              tool, state: status, input, output or error))

A user or assistant text part is a turn. A tool part is a call of the assistant; with the status "completed" its output
is the tool row, with "error" its error text. Every other part type (reasoning, step-start, step-finish, file, patch,
snapshot, subtask, agent, retry, compaction), the text parts that are synthetic or ignored, and the older JSON files
under storage/ (before OpenCode kept a database) are skipped. The session meta keeps cwd (the directory) and the parent
session. A message or part whose data is not JSON is skipped and counted.
"""
import json
import os
import pathlib
import sqlite3

from breadcrumbs.transcript import Rows, meta

DEFAULT = os.path.join("opencode", "opencode.db")  # under $XDG_DATA_HOME
ROWS = ("SELECT m.data, p.time_created, p.data FROM message m LEFT JOIN part p ON p.message_id = m.id"
        " WHERE m.session_id = ? ORDER BY m.time_created, m.id, p.id")


def session(con, sid, title, where, parent):
    """(id, title, meta, rows) of one session of the database."""
    rows, skipped = Rows(), 0
    for message, made, part in con.execute(ROWS, (sid,)).fetchall():
        try:
            role, part = json.loads(message).get("role"), part and json.loads(part)
        except (ValueError, AttributeError):
            skipped += 1
            continue
        ts = int((made or 0) / 1000)  # OpenCode counts milliseconds
        if not isinstance(part, dict) or role not in ("user", "assistant"):
            continue
        if part.get("type") == "text" and not (part.get("synthetic") or part.get("ignored")):
            rows.say(role, part.get("text"), ts)
        elif part.get("type") == "tool" and isinstance(part.get("state"), dict):
            state, call = part["state"], part.get("callID")
            rows.call(call, part.get("tool"), state.get("input"), ts)
            if state.get("status") in ("completed", "error"):
                rows.result(call, state.get("output") or state.get("error"), ts)
    return sid, title, meta(skipped=skipped, cwd=where, parent_session_id=parent), rows.rows


def sessions(path=None):
    """The source of the harness opencode: the sessions of the database at `path` (default: the database of
    OpenCode), oldest first, each (id, title, meta, rows). The database closes when the iterator ends."""
    path = path or os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), DEFAULT)
    if not os.path.isfile(path):
        raise SystemExit("breadcrumbs: no OpenCode database at %s" % path)
    con = sqlite3.connect(pathlib.Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        for found in con.execute("SELECT id, title, directory, parent_id FROM session ORDER BY time_created, id").fetchall():
            yield session(con, *found)
    finally:
        con.close()
