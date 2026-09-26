window.HINGLISH_BRIDGE = "http://127.0.0.1:8765";
try {
  const fs=require('fs'),path=require('path');
  const file=path.join(process.env.LOCALAPPDATA,'Hinglish Editor','install.json');
  window.HINGLISH_APP_ROOT=JSON.parse(fs.readFileSync(file,'utf8')).root;
} catch (_) {
  window.HINGLISH_APP_ROOT = "E:\\Hinglish Editor DEV";
}
