const { spawn } = require("node:child_process");
const { randomBytes } = require("node:crypto");
const net = require("node:net");
const fs = require("node:fs");
const path = require("node:path");
const { EventEmitter } = require("node:events");
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function freePort() {
  const server = net.createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

class Backend extends EventEmitter {
  constructor(root) {
    super();
    this.root = root;
    this.child = null;
    this.token = "";
    this.port = null;
    this.state = { status: "starting", detail: "Starting the local assistant…" };
    this.stopping = false;
    this.starting = null;
    this.restarts = 0;
  }
  update(status, detail) {
    this.state = { status, detail };
    this.emit("state", this.state);
  }
  start() {
    if (this.starting) return this.starting;
    this.starting = this._start().finally(() => { this.starting = null; });
    return this.starting;
  }
  async _start() {
    this.stopping = false;
    const python = path.join(this.root, "agent", ".venv", "Scripts", "python.exe");
    if (!fs.existsSync(python)) {
      this.update("error", "Cortana's Python environment is missing. Run setup from the project folder.");
      return;
    }
    this.update("starting", "Starting the local assistant…");
    this.port = await freePort();
    this.token = randomBytes(32).toString("hex");
    const child = spawn(python, [
      "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", String(this.port), "--no-access-log",
    ], {
      cwd: path.join(this.root, "agent"),
      env: { ...process.env, CORTANA_API_TOKEN: this.token, CORTANA_HOST: "127.0.0.1",
        CORTANA_PORT: String(this.port), CORTANA_DESKTOP_PID: String(process.pid),
        PYTHONUTF8: "1", PYTHONUNBUFFERED: "1" },
      windowsHide: true, shell: false, stdio: ["ignore", "pipe", "pipe"],
    });
    this.child = child;
    // Do not forward arbitrary server exception text into the renderer:
    // validation traces can contain environment values or private tool input.
    child.stdout.resume();
    child.stderr.resume();
    child.once("error", () => {
      if (this.child === child) this.update("error", "Cortana could not start its Python environment.");
    });
    child.once("exit", (code) => {
      if (this.child !== child) return;
      this.child = null;
      if (this.stopping) return;
      this.update("error", `The local assistant stopped (exit ${code ?? "unknown"}). Check the Python environment, then use Restart assistant.`);
      if (this.restarts < 2) {
        this.restarts += 1;
        const retry = setTimeout(() => {
          if (!this.stopping && !this.child) this.start().catch(() => this.update("error", "The local assistant could not restart."));
        }, 2000 * this.restarts);
        retry.unref();
      }
    });
    for (let attempt = 0; attempt < 100; attempt += 1) {
      if (this.child !== child || this.stopping) return;
      try {
        // Authenticated status proves readiness of OUR child if another process
        // happened to take the ephemeral port before Python bound it.
        const response = await this.fetch("/api/ready", { signal: AbortSignal.timeout(1500) });
        if (response.ok) { this.update("ready", "Local assistant connected"); return; }
      } catch { /* Python is still importing dependencies. */ }
      await delay(300);
    }
    if (this.child === child) this.update("error", "The local assistant did not become ready. Check setup and use Restart assistant.");
  }
  fetch(route, options = {}) {
    if (!this.port || !this.token) throw new Error("The local assistant is still starting.");
    return fetch(`http://127.0.0.1:${this.port}${route}`, {
      ...options, redirect: "error",
      headers: { ...(options.headers || {}), Authorization: `Bearer ${this.token}` },
    });
  }
  stop() {
    this.stopping = true;
    const child = this.child;
    this.child = null;
    if (child && child.exitCode === null) child.kill();
  }
  async restart() {
    this.stop();
    this.restarts = 0;
    await this.starting;
    return this.start();
  }
}
module.exports = { Backend, freePort };
