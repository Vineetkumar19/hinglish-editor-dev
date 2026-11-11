"""External applications must not inherit the desktop's session credential."""
import os
import subprocess
import sys


def public_environment() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("CORTANA_")
    }


def shell_open(target: str):
    """Use Windows file/protocol associations without leaking agent secrets."""
    subprocess.run(
        [sys.executable, "-I", "-c", "import os,sys; os.startfile(sys.argv[1])", target],
        env=public_environment(), shell=False, check=True, timeout=10,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
