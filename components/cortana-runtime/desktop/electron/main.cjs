const { app, BrowserWindow, Menu, Tray, nativeImage, ipcMain, session, protocol, screen, globalShortcut, powerMonitor } = require("electron");
const fs = require("node:fs/promises");
const path = require("node:path");
const { Backend } = require("./backend.cjs");
const { validateRequest, trustedUrl, resolveAsset, loginOptions, loginEntryEnabled } = require("./security.cjs");

const isDev = process.env.CORTANA_DEV === "1";
const isSmokeTest = process.env.CORTANA_DESKTOP_TEST === "1";
const appRoot = app.getAppPath();
const projectRoot = app.isPackaged ? path.resolve(process.resourcesPath, "cortana") : path.resolve(__dirname, "..", "..");
const distRoot = path.join(appRoot, "dist");
const backend = new Backend(projectRoot);
let mainWindow, floatingWindow, tray;
let quitting = false;
let capturing = false;
let locked = false;
let savedSettings = { floatingButton: true };
const shortcuts = { shortcut: null, screenShortcut: null };
const controllers = new Map();
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'";

protocol.registerSchemesAsPrivileged([
  { scheme: "app", privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true } },
]);

function senderRole(event) {
  if (!event.senderFrame || event.senderFrame !== event.sender.mainFrame) throw new Error("Untrusted assistant frame.");
  if (event.sender === mainWindow?.webContents && trustedUrl(event.senderFrame.url, isDev, "main")) return "main";
  if (event.sender === floatingWindow?.webContents && trustedUrl(event.senderFrame.url, false, "floating")) return "floating";
  throw new Error("Untrusted assistant window.");
}

function requireMain(event) {
  if (senderRole(event) !== "main" || locked) throw new Error("Unlock Windows and use the Cortana window.");
}

function sendMain(channel, value) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(channel, value);
}

function showMain() {
  if (isSmokeTest || locked || !mainWindow || mainWindow.isDestroyed()) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

function toggleMain() {
  if (capturing || locked) return;
  if (mainWindow?.isVisible() && mainWindow.isFocused()) mainWindow.hide();
  else showMain();
}

function protectWindow(win) {
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event) => event.preventDefault());
  win.webContents.on("will-attach-webview", (event) => event.preventDefault());
}

function settingsPath() { return path.join(app.getPath("userData"), "desktop-settings.json"); }

async function saveSettings() {
  const file = settingsPath();
  await fs.mkdir(path.dirname(file), { recursive: true });
  await fs.writeFile(file, JSON.stringify(savedSettings, null, 2), "utf8");
}

function currentSettings() {
  const login = app.getLoginItemSettings(loginOptions(process.execPath, appRoot, app.isPackaged));
  return {
    floatingButton: savedSettings.floatingButton !== false,
    openAtLogin: loginEntryEnabled(login, process.execPath, appRoot, app.isPackaged),
    ...shortcuts, version: app.getVersion(),
  };
}

function applyLogin(enabled) {
  app.setLoginItemSettings({
    ...loginOptions(process.execPath, appRoot, app.isPackaged),
    name: "Cortana", openAtLogin: enabled, enabled,
  });
}

function floatPosition() {
  const area = screen.getPrimaryDisplay().workArea;
  return { x: area.x + area.width - 86, y: area.y + Math.round(area.height * 0.35) };
}

function registerShortcut(candidates, callback) {
  for (const accelerator of candidates) {
    if (globalShortcut.register(accelerator, callback)) return accelerator.replace('Control', 'Ctrl');
  }
  return null;
}

