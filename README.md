# breadcrumbs-opencode

The OpenCode plugin of breadcrumbs, for OpenCode 2 (`opencode` 2.3.0, the V2 plugin API: `Plugin.define` from
`@opencode/plugin`). It gives OpenCode the parts of the Hermes plugin that the plugin API allows.

Part of breadcrumbs-agency. MIT licence. Needs breadcrumbs-common (and breadcrumbs-spacegraph for `/viz`), found beside
this folder, or in `lib/` of a bundle.

## Install

From a clone (with `breadcrumbs-common` and `breadcrumbs-spacegraph` beside it):

```jsonc
// opencode.json: the global one (~/.config/opencode/opencode.json), or the one of a project
{
  "plugins": ["/absolute/path/to/breadcrumbs-opencode"]
}
```

A bundle (`python tools/bundle.py opencode OUT` in breadcrumbs) is the same folder with the layers under `lib/`; list
its folder the same way. No package or release repository exists for this part yet.

Python 3.11 or newer is needed; `bin/bc-python` picks one (`BREADCRUMBS_PY` names another). The memory is
`$XDG_DATA_HOME/opencode/breadcrumbs` (default `~/.local/share/opencode/breadcrumbs`). `BREADCRUMBS_HOME` names another
memory; its last folder must be `breadcrumbs`.

## What it adds

- **The MCP server** `breadcrumbs`: the core's verbs `find`, `open`, `zoom`, `trail`, `stores`, `health`
  (`python -m breadcrumbs core mcp`), started with `BREADCRUMBS_HERE=1`: a call that names no store looks in the memory
  of the folder where OpenCode runs.
- **Tools** `crumb(id, level)` (the verb `zoom`; level 0 is the handle, 1 the exact text, default 1) and
  `crumb_find(q, k, scope)` (the verb `find`; `scope: "all"` searches every store). Each answer is text for the model.
  No receipts yet: Hermes writes an `rcpt` crumb per read, this plugin does not.
- **Commands** `/viz` (opens the explorer of the whole memory, `python -m breadcrumbs viz`, in the background) and
  `/scope` (posts the scope of the folder and its memory into the chat).
- **Skill** `breadcrumbs-dispatch`: how to hand work to a helper with the user's words and exact crumbs. It is generic:
  it names no model lanes.
- **Sync**: `python -m breadcrumbs sync opencode` runs when the plugin loads and on each `session.idle`, in the
  background, one run at a time. It reads OpenCode's database read-only and puts each session in the memory of the
  project where it ran (`breadcrumbs_opencode/sessions.py`). The OpenCode 2 layout (`session_v2`, `session_message`) is
  read from its own tables; the OpenCode 1 layout (`session`, `message`, `part`) is still read when those tables exist.
- **ACE** through two hooks. `context` runs before each request of the agent loop; when the request passes the target
  (the dials of `config.json` in the memory folder, as in Hermes), the older messages fold into a layer of crumbs and the
  newest stay exact. `compaction` gives the layer as the summary of a compaction. The bridge is
  `breadcrumbs_opencode/ace.py` (the engine of breadcrumbs-common). Each request writes one line to `ace.log` in the
  memory's `breadcrumbs` folder, in the format of the Hermes plugin.

## Limits

- **The hooks have not run against a model.** The messages were read from the schemas in the binary of OpenCode 2.3.0
  (parts `text`, `reasoning`, `tool-call`, `tool-result`), not from a documented example. A message of another shape is
  passed as it is. Replacing the array of messages in place is what the binary's own hooks do; live behaviour is not
  checked.
- **ACE gets no token counts from the host.** The engine sizes requests in bytes until a count is logged. A request's
  line in `usage.log` comes from `sync`, not from the hook.
- **A folded request merges its first kept user message into the layer, as text.** Files and images of that message
  stay in its source, which is not kept in the request.
- **Scope is by folder.** A folder with a git repository, or with a `.breadcrumbs` entry, is its own memory; any other
  folder that is not the home folder is its own scope too; the home folder uses the default memory.
- **OpenCode 2 usage is read as OpenCode 1 reads it** (`input` without the cache, `cache.read` and `cache.write` apart).
  That was not checked against a live OpenCode 2 session.
- **Not done:** `crumb_find`'s `up` scope; receipts; the Hermes autostart of `/viz`; a hook for live `usage.log` lines.

## Verified

- The Python suite (`PYTHONPATH=../breadcrumbs-common:. python3.12 -m unittest discover -s tests`): the ACE bridge (a
  long request folds, the newest message stays exact, the layer is the summary, one line in `ace.log`, the memory of a
  folder); the verbs, the scope line and the launcher; the OpenCode 2 reader on a fixture with invented text.
- The plugin against a fake of the server context (`npm test`, which runs `node --test plugin/test/*.test.mjs`): the
  MCP entry, the tools and their arguments, the commands, the skill, the sync at load and at idle with one run at a
  time, the two hooks, and unload.
- The real `opencode` 2.3.0: `opencode --print-logs serve` on a private port, with `HOME` and the `XDG_*` folders set to a
  throwaway folder and this plugin listed in that folder's `opencode.json`. The log shows `loading plugin` and
  `mcp connected server=breadcrumbs tools=6`; the command list has `viz` and `scope`; the skill list has
  `breadcrumbs-dispatch`. No model was called and no session was run.
- The bundle target (`tools/bundle.py opencode`, tested in breadcrumbs): the folder, the launcher and the layers.

## Files

- `plugin/index.js`: the entry (`Plugin.define`) with the SDK's skill helpers. `plugin/setup.js`: what the plugin
  registers, testable without the SDK. `plugin/convert.js`: the message converter of ACE. `plugin/runner.js`: the child
  processes.
- `bin/bc-python`: runs Python with the layers on the path and the default memory.
- `breadcrumbs_opencode/`: `adapter.py` (the harness entry), `sessions.py` (the sources and usage), `ace.py` (the ACE
  bridge), `tools.py` (the verbs and the scope line), `icon.png`.
- `skills/dispatch/SKILL.md`; `package.json` (`exports` names `plugin/index.js`).

Tests: `PYTHONPATH=../breadcrumbs-common:. python3.12 -m unittest discover -s tests` and `npm test`.

MIT licence. Part of breadcrumbs-agency.
