// The message converter of the ACE hooks: OpenCode's model messages <-> the chat-completions shape of breadcrumbs-common
// (ace_core.Engine). No import: it runs in node's test runner and in the server alike.
//
// toOpenAI(messages) -> [{ msg, src }]: one entry per chat-completions message, src = the index of the OpenCode message
// it came from. A tool result is its own message (role "tool"); a call is a tool_calls item of its assistant message.
//
// rebuild(items, messages, converted) -> OpenCode messages: an { i } item is the source message (once, in order); a
// { new } item (the layer, or the first kept user message merged with it) becomes a text message of its role.
// Only text survives a new message: files and images of a merged message stay in its source, which is not kept.

const textOf = (parts) => parts.filter((p) => p && p.type === "text" && typeof p.text === "string").map((p) => p.text).join("\n");

const partsOf = (content) => {
  if (Array.isArray(content)) return content;
  if (content === undefined || content === null) return [];
  return [{ type: "text", text: String(content) }];
};

// A call has an id, a name and an input under the names of the AI SDK (id, name, input) or of OpenCode's own (params).
const callId = (p) => String(p.id ?? p.toolCallId ?? "");
const callName = (p) => String(p.name ?? p.toolName ?? "unknown");
const callInput = (p) => p.input ?? p.params ?? p.args ?? {};

const resultText = (p) => {
  const value = p.modelOutput ?? p.output ?? p.result;
  if (value && typeof value === "object" && "value" in value) return typeof value.value === "string" ? value.value : JSON.stringify(value.value);
  return typeof value === "string" ? value : JSON.stringify(value ?? "");
};

export function toOpenAI(messages) {
  const out = [];
  (messages || []).forEach((m, src) => {
    if (!m || typeof m !== "object") return;
    const parts = partsOf(m.content);
    if (m.role === "system" || m.role === "user") {
      out.push({ msg: { role: m.role, content: textOf(parts) }, src });
      return;
    }
    if (m.role === "assistant") {
      const msg = { role: "assistant", content: textOf(parts) };
      const calls = parts.filter((p) => p && p.type === "tool-call");
      if (calls.length) {
        msg.tool_calls = calls.map((c) => ({
          id: callId(c), type: "function",
          function: { name: callName(c), arguments: JSON.stringify(callInput(c)) },
        }));
      }
      out.push({ msg, src });
    }
    // tool results: a "tool" message, or a tool-result part of an assistant message (OpenCode keeps both)
    if (m.role === "tool" || m.role === "assistant") {
      for (const p of parts) {
        if (p && p.type === "tool-result") out.push({ msg: { role: "tool", tool_call_id: callId(p), content: resultText(p) }, src });
      }
    }
  });
  return out;
}

export function rebuild(items, messages, converted) {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    if (item && "i" in item) {
      const entry = converted[item.i];
      if (!entry || seen.has(entry.src)) continue;
      seen.add(entry.src);
      out.push(messages[entry.src]);
    } else if (item && item.new && (item.new.role === "user" || item.new.role === "assistant")) {
      out.push({ role: item.new.role, content: [{ type: "text", text: String(item.new.content ?? "") }] });
    }
  }
  return out;
}