function createWindows() {
  mainWindow = new BrowserWindow({
    width: 1120, height: 790, minWidth: 760, minHeight: 600,
    title: "Cortana", backgroundColor: "#05070a", show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      additionalArguments: process.argv.includes("--mic-off") ? ["--cortana-mic-off"] : [],
      contextIsolation: true, nodeIntegration: false, sandbox: true,
      autoplayPolicy: "no-user-gesture-required",
      webviewTag: false, backgroundThrottling: false,
    },
  });
  mainWindow.setMenuBarVisibility(false);
  mainWindow.webContents.on("console-message", (_event, details) => {
    if (details.level === "error") fs.appendFile(path.join(projectRoot, "tmp", "live-desktop-errors.log"), String(details.message).slice(0, 1500) + "\n").catch(() => {});
  });
  mainWindow.webContents.on("did-fail-load", (_event, code, description) => {
    fs.appendFile(path.join(projectRoot, "tmp", "live-desktop-errors.log"), `Load failed: ${code} ${description}\n`).catch(() => {});
  });
  mainWindow.webContents.once("did-finish-load", () => {
    if (!process.argv.includes("--background")) showMain();
  });
  protectWindow(mainWindow);
  mainWindow.on("close", (event) => {
    if (!quitting) { event.preventDefault(); mainWindow.hide(); }
  });
  mainWindow.webContents.on("render-process-gone", () => mainWindow.reload());
  mainWindow.once("ready-to-show", () => {
    if (!process.argv.includes("--background")) showMain();
  });
  mainWindow.loadURL(isDev ? "http://localhost:5173" : "app://cortana/index.html");
  floatingWindow = new BrowserWindow({
    ...floatPosition(), width: 72, height: 102,
    frame: false, transparent: true, resizable: false, maximizable: false,
    minimizable: false, alwaysOnTop: true, skipTaskbar: true, show: false,
    title: "Cortana quick access",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true, nodeIntegration: false, sandbox: true, webviewTag: false,
    },
  });
  protectWindow(floatingWindow);
  floatingWindow.setAlwaysOnTop(true, "floating");
  floatingWindow.once("ready-to-show", () => {
    if (!isSmokeTest && savedSettings.floatingButton !== false && !locked) floatingWindow.showInactive();
  });
  floatingWindow.on("close", (event) => {
    if (!quitting) { event.preventDefault(); floatingWindow.hide(); }
  });
  floatingWindow.loadURL("app://cortana/floating.html");
  screen.on("display-removed", () => {
    const position = floatPosition();
    floatingWindow?.setPosition(position.x, position.y);
  });
}

function createTray() {
  const size = 32;
  const rgba = Buffer.alloc(size * size * 4);
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const r = Math.hypot(x - 15.5, y - 15.5);
      const i = (y * size + x) * 4;
      if (r < 14 && r > 8) { rgba[i] = 255; rgba[i + 1] = 225; rgba[i + 2] = 55; rgba[i + 3] = 255; }
    }
  }
  tray = new Tray(nativeImage.createFromBitmap(rgba, { width: size, height: size }));
  tray.setToolTip(`Cortana${shortcuts.shortcut ? ` · ${shortcuts.shortcut}` : ''}`);
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "Open Cortana", click: showMain },
    { label: "Ask about this screen", click: () => captureAndShow().catch((e) => sendMain("cortana:error", e.message)) },
    { label: "Restart assistant", click: () => backend.restart() },
    { type: "separator" },
    { label: "Quit Cortana", click: () => app.quit() },
  ]));
  tray.on("click", toggleMain);
}

