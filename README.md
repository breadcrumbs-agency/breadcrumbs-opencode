# breadcrumbs-opencode

The OpenCode adapter of breadcrumbs. It gives `identify` (the client name that means OpenCode) and `setup` (the line that adds the breadcrumbs MCP server to OpenCode), the source of its sessions for the ingest of breadcrumbs-common, its usage (one record per model request, with input, cache read and write, output and the prompt total) and an icon.

- Needs: breadcrumbs-common.
- Use: `python -m breadcrumbs core setup opencode` prints the setup line. `python -m breadcrumbs ingest opencode [PATH]` reads the stored sessions of OpenCode into the store (see `breadcrumbs_opencode/sessions.py` for the files and the records that it reads).
- Sync: `python -m breadcrumbs sync opencode [PATH]` puts each session in the memory of the project where it ran (its `directory`), with a state.db for the viewers. The database is opened read-only.
- No plugin file: the plugin API of OpenCode changed between V1 and V2 (1.18.x), so a session-end hook is not shipped; run `sync` by hand or from cron.
- Test: `PYTHONPATH=../breadcrumbs-common:. python -m unittest discover -s tests`.

MIT licence. Part of breadcrumbs-agency.
