"""Cortana tool implementations — Windows/file/browser actions the agent
can take, per spec's top-level tools/ folder. Each module here defines
plain Python functions; agent/core/tool_registry.py is what wraps them
with the @tool decorator, schema, and permission enforcement.

Kept as a package separate from agent/ so it matches the spec's folder
layout (agent/ = runtime/orchestration, tools/ = the actual actions).
"""
