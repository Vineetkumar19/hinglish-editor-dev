const { contextBridge, ipcRenderer } = require("electron");
const listen = (channel, callback) => {
  const listener = (_event, value) => callback(value);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
};
contextBridge.exposeInMainWorld("cortana", {
  startMuted: process.argv.includes("--cortana-mic-off"),
  request: (id, route, options) => ipcRenderer.invoke("cortana:request", id, route, options),
  abortRequest: (id) => ipcRenderer.invoke("cortana:abort", id),
  getState: () => ipcRenderer.invoke("cortana:state"),
  restart: () => ipcRenderer.invoke("cortana:restart"),
  getSettings: () => ipcRenderer.invoke("cortana:settings"),
  setSettings: (options) => ipcRenderer.invoke("cortana:set-settings", options),
  hide: () => ipcRenderer.invoke("cortana:hide"),
  toggle: () => ipcRenderer.invoke("cortana:toggle"),
  captureScreen: () => ipcRenderer.invoke("cortana:capture"),
  quickScreen: () => ipcRenderer.invoke("cortana:quick-screen"),
  onState: (callback) => listen("cortana:state-changed", callback),
  onScreen: (callback) => listen("cortana:screen", callback),
  onLocked: (callback) => listen("cortana:locked", callback),
  onError: (callback) => listen("cortana:error", callback),
});
