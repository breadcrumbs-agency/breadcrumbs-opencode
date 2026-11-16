"""ACE for OpenCode: the breadcrumb layer of breadcrumbs-common over the requests of an OpenCode session.

A bridge, not a server. The plugin (plugin/index.js) starts `bin/bc-python -m breadcrumbs_opencode.ace` for each
request, writes one JSON object on stdin and reads one JSON object on stdout:

    {"op": "select", "sid": ID, "cwd": FOLDER, "model": NAME, "messages": [openai-shaped messages]}
        -> {"messages": [{"i": N}, {"new": MESSAGE}, ...]}  or  {"messages": null} when the request passes as it is
           i: the N-th message of the request (the engine kept it byte for byte); new: a message the engine made
           (the layer, merged into the first kept user message).
    {"op": "layer", "sid": ID, "cwd": FOLDER, "model": NAME, "messages": [...]}
        -> {"layer": TEXT}  the crumb layer of the whole transcript, "" when nothing folds (the compaction summary)

The engine (breadcrumbs.ace_core.Engine) decides and writes <root>/ace.log, one line per request, in the format of the
Hermes plugin. root is the memory of the project of cwd (breadcrumbs.sync.where), the default memory when the folder
is no project. The model's own token counts are not given to the bridge yet, so the engine sizes requests in bytes
with its default ratio until a count is logged (see ace_core.Engine.counted).

Run with breadcrumbs-common and this folder on PYTHONPATH.
"""
import json
import os
import sys

from breadcrumbs import costs, sync
from breadcrumbs.ace_core import Engine, logged_counts, logged_ratchet
from breadcrumbs.index import Index
from breadcrumbs.store import Store
from breadcrumbs.zoom import Zoom

WINDOW = 200_000  # the context window when no profile of costs.py names the model


class Ace(Engine):
    """The engine for one OpenCode session, with the memory root given by the caller (as the Codex provider does)."""

    def __init__(self, root, sid, model, window):
        super().__init__()
        self.start_session(sid)
        self.root = root
        os.makedirs(root, exist_ok=True)
        self.store = Store(os.path.join(root, "store"))
        path = os.path.join(root, "index.db")
        self._index = Index(path, readonly=True) if os.path.exists(path) else None
        ix = self._index
        self.zoom = Zoom(self.store, summaries=ix and ix.summary_of, cues=ix and ix.signature, words=ix and ix.tiers)
        self.use_model(model, window)  # the dials of this model in the config chain of root
        counts = logged_counts(root, self.session, self._target())  # a new object takes the counts of its session
        if counts:
            self.base, self.tpb, self.ratio = counts
        state = logged_ratchet(root, self.session)
        if state:
            self.ratchet, self.gain = max(1.0, state[0] / self.target_tokens), state[1]

    def close_all(self):
        for obj in (self.store, self._index):
            if obj is not None:  # not `obj and ...`: a store with no crumbs may be falsy
                obj.close()
        self.store = self._index = None


def window_of(model, base):
    """The context window of the model (its profile in costs.py), else WINDOW."""
    try:
        return costs.context_window(model, base) or WINDOW
    except Exception:
        return WINDOW


def select(engine, messages):
    """The engine's choice for a request: a list of {"i": n} | {"new": message}, or None when it passes as it is."""
    position = {id(m): n for n, m in enumerate(messages)}
    out = engine.select_context(messages)
    if out is None:
        return None
    return [{"i": position[id(m)]} if id(m) in position else {"new": m} for m in out]


def layer(engine, messages):
    """The crumb layer of the transcript: the text of engine.layer after the fold, "" when nothing folds."""
    engine.compress(messages, force=True)
    return engine.layer or ""


def handle(req):
    root = home(req.get("cwd"))
    engine = Ace(root, str(req.get("sid") or ""), str(req.get("model") or ""), window_of(req.get("model"), root_base()))
    try:
        messages = req.get("messages") or []
        if req.get("op") == "layer":
            return {"layer": layer(engine, messages)}
        return {"messages": select(engine, messages)}
    finally:
        engine.close_all()


def root_base():
    """The base memory of OpenCode: BREADCRUMBS_HOME (its last folder is `breadcrumbs`), else the default in cli."""
    from breadcrumbs.cli import default_home
    return default_home()


def home(cwd):
    """The memory folder (the store, index.db) of the project of cwd under the base; the base when it is no project."""
    return sync.where(root_base(), cwd or os.getcwd())


def main(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    try:
        req = json.loads(stdin.read() or "{}")
        out = handle(req)
    except Exception as e:  # a failed fold must not break the request: the caller sends it as it is
        print("breadcrumbs ace: %s" % type(e).__name__, file=sys.stderr)
        out = {"error": type(e).__name__}
    stdout.write(json.dumps(out, ensure_ascii=False))
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
