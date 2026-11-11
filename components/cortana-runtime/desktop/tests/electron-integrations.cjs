// Renderer + real preload/IPC validation against an in-process fake backend.
// No browser account, model, microphone, desktop capture or message is accessed.
const { app, powerMonitor } = require("electron");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
process.env.CORTANA_DESKTOP_TEST = "1";
process.env.CORTANA_DEV = "0";
app.setAppPath(root);
app.setPath("userData", path.resolve(root, "..", "tmp", "integrations-ui-profile"));
const desktop = require("../electron/main.cjs");
const requests = [];
const expectedBody = "  Hi Alex!\nKal milte hain at 7.\n";
let statusUnavailable = true;
let holdPrepare = false;
let releasePrepare;
desktop.backend.start = async () => desktop.backend.update("ready", "Test fixture connected");
desktop.backend.fetch = async (route, options = {}) => {
  const body = options.body ? JSON.parse(options.body) : null;
  requests.push({ route, method: options.method || "GET", body });
  let data;
  if (route === "/api/status") {
    data = { status: "ready", local_only: true, cloud_enabled: false, brain: { available: true, loaded: true, model: "fixture" } };
  } else if (route === "/api/integrations/status") {
    if (statusUnavailable) return new Response(JSON.stringify({ detail: "Connections are not ready yet." }), { status: 503, headers: { "Content-Type": "application/json" } });
    data = { browser: { status: "ready", note: "Controlled UI fixture" }, integrations: [
      { platform: "whatsapp", status: "available", transport: "application", note: "Installed app preferred." },
      { platform: "gmail", status: "available", transport: "chrome", note: "Uses your normal Chrome profile." },
      { platform: "instagram", status: "available", transport: "application", note: "Installed app preferred." },
    ] };
  } else if (route === "/api/integrations/whatsapp/open") {
    data = { platform: "whatsapp", status: "opened", transport: "application", note: "Opened your installed WhatsApp." };
  } else if (route === "/api/drafts/prepare") {
    if (body.body !== expectedBody || body.recipient !== "Alex") throw new Error("The UI changed exact draft content.");
    if (holdPrepare) {
      await new Promise((resolve) => { releasePrepare = resolve; });
      data = { platform: "whatsapp", draft_id: "fixture-cancelled", status: "draft_ready", recipient: "LATE RESULT MUST NOT APPEAR", preview: { body: expectedBody } };
    } else {
    data = { platform: "whatsapp", draft_id: "fixture-draft-1", status: "needs_app", recipient: "Alex", preview: { body: body.body }, note: "Select the intended conversation in your installed app." };
    }
  } else if (route === "/api/drafts/cancel") {
    // Deliberately let the old prepare resolve after cancellation. Main must
    // discard that stale success even if a worker ignores transport abort.
    releasePrepare?.();
    releasePrepare = null;
    data = { status: "cancelled", note: "Draft preparation stopped." };
  } else if (route === "/api/drafts/fixture-draft-1/resume") {
    data = { platform: "whatsapp", draft_id: "fixture-draft-1", status: "choose_recipient", recipient: "Alex", preview: { body: expectedBody }, note: "Two contacts matched.", candidates: [
      { id: "alex-work", label: "Alex", detail: "Work · ending 1122" },
      { id: "alex-family", label: "Alex", detail: "Family · ending 7788" },
    ] };
  } else if (route === "/api/drafts/fixture-draft-1/select") {
    if (body.candidate_id !== "alex-family") throw new Error("Wrong contact selected.");
    data = { platform: "whatsapp", draft_id: "fixture-draft-1", status: "draft_ready", recipient: "Alex · Family", preview: { body: expectedBody }, note: "The exact message is in the compose box." };
  } else if (route === "/api/reminders/due") {
    data = { due: [] };
  } else {
    throw new Error(`Unexpected test request: ${route}`);
  }
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
};
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const timer = setTimeout(() => { process.exitCode = 1; console.error("INTEGRATIONS UI TIMEOUT"); app.quit(); }, 25_000);
const errors = [];
app.on("web-contents-created", (_event, contents) => contents.on("console-message", (_event, details) => {
  if (details.level === "error") errors.push(details.message);
}));

