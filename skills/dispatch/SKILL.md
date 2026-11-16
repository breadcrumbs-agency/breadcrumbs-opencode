---
name: breadcrumbs-dispatch
description: Use when you hand work to a helper. Exact crumbs, not summaries.
---

1. Keep the user's intent. Give the helper the user's own words and the exact crumbs, not your summary of them.
2. Find each source with the `crumb_find` tool (or the MCP `find`), then name it by its crumb id, or `id:a-b` for a span, and open it at level 1 with `crumb` (or the MCP `open`). Level 1 is the exact text.
3. Write the brief in this order: the user's request in quotes with its crumb id, the sources, the test for done, then your own notes, marked as yours.
4. A helper that cannot reach this memory cannot open your crumbs: paste the level-1 text into the brief.
5. Check each quote in the helper's report against `crumb(id, 1)`, and cite the crumb ids in your reply to the user.
