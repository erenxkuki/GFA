const readline = require("readline");

let counter = 0;
let initialized = false;

function respond(id, result, error) {
  const msg = { jsonrpc: "2.0", id };
  if (error) msg.error = error; else msg.result = result;
  process.stdout.write(JSON.stringify(msg) + "\n");
}

const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  line = line.trim();
  if (!line) return;
  let req;
  try { req = JSON.parse(line); } catch (e) {
    respond(null, null, { code: -32700, message: "parse error" });
    return;
  }
  const method = req.method;
  const params = req.params || {};
  const id = req.id;
  try {
    if (method === "initialize") {
      initialized = true;
      respond(id, { ok: true, capabilities: ["echo.observe", "echo.act"] });
    } else if (method === "health") {
      respond(id, { ok: true, initialized });
    } else if (method === "observe") {
      counter += 1;
      respond(id, { observations: [{ type: "echo", count: counter, lang: "node" }] });
    } else if (method === "execute") {
      respond(id, { status: "succeeded", echoed: params.command });
    } else if (method === "shutdown") {
      initialized = false;
      respond(id, { ok: true });
      process.exit(0);
    } else {
      respond(id, null, { code: -32601, message: "method not found" });
    }
  } catch (e) {
    respond(id, null, { code: -32603, message: String(e) });
  }
});