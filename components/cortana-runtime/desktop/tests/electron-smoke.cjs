// Run: electron tests/electron-smoke.cjs
// Real hidden Electron + real local backend. Does not capture the desktop,
// register startup, send chat to a model, or open external apps.
const { app } = require("electron");
const path = require("node:path");
const fs = require("node:fs/promises");
process.env.CORTANA_DESKTOP_TEST = "1";
process.env.CORTANA_DEV = "0";
const root = path.resolve(__dirname, "..");
app.setAppPath(root);
app.setPath("userData", path.resolve(root, "..", "tmp", "desktop-smoke-profile"));
app.commandLine.appendSwitch("use-fake-device-for-media-stream");
const desktop = require("../electron/main.cjs");
const errors = [];
app.on("web-contents-created", (_event, contents) => {
  contents.on("console-message", (_event, details) => {
    if (details.level === "error") errors.push(details.message);
  });
  contents.on("did-fail-load", (_event, code, reason) => errors.push(`${code}: ${reason}`));
});
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const timeout = setTimeout(() => { console.error("SMOKE TIMEOUT", desktop.backend.state); app.quit(); process.exitCode = 1; }, 60_000);

app.whenReady().then(async () => {
  try {
    let mainWindow, floatingWindow;
    for (let i = 0; i < 150; i += 1) {
      ({ mainWindow, floatingWindow } = desktop.getWindows());
      if (mainWindow && floatingWindow && !mainWindow.webContents.isLoading() && !floatingWindow.webContents.isLoading() && desktop.backend.state.status === "ready") break;
      await sleep(300);
    }
    if (!mainWindow || desktop.backend.state.status !== "ready") throw new Error(`Backend not ready: ${desktop.backend.state.detail}`);
    const result = await mainWindow.webContents.executeJavaScript(`(async () => {
      const state = await window.cortana.getState();
      const res = await window.cortana.request(crypto.randomUUID(), '/api/status', {});
      let denied = false;
      try { await window.cortana.request(crypto.randomUUID(), 'https://example.com', {}); }
      catch { denied = true; }
      const virtualMic = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      const micWorks = virtualMic.getAudioTracks().length === 1;
      virtualMic.getTracks().forEach(track => track.stop());
      return {
        text: document.body.innerText.slice(0, 800),
        url: location.href,
        state: state.status,
        status: res.status,
        denied,
        bridgeKeys: Object.keys(window.cortana),
        media: !!navigator.mediaDevices,
        secure: isSecureContext,
        micWorks,
      };
    })()`);
    if (result.status !== 200 || !result.denied || !result.text.includes("CORTANA") || !result.media || !result.secure || !result.micWorks) throw new Error(JSON.stringify(result));
    if (mainWindow.isVisible() || floatingWindow.isVisible()) throw new Error("Smoke test must remain hidden.");
    const floating = await floatingWindow.webContents.executeJavaScript("({buttons:document.querySelectorAll('button').length,url:location.href})");
    if (floating.buttons !== 2) throw new Error("Floating UI did not render.");
    const oldPort = desktop.backend.port;
    const oldToken = desktop.backend.token;
    const oldPid = desktop.backend.child.pid;
    await desktop.backend.restart();
    if (desktop.backend.state.status !== "ready" || desktop.backend.child.pid === oldPid || desktop.backend.token === oldToken) throw new Error("Restart did not replace the owned backend and rotate authentication.");
    await sleep(200);
    let oldBackendAlive = false;
    try {
      const old = await fetch(`http://127.0.0.1:${oldPort}/api/ready`, { headers: { Authorization: `Bearer ${oldToken}` }, signal: AbortSignal.timeout(1500) });
      oldBackendAlive = old.ok;
    } catch { /* The old owned process must no longer be reachable. */ }
    if (oldBackendAlive) throw new Error("Restart left the old Python backend running.");
    await sleep(250);
    const shot = await mainWindow.webContents.capturePage();
    const output = path.resolve(root, "..", "tmp", "desktop-smoke.png");
    await fs.writeFile(output, shot.toPNG());
    console.log(JSON.stringify({ result, floating, restart: "new child, rotated token, previous backend stopped", rendererErrors: errors, screenshot: output, electron: process.versions.electron }, null, 2));
    if (errors.length) throw new Error("Renderer logged errors.");
  } catch (error) {
    console.error("SMOKE FAILED:", error.message);
    process.exitCode = 1;
  } finally {
    clearTimeout(timeout);
    app.quit();
  }
});