async function captureScreen() {
  if (locked) throw new Error("Unlock Windows before capturing your screen.");
  if (capturing) throw new Error("A screen capture is already in progress.");
  if (backend.state.status !== "ready") throw new Error("Wait for the local assistant to connect.");
  capturing = true;
  const restoreMain = mainWindow?.isVisible();
  const restoreFloating = floatingWindow?.isVisible();
  try {
    mainWindow?.hide();
    floatingWindow?.hide();
    await sleep(350); // Allow the compositor to reveal the underlying app.
    const response = await backend.fetch("/api/screen/capture", {
      method: "POST", signal: AbortSignal.timeout(15_000),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "The screen could not be captured.");
    return data;
  } finally {
    capturing = false;
    if (restoreMain && !locked) showMain();
    if (restoreFloating && savedSettings.floatingButton !== false && !locked) floatingWindow?.showInactive();
  }
}

async function captureAndShow() {
  const result = await captureScreen();
  showMain();
  sendMain("cortana:screen", result);
}

async function proxyRequest(event, id, route, options = {}) {
  requireMain(event);
  if (typeof id !== "string" || !/^[a-zA-Z0-9-]{1,80}$/.test(id)) throw new Error("Invalid request id.");
  const { pathname, method } = validateRequest(route, options);
  if (pathname === "/api/drafts/cancel") {
    for (const entry of controllers.values()) {
      if (/^\/api\/(?:drafts|integrations)\//.test(entry.pathname || "")
        && entry.pathname !== "/api/drafts/cancel") entry.controller.abort();
    }
  }
  if (controllers.has(id)) throw new Error("Request already exists.");
  const controller = new AbortController();
  const activeRequest = { controller, senderId: event.sender.id, pathname };
  controllers.set(id, activeRequest);
  const timeout = setTimeout(() => controller.abort(), pathname === "/api/chat" ? 240_000 : 90_000);
  try {
    const headers = {};
    let body = options.body;
    if (body !== undefined) {
      const data = JSON.parse(body);
      if (pathname === "/api/chat" && /^[a-zA-Z0-9_-]{1,80}$/.test(data.request_id || "")) activeRequest.taskId = data.request_id;
      headers["Content-Type"] = "application/json";
    }
    if (options.form) {
      body = new FormData();
      for (const entry of options.form) {
        if (entry.name === "audio" && entry.bytes) {
          const bytes = new Uint8Array(entry.bytes);
          if (bytes.byteLength > 15_000_000) throw new Error("Audio recording is too large.");
          if (!["audio/webm", "audio/webm;codecs=opus", "audio/ogg", "audio/ogg;codecs=opus", "audio/wav", "audio/mp4"].includes(entry.type)) throw new Error("Unsupported audio recording.");
          body.append("audio", new Blob([bytes], { type: entry.type }), "recording.webm");
        } else if (entry.name === "language" && typeof entry.value === "string" && entry.value.length < 30) {
          body.append(entry.name, entry.value);
        } else { throw new Error("Invalid audio upload."); }
      }
    }
    const response = await backend.fetch(route, { method, body, headers, signal: controller.signal });
    const contentType = response.headers.get("content-type") || "application/json";
    const bytes = new Uint8Array(await response.arrayBuffer());
    controller.signal.throwIfAborted();
    if (bytes.byteLength > 25_000_000) throw new Error("Assistant response is too large.");
    return { status: response.status, contentType, bytes };
  } catch (error) {
    if (controller.signal.aborted) return { cancelled: true };
    throw error;
  } finally {
    clearTimeout(timeout);
    controllers.delete(id);
  }
}

function installIpc() {
  ipcMain.handle("cortana:request", proxyRequest);
  ipcMain.handle("cortana:abort", (event, id) => {
    requireMain(event);
    const entry = controllers.get(id);
    if (entry?.senderId === event.sender.id) entry.controller.abort();
  });
  ipcMain.handle("cortana:state", (event) => { requireMain(event); return backend.state; });
  ipcMain.handle("cortana:restart", (event) => { requireMain(event); return backend.restart(); });
  ipcMain.handle("cortana:settings", (event) => { requireMain(event); return currentSettings(); });
  ipcMain.handle("cortana:set-settings", async (event, options) => {
    requireMain(event);
    if (typeof options?.openAtLogin === "boolean") applyLogin(options.openAtLogin);
    if (typeof options?.floatingButton === "boolean") {
      savedSettings.floatingButton = options.floatingButton;
      if (options.floatingButton) floatingWindow?.showInactive();
      else floatingWindow?.hide();
      await saveSettings();
    }
    return currentSettings();
  });
  ipcMain.handle("cortana:toggle", (event) => { senderRole(event); toggleMain(); });
  ipcMain.handle("cortana:hide", (event) => { requireMain(event); mainWindow.hide(); });
  ipcMain.handle("cortana:capture", (event) => { requireMain(event); return captureScreen(); });
  ipcMain.handle("cortana:quick-screen", (event) => { senderRole(event); return captureAndShow(); });
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", (_event, argv) => {
    if (argv.includes("--enable-autostart")) applyLogin(true);
    showMain();
  });
  app.whenReady().then(async () => {
    app.setAppUserModelId("com.cortana.assistant");
    try {
      const stored = JSON.parse(await fs.readFile(settingsPath(), "utf8"));
      savedSettings.floatingButton = stored.floatingButton !== false;
    } catch { /* New installation. */ }
    if (process.argv.includes("--enable-autostart")) applyLogin(true);
    protocol.handle("app", async (request) => {
      const asset = resolveAsset(request.url, distRoot, __dirname);
      if (!asset) return new Response("Not found", { status: 404 });
      try {
        const mime = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon" }[path.extname(asset)];
        if (!mime) return new Response("Not found", { status: 404 });
        return new Response(await fs.readFile(asset), {
          headers: { "Content-Type": mime, "Content-Security-Policy": csp, "X-Content-Type-Options": "nosniff" },
        });
      } catch { return new Response("Not found", { status: 404 }); }
    });
    session.defaultSession.setPermissionRequestHandler((webContents, permission, callback, details) => {
      const trusted = webContents === mainWindow?.webContents && trustedUrl(details.requestingUrl || webContents.getURL(), isDev);
      callback(!locked && trusted && permission === "media"
        && details.mediaTypes?.length > 0 && details.mediaTypes.every((type) => type === "audio"));
    });
    session.defaultSession.setPermissionCheckHandler((webContents, permission, _origin, details) => (
      !locked && webContents === mainWindow?.webContents && trustedUrl(details.requestingUrl || webContents.getURL(), isDev)
      && permission === "media" && details.mediaType === "audio"
    ));
    installIpc();
    createWindows();
    backend.on("state", (state) => sendMain("cortana:state-changed", state));
    backend.start().catch(() => backend.update("error", "The local assistant could not start."));
    if (!isSmokeTest) {
      shortcuts.shortcut = registerShortcut(["Control+Alt+Space", "Control+Alt+Shift+C"], toggleMain);
      shortcuts.screenShortcut = registerShortcut(["Control+Alt+S", "Control+Alt+Shift+S"], () => captureAndShow().catch((e) => { showMain(); sendMain("cortana:error", e.message); }));
      createTray();
    }
    powerMonitor.on("lock-screen", () => {
      locked = true;
      sendMain("cortana:locked", true);
      backend.fetch("/api/drafts/cancel", { method: "POST", signal: AbortSignal.timeout(10_000) }).catch(() => {});
      for (const { controller, taskId } of controllers.values()) {
        if (taskId) backend.fetch(`/api/tasks/${taskId}/cancel`, { method: "POST", signal: AbortSignal.timeout(3000) }).catch(() => {});
        controller.abort();
      }
      mainWindow?.hide();
      floatingWindow?.hide();
    });
    powerMonitor.on("unlock-screen", () => {
      locked = false;
      sendMain("cortana:locked", false);
      if (savedSettings.floatingButton !== false) floatingWindow?.showInactive();
    });
  }).catch((error) => {
    console.error("Cortana desktop could not initialize:", error.message);
    app.quit();
  });
}

app.on("before-quit", () => {
  quitting = true;
  for (const { controller } of controllers.values()) controller.abort();
  backend.stop();
  globalShortcut.unregisterAll();
});
app.on("window-all-closed", () => { if (quitting) app.quit(); });
app.on("activate", showMain);
// Only the Node integration test process can read these references; they are
// never placed on a renderer bridge or opened on a debug network port.
module.exports = { getWindows: () => ({ mainWindow, floatingWindow }), backend };
