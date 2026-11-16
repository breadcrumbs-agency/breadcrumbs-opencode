// The registrations of the plugin (plugin/setup.js) against a fake of the server context. Run: node --test plugin/test/
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { mcpCommand, setup } from "../setup.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function fakeContext({ idle = [] } = {}) {
  const made = { mcp: {}, skills: [], tools: [], commands: [], hooks: {}, disposed: [], synthetic: [], subscriptions: [] };
  const ctx = {
    location: { directory: "/work/kettle" },
    mcp: { transform: async (fn) => fn({ set: (name, config) => { made.mcp[name] = config; } }) },
    skill: { transform: async (fn) => fn({ add: (s) => made.skills.push(s) }) },
    tool: { transform: async (fn) => fn({ add: (t) => made.tools.push(t) }) },
    command: { transform: async (fn) => fn({ add: (c) => made.commands.push(c) }) },
    session: {
      hook: async (name, fn) => {
        made.hooks[name] = fn;
        return { dispose: async () => { made.disposed.push(name); } };
      },
      synthetic: async (x) => { made.synthetic.push(x); },
    },
    event: {
      subscribe: ({ types, signal }) => {
        made.subscriptions.push({ types, signal });
        return (async function* () {
          for (const type of idle) yield { type };
          await new Promise((resolve) => signal.addEventListener("abort", resolve));
        })();
      },
    },
  };
  return { ctx, made };
}

function fakeRun({ answer = null, captured = "" } = {}) {
  const log = { background: [], capture: [], json: [], finish: [] };
  return {
    log,
    capture: async (argv, opts) => { log.capture.push({ argv, opts }); return { code: 0, stdout: captured, stderr: "" }; },
    json: async (argv, payload) => { log.json.push({ argv, payload }); return typeof answer === "function" ? answer(payload) : answer; },
    background: (argv, opts = {}) => {
      log.background.push({ argv, opts });
      log.finish.push(opts.done || (() => {}));
      return true;
    },
  };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 5));

test("the MCP server runs the core through bin/bc-python, with the memory of the folder", async () => {
  const { ctx, made } = fakeContext();
  await setup(ctx, { root: ROOT, run: fakeRun() });
  assert.deepEqual(made.mcp.breadcrumbs.command, mcpCommand(ROOT));
  assert.deepEqual(mcpCommand(ROOT).slice(-4), ["-m", "breadcrumbs", "core", "mcp"]);
  assert.equal(made.mcp.breadcrumbs.enabled, true);
  assert.equal(made.mcp.breadcrumbs.environment.BREADCRUMBS_HERE, "1");
  assert.equal(made.mcp.breadcrumbs.type, "local");
});

test("the plugin adds the two tools, the two commands and the dispatch skill", async () => {
  const { ctx, made } = fakeContext();
  await setup(ctx, { root: ROOT, run: fakeRun() });
  assert.deepEqual(made.tools.map((t) => t.name), ["crumb", "crumb_find"]);
  assert.deepEqual(made.commands.map((c) => c.name), ["viz", "scope"]);
  assert.equal(made.skills.length, 1);
  assert.equal(made.skills[0].id, "breadcrumbs-dispatch");
  assert.match(made.skills[0].content, /^---\nname: breadcrumbs-dispatch/);
  assert.equal(made.skills[0].path, path.join(ROOT, "skills", "dispatch", "SKILL.md"));
  assert.ok(fs.existsSync(made.skills[0].path));
});

test("crumb_find answers with the handles of the core, and a scope of all asks every store", async () => {
  const { ctx, made } = fakeContext();
  const run = fakeRun({ captured: JSON.stringify({ ok: true, result: { q: "tea", groups: [] } }) });
  await setup(ctx, { root: ROOT, run });
  const find = made.tools.find((t) => t.name === "crumb_find");
  const out = await find.execute({ q: "tea", scope: "all", k: 3 });
  assert.match(out.content, /"groups": \[\]/);
  const argv = run.log.capture[0].argv;
  assert.equal(argv[argv.length - 3], "find");
  assert.equal(argv[argv.length - 2], JSON.stringify({ q: "tea", k: 3, store: "*" }));
});

test("crumb shows the text at its level, and a refusal of the core is said in words", async () => {
  const { ctx, made } = fakeContext();
  const run = fakeRun({ captured: JSON.stringify({ ok: true, result: { id: "d98e0bf6", level: 1, store: "local", tokens: 31, text: "Green tea likes water at about 80 C." } }) });
  await setup(ctx, { root: ROOT, run });
  const crumb = made.tools.find((t) => t.name === "crumb");
  const out = await crumb.execute({ id: "d98e0bf6" });
  assert.match(out.content, /Green tea likes water/);
  const argv = run.log.capture[0].argv;
  assert.equal(argv[argv.length - 2], JSON.stringify({ id: "d98e0bf6", level: 1 }));

  const refused = fakeRun({ captured: JSON.stringify({ ok: false, error: "not_found", message: "no crumb" }) });
  const { ctx: ctx2, made: made2 } = fakeContext();
  await setup(ctx2, { root: ROOT, run: refused });
  const out2 = await made2.tools.find((t) => t.name === "crumb").execute({ id: "nope" });
  assert.equal(out2.content, "breadcrumbs: not_found: no crumb");
});

