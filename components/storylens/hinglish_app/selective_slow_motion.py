"""Motion proposals and source-bound, editable slow-motion renders."""
from fractions import Fraction
from bisect import bisect_left
import json
import math
from pathlib import Path
import subprocess
import time
import uuid

from hinglish_cinematic.curation import digest, file_hash


FPS = 30
PRESETS = (0.7, 0.6, 0.5)
VERSION = "slow-motion-v7"
# Discovery changes do not invalidate identical verified rendered pixels.
RENDER_VERSION = "slow-motion-v6"
LEAD = .65
TAIL = 1.15


def check_stop(stop):
    if stop.is_set():
        raise InterruptedError("Selective Slow Motion stopped.")


def _fingerprint(path, stop):
    from hinglish_cinematic.planner import _content_fingerprint
    try:
        return _content_fingerprint(path, stop)
    except RuntimeError:
        check_stop(stop)
        raise


def _paths(request):
    from hinglish_cinematic.planner import VIDEO_EXTENSIONS

    def local_path(value):
        path = Path(value)
        # Owner's project-drive migration: saved A: footage indexes refer to D:.
        if path.drive.upper() == 'A:':
            path = Path('D:' + str(path)[2:])
        return path.resolve()

    paths = request.get("paths", [])
    folders = request.get("folders", [])
    if request.get("folder"):
        folders = [*folders, request["folder"]] if isinstance(folders, list) else folders
    if (not isinstance(paths, list) or
            any(not isinstance(path, str) or not path for path in paths) or
            not isinstance(folders, list) or any(not isinstance(folder, str) or not folder for folder in folders)):
        raise ValueError("Choose local video files or footage folders.")
    unique = dict.fromkeys(local_path(path) for path in paths)
    for folder in folders:
        directory = local_path(folder)
        if not directory.is_dir():
            raise ValueError("The footage folder is unavailable.")
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                unique[path.resolve()] = None
    if not unique:
        raise ValueError("Choose a folder containing videos or add individual video files.")
    return sorted(unique)


