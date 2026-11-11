"""A small YAML subset - enough for config, target lists and resume data.

PyYAML is not a dependency of this project, so this module implements the part
of YAML that configuration files actually use:

  * nested block mappings and sequences (indentation based)
  * scalars: strings, ints, floats, booleans, null, dates left as strings
  * single and double quoted strings, with escapes in double quotes
  * flow collections: [a, b] and {k: v}
  * block scalars: | (literal) and > (folded), with - and + chomping
  * comments, document markers (---), and blank lines

It does not support anchors, aliases, tags, multi-document streams or complex
keys. `load_yaml` raises YamlError with a line number when it meets one.
"""
from __future__ import annotations

import re
from typing import Any

__all__ = ["load_yaml", "dump_yaml", "YamlError"]


class YamlError(ValueError):
    def __init__(self, msg: str, line: int = 0):
        super().__init__(f"line {line}: {msg}" if line else msg)
        self.line = line


_UNSUPPORTED = re.compile(r"^\s*(?:&\w+|\*\w+|!!?\w+)")


# --------------------------------------------------------------------------
# scalars
# --------------------------------------------------------------------------
_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?$")

_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", '"': '"',
            "\\": "\\", "/": "/", "b": "\b", "f": "\f"}


def _unescape(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "u" and i + 5 < len(s) + 1:
                try:
                    out.append(chr(int(s[i + 2:i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_scalar(raw: str, line: int = 0) -> Any:
    s = raw.strip()
    if s == "":
        return ""
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return _unescape(s[1:-1])
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    if s.startswith(("[", "{")):
        return _parse_flow(s, line)
    low = s.lower()
    if low in ("null", "~", ""):
        return None
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s) and not s.rstrip().endswith("."):
        try:
            return float(s)
        except ValueError:
            pass
    return s


def _split_flow(body: str, line: int) -> list[str]:
    parts, depth, buf, quote = [], 0, [], ""
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if quote:
        raise YamlError("unterminated quote in flow collection", line)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return [p.strip() for p in parts if p.strip() != ""]


def _parse_flow(s: str, line: int) -> Any:
    s = s.strip()
    if s.startswith("["):
        if not s.endswith("]"):
            raise YamlError("unterminated flow sequence", line)
        return [parse_scalar(p, line) for p in _split_flow(s[1:-1], line)]
    if s.startswith("{"):
        if not s.endswith("}"):
            raise YamlError("unterminated flow mapping", line)
        out = {}
        for part in _split_flow(s[1:-1], line):
            k, sep, v = _split_key(part)
            if not sep:
                raise YamlError(f"expected key: value in flow mapping, got {part!r}", line)
            out[str(parse_scalar(k, line))] = parse_scalar(v, line)
        return out
    return s


def _split_key(text: str) -> tuple[str, bool, str]:
    """Split 'key: value' honouring quotes and URLs like http://x."""
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == "#" and i > 0 and text[i - 1] in " \t":
            break
        if ch == ":":
            nxt = text[i + 1] if i + 1 < len(text) else " "
            if nxt in " \t" or i + 1 == len(text):
                return text[:i], True, text[i + 1:]
    return text, False, ""


def _strip_comment(text: str) -> str:
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch == "#" and (i == 0 or text[i - 1] in " \t"):
            return text[:i]
    return text


# --------------------------------------------------------------------------
# block parsing
# --------------------------------------------------------------------------
class _Line:
    __slots__ = ("indent", "text", "no")

    def __init__(self, indent: int, text: str, no: int):
        self.indent, self.text, self.no = indent, text, no

    def __repr__(self):
        return f"<{self.no}:{self.indent}:{self.text!r}>"


def _tokenize(src: str) -> list[_Line]:
    out = []
    for i, raw in enumerate(src.replace("\t", "    ").splitlines(), 1):
        if raw.strip() in ("---", "..."):
            continue
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        out.append(_Line(indent, stripped.strip(), i))
    return out


def _block_scalar(lines: list[_Line], idx: int, header: str,
                  parent_indent: int) -> tuple[str, int]:
    style = header[0]
    chomp = "clip"
    if "-" in header:
        chomp = "strip"
    elif "+" in header:
        chomp = "keep"
    body: list[str] = []
    base = None
    j = idx
    while j < len(lines):
        ln = lines[j]
        if ln.indent <= parent_indent:
            break
        if base is None:
            base = ln.indent
        body.append(" " * max(0, ln.indent - base) + ln.text)
        j += 1
    if style == "|":
        text = "\n".join(body)
    else:  # folded
        folded, buf = [], []
        for b in body:
            if b.strip() == "":
                folded.append(" ".join(buf))
                buf = []
                folded.append("")
            elif b.startswith(" "):
                if buf:
                    folded.append(" ".join(buf))
                    buf = []
                folded.append(b)
            else:
                buf.append(b.strip())
        if buf:
            folded.append(" ".join(buf))
        text = "\n".join(folded)
    if chomp == "strip":
        text = text.rstrip("\n")
    elif chomp == "clip":
        text = text.rstrip("\n") + ("\n" if body else "")
    return text, j


def _parse_block(lines: list[_Line], idx: int, indent: int) -> tuple[Any, int]:
    if idx >= len(lines):
        return None, idx
    first = lines[idx]
    if first.text.startswith("- "):
        return _parse_seq(lines, idx, first.indent)
    if first.text == "-":
        return _parse_seq(lines, idx, first.indent)
    return _parse_map(lines, idx, first.indent)


def _parse_seq(lines: list[_Line], idx: int, indent: int) -> tuple[list, int]:
    out: list = []
    while idx < len(lines):
        ln = lines[idx]
        if ln.indent < indent or not (ln.text == "-" or ln.text.startswith("- ")):
            break
        if ln.indent > indent:
            raise YamlError("unexpected indentation in sequence", ln.no)
        rest = ln.text[1:].strip()
        if not rest:
            idx += 1
            if idx < len(lines) and lines[idx].indent > indent:
                val, idx = _parse_block(lines, idx, lines[idx].indent)
                out.append(val)
            else:
                out.append(None)
            continue
        key, is_kv, val = _split_key(rest)
        if is_kv:
            # "- key: value" starts a mapping whose first key sits inline
            child_indent = ln.indent + 2
            synthetic = [_Line(child_indent, rest, ln.no)]
            j = idx + 1
            while j < len(lines) and lines[j].indent > ln.indent:
                synthetic.append(_Line(lines[j].indent, lines[j].text, lines[j].no))
                j += 1
            norm = _normalise_indent(synthetic, child_indent)
            value, _ = _parse_map(norm, 0, child_indent)
            out.append(value)
            idx = j
            continue
        if rest[0] in "|>":
            text, idx = _block_scalar(lines, idx + 1, rest, ln.indent)
            out.append(text)
            continue
        out.append(parse_scalar(rest, ln.no))
        idx += 1
    return out, idx


def _normalise_indent(lines: list[_Line], target: int) -> list[_Line]:
    if not lines:
        return lines
    shift = target - lines[0].indent
    return [_Line(max(0, l.indent + shift), l.text, l.no) for l in lines]


def _parse_map(lines: list[_Line], idx: int, indent: int) -> tuple[dict, int]:
    out: dict = {}
    while idx < len(lines):
        ln = lines[idx]
        if ln.indent < indent:
            break
        if ln.indent > indent:
            raise YamlError(f"unexpected indentation (expected {indent})", ln.no)
        if ln.text.startswith("- "):
            break
        key_raw, is_kv, val_raw = _split_key(ln.text)
        if not is_kv:
            raise YamlError(f"expected 'key: value', got {ln.text!r}", ln.no)
        if _UNSUPPORTED.match(val_raw):
            raise YamlError("anchors, aliases and tags are not supported", ln.no)
        key = str(parse_scalar(key_raw, ln.no))
        val_raw = val_raw.strip()
        if val_raw and val_raw[0] in "|>":
            out[key], idx = _block_scalar(lines, idx + 1, val_raw, ln.indent)
            continue
        if val_raw:
            out[key] = parse_scalar(val_raw, ln.no)
            idx += 1
            continue
        # value lives on following, more-indented lines
        idx += 1
        if idx < len(lines) and lines[idx].indent > ln.indent:
            out[key], idx = _parse_block(lines, idx, lines[idx].indent)
        elif (idx < len(lines) and lines[idx].indent == ln.indent
              and lines[idx].text.startswith(("- ", "-"))):
            out[key], idx = _parse_seq(lines, idx, lines[idx].indent)
        else:
            out[key] = None
    return out, idx


def load_yaml(src: str) -> Any:
    lines = _tokenize(src or "")
    if not lines:
        return {}
    value, idx = _parse_block(lines, 0, lines[0].indent)
    if idx < len(lines):
        raise YamlError("could not parse the whole document", lines[idx].no)
    return value


# --------------------------------------------------------------------------
# dumping
# --------------------------------------------------------------------------
_PLAIN_SAFE = re.compile(r"^[A-Za-z_][\w .,'/()&+-]*$")
_RESERVED = {"true", "false", "yes", "no", "on", "off", "null", "~"}


def _fmt_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    s = str(v)
    if s == "":
        return '""'
    if "\n" in s:
        return None  # signals block scalar
    if (_PLAIN_SAFE.match(s) and s.lower() not in _RESERVED
            and not s.endswith(" ") and ": " not in s and " #" not in s):
        return s
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _block_header(text: str) -> tuple[str, list[str]]:
    """Pick the right chomping indicator so a block scalar round-trips.

    |   keeps exactly one trailing newline (clip)
    |-  keeps none (strip)
    |+  keeps them all (keep)
    """
    trailing = len(text) - len(text.rstrip("\n"))
    if trailing == 0:
        return "|-", text.split("\n")
    if trailing == 1:
        return "|", text[:-1].split("\n")
    return "|+", text.split("\n")


def dump_yaml(data: Any, indent: int = 0) -> str:
    pad = " " * indent
    if isinstance(data, dict):
        if not data:
            return pad + "{}"
        out = []
        for k, v in data.items():
            key = _fmt_scalar(str(k)) or str(k)
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{key}:")
                out.append(dump_yaml(v, indent + 2))
            elif isinstance(v, (dict, list)):
                out.append(f"{pad}{key}: " + ("{}" if isinstance(v, dict) else "[]"))
            else:
                scalar = _fmt_scalar(v)
                if scalar is None:
                    header, body = _block_header(str(v))
                    out.append(f"{pad}{key}: {header}")
                    for line in body:
                        out.append((" " * (indent + 2) + line) if line else "")
                else:
                    out.append(f"{pad}{key}: {scalar}")
        return "\n".join(out)
    if isinstance(data, list):
        if not data:
            return pad + "[]"
        out = []
        for item in data:
            if isinstance(item, (dict, list)) and item:
                body = dump_yaml(item, indent + 2)
                first, _, rest = body.partition("\n")
                out.append(f"{pad}- {first.strip()}")
                if rest:
                    out.append(rest)
            else:
                scalar = _fmt_scalar(item)
                out.append(f"{pad}- " + (scalar if scalar is not None
                                         else repr(str(item))))
        return "\n".join(out)
    return pad + (_fmt_scalar(data) or str(data))
