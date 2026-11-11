"""Minimal declarative schema validation - the Pydantic role, stdlib only.

Used to constrain LLM output (the blueprint's "strict Pydantic schema") and to
validate the resume YAML before it is rendered.

A schema is a dict::

    {"type": "object",
     "required": ["name"],
     "properties": {
        "name":  {"type": "string", "min_length": 1, "max_length": 80},
        "score": {"type": "number", "minimum": 0, "maximum": 1, "default": 0},
        "tags":  {"type": "array", "items": {"type": "string"}, "max_items": 10},
        "kind":  {"type": "string", "enum": ["a", "b"]},
     }}
"""
from __future__ import annotations

from typing import Any

TYPES = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


class ValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _coerce(value: Any, want: str) -> Any:
    """Nudge obvious near-misses into the right type (LLMs emit "3" for 3)."""
    if want == "number" and isinstance(value, str):
        try:
            return float(value) if "." in value or "e" in value.lower() else int(value)
        except ValueError:
            return value
    if want == "integer" and isinstance(value, (str, float)):
        try:
            f = float(value)
            return int(f) if f == int(f) else value
        except (ValueError, TypeError):
            return value
    if want == "boolean" and isinstance(value, str):
        low = value.strip().lower()
        if low in ("true", "yes", "1"):
            return True
        if low in ("false", "no", "0"):
            return False
    if want == "string" and isinstance(value, (int, float)):
        return str(value)
    if want == "array" and isinstance(value, (str, dict)):
        return [value]
    return value


def validate(data: Any, schema: dict, path: str = "$", coerce: bool = True,
             errors: list[str] | None = None) -> Any:
    top = errors is None
    errs: list[str] = [] if errors is None else errors
    want = schema.get("type")

    if want:
        if coerce:
            data = _coerce(data, want)
        expected = TYPES.get(want)
        if expected is not None:
            # bool is a subclass of int; keep them distinct
            if want in ("number", "integer") and isinstance(data, bool):
                errs.append(f"{path}: expected {want}, got boolean")
            elif not isinstance(data, expected):
                errs.append(f"{path}: expected {want}, got "
                            f"{type(data).__name__}")
                if top:
                    raise ValidationError(errs)
                return data

    if "enum" in schema and data not in schema["enum"]:
        errs.append(f"{path}: {data!r} is not one of {schema['enum']}")

    if isinstance(data, str):
        if "min_length" in schema and len(data) < schema["min_length"]:
            errs.append(f"{path}: shorter than {schema['min_length']} chars")
        if "max_length" in schema and len(data) > schema["max_length"]:
            errs.append(f"{path}: longer than {schema['max_length']} chars")

    if isinstance(data, (int, float)) and not isinstance(data, bool):
        if "minimum" in schema and data < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and data > schema["maximum"]:
            errs.append(f"{path}: above maximum {schema['maximum']}")

    if isinstance(data, list):
        if "min_items" in schema and len(data) < schema["min_items"]:
            errs.append(f"{path}: needs at least {schema['min_items']} items")
        if "max_items" in schema and len(data) > schema["max_items"]:
            errs.append(f"{path}: at most {schema['max_items']} items allowed")
        item_schema = schema.get("items")
        if item_schema:
            data = [validate(v, item_schema, f"{path}[{i}]", coerce, errs)
                    for i, v in enumerate(data)]

    if isinstance(data, dict):
        props: dict = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in data or data[key] in (None, ""):
                errs.append(f"{path}.{key}: required field is missing")
        out = {}
        for key, value in data.items():
            sub = props.get(key)
            if sub is None:
                if schema.get("additional_properties", True):
                    out[key] = value
                # else: silently drop unknown keys
                continue
            out[key] = validate(value, sub, f"{path}.{key}", coerce, errs)
        for key, sub in props.items():
            if key not in out and "default" in sub:
                out[key] = sub["default"]
        data = out

    if top and errs:
        raise ValidationError(errs)
    return data


def describe(schema: dict, indent: int = 0) -> str:
    """Render a schema as compact instructions for an LLM prompt."""
    pad = "  " * indent
    t = schema.get("type", "any")
    if t == "object":
        lines = []
        req = set(schema.get("required", []))
        for k, v in schema.get("properties", {}).items():
            flag = " (required)" if k in req else ""
            desc = f" - {v['description']}" if v.get("description") else ""
            if v.get("type") in ("object", "array"):
                lines.append(f"{pad}  {k}{flag}:{desc}")
                lines.append(describe(v, indent + 2))
            else:
                enum = f" one of {v['enum']}" if "enum" in v else ""
                lines.append(f"{pad}  {k}{flag}: {v.get('type','any')}{enum}{desc}")
        return "\n".join(lines)
    if t == "array":
        return f"{pad}  array of:\n" + describe(schema.get("items", {}), indent + 1)
    return f"{pad}  {t}"
