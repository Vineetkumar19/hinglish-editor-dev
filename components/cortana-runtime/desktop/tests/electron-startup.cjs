// Windows-only, isolated login registration test. The temporary entry points
// to an inert fixture; no real Cortana instance is started or stopped.
const { app } = require("electron");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { execFileSync, spawn } = require("node:child_process");
const { loginOptions, loginEntryEnabled } = require("../electron/security.cjs");

const root = path.resolve(__dirname, "..", "..");
const python = path.join(root, "agent", ".venv", "Scripts", "python.exe");
const testName = `CortanaStartupTest-${process.pid}`;
const fixtureRoot = path.join(root, "tmp", `startup verification ${process.pid}`);
const fixtureApp = path.join(fixtureRoot, "app with spaces");
const resultFile = path.join(fixtureRoot, "args.json");
app.setPath("userData", path.join(fixtureRoot, "controller-profile"));
const registryCode = `
import ctypes, json, sys, winreg
name = sys.argv[1]
assert name.startswith("CortanaStartupTest-")
with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run") as key:
    command = winreg.QueryValueEx(key, name)[0]
parse = ctypes.windll.shell32.CommandLineToArgvW
parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
count = ctypes.c_int()
args = parse(command, ctypes.byref(count))
try:
    print(json.dumps({"command": command, "args": [args[i] for i in range(count.value)]}))
finally:
    ctypes.windll.kernel32.LocalFree(args)
`;
const cleanupCode = `
import sys, winreg
name = sys.argv[1]
assert name.startswith("CortanaStartupTest-")
for subkey in [r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", r"Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\StartupApproved\\Run"]:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, name)
    except FileNotFoundError:
        pass
`;

app.whenReady().then(async () => {
  let settings;
  try {
    assert.equal(process.platform, "win32");
    await fs.mkdir(fixtureApp, { recursive: true });
    await fs.writeFile(path.join(fixtureApp, "package.json"), JSON.stringify({ name: "cortana-startup-fixture", main: "main.cjs" }));
    await fs.writeFile(path.join(fixtureApp, "main.cjs"), `
const { app } = require("electron");
const fs = require("node:fs");
app.setPath("userData", ${JSON.stringify(path.join(fixtureRoot, "fixture-profile"))});
app.whenReady().then(() => { fs.writeFileSync(${JSON.stringify(resultFile)}, JSON.stringify(process.argv)); app.quit(); });
`);
    settings = { ...loginOptions(process.execPath, fixtureApp, false), name: testName, openAtLogin: true, enabled: true };
    app.setLoginItemSettings(settings);
    const registered = JSON.parse(execFileSync(python, ["-c", registryCode, testName], { encoding: "utf8", windowsHide: true }));
    assert.deepEqual(registered.args, [process.execPath, fixtureApp, "--background"]);
    const loginStatus = app.getLoginItemSettings({ path: process.execPath, args: settings.args });
    assert.equal(loginEntryEnabled(loginStatus, process.execPath, fixtureApp, false, testName), true);
    // Launch exactly the arguments decoded from the actual Windows Run entry.
    // The inert fixture only records argv and exits, without creating windows.
    await new Promise((resolve, reject) => {
      const child = spawn(registered.args[0], registered.args.slice(1), { windowsHide: true, stdio: "ignore" });
      const timer = setTimeout(() => { child.kill(); reject(new Error("Startup fixture timed out.")); }, 15_000);
      child.once("error", (error) => { clearTimeout(timer); reject(error); });
      child.once("exit", (code) => {
        clearTimeout(timer);
        if (code === 0) resolve();
        else reject(new Error(`Startup fixture exited ${code}`));
      });
    });
    const actualArgs = JSON.parse(await fs.readFile(resultFile, "utf8"));
    assert.deepEqual(actualArgs.slice(1), [fixtureApp, "--background"]);
    app.setLoginItemSettings({ ...settings, enabled: false });
    assert.equal(loginEntryEnabled(app.getLoginItemSettings({ path: process.execPath, args: settings.args }), process.execPath, fixtureApp, false, testName), false);
    console.log(JSON.stringify({ status: "passed", registryCommand: registered.command, windowsArgv: registered.args, actualElectronArgv: actualArgs, namedEntryStatusAndDisableVerified: true, productionInstanceUntouched: true }, null, 2));
  } catch (error) {
    console.error("STARTUP REGISTRATION FAILED:", error.message);
    process.exitCode = 1;
  } finally {
    if (settings) app.setLoginItemSettings({ ...settings, openAtLogin: false });
    try {
      execFileSync(python, ["-c", cleanupCode, testName], { windowsHide: true });
      console.log("Temporary startup registration removed.");
    } catch (error) {
      console.error("Temporary startup cleanup failed:", error.message);
      process.exitCode = 1;
    }
    app.exit(process.exitCode || 0);
  }
});
