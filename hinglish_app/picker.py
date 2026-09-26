"""Native picker helper, intentionally run in its own main-thread process."""
import sys
import tkinter as tk
from tkinter import filedialog


def main(argv=None):
    kind = (argv or sys.argv[1:] or ['folder'])[0]
    window = tk.Tk()
    window.withdraw()
    window.attributes('-topmost', True)
    window.update_idletasks()
    try:
        if kind == 'script':
            path = filedialog.askopenfilename(
                parent=window,
                title='Choose your script',
                filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            )
        else:
            path = filedialog.askdirectory(
                parent=window,
                title='Choose folder containing your videos',
                mustexist=True,
            )
        sys.stdout.write(path or '')
        sys.stdout.flush()
        return 0
    finally:
        window.destroy()


if __name__ == '__main__':
    raise SystemExit(main())
