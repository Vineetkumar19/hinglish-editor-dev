# Cortana selected workspace extension

This unpacked MV3 extension is local to this checkout. It is not installed yet.
It requests tabs, activeTab, scripting, storage and nativeMessaging; YouTube host
access is optional and requested separately. It has no history, cookies,
password, downloads or external messaging capability. Incognito is excluded.

After the owner approves installation, load this directory with the browser's
Load unpacked control. Copy the actual extension ID and register the local host:

```
D:\Cortana\agent\.venv\Scripts\python.exe D:\Cortana\scripts\register_browser_host.py EXTENSION_ID --browser chrome
```

Use `--browser brave` for Brave and independently verify that route. In the
extension popup choose the actual browser, a unique profile label, and Connect.
Use that label in Cortana Workbench. Select only the desired tabs (highlighted
tabs in the last focused browser window), then choose Capture selected browser
tabs. Snapshots are explicit; no background browsing-history collection occurs.

Restoration reuses one exact matching tab. Multiple matches stop for selection.
New YouTube tabs begin muted and pause/seek only with the necessary permission.
Failure to verify video state is reported, never counted as a successful restore.
The extension has no messaging send action.

Native host registration is per Windows user. It is not a security boundary
against software already executing as that same user. The host validates the
origin against its installed manifest and does not expose a network listener.

Reviewed API references: [Chrome native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)
and [tabs](https://developer.chrome.com/docs/extensions/reference/api/tabs).
