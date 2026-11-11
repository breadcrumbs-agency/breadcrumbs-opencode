# breadcrumbs-opencode

The OpenCode adapter of breadcrumbs. It gives `identify` (the client name that means OpenCode) and `setup` (the line that adds the breadcrumbs MCP server to OpenCode).

- Needs: breadcrumbs-common.
- Use: `python -m breadcrumbs core setup opencode` prints the setup line.
- Test: `PYTHONPATH=../breadcrumbs-common:. python -m unittest discover -s tests`.

MIT licence. Part of breadcrumbs-agency.
