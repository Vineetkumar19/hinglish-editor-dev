"""Local Call QA storage and validation. A provider can submit completed test recordings."""

import base64
import binascii
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
import re
import sqlite3
import uuid
import wave

from .call_qa_report import OUTCOMES, RUBRIC


LANGUAGES = {"en": "English", "hi": "Hindi", "hinglish": "Hinglish"}
MAX_AUDIO_BYTES = 24 * 1024 * 1024
MAX_BODY_BYTES = 4 * ((MAX_AUDIO_BYTES + 2) // 3) + 768 * 1024
MAX_DURATION_MS = 15 * 60 * 1000
ID = re.compile(r"[a-f0-9]{32}")
EVENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}")


class Conflict(ValueError):
    pass


def bounded_text(value, limit, label, *, required=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{label} must be text of at most {limit} characters.")
    text = value.strip()
    if required and not text:
        raise ValueError(f"Enter {label.lower()}.")
    return text


def milliseconds(value, duration, label):
    if type(value) is not int or not 0 <= value <= duration:
        raise ValueError(f"{label} must be an integer inside the recording, in milliseconds.")
    return value


def timestamp_range(data, duration):
    start = milliseconds(data.get("start_ms"), duration, "Evidence start")
    end = milliseconds(data.get("end_ms"), duration, "Evidence end")
    if end <= start:
        raise ValueError("The evidence end must follow its start.")
    return {"start_ms": start, "end_ms": end}


def transcript_rows(value, duration):
    if not isinstance(value, list) or len(value) > 600:
        raise ValueError("Supply up to 600 timed transcript segments as a JSON array.")
    rows = []
    for index, item in enumerate(value, 1):
        if not isinstance(item, dict) or item.get("speaker") not in ("agent", "caller", "unknown"):
            raise ValueError("Each transcript segment needs speaker agent, caller, or unknown.")
        timing = timestamp_range(item, duration)
        confidence = item.get("confidence", "unknown")
        locale = item.get("locale")
        played = item.get("played", True)
        if (confidence not in ("high", "medium", "low", "unknown")
                or locale not in (None, *LANGUAGES) or type(played) is not bool):
            raise ValueError("Invalid transcript locale, confidence, or playback status.")
        rows.append({
            **timing, "id": index, "speaker": item["speaker"], "locale": locale,
            "played": played, "confidence": confidence,
            "romanized": bounded_text(item.get("romanized", ""), 600, "Romanized transcript"),
            "text": bounded_text(item.get("text"), 600, "Transcript text", required=True),
        })
    return sorted(rows, key=lambda row: row["start_ms"])


def decode_audio(value):
    if not isinstance(value, str) or len(value) > 4 * ((MAX_AUDIO_BYTES + 2) // 3):
        raise ValueError("Choose a PCM WAV recording of at most 24 MiB.")
    try:
        data = base64.b64decode(value, validate=True)
        if len(data) > MAX_AUDIO_BYTES:
            raise ValueError("Choose a recording of at most 24 MiB.")
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames, rate, channels, width = (
                wav.getnframes(), wav.getframerate(), wav.getnchannels(), wav.getsampwidth()
            )
            if not (8000 <= rate <= 48000 and channels in (1, 2) and width in (1, 2, 3, 4)):
                raise ValueError("Use mono or stereo PCM WAV at 8–48 kHz.")
            duration = frames * 1000 // rate
            if not 100 <= duration <= MAX_DURATION_MS:
                raise ValueError("Use a recording from 0.1 seconds to 15 minutes.")
            frame_bytes = channels * width
            if frames * frame_bytes > len(data) or len(wav.readframes(frames)) != frames * frame_bytes:
                raise ValueError("The WAV recording is incomplete.")
    except (binascii.Error, wave.Error, EOFError, OverflowError) as error:
        raise ValueError("Choose a valid PCM WAV recording.") from error
    return data, duration


def review_rows(value, duration):
    if not isinstance(value, dict) or value.keys() != RUBRIC.keys():
        raise ValueError("Review every checklist item.")
    result = {}
    for key, row in value.items():
        if not isinstance(row, dict) or row.get("outcome") not in tuple(OUTCOMES):
            raise ValueError("Choose an outcome for each checklist item.")
        outcome = row["outcome"]
        note = bounded_text(row.get("note", ""), 1000, "Reviewer note", required=outcome == "needs_attention")
        evidence = row.get("evidence")
        if outcome in ("unobserved", "not_applicable"):
            if evidence is not None:
                raise ValueError("Clear the evidence on an unobserved item.")
        else:
            if not isinstance(evidence, dict):
                raise ValueError("Add playable evidence for each observed item.")
            evidence = timestamp_range(evidence, duration)
        result[key] = {"outcome": outcome, "note": note, "evidence": evidence}
    return result


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def retention_days():
    value = os.environ.get("STORYLENS_CALL_QA_RETENTION_DAYS", "30")
    return int(value) if re.fullmatch(r"[1-9][0-9]{0,2}", value) and int(value) <= 365 else 30


def past(seconds):
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(timespec="seconds")


class CallQA:
    def __init__(self, root):
        self.path = root / "cache" / "call-qa" / "calls.sqlite3"

    @contextmanager
    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=8)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys = ON")
            db.execute("PRAGMA secure_delete = ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS calls (
                    id TEXT NOT NULL UNIQUE, source TEXT NOT NULL, event_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL, title TEXT NOT NULL, language TEXT NOT NULL,
                    received_at TEXT NOT NULL, duration_ms INTEGER NOT NULL,
                    transcript TEXT NOT NULL, recording BLOB NOT NULL, review TEXT,
                    revision INTEGER NOT NULL DEFAULT 0, reviewed_at TEXT,
                    UNIQUE(source, event_id)
                );
                CREATE TABLE IF NOT EXISTS call_audio (
                    call_id TEXT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE, wav BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS call_details (
                    call_id TEXT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE, metadata TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS qa_reports (
                    call_id TEXT PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,
                    claim TEXT, claimed_at TEXT, report TEXT
                );
                CREATE TABLE IF NOT EXISTS call_review_revisions (
                    call_id TEXT REFERENCES calls(id) ON DELETE CASCADE, revision INTEGER,
                    review TEXT NOT NULL, reviewed_at TEXT NOT NULL, PRIMARY KEY(call_id, revision)
                );
                CREATE TABLE IF NOT EXISTS call_tombstones (
                    key TEXT PRIMARY KEY, removed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS call_gateway_state (
                    slot INTEGER PRIMARY KEY CHECK(slot=1), status TEXT NOT NULL, detail TEXT NOT NULL, updated_at TEXT NOT NULL
                );
            """)
            with db:
                yield db
        finally:
            db.close()

    def ingest(self, payload, source):
        if payload.get("consent") is not True or payload.get("test_call") is not True:
            raise ValueError("Confirm this is a test call and all participants agreed to recording and review.")
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not EVENT_ID.fullmatch(event_id):
            raise ValueError("Supply a stable test call event ID.")
        title = bounded_text(payload.get("title"), 100, "Call label", required=True)
        language = payload.get("language")
        if not isinstance(language, str) or language not in LANGUAGES:
            raise ValueError("Select English, Hindi, or Hinglish.")
        audio, duration = decode_audio(payload.get("recording"))
        transcript = dump(transcript_rows(payload.get("transcript", []), duration))
        status = payload.get("status", "ended")
        if status not in ("ended", "partial"):
            raise ValueError("A recording must belong to an ended or partial test call.")
        provider = bounded_text(payload.get("provider", ""), 30, "Provider")
        timing = payload.get("timing", [])
        timing_fields = {"reply_mark_ms", "first_output_ms", "first_chunk_ms", "speech_end_ms"}
        if (not isinstance(timing, list) or len(timing) > 100 or
                any(not isinstance(sample, dict) or sample.keys() != timing_fields
                    or any(type(value) is not int or not 0 <= value <= MAX_DURATION_MS for value in sample.values())
                    for sample in timing)):
            raise ValueError("Invalid call timing metrics.")
        metadata = dump({
            "status": status, "provider": provider if source == "gateway" else "local",
            "consent": "caller-confirmed" if provider == "twilio" and source == "gateway" else "test-attested",
            "started_at": bounded_text(payload.get("started_at", ""), 40, "Start time"),
            "ended_at": bounded_text(payload.get("ended_at", ""), 40, "End time"),
            "quality": bounded_text(payload.get("quality", ""), 180, "Recording notes"),
            "timing": timing,
        })
        fingerprint = hashlib.sha256(dump([
            title, language, transcript, metadata, hashlib.sha256(audio).hexdigest(),
        ]).encode()).hexdigest()
        call_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self.purge(db)
            if db.execute("SELECT 1 FROM call_tombstones WHERE key=?", (self.event_key(source, event_id),)).fetchone():
                raise Conflict("This event was removed under the test workspace’s retention controls.")
            inserted = db.execute("""
                INSERT INTO calls (id, source, event_id, fingerprint, title, language,
                                   received_at, duration_ms, transcript, recording)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source, event_id) DO NOTHING
            """, (call_id, source, event_id, fingerprint, title, language, now(), duration, transcript, b""))
            if inserted.rowcount:
                db.execute("INSERT INTO call_audio VALUES (?, ?)", (call_id, audio))
                db.execute("INSERT INTO call_details VALUES (?, ?)", (call_id, metadata))
                db.execute("INSERT INTO qa_reports(call_id) VALUES (?)", (call_id,))
                return {"id": call_id, "duplicate": False}
            existing = db.execute("SELECT id, fingerprint FROM calls WHERE source=? AND event_id=?",
                                  (source, event_id)).fetchone()
            if existing["fingerprint"] != fingerprint:
                raise Conflict("That event ID already belongs to a different recording or transcript.")
            return {"id": existing["id"], "duplicate": True}

    def list(self, language, before):
        if language and language not in LANGUAGES:
            raise ValueError("Choose a supported language.")
        if not re.fullmatch(r"[0-9]{0,18}", before):
            raise ValueError("Invalid call list cursor.")
        with self.connect() as db:
            self.purge(db)
            rows = db.execute("""
                SELECT rowid AS cursor, id, source, title, language, received_at, duration_ms, revision
                FROM calls WHERE (? = '' OR language = ?) AND (? = 0 OR rowid < ?)
                ORDER BY rowid DESC LIMIT 51
            """, (language, language, int(before or 0), int(before or 0))).fetchall()
        return {"calls": [dict(row) for row in rows[:50]], "before": rows[49]["cursor"] if len(rows) > 50 else None}

    def get(self, call_id, *, audio=False):
        if not ID.fullmatch(call_id):
            raise KeyError
        fields = ("COALESCE(call_audio.wav, calls.recording) AS recording" if audio else
                  "id, source, title, language, received_at, duration_ms, transcript, review, revision, "
                  "reviewed_at, call_details.metadata, qa_reports.report")
        join = ("LEFT JOIN call_audio ON call_audio.call_id=calls.id" if audio else
                "LEFT JOIN call_details ON call_details.call_id=calls.id "
                "LEFT JOIN qa_reports ON qa_reports.call_id=calls.id")
        with self.connect() as db:
            self.purge(db)
            row = db.execute(f"SELECT {fields} FROM calls {join} WHERE id=?", (call_id,)).fetchone()
        if row is None:
            raise KeyError
        if audio:
            return row["recording"]
        call = dict(row)
        call["transcript"] = json.loads(row["transcript"])
        for index, turn in enumerate(call["transcript"], 1):
            turn.setdefault("id", index)
        call["review"] = json.loads(row["review"]) if row["review"] is not None else None
        call["report"] = json.loads(row["report"]) if row["report"] is not None else None
        call.update({"status": "ended", **json.loads(call.pop("metadata") or "{}")})
        return call

    def save(self, call_id, payload):
        current = self.get(call_id)
        revision = payload.get("revision")
        if type(revision) is not int or revision < 0:
            raise ValueError("Reload the call to get its current review revision.")
        review = review_rows(payload.get("review"), current["duration_ms"])
        with self.connect() as db:
            result = db.execute("""
                UPDATE calls SET review=?, reviewed_at=?, revision=revision+1
                WHERE id=? AND revision=?
            """, (dump(review), now(), call_id, revision))
            row = db.execute("SELECT revision, review, reviewed_at FROM calls WHERE id=?", (call_id,)).fetchone()
            if row is None:
                raise KeyError
            if not result.rowcount and not (row["revision"] == revision + 1 and row["review"] == dump(review)):
                raise Conflict("The review changed in another tab. Reload before editing it again.")
            if result.rowcount:
                db.execute("INSERT INTO call_review_revisions VALUES (?, ?, ?, ?)",
                           (call_id, row["revision"], row["review"], row["reviewed_at"]))
            return {"review": review, "revision": row["revision"], "reviewed_at": row["reviewed_at"]}

    def claim_report(self):
        claim = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("INSERT OR IGNORE INTO qa_reports(call_id) SELECT id FROM calls")
            row = db.execute("""
                SELECT call_id FROM qa_reports WHERE report IS NULL AND (claim IS NULL OR claimed_at < ?)
                ORDER BY rowid LIMIT 1
            """, (past(120),)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE qa_reports SET claim=?, claimed_at=? WHERE call_id=?",
                       (claim, now(), row["call_id"]))
            return row["call_id"], claim

    def finish_report(self, call_id, claim, report):
        with self.connect() as db:
            db.execute("UPDATE qa_reports SET report=?, claim=NULL WHERE call_id=? AND claim=?",
                       (dump(report), call_id, claim))

    @staticmethod
    def event_key(source, event_id):
        return hashlib.sha256(f"{source}:{event_id}".encode()).hexdigest()

    def remove(self, db, row):
        db.execute("INSERT OR IGNORE INTO call_tombstones VALUES (?, ?)",
                   (self.event_key(row["source"], row["event_id"]), now()))
        db.execute("DELETE FROM calls WHERE id=?", (row["id"],))

    def purge(self, db):
        expired = db.execute("SELECT id, source, event_id FROM calls WHERE received_at < ?",
                             (past(retention_days() * 86400),)).fetchall()
        for row in expired:
            self.remove(db, row)

    def delete(self, call_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT id, source, event_id FROM calls WHERE id=?", (call_id,)).fetchone()
            if row:
                self.remove(db, row)
            return {"deleted": bool(row)}

    def gateway_state(self):
        with self.connect() as db:
            row = db.execute("SELECT status, detail, updated_at FROM call_gateway_state WHERE slot=1").fetchone()
        return dict(row) if row else None

    def set_gateway_state(self, data):
        status = data.get("state")
        if status not in ("connected", "ended", "unavailable", "pending", "expired"):
            raise ValueError("Unsupported gateway state.")
        detail = bounded_text(data.get("detail", ""), 160, "Gateway detail")
        with self.connect() as db:
            db.execute("REPLACE INTO call_gateway_state VALUES (1, ?, ?, ?)", (status, detail, now()))
