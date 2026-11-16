// The breadcrumbs plugin of OpenCode, without the host SDK: setup(ctx, options) registers what the plugin gives, and its
// cleanup takes it back. plugin/index.js is the entry that OpenCode loads; it passes the SDK's skill helpers in `brand`.
//
//   mcp       the breadcrumbs MCP server (the verbs find, open, zoom, trail, stores, health)
//   tools     crumb (a crumb at a level, 0 to 1) and crumb_find (find the crumbs of a question)
//   commands  /viz (the explorer) and /scope (which memory this folder uses)
//   skill     breadcrumbs-dispatch: how to hand work to a helper with exact crumbs
//   sync      `sync opencode` at load and at each session.idle, in the background, one at a time
//   ACE       the context hook folds an old chat into crumbs; the compaction hook gives the layer as the summary
import fs from "node:fs";
import path from "node:path";
import { rebuild, toOpenAI } from "./convert.js";
import { runner as defaultRunner } from "./runner.js";

export const NAME = "breadcrumbs";

export function python(root) {
  return ["sh", path.join(root, "bin", "bc-python")];
}

export function mcpCommand(root) {
  return [...python(root), "-m", "breadcrumbs", "core", "mcp"];
}

const CRUMB_INPUT = {
  type: "object",
  properties: {
    id: { type: "string", description: "The crumb id, as a find returned it." },
    level: { type: "number", minimum: 0, maximum: 1, description: "0 is the handle, 1 the exact text (default 1)." },
  },
  required: ["id"],
  additionalProperties: false,
};

const FIND_INPUT = {
  type: "object",
  properties: {
    q: { type: "string", description: "The words to look for." },
    k: { type: "integer", minimum: 1, maximum: 50, description: "The number of handles (default 8)." },
    scope: { type: "string", enum: ["here", "all"], description: "here: this folder's memory (default); all: every memory." },
  },
  required: ["q"],
  additionalProperties: false,
};

// core: one verb of the core, through tools.py. Returns the text for the model.
export async function core(run, root, dir, verb, params) {
  const out = await run.capture(
    [...python(root), "-m", "breadcrumbs_opencode.tools", "call", verb, JSON.stringify(params), dir], { cwd: dir });
  let answer;
  try {
    answer = JSON.parse(out.stdout.trim().split("\n").pop() || "null");
  } catch {
    return "breadcrumbs: no answer from the memory";
  }
  if (!answer || !answer.ok) return `breadcrumbs: ${answer ? answer.error : "failed"}: ${answer ? answer.message : ""}`.trim();
  const result = answer.result;
  if (verb === "zoom") return `${result.id} level ${result.level} (${result.store}, ${result.tokens} tokens)\n${result.text}`;
  return JSON.stringify(result, null, 2);
}

