"""Register this checkout's native host for a reviewed unpacked extension ID.

Run explicitly after the owner installs the extension; no automatic extension
installation, permission grants or browser-profile changes occur here.
"""
import argparse
import json
import re
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('extension_id')
    parser.add_argument('--browser', choices=['chrome','brave'], required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-p]{32}', args.extension_id):
        parser.error('Expected the actual 32-character Chrome/Brave extension ID.')
    root = Path(__file__).resolve().parents[1]
    folder = root / 'browser-extension'
    launcher = folder / 'native-host.cmd'
    launcher.write_text('@echo off\n"' + str(root / 'agent/.venv/Scripts/python.exe') + '" "' +
                        str(root / 'scripts/browser_native_host.py') + '" %*\n', encoding='utf-8')
    manifest = folder / 'native-host.json'
    origins = []
    if manifest.exists():
        origins = json.loads(manifest.read_text())['allowed_origins']
    origin = 'chrome-extension://' + args.extension_id + '/'
    if origin not in origins:
        origins.append(origin)
    manifest.write_text(json.dumps({'name':'com.cortana.workspace','description':'Cortana local workspace broker',
        'path':str(launcher),'type':'stdio','allowed_origins':origins}, indent=2), encoding='utf-8')
    import winreg
    brand = r'Google\Chrome' if args.browser == 'chrome' else r'BraveSoftware\Brave-Browser'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, 'Software\\' + brand + r'\NativeMessagingHosts\com.cortana.workspace') as key:
        winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
    print('Registered native host for', args.browser, origin)


if __name__ == '__main__':
    main()
