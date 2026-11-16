"""The model-facing side of breadcrumbs for OpenCode: the verbs of core.py for the tools of the plugin, and the scope line.

    python -m breadcrumbs_opencode.tools call VERB PARAMS_JSON [CWD]   one verb of core.py, as JSON on stdout
    python -m breadcrumbs_opencode.tools scope [CWD]                   the folder, its scope and its memory, as text

The plugin's tools are `crumb` (the verb zoom: a crumb at a level from 0 to 1) and `crumb_find` (the verb find). Both read
the memory of the project of the folder where OpenCode runs (sync.where), or the default memory when the folder is no
project. Nothing here writes a crumb.

Run with breadcrumbs-common and this folder on PYTHONPATH.
"""
import json
import os
import sys

from breadcrumbs import core as corelib
from breadcrumbs import scope, sync
from breadcrumbs.cli import default_home


def stores(cwd):
    """The stores that a call looks in: the memory of the project of cwd, else the default memory of OpenCode."""
    base = os.path.abspath(default_home())
    local = os.path.abspath(sync.where(base, cwd))
    if os.path.realpath(local) == os.path.realpath(base):  # no project: the default memory, and no other one
        return corelib.Stores(local=base, root=os.path.dirname(base), here=False)
    return corelib.Stores(local=local, root=os.path.dirname(base), here=True)


def call(verb, params, cwd):
    """The result of one verb (core.Core.call), or the refusal as {"error", "message"}."""
    core = corelib.Core(stores(cwd))
    try:
        return {"ok": True, "result": core.call(verb, params, harness="opencode")}
    except corelib.CoreError as e:
        return {"ok": False, "error": e.code, "message": e.message}
    finally:
        core.close()


def scope_text(cwd):
    base = os.path.abspath(default_home())
    hit = scope.nearest(cwd)
    memory = os.path.abspath(sync.where(base, cwd))
    where = "default memory (%s)" % base if os.path.realpath(memory) == os.path.realpath(base) else memory
    return "\n".join([
        "folder: %s" % cwd,
        "scope: %s %s" % hit if hit else "scope: none (the folder is no project)",
        "memory: %s" % where,
    ])


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: tools call VERB PARAMS [CWD] | scope [CWD]", file=sys.stderr)
        return 2
    cwd = os.path.abspath(argv[-1] if argv[0] == "scope" and len(argv) > 1 else os.getcwd())
    if argv[0] == "scope":
        print(scope_text(cwd))
        return 0
    if argv[0] == "call" and len(argv) >= 3:
        if len(argv) > 3:
            cwd = os.path.abspath(argv[3])
        print(json.dumps(call(argv[1], json.loads(argv[2] or "{}"), cwd), ensure_ascii=False))
        return 0
    print("usage: tools call VERB PARAMS [CWD] | scope [CWD]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
