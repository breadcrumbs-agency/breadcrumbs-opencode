# breadcrumbs-opencode

The OpenCode adapter of breadcrumbs. It gives `identify` (the client name that means OpenCode) and `setup` (the line that adds the breadcrumbs MCP server to OpenCode), and the source of its sessions for the ingest of breadcrumbs-common.

- Needs: breadcrumbs-common.
- Use: `python -m breadcrumbs core setup opencode` prints the setup line. `python -m breadcrumbs ingest opencode [PATH]` reads the stored sessions of OpenCode into the store (see `breadcrumbs_opencode/sessions.py` for the files and the records that it reads).
- Test: `PYTHONPATH=../breadcrumbs-common:. python -m unittest discover -s tests`.

MIT licence. Part of breadcrumbs-agency.
