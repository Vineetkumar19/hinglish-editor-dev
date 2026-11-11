"""Imports every tools/*.py module so their @tool-decorated functions
register themselves into core.tool_registry.REGISTRY.

The tools/ package lives at the project root (a sibling of agent/, per
the spec's folder layout), not inside agent/ itself, so it isn't on
sys.path by default when uvicorn runs from inside agent/ — this adds it
before importing.
"""

import sys

from core.config import ROOT_DIR

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def load_all_tools():
    from tools import (  # noqa: F401
        apps,
        code,
        communication,
        computer,
        dev,
        documents,
        files,
        folders,
        memory,
        message_drafts,
        openpath,
        reminders,
        screenshot,
        weather,
        web,
        local_architecture,
    )