export async function setup(ctx, { root, run = defaultRunner, brand = {} } = {}) {
  const dir = (ctx.location && ctx.location.directory) || process.cwd();
  const skillPath = path.join(root, "skills", "dispatch", "SKILL.md");
  const skillText = fs.readFileSync(skillPath, "utf8");
  const cleanups = [];

  // MCP server
  await ctx.mcp.transform((editor) => {
    editor.set(NAME, { type: "local", command: mcpCommand(root), environment: { BREADCRUMBS_HERE: "1" }, enabled: true });
  });

  // skill
  await ctx.skill.transform((editor) => {
    editor.add({
      id: (brand.skillID || String)("breadcrumbs-dispatch"),
      name: (brand.skillName || String)("Breadcrumbs dispatch"),
      description: "Use when you hand work to a helper. Exact crumbs, not summaries.",
      path: (brand.skillPath || String)(skillPath),
      content: skillText,
    });
  });

  // tools
  await ctx.tool.transform((editor) => {
    editor.add({
      name: "crumb",
      description: "Show one breadcrumb by its id at a level from 0 (its handle) to 1 (its exact text).",
      input: CRUMB_INPUT,
      execute: async (input) => ({
        content: await core(run, root, dir, "zoom", { id: input.id, level: input.level === undefined ? 1 : input.level }),
      }),
    });
    editor.add({
      name: "crumb_find",
      description: "Find breadcrumbs by words. Returns handles: each names a memory by its id, to open with crumb.",
      input: FIND_INPUT,
      execute: async (input) => {
        const params = { q: input.q };
        if (input.k !== undefined) params.k = input.k;
        if (input.scope === "all") params.store = "*";
        return { content: await core(run, root, dir, "find", params) };
      },
    });
  });

  // commands
  await ctx.command.transform((editor) => {
    editor.add({
      name: "viz",
      description: "Open the breadcrumbs explorer of the whole memory",
      execute: async ({ sessionID }) => {
        run.background([...python(root), "-m", "breadcrumbs", "viz"], { cwd: dir });
        await ctx.session.synthetic({ sessionID, text: "breadcrumbs: the explorer opens." });
      },
    });
    editor.add({
      name: "scope",
      description: "Show which breadcrumbs memory this folder uses",
      execute: async ({ sessionID }) => {
        const out = await run.capture([...python(root), "-m", "breadcrumbs_opencode.tools", "scope", dir], { cwd: dir });
        await ctx.session.synthetic({ sessionID, text: out.stdout.trim() || "breadcrumbs: no scope line" });
      },
    });
  });

  // sync: the sessions of OpenCode into their memories. One run at a time; a run that is still going is not doubled.
  let syncing = false;
  const sync = () => {
    if (syncing) return;
    syncing = true;
    const started = run.background([...python(root), "-m", "breadcrumbs", "sync", "opencode"], {
      cwd: root, done: () => { syncing = false; },
    });
    if (!started) syncing = false;
  };
  sync();
  const stream = new AbortController();
  cleanups.push(() => stream.abort());
  (async () => {
    try {
      for await (const event of ctx.event.subscribe({ types: ["session.idle"], signal: stream.signal })) {
        void event;
        sync();
      }
    } catch {
      // the stream ends when the plugin unloads
    }
  })();

  // ACE: the context of each model request, and the compaction summary
  const modelOf = (event) => (event.model && (event.model.id || event.model.modelID)) || "";
  const hookContext = await ctx.session.hook("context", async (event) => {
    try {
      const converted = toOpenAI(event.messages);
      if (!converted.length) return;
      const answer = await run.json([...python(root), "-m", "breadcrumbs_opencode.ace"], {
        op: "select", sid: event.sessionID, cwd: dir, model: modelOf(event), messages: converted.map((c) => c.msg),
      }, { cwd: dir });
      if (!answer || !Array.isArray(answer.messages)) return;  // null: the request passes as it is
      const next = rebuild(answer.messages, event.messages, converted);
      event.messages.splice(0, event.messages.length, ...next);
    } catch {
      // a failed fold leaves the request as it is
    }
  });
  const hookCompaction = await ctx.session.hook("compaction", async (event) => {
    try {
      const converted = toOpenAI(event.messages);
      if (!converted.length) return;
      const answer = await run.json([...python(root), "-m", "breadcrumbs_opencode.ace"], {
        op: "layer", sid: event.sessionID, cwd: dir, model: modelOf(event), messages: converted.map((c) => c.msg),
      }, { cwd: dir });
      if (answer && typeof answer.layer === "string" && answer.layer) event.result = { summary: answer.layer };
    } catch {
      // without a summary, OpenCode summarizes the transcript itself
    }
  });
  for (const hook of [hookContext, hookCompaction]) {
    if (hook && typeof hook.dispose === "function") cleanups.push(() => hook.dispose());
  }

  return async () => {
    for (const fn of cleanups.reverse()) {
      try {
        await fn();
      } catch {
        // unloading never throws
      }
    }
  };
}
