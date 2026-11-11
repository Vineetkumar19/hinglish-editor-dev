"""One explicit, read-only Explorer selection; no clipboard or keyboard access."""
import argparse
import json
import ntpath
from .adobe_clipboard import usable_media


def selected_paths(windows, window_handle=0):
    paths = []
    for window in windows:
        if ntpath.basename(str(window.FullName)).lower() != 'explorer.exe':
            continue
        if window_handle and int(window.HWND) != window_handle:
            continue
        for item in window.Document.SelectedItems():
            if item.IsFileSystem and not item.IsFolder:
                path = str(item.Path)
                if path not in paths:
                    paths.append(path)
    if not usable_media(paths):
        raise ValueError('Select one image or video in one Explorer window.')
    return paths


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--window-handle', type=int, default=0)
    args = parser.parse_args()
    if args.window_handle < 0:
        raise ValueError('Select the Explorer window again.')
    from comtypes.client import CreateObject
    shell = CreateObject('Shell.Application', dynamic=True)
    print(json.dumps({'paths': selected_paths(shell.Windows(), args.window_handle)}))


if __name__ == '__main__':
    main()
