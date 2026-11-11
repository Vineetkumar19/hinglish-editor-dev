"""Read every project source/config/document and compile all Python sources.

The manifest excludes generated state, downloaded dependencies, caches and
credential values. Reading/compilation is not a proof of semantic correctness.
"""
from pathlib import Path
import ast
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {".venv", ".git", "__pycache__", "data", "tmp", "node_modules"}
TEXT = {".py", ".md", ".txt", ".yaml", ".yml", ".ps1", ".json", ".toml", ".html", ".css", ".js"}


def main():
    files, errors = [], []
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if not path.is_file() or set(rel.parts) & EXCLUDED:
            continue
        raw = path.read_bytes()
        record = {"path": rel.as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if path.suffix in TEXT or path.name in ("Dockerfile", ".env.example", ".gitignore"):
            source = raw.decode("utf-8-sig")
            record["lines"] = len(source.splitlines())
            if path.suffix == ".py":
                try:
                    tree = ast.parse(source, filename=str(rel))
                    compile(tree, str(rel), "exec")
                    record["python_compiles"] = True
                    record["definitions"] = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for n in ast.walk(tree))
                except SyntaxError as exc:
                    errors.append(f"{rel}:{exc.lineno}: {exc.msg}")
        files.append(record)
    report = {"files": files, "file_count": len(files),
              "python_files": sum(f["path"].endswith(".py") for f in files),
              "text_lines": sum(f.get("lines", 0) for f in files), "errors": errors}
    target = ROOT / "data" / "project-review-manifest.json"
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Read {len(files)} project files; compiled {report['python_files']} Python files; {len(errors)} errors")
    for error in errors:
        print(error)
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
