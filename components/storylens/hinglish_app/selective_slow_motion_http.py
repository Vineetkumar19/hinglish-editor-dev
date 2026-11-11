"""Scoped media and job routes for the Selective Slow Motion workbench."""
from pathlib import Path

from .selective_slow_motion import prepare_render


def media(handler, jobs, query):
    from .workbench_http import _media
    from .selective_slow_motion_review import _export_root, _review_state

    job = jobs.snapshot(query.get("id", [""])[0])
    if job["status"] != "complete":
        raise ValueError("Wait for the slow-motion job to finish.")
    if job["kind"] == "slow-motion-scan":
        moment_id = query.get("moment", [""])[0]
        moment = next((row for row in job["result"]["moments"] if row["id"] == moment_id), None)
        if moment is None:
            raise ValueError("Choose a source moment from this scan.")
        path = Path(moment["source"]).resolve(strict=True)
        stat = path.stat()
        if (stat.st_size, stat.st_mtime_ns) != (moment["size"], moment["mtime_ns"]):
            raise ValueError("The source changed. Scan it again.")
        return _media(handler, path, False)
    part = query.get("part", [""])[0]
    if job["kind"] != "slow-motion-render":
        raise ValueError("Choose a completed slow-motion preview.")
    folder = jobs._file(job["id"]).parent.resolve()
    if part == "review":
        return handler._json(200, _review_state(job, _export_root(jobs, job)))
    if part == "recipe":
        path = Path(job["result"]["recipe"]).resolve(strict=True)
        base = folder
    elif part == "manifest":
        path = (export_directory(jobs, job) / "index.json").resolve(strict=True)
        base = export_directory(jobs, job)
    elif part.isascii() and part.isdecimal() and len(part) <= 8 and int(part) < len(job["result"]["variants"]):
        index = int(part)
        variant = job["result"]["variants"][index]
        editor = query.get("native", [""])[0]
        if editor in ("premiere", "aftereffects"):
            base = _export_root(jobs, job).resolve()
            path = (base / "Native_Fallback" / variant["moment"]["label"] /
                    f"{index:03d}" / editor / f"{editor}-comparison.mp4").resolve(strict=True)
        else:
            if variant["state"] != "awaiting-review":
                raise ValueError("This variant did not pass technical checks.")
            path = Path(variant["path"]).resolve(strict=True)
            base = (jobs.root / "cache/slow-motion").resolve()
    else:
        raise ValueError("Choose a slow-motion variant.")
    if not path.is_relative_to(base) or not path.is_file():
        raise ValueError("The slow-motion export is unavailable.")
    return _media(handler, path, query.get("download") == ["1"])


def export_directory(jobs, job):
    if job["kind"] != "slow-motion-render" or job["status"] != "complete":
        raise ValueError("Choose a completed slow-motion render.")
    expected = jobs.base.resolve() / job["id"] / "Trip_Output" / "Slow Motion"
    directory = expected.resolve(strict=True)
    if directory != expected or not directory.is_dir():
        raise ValueError("The Slow Motion folder is unavailable.")
    return directory


def post(handler, jobs, action, request):
    if action == "slow-motion-scan":
        from .selective_slow_motion import _paths

        paths = request.get("paths", [])
        if request.get("dataset_id"):
            dataset = jobs.snapshot(request["dataset_id"])
            if dataset["kind"] != "footage" or dataset["status"] != "complete" or not isinstance(paths, list):
                raise ValueError("Choose a completed Cinematic Footage index.")
            outcomes = dataset["result"].get("source_outcomes", [])
            if outcomes:
                indexed = [row["path"] for row in outcomes]
            else:
                indexed = list(dict.fromkeys(row["source"] for row in dataset["result"]["assets"]))
            paths = list(dict.fromkeys([*paths, *indexed]))
        settings = {"paths": paths, "folders": request.get("folders", []), "folder": request.get("folder", "")}
        _paths(settings)
        key = request.get("idempotency_key")
        if isinstance(key, str) and 0 < len(key) <= 80:
            settings["idempotency_key"] = key
        return handler._json(202, jobs.start(action, settings))
    if action == "slow-motion-render":
        return handler._json(202, jobs.start(action, prepare_render(jobs, request)))
    if action == "slow-motion-open":
        import os

        os.startfile(str(export_directory(jobs, jobs.snapshot(request.get("id")))))
        return handler._json(200, {"ok": True})
    if action == "slow-motion-review":
        from .selective_slow_motion_review import review
        return handler._json(200, review(jobs, request))
    if action == "slow-motion-native-request":
        from .selective_slow_motion_review import native_request
        return handler._json(200, native_request(jobs, request))
    if action == "slow-motion-native-import":
        from .selective_slow_motion_review import native_import
        return handler._json(200, native_import(jobs, request))
    if action == "slow-motion-native-status":
        from .selective_slow_motion_review import native_status
        return handler._json(200, native_status(jobs, request))
    raise ValueError("Choose a supported slow-motion action.")
