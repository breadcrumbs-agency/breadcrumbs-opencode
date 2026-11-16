// The message converter of the ACE hooks (plugin/convert.js). Run: node --test plugin/test/
import assert from "node:assert/strict";
import { test } from "node:test";
import { rebuild, toOpenAI } from "../convert.js";

const conversation = [
  { role: "system", content: "be brief" },
  { role: "user", content: [{ type: "text", text: "how long to boil an egg?" }] },
  {
    role: "assistant",
    content: [
      { type: "text", text: "Let me look." },
      { type: "tool-call", id: "c1", name: "bash", input: { command: "date" } },
      { type: "tool-result", id: "c1", name: "bash", result: "Fri 03:04" },
      { type: "text", text: "About ten minutes." },
    ],
  },
  { role: "user", content: "thanks" },
];

test("toOpenAI makes one chat-completions message per text, call and result, from the message it came from", () => {
  const got = toOpenAI(conversation);
  assert.deepEqual(got.map((c) => c.src), [0, 1, 2, 2, 3]);
  assert.deepEqual(got[0].msg, { role: "system", content: "be brief" });
  assert.deepEqual(got[1].msg, { role: "user", content: "how long to boil an egg?" });
  assert.deepEqual(got[2].msg.tool_calls, [{ id: "c1", type: "function", function: { name: "bash", arguments: "{\"command\":\"date\"}" } }]);
  assert.equal(got[2].msg.content, "Let me look.\nAbout ten minutes.");
  assert.deepEqual(got[3].msg, { role: "tool", tool_call_id: "c1", content: "Fri 03:04" });
  assert.deepEqual(got[4].msg, { role: "user", content: "thanks" });
});

test("toOpenAI reads the AI SDK names and the OpenCode names of a call and a result alike", () => {
  const got = toOpenAI([{ role: "assistant", content: [
    { type: "tool-call", toolCallId: "x", toolName: "read", args: { path: "a" } },
    { type: "tool-result", toolCallId: "x", output: { type: "text", value: "file body" } },
  ] }]);
  assert.equal(got[0].msg.tool_calls[0].function.name, "read");
  assert.equal(got[0].msg.tool_calls[0].function.arguments, "{\"path\":\"a\"}");
  assert.deepEqual(got[1].msg, { role: "tool", tool_call_id: "x", content: "file body" });
});

test("rebuild keeps the source messages in order, each once, and turns a new message into text", () => {
  const converted = toOpenAI(conversation);
  const items = [{ i: 0 }, { new: { role: "user", content: "LAYER" } }, { i: 2 }, { i: 3 }, { i: 4 }, { i: 5 }, { i: 5 }];
  const out = rebuild(items, conversation, converted);
  assert.equal(out[0], conversation[0]);
  assert.deepEqual(out[1], { role: "user", content: [{ type: "text", text: "LAYER" }] });
  assert.equal(out[2], conversation[2]);
  assert.equal(out.length, 4, "the assistant message is kept once, the last user message once");
  assert.equal(out[3], conversation[3]);
});

test("rebuild skips an index that the request never had", () => {
  assert.deepEqual(rebuild([{ i: 99 }], conversation, toOpenAI(conversation)), []);
});
