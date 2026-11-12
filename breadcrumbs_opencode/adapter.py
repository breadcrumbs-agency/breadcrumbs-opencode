"""The adapter of the package breadcrumbs_opencode: OpenCode gives its entry of the harness table of core.py.
ports.load() imports this module by the name of its package (breadcrumbs_*); no module imports it.

    harness   opencode: identify, setup (an opencode.json block), the source of the ingest and of `sync` (sessions.py),
              its usage (one record per request, with the prompt tokens) and its icon (drawn for this package)
    ports     state codebase profile  (for the viewers of breadcrumbs-spacegraph: the numbers of a session that `sync` wrote
              to state.db, the project where it ran, and the name of the store; OpenCode has no ACE log, no hidden
              sessions and no price table here)

The memory of OpenCode is a base folder of its own, and `sync` puts each session in the memory of its project under it
(breadcrumbs/sync.py): the git repository or folder where the session ran (the `directory` of the session).
"""
import json

from breadcrumbs import ports, statedb, sync

NAME = "opencode"  # the profile: the one program whose sessions these memories hold


def _source(path):
    from . import sessions
    return sessions.sessions(path)


def _usage(path):
    from . import sessions
    return sessions.usage(path)


def _codebase(folder):
    found = sync.project(folder, sync.enabled())
    return found[1] if found else None


if ports.layer("opencode", __file__):
    ports.give("state", statedb.read)
    ports.give("codebase", _codebase)
    ports.give("profile", lambda home: NAME)
    ports.harness("opencode", "OpenCode", ("opencode",),
                  lambda cmd: "# opencode.json\n" + json.dumps({"mcp": {"breadcrumbs": {
                      "type": "local", "command": cmd, "enabled": True}}}, indent=2), order=40, source=_source,
                  usage=_usage, icon=ports.image(__file__, "icon.png"))
