const path = require("node:path");

// No server address, bearer token, arbitrary IPC method or arbitrary fetch is
// exposed to the renderer. Every route and verb is checked again in main.
const ROUTES = [
  ["GET", /^\/api\/local\/state$/],
  ["GET", /^\/api\/local\/tasks\/due$/],
  ["POST", /^\/api\/local\/(?:action|capture-browser|stop)$/],
  ["GET", /^\/api\/(?:health|status|capabilities)$/],
  ["POST", /^\/api\/(?:chat|stt|stt-preview|wake-check|tts)$/],
  ["POST", /^\/api\/tasks\/[a-zA-Z0-9_-]{1,80}\/cancel$/],
  ["POST", /^\/api\/confirm\/[1-9]\d*$/],
  ["GET", /^\/api\/memory\/facts$/],
  ["DELETE", /^\/api\/memory\/facts\/[1-9]\d*$/],
  ["GET", /^\/api\/reminders(?:\/due)?$/],
  ["POST", /^\/api\/reminders\/[1-9]\d*\/complete$/],
  ["GET", /^\/api\/audit\/log$/],
  ["GET", /^\/api\/integrations\/status$/],
  ["POST", /^\/api\/integrations\/(?:whatsapp|gmail|instagram)\/open$/],
  ["POST", /^\/api\/drafts\/(?:prepare|cancel)$/],
  ["POST", /^\/api\/drafts\/[a-zA-Z0-9_-]{1,100}\/(?:select|resume)$/],
];

function validateRequest(route, options = {}) {
  if (typeof route !== "string" || route.length > 300 || /[%\\#\r\n]/.test(route)) {
    throw new Error("Invalid assistant request.");
  }
  const [pathname, query] = route.split("?");
  const method = String(options.method || "GET").toUpperCase();
  if (!ROUTES.some(([verb, pattern]) => verb === method && pattern.test(pathname))) {
    throw new Error("This assistant request is not allowed.");
  }
  if (query && (method !== "GET" || !/^(?:limit=\d{1,3}|include_done=(?:true|false))$/.test(query))) {
    throw new Error("Invalid assistant request parameters.");
  }
  if (options.body !== undefined && typeof options.body !== "string") {
    throw new Error("Expected a JSON request body.");
  }
  if (options.body?.length > 100_000) throw new Error("Request is too large.");
  if (options.form && !["/api/stt", "/api/stt-preview", "/api/wake-check"].includes(pathname)) {
    throw new Error("File uploads are only accepted by speech recognition.");
  }
  return { route, pathname, method };
}

function trustedUrl(url, isDev = false, role = "main") {
  try {
    const parsed = new URL(url);
    if (parsed.username || parsed.password) return false;
    if (role === "floating") return parsed.protocol === "app:" && parsed.host === "cortana"
      && parsed.pathname === "/floating.html";
    if (parsed.protocol === "app:" && parsed.host === "cortana") {
      return parsed.pathname === "/" || parsed.pathname === "/index.html";
    }
    return isDev && parsed.origin === "http://localhost:5173"
      && (parsed.pathname === "/" || parsed.pathname === "/index.html");
  } catch {
    return false;
  }
}

function resolveAsset(url, distRoot, electronRoot) {
  const parsed = new URL(url);
  if (parsed.protocol !== "app:" || parsed.host !== "cortana" || parsed.search) return null;
  let decoded;
  try { decoded = decodeURIComponent(parsed.pathname); } catch { return null; }
  if (decoded.includes("\\") || decoded.includes("\0")) return null;
  const floatingFiles = new Set(["/floating.html", "/floating.css", "/floating.js"]);
  const base = floatingFiles.has(decoded) ? electronRoot : distRoot;
  const name = decoded === "/" ? "/index.html" : decoded;
  const candidate = path.resolve(base, "." + name);
  const relative = path.relative(base, candidate);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return null;
  return candidate;
}

function loginOptions(execPath, appPath, packaged) {
  return {
    path: execPath,
    // Electron's Windows command-line builder quotes/escapes each argument.
    // Supplying quote characters here makes them part of the application path.
    args: packaged ? ["--background"] : [appPath, "--background"],
  };
}

function loginEntryEnabled(login, execPath, appPath, packaged, name = "Cortana") {
  const samePath = (left, right) => typeof left === "string" && typeof right === "string"
    && path.win32.normalize(left).toLowerCase() === path.win32.normalize(right).toLowerCase();
  // openAtLogin checks Electron's default entry name. Our explicit name must
  // be looked up in launchItems, where Windows startup-disable state is read.
  return Boolean(login.launchItems?.some((item) => item.name === name
    && item.scope === "user" && item.enabled && samePath(item.path, execPath)
    && (packaged || samePath(item.args?.[0], appPath))));
}

module.exports = { validateRequest, trustedUrl, resolveAsset, loginOptions, loginEntryEnabled };
