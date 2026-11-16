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

The usage of a model request (usage()): OpenCode writes a part of type "step-finish" at the end of each step, one
request to the model, with its tokens {input, output, reasoning, cache: {read, write}} (packages/opencode/src/session/
processor.ts; session.ts getUsage()). Its input is already the input that no cache held: getUsage() takes the cache read
and write out of the input count of the AI SDK. (The tokens of the assistant message are those of its last step only, so
they are not read.) The model and provider are modelID and providerID of the assistant message; the id is the id of the
part.
"""
import contextlib
import json
import os
import pathlib
import sqlite3

from breadcrumbs import usage as usage_record
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


@contextlib.contextmanager
def database(path=None):
    """A read-only connection to the database at `path` (default: the database of OpenCode); it closes after the block."""
    path = path or os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), DEFAULT)
    if not os.path.isfile(path):
        raise SystemExit("breadcrumbs: no OpenCode database at %s" % path)
    con = sqlite3.connect(pathlib.Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        yield con
    finally:
        con.close()


def is_v2(con):
    """True for the layout of OpenCode 2 (its session_v2, session_message and session_part tables)."""
    return con.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'session_v2'").fetchone() is not None


V2_SESSIONS = "SELECT id, title, directory, parent_id FROM session_v2 ORDER BY time_created, id"
V2_MESSAGES = ("SELECT id, type, time_created, data FROM session_message WHERE session_id = ?"
               " ORDER BY seq, time_created, id")
V2_USAGE = "SELECT m.id, m.session_id, m.time_created, m.data FROM session_message m WHERE m.type = 'assistant' ORDER BY m.time_created, m.id"


def output_text(content):
    """The text of a tool's output in the state of OpenCode 2: a text, or a list of parts with text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p["text"] for p in content if isinstance(p, dict) and isinstance(p.get("text"), str))
    return ""


def session_v2(con, sid, title, where, parent):
    """(id, title, meta, rows) of one session of the OpenCode 2 layout. A user message is a user row; an assistant
    message holds its text parts (a text row), its reasoning (skipped) and its tool calls (a call, then its result
    when the call is completed or failed). Messages of another type (idle, model-switched) are skipped."""
    rows, skipped = Rows(), 0
    for mid, mtype, made, data in con.execute(V2_MESSAGES, (sid,)).fetchall():
        ts = int((made or 0) / 1000)  # OpenCode counts milliseconds
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            skipped += 1
            continue
        if not isinstance(data, dict):
            continue
        if mtype == "user":
            rows.say("user", data.get("text"), ts)
        elif mtype == "assistant":
            for item in data.get("content") or []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    rows.say("assistant", item.get("text"), ts)
                elif item.get("type") == "tool" and isinstance(item.get("state"), dict):
                    state, call = item["state"], item.get("id")
                    rows.call(call, item.get("name"), state.get("input"), ts)
                    if state.get("status") in ("completed", "error"):
                        rows.result(call, output_text(state.get("content")) or str(state.get("error") or ""), ts)
    return sid, title, meta(skipped=skipped, cwd=where, parent_session_id=parent), rows.rows


def usage_v2(con):
    """The usage of the OpenCode 2 layout: one record for each assistant message that counted its tokens."""
    for mid, sid, made, data in con.execute(V2_USAGE).fetchall():
        try:
            data = json.loads(data)
            tokens = data["tokens"]
            cache, model = tokens.get("cache") or {}, data.get("model") or {}
            model_id, prov = model.get("id"), model.get("providerID")
            read, write = cache.get("read"), cache.get("write")
        except (ValueError, AttributeError, KeyError, TypeError):
            continue
        yield usage_record.record("opencode", sid, mid, int((made or 0) / 1000), model_id, prov, tokens.get("input"),
                                  read, write, tokens.get("output"), tokens.get("reasoning"))


def sessions(path=None):
    """The source of the harness opencode: the sessions of the database at `path` (default: the database of
    OpenCode), oldest first, each (id, title, meta, rows). The database closes when the iterator ends. The layout is
    read from the tables: session_v2 (OpenCode 2) or session (OpenCode 1)."""
    with database(path) as con:
        if is_v2(con):
            for found in con.execute(V2_SESSIONS).fetchall():
                yield session_v2(con, *found)
            return
        for found in con.execute("SELECT id, title, directory, parent_id FROM session ORDER BY time_created, id").fetchall():
            yield session(con, *found)


STEPS = ("SELECT p.id, p.session_id, p.time_created, m.data, p.data FROM part p JOIN message m ON m.id = p.message_id"
         " WHERE p.data LIKE '%step-finish%' ORDER BY p.time_created, p.id")


def usage(path=None):
    """The usage of the harness opencode: a usage record (breadcrumbs/usage.py record()) for each step-finish part of the
    database, oldest first (OpenCode 2: for each assistant message with its tokens). A part or message whose data is
    not JSON is skipped."""
    with database(path) as con:
        if is_v2(con):
            yield from usage_v2(con)
            return
        for pid, sid, made, message, part in con.execute(STEPS).fetchall():
            try:
                message, part = json.loads(message), json.loads(part)
                tokens = part["tokens"] if part.get("type") == "step-finish" else None
                cache, model, prov = tokens.get("cache") or {}, message.get("modelID"), message.get("providerID")
                read, write = cache.get("read"), cache.get("write")
            except (ValueError, AttributeError, KeyError, TypeError):
                continue
            yield usage_record.record("opencode", sid, pid, int((made or 0) / 1000), model, prov, tokens.get("input"), read,
                                      write, tokens.get("output"), tokens.get("reasoning"))