test("/scope posts the scope line into the chat; /viz opens the explorer in the background", async () => {
  const { ctx, made } = fakeContext();
  const run = fakeRun({ captured: "folder: /work/kettle\nscope: git /work/kettle\nmemory: default memory\n" });
  await setup(ctx, { root: ROOT, run });
  const scope = made.commands.find((c) => c.name === "scope");
  await scope.execute({ sessionID: "ses_1" });
  assert.match(made.synthetic[0].text, /scope: git/);
  assert.equal(made.synthetic[0].sessionID, "ses_1");
  const viz = made.commands.find((c) => c.name === "viz");
  const before = run.log.background.length;
  await viz.execute({ sessionID: "ses_1" });
  assert.equal(run.log.background.length, before + 1);
  assert.ok(run.log.background[before].argv.includes("viz"));
});

test("sync runs at load and at each session.idle, one run at a time", async () => {
  const { ctx, made } = fakeContext({ idle: ["session.idle", "session.idle"] });
  const run = fakeRun();
  const cleanup = await setup(ctx, { root: ROOT, run });
  await tick();
  assert.deepEqual(made.subscriptions[0].types, ["session.idle"]);
  assert.equal(run.log.background.length, 1, "the second idle waits for the first run");
  assert.ok(run.log.background[0].argv.includes("sync"));
  assert.ok(run.log.background[0].argv.includes("opencode"));
  run.log.finish[0](0);
  await tick();
  await cleanup();
  assert.equal(made.subscriptions[0].signal.aborted, true);
});

test("the context hook replaces the messages with the bridge's answer, and a null answer changes nothing", async () => {
  const { ctx, made } = fakeContext();
  const answer = (payload) => ({ messages: [{ i: 0 }, { new: { role: "user", content: `LAYER of ${payload.messages.length}` } }, { i: 2 }] });
  const run = fakeRun({ answer });
  await setup(ctx, { root: ROOT, run });
  const messages = [
    { role: "user", content: [{ type: "text", text: "one" }] },
    { role: "assistant", content: [{ type: "text", text: "two" }] },
    { role: "user", content: [{ type: "text", text: "three" }] },
  ];
  const event = { sessionID: "ses_9", model: { id: "demo-model" }, messages };
  await made.hooks.context(event);
  assert.equal(run.log.json[0].payload.op, "select");
  assert.equal(run.log.json[0].payload.sid, "ses_9");
  assert.equal(run.log.json[0].payload.model, "demo-model");
  assert.equal(messages.length, 3);
  assert.equal(messages[0], event.messages[0]);
  assert.deepEqual(messages[1], { role: "user", content: [{ type: "text", text: "LAYER of 3" }] });
  assert.equal(messages[2].content[0].text, "three");

  const quiet = fakeRun({ answer: null });
  const { ctx: c2, made: m2 } = fakeContext();
  await setup(c2, { root: ROOT, run: quiet });
  const again = [{ role: "user", content: "x" }];
  await m2.hooks.context({ sessionID: "s", messages: again });
  assert.equal(again.length, 1);
  assert.equal(again[0].content, "x");
});

test("the compaction hook gives the layer as the summary, and nothing when the layer is empty", async () => {
  const { ctx, made } = fakeContext();
  const run = fakeRun({ answer: { layer: "crumbs: a b c" } });
  await setup(ctx, { root: ROOT, run });
  const event = { sessionID: "s", messages: [{ role: "user", content: "a long talk" }] };
  await made.hooks.compaction(event);
  assert.deepEqual(event.result, { summary: "crumbs: a b c" });
  assert.equal(run.log.json[0].payload.op, "layer");

  const { ctx: c2, made: m2 } = fakeContext();
  await setup(c2, { root: ROOT, run: fakeRun({ answer: { layer: "" } }) });
  const quiet = { sessionID: "s", messages: [{ role: "user", content: "x" }] };
  await m2.hooks.compaction(quiet);
  assert.equal(quiet.result, undefined);
});

test("unloading disposes the hooks and stops the event stream", async () => {
  const { ctx, made } = fakeContext();
  const cleanup = await setup(ctx, { root: ROOT, run: fakeRun() });
  await cleanup();
  assert.deepEqual(made.disposed.sort(), ["compaction", "context"]);
});
