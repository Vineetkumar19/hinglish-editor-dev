"""Central action policy.

LOW/MEDIUM actions are bounded reads, approved application/folder launches
and ordinary assistant memory operations. HIGH actions require a one-use
review: code edits/undo, generic mouse/keyboard input, model-selected web
navigation, and communication drafts that put text in a provider URL.

The dedicated message draft tool requires an explicit communication request.
Sending is not a capability. Generic input cannot control protected message
windows, even after approval; the human presses Send in the provider's app.

Only the deterministic command parser can authorize an exact user-requested
website launch without another card. CRITICAL capabilities are unavailable.
The registered tools, validated arguments, path guards and review snapshots
enforce the policy; a prompt or a tool-name blacklist alone cannot do that.
"""

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Decision(str, Enum):
    ALLOWED = "allowed"
    NEEDS_CONFIRMATION = "needs_confirmation"
    DENIED = "denied"


# Capability names that must never be registered as tools. This is a
# tripwire, not the main defence — the main defence is simply not writing
# these tools. If one ever appears (added carelessly, or by a future
# contributor), the registry refuses it at import time rather than
# silently exposing it to the model.
FORBIDDEN_TOOL_NAMES = {
    "run_command", "run_shell", "execute", "exec", "eval", "system",
    "powershell", "cmd", "bash", "shell", "subprocess",
    "delete_file", "delete_folder", "remove_file", "rmdir", "format_disk",
    "edit_registry", "registry_write", "disable_defender", "kill_process",
    "install_package", "uninstall", "shutdown", "restart_pc",
}


def check(risk_level: RiskLevel) -> Decision:
    if risk_level == RiskLevel.LOW:
        return Decision.ALLOWED
    if risk_level == RiskLevel.MEDIUM:
        # Narrow assistant-local bookkeeping, audited like every tool.
        return Decision.ALLOWED
    if risk_level == RiskLevel.HIGH:
        return Decision.NEEDS_CONFIRMATION
    return Decision.DENIED  # CRITICAL — always blocked, no exceptions.
