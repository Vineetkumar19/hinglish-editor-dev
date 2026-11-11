// Real local backend + local model, with an owned disposable coding fixture.
// --open-apps additionally exercises the three launch examples requested by owner.
const fs = require("node:fs");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const { Backend } = require("../desktop/electron/backend.cjs");
const root = path.resolve(__dirname, "..");
const output = path.join(root, "tmp", "runtime-smoke");
fs.mkdirSync(output, { recursive: true });
process.env.CORTANA_MEMORY_DIR = path.join(output, "memory");
process.env.CORTANA_LOGS_DIR = path.join(output, "logs");
const fixtureDir = path.join(root, "tests", ".runtime-fixture");
fs.mkdirSync(fixtureDir, { recursive: true });
const fixture = path.join(fixtureDir, "invoice_example.py");
fs.writeFileSync(fixture, "def compute_total(price, tax_rate):\n    return price + tax_rate\n");
const backend = new Backend(root);
async function request(route, body) {
  const response = await backend.fetch(route, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: AbortSignal.timeout(180_000),
  });
  return { status: response.status, body: await response.json() };
}
async function chat(message) {
  const t = Date.now();
  const result = await request("/api/chat", { message, request_id: randomUUID(), session_id: randomUUID() });
  return { ...result, elapsed_seconds: (Date.now() - t) / 1000 };
}
(async () => {
  const report = {};
  try {
    await backend.start();
    if (backend.state.status !== "ready") throw new Error(backend.state.detail);
    const unauthenticated = await fetch(`http://127.0.0.1:${backend.port}/api/status`);
    if (unauthenticated.status !== 401) throw new Error("Unauthenticated service request was accepted");
    report.auth_rejected = unauthenticated.status;
    if (process.argv.includes("--open-apps")) {
      report.launches = [];
      for (const message of ["Open Chrome", "YouTube kholo", "चैट जीपीटी खोलो"]) {
        const result = await chat(message);
        if (result.status !== 200 || result.body.answered_by !== "local command" || !result.body.reply.startsWith("Opening")) {
          throw new Error(JSON.stringify(result));
        }
        report.launches.push({ command: message, ...result });
      }
    }
    report.code = await chat(`Read the file ${fixture}. Its compute_total should apply tax_rate as a decimal fraction: price 100 and tax_rate 0.18 should return 118. Prepare the smallest exact code edit for my approval. Read the file first and use edit_code_file.`);
    if (!report.code.body.pending_confirmation) throw new Error("The local model did not prepare a reviewable code edit: " + JSON.stringify(report.code));
    const id = report.code.body.pending_confirmation.id;
    if (fs.readFileSync(fixture, "utf8") !== "def compute_total(price, tax_rate):\n    return price + tax_rate\n") throw new Error("File changed before approval");
    report.approval = await request(`/api/confirm/${id}`, { approve: true });
    if (report.approval.status !== 200) throw new Error("Approved fixture edit failed: " + JSON.stringify(report.approval));
    report.edited_source = fs.readFileSync(fixture, "utf8");
    report.replay = await request(`/api/confirm/${id}`, { approve: true });
    if (report.replay.status !== 409) throw new Error("Approval replay was accepted");
    const { spawnSync } = require("node:child_process");
    const validateCode = [
      "import ast,sys,pathlib",
      "tree=ast.parse(pathlib.Path(sys.argv[1]).read_text())",
      "expressions=['price * (1 + tax_rate)','price + price * tax_rate','price * tax_rate + price']",
      "allowed=[ast.dump(ast.parse('def compute_total(price, tax_rate):\\n    return '+x+'\\n')) for x in expressions]",
      "assert ast.dump(tree) in allowed, 'Generated fixture changed beyond the expected arithmetic'",
      "ns={}",
      "exec(compile(tree,'<validated fixture>','exec'), {'__builtins__':{}}, ns)",
      "assert abs(ns['compute_total'](100,0.18)-118)<1e-9",
      "print('fixture calculation passed')",
    ].join("\n");
    const validation = spawnSync(path.join(root, "agent", ".venv", "Scripts", "python.exe"),
      ["-I", "-c", validateCode, fixture],
      { encoding: "utf8", windowsHide: true });
    if (validation.status !== 0) throw new Error(validation.stderr || "Fixture result incorrect");
    report.calculation = validation.stdout.trim();
    report.success = true;
  } catch (error) {
    report.success = false;
    report.error = error.message;
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, "result.json"), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    backend.stop();
  }
})();
