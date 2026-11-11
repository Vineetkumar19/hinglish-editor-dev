"""Review and commit retimes after technical validation and a visual decision."""
from html import escape
import json
from pathlib import Path
import shutil
from threading import Event
import uuid

from hinglish_cinematic.curation import file_hash

from .durable_json import write
from .selective_slow_motion import FPS, VERSION, _run, _verify


def _copy_verified(source, target, identity):
    from .workbench_jobs import replace_retry

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{uuid.uuid4().hex}.partial")
    try:
        shutil.copyfile(source, temporary)
        if file_hash(temporary) != identity:
            raise ValueError("The staged video checksum changed. Render it again.")
        replace_retry(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _export_root(jobs, job):
    return jobs._file(job["id"]).parent / "Trip_Output" / "Slow Motion"


def review(jobs, request):
    job = _job(jobs, request.get("id"))
    output = _export_root(jobs, job)
    receipt = output / "index.json"
    current = json.loads(receipt.read_text("utf-8")) if receipt.exists() else {
        "version": 1, "evaluator": VERSION, "job_id": job["id"], "scan_id": job["request"]["scan_id"],
        "decisions": {}, "approved": {},
    }
    index, variant = _variant(job, request)
    editor = request.get("editor")
    key = str(index)
    if editor is not None:
        folder = _native_folder(jobs, job, index, variant, editor)
        imported = json.loads((folder / f"{editor}-comparison.json").read_text("utf-8"))
        if imported["reference_sha256"] != variant["sha256"]:
            raise ValueError("The native comparison belongs to a different reference render.")
        path = folder / imported["path"]
        if file_hash(path) != imported["sha256"]:
            raise ValueError("The native comparison changed. Attach and review it again.")
        variant = {**variant, **imported, "path": str(path),
                   "filename": variant["filename"].replace("__motion.mp4", f"__{editor}.mp4"),
                   "method": imported["method_claim"]}
        key += ":" + editor
    decision = request.get("decision")
    notes = request.get("notes", "")
    if decision not in ("approve", "reject") or not isinstance(notes, str) or not 1 <= len(notes.strip()) <= 1200:
        raise ValueError("Choose a decision and write a visual review note.")
    moment = variant["moment"]
    original = Path(moment["source"])
    output.mkdir(parents=True, exist_ok=True)
    approved = current["approved"]
    if decision == "approve":
        if variant["state"] != "awaiting-review":
            raise ValueError("This variant failed technical checks. Review a new render.")
        if file_hash(original) != moment["sha256"]:
            raise ValueError("The original source changed. Rescan before approving.")
        primary = not any(row["moment_id"] == moment["id"] and row["primary"]
                          for old_key, row in approved.items() if old_key != key)
        directory = output if primary else output / "Variants" / moment["label"]
        target = directory / variant["filename"]
        _copy_verified(variant["path"], target, variant["sha256"])
        record = {**variant, "path": target.relative_to(output).as_posix(), "primary": primary,
                  "state": "approved", "review_note": notes.strip()}
        if variant["audio"] == "separate":
            _separate_audio(variant, target)
            record["original_audio"] = target.with_suffix(".source-audio.wav").relative_to(output).as_posix()
        write(target.with_suffix(".json"), record)
        approved[key] = record
    elif key in approved:
        raise ValueError("This variant was already exported. Reject a new comparison before approving it.")
    current["decisions"][key] = {"decision": decision, "notes": notes.strip(),
                                "moment_id": moment["id"], "preset": variant["preset"], "editor": editor}
    current["render_rejections"] = [row for row in job["result"]["variants"] if row["state"] == "render-rejected"]
    _review_html(output / "review.html", current)
    write(receipt, current)
    return _review_state(job, output)


def _separate_audio(variant, target):
    from fractions import Fraction
    from imageio_ffmpeg import get_ffmpeg_exe

    moment = variant["moment"]
    a = float(Fraction(moment["pts_origin_seconds"])) + moment["start"]
    b = a + moment["end"] - moment["start"]
    partial = target.with_name(f".{uuid.uuid4().hex}.part.wav")
    try:
        _run([get_ffmpeg_exe(), "-nostdin", "-loglevel", "error", "-copyts", "-i", moment["source"],
              "-map", "0:a:0", "-vn", "-af",
              f"atrim=start={a:.9f}:end={b:.9f},asetpts=PTS-{a:.9f}/TB,aresample=async=1:first_pts=0",
              "-c:a", "pcm_s24le", str(partial)], Event(), target.with_suffix(".audio.log"))
        partial.replace(target.with_suffix(".source-audio.wav"))
    finally:
        partial.unlink(missing_ok=True)


def _review_html(path, manifest):
    from .workbench_jobs import replace_retry

    rows = []
    for key, row in manifest["decisions"].items():
        clip = manifest["approved"].get(key)
        video = f'<video controls preload="metadata" width="360" src="{escape(clip["path"], quote=True)}"></video>' if clip else ""
        rows.append(f'<article><h2>{row["preset"]:.1f}× · {row["decision"]}</h2>{video}<p>{escape(row["notes"])}</p></article>')
    for row in manifest["render_rejections"]:
        rows.append(f'<article><h2>{row["preset"]:.1f}× · Render rejected</h2><p>{escape(row["reason"])}</p></article>')
    temporary = path.with_name(f".{uuid.uuid4().hex}.partial")
    try:
        temporary.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Slow Motion Review</title>'
                             '<h1>Slow Motion Review</h1>' + "".join(rows) + "</html>", "utf-8")
        replace_retry(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _job(jobs, identifier):
    job = jobs.snapshot(identifier)
    if job["kind"] != "slow-motion-render" or job["status"] != "complete":
        raise ValueError("Choose a completed slow-motion preview job.")
    return job


def _variant(job, request):
    index = request.get("variant")
    if type(index) is not int or not 0 <= index < len(job["result"]["variants"]):
        raise ValueError("Choose a variant from this comparison.")
    return index, job["result"]["variants"][index]


def _review_state(job, output):
    path = output / "index.json"
    if not path.is_file():
        return {"id": job["id"], "decisions": {}, "export_count": 0}
    data = json.loads(path.read_text("utf-8"))
    exports = {}
    for key, row in data["approved"].items():
        media = (output / row["path"]).resolve()
        if media.is_relative_to(output.resolve()) and media.is_file():
            exports[key] = str(media)
    return {"id": job["id"], "decisions": data["decisions"], "export_count": len(data["approved"]),
            "exports": exports}


def native_request(jobs, request):
    job = _job(jobs, request.get("id"))
    index, row = _variant(job, request)
    if row["state"] != "awaiting-review":
        raise ValueError("Choose a technically verified reference render for comparison.")
    moment = row["moment"]
    source = Path(moment["source"])
    if file_hash(source) != moment["sha256"]:
        raise ValueError("Source changed. Scan the original again.")
    editor = request.get("editor")
    root = _native_folder(jobs, job, index, row, editor)
    root.mkdir(parents=True, exist_ok=True)
    preview = root / "Reference.mp4"
    _copy_verified(row["path"], preview, row["sha256"])
    record = {"version": VERSION, "reference": preview.name, "reference_sha256": row["sha256"],
              "editor": editor, "request": row, "state": "native-render-needed"}
    file = root / "native-request.json"
    write(file, record)
    guide = root / "Render checklist.txt"
    guide.write_text(
        f"Source: {source}\n"
        f"Original SHA-256: {moment['sha256']}\n"
        f"Source in/out relative to first video frame: {moment['start']} to {moment['end']} seconds (exclusive out)\n"
        f"Sequence: {row['width']}x{row['height']}, {FPS} fps, {row['frames']} frames\n"
        f"Action anchor: output frame {row['impact_frame']}\n"
        "Create a new sequence or composition. Keep the original footage and handles. "
        "Use the source ticks in native-request.json to check the editable time map.\n"
        "Premiere: use Speed/Duration and Optical Flow for a flat speed. Use Time Remapping for ramps and "
        "verify the exported time map. After Effects: use Time Remapping and enable Pixel Motion "
        "for the layer and composition.\n"
        "Use the same crop and grade as the reference. Render H.264 MP4 at matching dimensions and frame rate. "
        "Review both outputs around occlusion and thin edges before returning the native MP4.\n",
        "utf-8",
    )
    if editor == "aftereffects":
        from .selective_slow_motion_native import write_aftereffects
        write_aftereffects(root, row)
    return {"folder": str(root), "request": str(file), "guide": str(guide)}


def _native_folder(jobs, job, index, reference, editor):
    if editor not in ("premiere", "aftereffects"):
        raise ValueError("Choose Premiere Pro or After Effects.")
    return _export_root(jobs, job) / "Native_Fallback" / reference["moment"]["label"] / f"{index:03d}" / editor


def native_import(jobs, request):
    job = _job(jobs, request.get("id"))
    index, reference = _variant(job, request)
    editor = request.get("editor")
    folder = _native_folder(jobs, job, index, reference, editor)
    record = json.loads((folder / "native-request.json").read_text("utf-8"))
    if record["editor"] != editor:
        raise ValueError("This native request belongs to a different editor.")
    if file_hash(reference["moment"]["source"]) != reference["moment"]["sha256"]:
        raise ValueError("Source changed. Scan and benchmark the original again.")
    path = request.get("path")
    if not isinstance(path, str) or not path or Path(path).suffix.lower() != ".mp4":
        raise ValueError("Choose the locally rendered native MP4.")
    path = Path(path).resolve(strict=True)
    result = _verify(path, reference["frames"], Event())
    if reference["audio"] == "pitch" and not result["has_audio"]:
        raise ValueError("The native output is missing the requested pitch-preserved audio.")
    if (result["width"], result["height"]) != (reference["width"], reference["height"]):
        raise ValueError("The native output dimensions differ from the matched comparison.")
    identity = file_hash(path)
    manifest = _export_root(jobs, job) / "index.json"
    if manifest.exists():
        previous = json.loads(manifest.read_text("utf-8"))["approved"].get(f"{index}:{editor}")
        if previous and previous["sha256"] != identity:
            raise ValueError("This native comparison is already approved. Create a new comparison job for a revision.")
    target = folder / f"{editor}-comparison.mp4"
    _copy_verified(path, target, identity)
    imported = {**result, "editor": editor, "sha256": identity, "path": target.name,
                "method_claim": "Optical Flow" if editor == "premiere" else "Pixel Motion",
                "state": "awaiting-review", "reference_sha256": reference["sha256"]}
    write(folder / f"{editor}-comparison.json", imported)
    return imported


def native_status(jobs, request):
    job = _job(jobs, request.get("id"))
    index, reference = _variant(job, request)
    editor = request.get("editor")
    folder = _native_folder(jobs, job, index, reference, editor)
    path = folder / f"{editor}-comparison.json"
    imported = json.loads(path.read_text("utf-8")) if path.exists() else None
    review = _review_state(job, _export_root(jobs, job))
    return {"imported": imported, "decision": review["decisions"].get(f"{index}:{editor}")}
