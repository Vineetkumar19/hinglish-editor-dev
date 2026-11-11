from pathlib import Path
import hashlib
import json
import sys

root = Path(__file__).resolve().parents[1]
manifest = json.loads((root / "docs/file-manifest.json").read_text(encoding="utf-8"))
errors = []
for entry in manifest["files"]:
    path = root / entry["path"]
    if not path.is_file():
        errors.append(entry["path"] + " missing")
    elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        errors.append(entry["path"] + " changed")
for error in errors:
    print(error)
print(str(len(manifest["files"])) + " manifest files checked")
sys.exit(bool(errors))
