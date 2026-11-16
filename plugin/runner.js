// The processes of the plugin: each breadcrumbs command runs through bin/bc-python (the layers on PYTHONPATH, the Python
// of 3.11 or newer, the default memory). No shell string is built: the argv is passed as it is.
import { spawn } from "node:child_process";

// capture: run argv, give it `input` on stdin, and collect stdout. Resolves { code, stdout, stderr }; never rejects.
export function capture(argv, { cwd, input = "", timeout = 60_000 } = {}) {
  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let done = false;
    const finish = (code) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      resolve({ code, stdout, stderr });
    };
    const child = spawn(argv[0], argv.slice(1), { cwd, stdio: ["pipe", "pipe", "pipe"] });
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      finish(-1);
    }, timeout);
    child.stdout.on("data", (d) => { stdout += d; });
    child.stderr.on("data", (d) => { stderr += d; });
    child.on("error", () => finish(-1));
    child.on("close", (code) => finish(code));
    child.stdin.on("error", () => {});
    child.stdin.end(input);
  });
}

// json: run a bridge that reads one JSON object on stdin and writes one on stdout. Resolves the object, or null.
export async function json(argv, payload, opts) {
  const out = await capture(argv, { ...opts, input: JSON.stringify(payload) });
  try {
    return JSON.parse(out.stdout.trim().split("\n").pop() || "null");
  } catch {
    return null;
  }
}

// background: start argv detached from the server, and call done(code) when it exits. Returns false when it cannot start.
export function background(argv, { cwd, done = () => {} } = {}) {
  try {
    const child = spawn(argv[0], argv.slice(1), { cwd, detached: true, stdio: "ignore" });
    child.on("error", () => done(-1));
    child.on("exit", (code) => done(code));
    child.unref();
    return true;
  } catch {
    return false;
  }
}

export const runner = { capture, json, background };
