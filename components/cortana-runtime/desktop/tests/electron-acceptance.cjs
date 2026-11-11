// Real primary-screen capture -> authenticated desktop bridge -> local vision.
// The only visible test window is a full-screen synthetic code fixture. It is
// closed immediately after capture; no screenshot bytes are saved to disk.
const { app, BrowserWindow, screen } = require("electron");
const path = require("node:path");
const { randomUUID } = require("node:crypto");
const root = path.resolve(__dirname, "..");
const testData = path.resolve(root, "..", "tmp", `screen-acceptance-${Date.now()}`);
process.env.CORTANA_DESKTOP_TEST = "1";
process.env.CORTANA_DEV = "0";
process.env.CORTANA_MEMORY_DIR = path.join(testData, "memory");
process.env.CORTANA_LOGS_DIR = path.join(testData, "logs");
process.env.CORTANA_PRIMARY_BACKEND = "local";
process.env.CORTANA_CLOUD_FALLBACK_ENABLED = "false";
process.env.CORTANA_CLOUD_VISION_ENABLED = "false";
app.setAppPath(root);
app.setPath("userData", path.join(testData, "desktop-profile"));
const desktop = require("../electron/main.cjs");
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let fixture;
let timeout = setTimeout(() => { fixture?.destroy(); console.error("SCREEN ACCEPTANCE TIMEOUT"); process.exitCode = 1; app.quit(); }, 180_000);

app.whenReady().then(async () => {
  try {
    let mainWindow;
    for (let i = 0; i < 150; i += 1) {
      ({ mainWindow } = desktop.getWindows());
      if (mainWindow && !mainWindow.webContents.isLoading() && desktop.backend.state.status === "ready") break;
      await sleep(250);
    }
    if (!mainWindow || desktop.backend.state.status !== "ready") throw new Error(`Backend not ready: ${desktop.backend.state.detail}`);
    const status = await desktop.backend.fetch("/api/status").then((r) => r.json());
    if (!status.local_only || status.cloud_enabled || !status.brain.available) throw new Error("Acceptance requires an available local model and cloud disabled.");
    const display = screen.getPrimaryDisplay();
    fixture = new BrowserWindow({
      ...display.bounds, fullscreen: true, frame: false, show: false,
      alwaysOnTop: true, skipTaskbar: true, backgroundColor: "#fafaf8",
      webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false },
    });
    const html = `<!doctype html><html><head>
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
      <title>Cortana controlled screen acceptance fixture</title>
      <style>body{margin:0;background:#fafaf8;color:#1d2430;font-family:Segoe UI,sans-serif;padding:7vh 7vw}h1{font-size:30px;margin:0 0 30px}p{font-size:20px;color:#525b69}pre{font:30px/1.65 Consolas,monospace;background:#eef1f4;border:2px solid #b9c3cd;border-radius:12px;padding:28px}.error{background:#fff0f0;border-color:#ed9b9b;color:#9f2222}small{font-size:18px}</style></head><body>
      <h1>Cortana screen test · synthetic Python example</h1>
      <p>File: greeting_example.py</p>
      <pre>def greet(name):\n    return "Hello, " + name\n\nprint(greet(42))</pre>
      <pre class="error">TypeError: can only concatenate str (not "int") to str</pre>
      <small>This temporary fixture closes immediately after screen capture.</small>
      </body></html>`;
    await fixture.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(html));
    fixture.show();
    fixture.focus();
    await sleep(900);
    const started = performance.now();
    const capture = await mainWindow.webContents.executeJavaScript("window.cortana.captureScreen()");
    fixture.destroy();
    fixture = null;
    const capturedMs = Math.round(performance.now() - started);
    const expectedWidth = Math.round(display.bounds.width * display.scaleFactor);
    const expectedHeight = Math.round(display.bounds.height * display.scaleFactor);
    if (capture.width !== expectedWidth || capture.height !== expectedHeight || capture.storage !== "memory") {
      throw new Error(`Unexpected capture dimensions/storage: ${JSON.stringify(capture)} vs ${expectedWidth}x${expectedHeight}`);
    }
    const request = JSON.stringify({
      message: "What exact error is visible, and how should the greet function be fixed? Answer from the screenshot only. Do not edit files or use tools.",
      session_id: "screen-acceptance-fixture",
      request_id: randomUUID(),
      screenshot_id: capture.screenshot_id,
    });
    const result = await mainWindow.webContents.executeJavaScript(`(async () => {
      const response = await window.cortana.request(crypto.randomUUID(), "/api/chat", {method:"POST", body:${JSON.stringify(request)}});
      return {status:response.status, data:JSON.parse(new TextDecoder().decode(response.bytes))};
    })()`);
    const elapsedMs = Math.round(performance.now() - started);
    if (result.status !== 200) throw new Error(`Vision returned ${result.status}: ${JSON.stringify(result.data)}`);
    if (!/TypeError/i.test(result.data.reply) || !/(?:greet|str\(name\)|str\(42\))/.test(result.data.reply)) throw new Error(`Reply did not identify the visible fixture: ${result.data.reply}`);
    if (/cloud/i.test(result.data.answered_by) || result.data.tools_used?.length || result.data.pending_confirmation) throw new Error("Vision should answer locally without desktop side effects.");
    // Capture IDs are consumed once. A second request must fail before inference.
    const repeat = await desktop.backend.fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: "Describe the same screen", session_id: "screen-acceptance-fixture", request_id: randomUUID(), screenshot_id: capture.screenshot_id }),
    });
    if (repeat.status !== 410) throw new Error(`Capture reuse was not rejected (${repeat.status}).`);
    console.log(JSON.stringify({
      test: "real primary-screen capture and local vision through Electron IPC",
      model: status.brain.model, electron: process.versions.electron,
      capture: { width: capture.width, height: capture.height, storage: capture.storage, milliseconds: capturedMs },
      reply: result.data.reply, answered_by: result.data.answered_by,
      tools_used: result.data.tools_used, milliseconds: elapsedMs,
      screenshot_reuse_status: repeat.status,
      screenshot_retained: false, fixture_closed: true, isolated_data: testData,
    }, null, 2));
  } catch (error) {
    console.error("SCREEN ACCEPTANCE FAILED:", error.message);
    process.exitCode = 1;
  } finally {
    fixture?.destroy();
    clearTimeout(timeout);
    timeout = null;
    app.quit();
  }
});