def _shot_moments(stamps, end, samples, rate):
    from statistics import median
    if len(samples) < 4:
        return []
    windows = []
    for sample in sorted(samples, key=lambda row: -row["score"]):
        if sample["score"] < .12:
            break
        event = sample["event"]
        first = max(0, bisect_left(stamps, event - LEAD) - 1)
        last = bisect_left(stamps, event + TAIL)
        start = stamps[first]
        finish = stamps[last] if last < len(stamps) else end
        position = bisect_left(windows, start, key=lambda row: row["start"])
        neighbors = windows[max(0, position - 1):position + 1]
        if finish - start < .75 or any(start < old["end"] and finish > old["start"] for old in neighbors):
            continue
        # A bright, sharp peak must not approve an otherwise dark or flashing
        # window. Judge the whole retained action, not just its best frame.
        neighborhood = [row for row in samples if start <= row['event'] < finish]
        if len(neighborhood) < 4:
            continue
        brightness = median(row['brightness'] for row in neighborhood)
        exposed = sorted(row['usable_exposure'] for row in neighborhood)
        lighting = sorted(row['light_change'] for row in neighborhood)
        clarity = median(row['quality'] for row in neighborhood)
        if (brightness < 48 or exposed[len(exposed)//4] < .45 or
                lighting[int(.9*(len(lighting)-1))] > 18 or clarity < .58):
            continue
        selected = stamps[first:last]
        if len(selected) < 4:
            continue
        gap = max(b - a for a, b in zip(selected, selected[1:]))
        risk = sample["motion"] > 5 or sample["shake"] > 2.5 or gap > .075
        recommended = .7 if risk or sample["motion"] < .65 else (.5 if gap <= 1/59.9 else .6)
        windows.insert(position, {
            **sample, "start": round(start, 8), "end": round(finish, 8),
            "score": round(sample['score'] * clarity * exposed[len(exposed)//4], 5),
            "window_quality": {"median_brightness": round(brightness, 3),
                               "exposed_lower_quartile": round(exposed[len(exposed)//4], 4),
                               "lighting_change_p90": round(lighting[int(.9*(len(lighting)-1))], 3)},
            "shot_start": round(stamps[0], 8), "shot_end": round(end, 8),
            "event": round(event, 8), "max_frame_gap": gap, "source_frames": len(selected),
            "fps": rate, "recommended": recommended,
            "review_risk": "Inspect fast edges, camera motion or irregular timing" if risk else "Inspect motion and occlusion",
        })
    return windows


def _analyze(path, stop):
    import av
    import cv2
    import numpy as np

    windows = []
    previous = None
    origin = last = None
    stamps, samples = [], []
    last_sample = None
    last_speed = 0.
    with av.open(str(path)) as container:
        if not container.streams.video:
            raise ValueError("No video track.")
        stream = container.streams.video[0]
        stream.thread_count = 2
        if stream.codec_context.color_trc in (16, 18):
            raise ValueError("HDR source. Use a color-managed SDR copy for this export.")
        if stream.codec_context.format and any(c.is_alpha for c in stream.codec_context.format.components):
            raise ValueError("Alpha source. This H.264 route cannot preserve transparency; supply a composited copy.")
        rate = float(stream.average_rate or stream.guessed_rate or 30)

        for frame in container.decode(stream):
            check_stop(stop)
            if frame.pts is None:
                raise ValueError("The video has missing presentation timestamps.")
            stamp = frame.pts * frame.time_base
            if origin is None:
                origin = stamp
            elapsed = float(stamp - origin)
            gap = elapsed - last if last is not None else 1 / rate
            if gap <= 0:
                raise ValueError("The video has non-monotonic presentation timestamps.")
            rgb = frame.reformat(width=96, height=54, format="rgb24").to_ndarray()
            luma = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 180, 0, 256])
            hist /= hist.sum()
            motion = float(cv2.absdiff(luma, previous[0]).mean()) / 255 if previous is not None else 0.
            cut = previous is not None and motion > .15 and cv2.compareHist(
                hist, previous[1], cv2.HISTCMP_BHATTACHARYYA
            ) > .40
            if cut or gap > .25:
                windows.extend(_shot_moments(stamps, elapsed if gap <= .25 else last + 1 / rate, samples, rate))
                stamps, samples = [], []
                last_sample = None
                last_speed = 0.
            stamps.append(elapsed)
            if last_sample is None or elapsed - last_sample[0] >= .08:
                # Remove only near-solid black border rows/columns from quality
                # statistics. Keep dark image content in the exposure assessment.
                rows = np.flatnonzero((luma.mean(axis=1)>3) | (luma.std(axis=1)>2))
                cols = np.flatnonzero((luma.mean(axis=0)>3) | (luma.std(axis=0)>2))
                content = rgb[rows[0]:rows[-1]+1, cols[0]:cols[-1]+1] if len(rows) and len(cols) else rgb
                content_luma = cv2.cvtColor(content, cv2.COLOR_RGB2GRAY)
                mean_rgb = content.mean(axis=(0,1))
                if last_sample is not None:
                    flow = cv2.calcOpticalFlowFarneback(last_sample[1], luma, None, .5, 2, 13, 2, 5, 1.1, 0)
                    # Black borders and smooth skies must not make a camera pan
                    # look like isolated subject motion. Fit the camera on
                    # informative pixels and compensate translation/rotation/zoom.
                    gy, gx = np.gradient(last_sample[1].astype(np.float32))
                    texture = np.hypot(gx, gy) > 5
                    texture[:3] = texture[-3:] = False
                    texture[:, :3] = texture[:, -3:] = False
                    texture &= (last_sample[1] > 15) & (last_sample[1] < 245)
                    yy, xx = np.nonzero(texture)
                    camera_flow = np.zeros_like(flow)
                    support = 0.
                    if len(xx) >= 24:
                        positions = np.column_stack((xx, yy)).astype(np.float32)
                        sampled = flow[yy, xx]
                        matrix, inliers = cv2.estimateAffinePartial2D(
                            positions, positions + sampled, method=cv2.RANSAC,
                            ransacReprojThreshold=.8, maxIters=300, confidence=.98)
                        if matrix is not None and inliers is not None:
                            support = float(inliers.mean())
                            if support >= .5:
                                grid_y, grid_x = np.indices(luma.shape, dtype=np.float32)
                                camera_flow[..., 0] = (matrix[0, 0]-1)*grid_x + matrix[0, 1]*grid_y + matrix[0, 2]
                                camera_flow[..., 1] = matrix[1, 0]*grid_x + (matrix[1, 1]-1)*grid_y + matrix[1, 2]
                    if support < .5:
                        camera_flow[:] = np.median(flow[texture] if texture.any() else flow.reshape(-1,2), axis=0)
                    normalizer = .1 / (elapsed - last_sample[0])
                    active = texture if texture.any() else np.ones(luma.shape,dtype=bool)
                    shake = float(np.percentile(np.linalg.norm(camera_flow,axis=2)[active],75)) * normalizer
                    residual = float(np.percentile(np.linalg.norm(flow - camera_flow, axis=2)[active], 90)) * normalizer
                    detail = min(1., math.log1p(cv2.Laplacian(luma, cv2.CV_32F).var()) / 8)
                    exposure = float(((luma > 10) & (luma < 247)).mean())
                    illumination = min(1., float(np.percentile(luma[active],60)) / 65)
                    quality = (.55 * detail + .45 * exposure) * illumination
                    change = abs(residual - last_speed)
                    score = quality * min((residual + .25 * change) / 2, 1) / (1 + shake / 1.5)
                    samples.append({"event": elapsed, "motion": round(residual, 4), "shake": round(shake, 4),
                                    "quality": round(quality, 4), "score": round(score, 5),
                                    "brightness": float(content_luma.mean()),
                                    "usable_exposure": float(((content_luma>30)&(content_luma<235)).mean()),
                                    "light_change": float(np.max(np.abs(mean_rgb-last_sample[2])))})
                    last_speed = residual
                last_sample = (elapsed, luma, mean_rgb)
            previous = (luma, hist)
            last = elapsed
            tail = float(frame.duration * frame.time_base) if frame.duration else 1 / rate
        if last is None:
            raise ValueError("No readable video frames.")
        windows.extend(_shot_moments(stamps, last + min(tail, .25), samples, rate))
        has_audio = bool(container.streams.audio)
    return windows, str(origin), has_audio


def analyze(request, stop, progress, cache_root=None):
    from hinglish_cinematic.planner import _content_fingerprint

    paths = _paths(request)
    from hinglish_cinematic.planner import VIDEO_EXTENSIONS

    moments, sources, seen = [], [], set()
    for index, path in enumerate(paths):
        check_stop(stop)
        progress(f"Reading video {index + 1} of {len(paths)} · {path.name}", int(100 * index / len(paths)))
        try:
            if path.suffix.lower() not in VIDEO_EXTENSIONS:
                raise ValueError("Unsupported video format.")
            before = path.stat()
            identity = _fingerprint(path, stop)
            if identity in seen:
                sources.append({"source": str(path), "status": "duplicate", "reason": "Exact duplicate"})
                continue
            cached = Path(cache_root) / (digest([VERSION, identity]) + '.json') if cache_root else None
            saved = None
            if cached and cached.exists():
                try:
                    saved = json.loads(cached.read_text('utf-8'))
                    if saved.get('source_sha256') != identity or saved.get('version') != VERSION:
                        saved = None
                except (OSError, ValueError):
                    pass
            if saved:
                windows, origin, has_audio = saved['windows'], saved['origin'], saved['has_audio']
            else:
                windows, origin, has_audio = _analyze(path, stop)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise ValueError("Source changed during analysis.")
            if cached and not saved:
                from .durable_json import write
                cached.parent.mkdir(parents=True, exist_ok=True)
                write(cached, {'version': VERSION, 'source_sha256': identity, 'windows': windows,
                               'origin': origin, 'has_audio': has_audio})
            seen.add(identity)
            for window in windows:
                key = digest([identity, window["start"], window["end"], "motion-v2"])[:24]
                moments.append({**window, "id": key, "source": str(path), "source_number": index + 1,
                                "sha256": identity, "pts_origin_seconds": origin, "has_audio": has_audio,
                                "size": after.st_size, "mtime_ns": after.st_mtime_ns})
            sources.append({"source": str(path), "status": "analyzed" if windows else "no-moment",
                            "sha256": identity, "candidates": len(windows),
                            "reason": f"{len(windows)} candidate moments" if windows else "No moving window passed clarity and lighting checks"})
        except InterruptedError:
            raise
        except (OSError, ValueError) as error:
            sources.append({"source": str(path), "status": "failed", "reason": str(error)})
    # Give distinct sources a review slot before proposing additional moments.
    moments.sort(key=lambda row: -row["score"])
    first = {}
    for moment in moments:
        first.setdefault(moment["sha256"], moment["id"])
    moments.sort(key=lambda row: first[row["sha256"]] != row["id"])
    for number, moment in enumerate(moments, 1):
        moment["label"] = f"SM_{number:04d}"
    return {"moments": moments, "scanned": len(paths), "sources": sources,
            "skipped": [row for row in sources if row["status"] != "analyzed"]}


def prepare_render(jobs, request):
    scan = jobs.snapshot(request.get("scan_id"))
    if scan["kind"] != "slow-motion-scan" or scan["status"] != "complete":
        raise ValueError("Choose a moment from a completed Selective Slow Motion scan.")
    backend = request.get("backend", "interpolate")
    if backend not in ("interpolate", "repeat", "blend"):
        raise ValueError("Choose motion interpolation, frame sampling or frame blending.")
    audio = request.get("audio", "mute")
    if audio not in ("mute", "pitch", "separate"):
        raise ValueError("Choose mute, preserve pitch, or original audio separately.")
    if request.get("batch") is True:
        items = []
        for moment in scan["result"]["moments"]:
            speed = moment["recommended"]
            points = _constant(moment, speed)
            items.append({"moment": moment, "plans": [{"preset": speed, "points": points}]})
        if not items:
            raise ValueError("No eligible moments in this scan.")
        prepared = {"scan_id": scan["id"], "items": items, "backend": backend, "audio": audio}
        return {**prepared, "idempotency_key": digest([VERSION, prepared])}
    moment = next((row for row in scan["result"]["moments"] if row["id"] == request.get("moment_id")), None)
    if moment is None:
        raise ValueError("This moment is unavailable. Rescan the footage.")
    variants = request.get("variants")
    if not isinstance(variants, list) or len(variants) != len(PRESETS):
        raise ValueError("Supply settings for the three variant speeds.")
    length = round(moment["end"] - moment["start"], 8)
    plans = [{"preset": preset, "points": validate_points(points, length)}
             for preset, points in zip(PRESETS, variants) if points is not None]
    if not plans:
        raise ValueError("Enable at least one variant.")
    lock = request.get("lock_from")
    if lock:
        previous = jobs.snapshot(lock)
        if previous["kind"] != "slow-motion-render" or previous["status"] != "complete":
            raise ValueError("Choose a completed comparison for the impact lock.")
        previous_frames = {row["preset"]: row["impact_frame"] for row in previous["result"]["variants"]
                           if row["moment_id"] == moment["id"] and "impact_frame" in row}
        if not previous_frames:
            raise ValueError("Render this moment before locking its action position.")
        for plan in plans:
            frame = previous_frames.get(plan["preset"])
            if frame is not None and _impact_frame(moment, plan["points"]) != frame:
                raise ValueError(f"The {plan['preset']:.1f}× curve moves the locked action off frame {frame}.")
    slot = request.get("slot_frames")
    if slot is not None and (type(slot) is not int or slot <= 0 or
            any(round(_time_map(plan["points"])[1] * FPS) != slot for plan in plans)):
        raise ValueError("The enabled curves do not fit that output frame count. Adjust the speeds or unlock the slot.")
    if audio == "pitch" and any(len({point["speed"] for point in plan["points"]}) > 1 for plan in plans):
        raise ValueError("Pitch preservation is available for flat speeds. Use separate original audio for ramps.")
    prepared = {"scan_id": scan["id"], "items": [{"moment": moment, "plans": plans}], "backend": backend, "audio": audio}
    return {**prepared, "idempotency_key": digest([VERSION, prepared])}


def _constant(moment, speed):
    return [{"offset": 0., "speed": speed}, {"offset": round(moment["end"] - moment["start"], 8), "speed": speed}]


def validate_points(points, length):
    if not isinstance(points, list) or not 2 <= len(points) <= 8:
        raise ValueError("Use two to eight speed points per variant.")
    result = []
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("Each speed point needs a source offset and speed.")
        offset, speed = point.get("offset"), point.get("speed")
        if (type(offset) not in (int, float) or type(speed) not in (int, float)
                or not 0 <= offset <= length + .00001 or not .5 <= speed <= 1):
            raise ValueError("Speed points must be within the clip at 0.5× to 1×.")
        result.append({"offset": round(offset, 8), "speed": float(speed)})
    if result[0]["offset"] != 0 or abs(result[-1]["offset"] - length) > .00001:
        raise ValueError("Keep the first and last points at the moment boundaries.")
    result[-1]["offset"] = length
    if any(right["offset"] - left["offset"] < .015 for left, right in zip(result, result[1:])):
        raise ValueError("Space speed points at least 0.015 source seconds apart, in order.")
    return result


def _time_map(points):
    """Integrate dt/speed, where speed changes linearly in source time."""
    output_seconds = 0.
    sections = []
    for left, right in zip(points, points[1:]):
        offset = left["offset"]
        length = right["offset"] - offset
        speed = left["speed"]
        slope = (right["speed"] - speed) / length
        local = f"(T-{offset:.8f})"
        if abs(slope) < 1e-7:
            expression = f"{local}/{speed:.12g}"
            span = length / speed
        else:
            expression = f"log(1+{slope / speed:.12g}*{local})/{slope:.12g}"
            span = math.log1p(slope / speed * length) / slope
        sections.append((right["offset"], f"{output_seconds:.12g}+{expression}"))
        output_seconds += span
    expression = sections[-1][1]
    for end, segment in reversed(sections[:-1]):
        expression = f"if(lt(T,{end:.8f}),{segment},{expression})"
    return expression, output_seconds


def _impact_frame(moment, points):
    target = moment["event"] - moment["start"]
    end = next(i for i, point in enumerate(points[1:], 1) if point["offset"] >= target - 1e-8)
    left, right = points[end - 1:end + 1]
    if target <= left["offset"]:
        return round(_time_map(points[:end])[1] * FPS) if end > 1 else 0
    fraction = (target - left["offset"]) / (right["offset"] - left["offset"])
    speed = left["speed"] + fraction * (right["speed"] - left["speed"])
    return round(_time_map([*points[:end], {"offset": target, "speed": speed}])[1] * FPS)


def _source_ticks(moment, points, count):
    """Output frame index to source microsecond tick, relative to the first decoded PTS."""
    result = []
    frame = 0
    elapsed = 0.
    for left, right in zip(points, points[1:]):
        span = right["offset"] - left["offset"]
        slope = (right["speed"] - left["speed"]) / span
        length = span / left["speed"] if abs(slope) < 1e-7 else math.log(right["speed"] / left["speed"]) / slope
        while frame < count and frame / FPS < elapsed + length:
            delta = frame / FPS - elapsed
            offset = left["speed"] * (delta if abs(slope) < 1e-7 else math.expm1(slope * delta) / slope)
            result.append(round((moment["start"] + left["offset"] + offset) * 1_000_000))
            frame += 1
        elapsed += length
    if len(result) != count or any(a >= b for a, b in zip(result, result[1:])):
        raise ValueError("The planned output-to-source time map is invalid.")
    return result


def _run(args, stop, log):
    started = time.monotonic()
    peak_bytes = None
    with log.open("wb") as stderr:
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=stderr,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            import psutil
            worker = psutil.Process(process.pid)
            peak_bytes = 0
        except (ImportError, OSError):
            worker = None
        deadline = time.monotonic() + 900
        try:
            while process.poll() is None:
                if worker is not None:
                    try:
                        peak_bytes = max(peak_bytes, worker.memory_info().rss)
                    except psutil.Error:
                        worker = None
                if stop.wait(.20):
                    raise InterruptedError("Selective Slow Motion stopped.")
                if time.monotonic() > deadline:
                    raise TimeoutError("Interpolation timed out. Try a lower-resolution source.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    if process.returncode:
        raise ValueError("Slow-motion render failed: " + log.read_text("utf-8", errors="replace")[-600:])
    return {"render_seconds": round(time.monotonic() - started, 3), "peak_rss_bytes_sampled": peak_bytes}


def _verify(path, count, stop):
    import av
    import cv2

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        frame_count = 0
        near_repeats = 0
        previous = None
        for frame in container.decode(stream):
            check_stop(stop)
            if frame.pts is None or abs(frame.pts * frame.time_base - Fraction(frame_count, FPS)) > Fraction(1, 9000):
                raise ValueError("Output frame timestamps did not verify.")
            frame_count += 1
            sample = frame.reformat(width=160, height=90, format="gray").to_ndarray()
            if previous is not None and float(cv2.absdiff(sample, previous).mean()) < .25:
                near_repeats += 1
            previous = sample
        if frame_count != count or stream.average_rate != FPS:
            raise ValueError(f"Output decoded {frame_count}/{count} frames at {stream.average_rate} fps; expected {FPS} fps.")
        return {"frames": count, "fps": FPS, "duration": count / FPS,
                "width": stream.width, "height": stream.height,
                "near_repeat_pairs": near_repeats, "has_audio": bool(container.streams.audio)}


def _render_variant(root, folder, moment, plan, backend, audio, stop, *, device="cpu"):
    import imageio_ffmpeg
    from .durable_json import write
    from .workbench_jobs import replace_retry
    from hinglish_cut.compute_policy import ffmpeg_h264

    source = Path(moment["source"])
    points = plan["points"]
    expression, duration = _time_map(points)
    count = round(duration * FPS)
    time_map = _source_ticks(moment, points, count)
    native = moment["max_frame_gap"] / min(point["speed"] for point in points) <= 1.0001 / FPS
    methods = {
        "interpolate": f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:scd=fdiff",
        "blend": f"minterpolate=fps={FPS}:mi_mode=blend:scd=fdiff",
        "repeat": f"fps={FPS}:start_time=0:round=near",
    }
    method = "native" if native and backend == "interpolate" else backend
    interpolation = methods["repeat" if method == "native" else method]
    label = f"s{round(plan['preset'] * 100):03d}"
    filename = f"{moment['label']}__src{moment['source_number']:03d}__{label}__motion.mp4"
    audio = audio if moment["has_audio"] else "mute"
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    key = digest([RENDER_VERSION, moment["sha256"], moment["start"], moment["end"], points, method, FPS, audio, ffmpeg, device])
    cache = root / "cache/slow-motion" / key
    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / "render.mp4"
    metadata = cache / "record.json"
    partial = cache / f".{uuid.uuid4().hex}.part.mp4"
    log = folder / f"{moment['label']}-{label}.log"
    record = None
    if cached.is_file() and metadata.is_file():
        try:
            saved = json.loads(metadata.read_text("utf-8"))
            if saved["sha256"] == file_hash(cached):
                record = saved
        except (ValueError, KeyError, OSError):
            pass
    cache_hit = record is not None
    if not cache_hit:
        endpoint = points[-1]["offset"]
        expression = f"if(gte(T,{endpoint:.8f}),{duration:.12g}+(T-{endpoint:.8f})/{points[-1]['speed']:.12g},{expression})"
        filters = (
            f"setpts=PTS-STARTPTS,trim=start={moment['start']:.8f}:end={moment['end']:.8f},"
            "setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop=12,"
            f"settb=AVTB,setpts='{expression.replace('T', '(PTS-STARTPTS)*TB')}/TB',"
            "scale=w='max(32,2*round(iw*sar/2))':h='max(32,2*round(ih/2))',setsar=1,format=yuv420p,"
            f"{interpolation}"
        )
        audio_args = ["-an"]
        if audio == "pitch":
            a = float(Fraction(moment["pts_origin_seconds"])) + moment["start"]
            b = a + moment["end"] - moment["start"]
            audio_args = [
                "-map", "0:a:0", "-af",
                f"atrim=start={a:.9f}:end={b:.9f},asetpts=PTS-{a:.9f}/TB,"
                f"aresample=async=1:first_pts=0,atempo={points[0]['speed']},apad,atrim=duration={count / FPS:.9f}",
                "-c:a", "aac", "-b:a", "192k",
            ]
        try:
            stats = _run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-copyts",
                          "-threads", "2", "-i", str(source), "-map", "0:v:0", *audio_args, "-sn", "-dn",
                          "-filter_threads", "2", "-vf", filters, "-fps_mode", "cfr", "-r", str(FPS),
                          "-frames:v", str(count), *ffmpeg_h264(device, 17),
                          "-threads", "2", "-movflags", "+faststart", str(partial)], stop, log)
            record = {**_verify(partial, count, stop), **stats, "sha256": file_hash(partial)}
            if audio == "pitch" and not record["has_audio"]:
                raise ValueError("The pitch-preserved export has no readable audio track.")
            replace_retry(partial, cached)
            write(metadata, record)
        finally:
            partial.unlink(missing_ok=True)
    names = {"native": "Captured-frame sampling", "interpolate": "Motion-compensated interpolation",
             "repeat": "Frame sampling / repetition", "blend": "Frame blending"}
    return {**record, **plan, "filename": filename, "path": str(cached), "method": names[method],
            "backend": method, "moment_id": moment["id"], "moment": moment, "audio": audio,
            "cache_hit": cache_hit, "state": "awaiting-review", "impact_frame": _impact_frame(moment, points),
            "time_map": {"source_ticks": time_map, "source_tick_base": "1/1000000", "output_tick_base": "1/30",
                         "source_pts_origin_seconds": moment["pts_origin_seconds"]}}


def render(root, request, folder, stop, progress, gpu_root=None):
    from .durable_json import write
    from hinglish_cinematic.planner import _content_fingerprint

    from collections import Counter
    from hinglish_cut.compute_policy import heavy_device
    from hinglish_cut.gpu_lock import gpu_lock

    device = heavy_device(gpu_root or root)

    items = request["items"]
    variants = []
    total = sum(len(row["plans"]) for row in items)
    expected = Counter(row["moment"]["source"] for row in items)
    verified = {}
    progress("Waiting for the shared render slot", 0)
    with gpu_lock(gpu_root or root):
        for item in items:
            moment = item["moment"]
            source = moment["source"]
            check_stop(stop)
            if source not in verified:
                verified[source] = _fingerprint(source, stop)
            if verified[source] != moment["sha256"]:
                raise ValueError("Source changed since the scan. Scan the original again.")
            for plan in item["plans"]:
                check_stop(stop)
                progress(f"Rendering {moment['label']} at {plan['preset']:.1f}× · {len(variants) + 1} of {total}",
                         round(98 * len(variants) / total))
                try:
                    variant = _render_variant(root, folder, moment, plan, request["backend"], request["audio"], stop, device=device)
                except (ValueError, OSError, TimeoutError) as error:
                    check_stop(stop)
                    variant = {**plan, "moment_id": moment["id"], "moment": moment, "state": "render-rejected",
                               "reason": str(error)}
                variants.append(variant)
            expected[source] -= 1
            if not expected[source] and _fingerprint(source, stop) != verified[source]:
                raise ValueError("Source changed during the render. Scan it again.")
    receipt = folder / "Speed Points.json"
    write(receipt, {"version": VERSION, "scan_id": request["scan_id"], "output_fps": FPS, "variants": variants})
    return {"variants": variants, "recipe": str(receipt), "reviewed": False}
