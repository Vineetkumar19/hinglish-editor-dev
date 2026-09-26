"""Local UI and editor bridge for the Hinglish editing engines."""

# The DEV copy uses its own port so it never collides with the original app (8765),
# which Premiere/Resolve may start automatically through the older plugin install.
DEFAULT_PORT = 8766
BRIDGE_URL = f'http://127.0.0.1:{DEFAULT_PORT}'