app.whenReady().then(async () => {
  try {
    let win;
    for (let i = 0; i < 60; i += 1) {
      win = desktop.getWindows().mainWindow;
      if (win && !win.webContents.isLoading() && desktop.backend.state.status === "ready") break;
      await sleep(100);
    }
    if (!win) throw new Error("No test renderer.");
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Connect').click()`);
    await sleep(200);
    let text = await win.webContents.executeJavaScript("document.body.innerText");
    if (!text.includes("Connections are not ready yet.")) throw new Error("Unavailable integration API was not reported.");
    statusUnavailable = false;
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Check status').click()`);
    await sleep(150);
    text = await win.webContents.executeJavaScript("document.body.innerText");
    if (!text.includes("Ready to open") || !text.includes("Installed app preferred.") || !text.includes("normal Chrome")) throw new Error("App routing states not rendered.");
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Open WhatsApp').click()`);
    await sleep(100);
    await win.webContents.executeJavaScript(`(() => {
      const input = document.querySelector('[name="draft-recipient"]');
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'Alex');
      input.dispatchEvent(new Event('input', {bubbles:true}));
      const area = document.querySelector('[name="draft-body"]');
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(area, ${JSON.stringify(expectedBody)});
      area.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await sleep(100);
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Prepare draft').click()`);
    await sleep(150);
    text = await win.webContents.executeJavaScript("document.body.innerText");
    if (!text.includes("Select the intended conversation in your installed app.")) throw new Error("Native app recovery was not rendered.");
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Continue in selected conversation').click()`);
    await sleep(150);
    text = await win.webContents.executeJavaScript("document.body.innerText");
    if (!text.includes("Choose the recipient") || !text.includes("ending 7788")) throw new Error("Recipient choices not rendered.");
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('.candidate-button')).find(b => b.textContent.includes('7788')).click()`);
    await sleep(150);
    const result = await win.webContents.executeJavaScript(`({
      text:document.body.innerText,
      draftBody:document.querySelector('.draft-body').textContent,
      sendButtons:Array.from(document.querySelectorAll('button')).filter(b => /^send$/i.test(b.textContent.trim())).length
    })`);
    if (!result.text.includes("Draft ready for your review") || !result.text.includes("The message has not been sent.") || result.sendButtons || result.draftBody !== expectedBody) throw new Error("Draft review did not preserve the manual-send contract.");
    holdPrepare = true;
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Prepare draft').click()`);
    await sleep(150);
    if (!releasePrepare) throw new Error("Controlled draft operation did not start.");
    const canStop = await win.webContents.executeJavaScript(`!document.querySelector('.stop-btn').disabled`);
    if (!canStop) throw new Error("Global Stop is unavailable for a Connect draft.");
    await win.webContents.executeJavaScript(`document.querySelector('.stop-btn').click()`);
    await sleep(200);
    text = await win.webContents.executeJavaScript("document.body.innerText");
    if (text.includes("LATE RESULT MUST NOT APPEAR") || !requests.some((request) => request.route === "/api/drafts/cancel")) throw new Error("Stop did not cancel and discard the late draft response.");
    if (text.includes("Draft ready for your review") || !text.includes("Draft session stopped.")) throw new Error("Stop retained an expired draft action.");
    await win.webContents.executeJavaScript(`Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'Prepare draft').click()`);
    await sleep(150);
    if (!releasePrepare) throw new Error("Controlled lock draft operation did not start.");
    const cancellationsBeforeLock = requests.filter((request) => request.route === "/api/drafts/cancel").length;
    powerMonitor.emit("lock-screen");
    await sleep(150);
    text = await win.webContents.executeJavaScript("document.body.innerText");
    if (text.includes("LATE RESULT MUST NOT APPEAR")) throw new Error("Lock allowed a late draft result.");
    if (requests.filter((request) => request.route === "/api/drafts/cancel").length <= cancellationsBeforeLock) throw new Error("Windows lock did not cancel the browser worker.");
    powerMonitor.emit("unlock-screen");
    if (requests.some((request) => /\/send(?:\/|$)/.test(request.route))) throw new Error("The UI attempted to send.");
    if (errors.length) throw new Error(`Renderer errors: ${errors.join("; ")}`);
    console.log(JSON.stringify({
      status: "passed", exactMessagePreserved: true, contactSelected: "alex-family",
      manualSendOnly: true, noAccountsAccessed: true, stopCancelsDraft: true,
      lockCancelsDraft: true, lateDraftResponsesDiscarded: true,
      routes: requests.map((request) => `${request.method} ${request.route}`), rendererErrors: errors,
    }, null, 2));
  } catch (error) {
    console.error("INTEGRATIONS UI FAILED:", error.message);
    process.exitCode = 1;
  } finally {
    clearTimeout(timer);
    app.quit();
  }
});
