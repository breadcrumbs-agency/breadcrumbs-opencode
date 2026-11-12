"""The adapter of the package breadcrumbs_opencode: OpenCode gives its entry of the harness table of core.py.
ports.load() imports this module by the name of its package (breadcrumbs_*); no module imports it.
"""
import json

from breadcrumbs import ports


def _source(path):
    from . import sessions
    return sessions.sessions(path)


def _usage(path):
    from . import sessions
    return sessions.usage(path)


if ports.layer("opencode", __file__):
    ports.harness("opencode", "OpenCode", ("opencode",),
                  lambda cmd: "# opencode.json\n" + json.dumps({"mcp": {"breadcrumbs": {
                      "type": "local", "command": cmd, "enabled": True}}}, indent=2), order=40, source=_source,
                  usage=_usage)
