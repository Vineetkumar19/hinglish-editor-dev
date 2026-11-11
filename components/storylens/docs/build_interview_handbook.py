"""Build the interview-ready Hinglish Editor architecture handbook as a searchable PDF."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, ListFlowable, ListItem, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


ROOT = Path(r"E:\remove silence")
OUT = ROOT / "docs" / "HINGLISH_EDITOR_12_TOOLS_INTERVIEW_HANDBOOK.pdf"

PAGE_W, PAGE_H = A4
NAVY = colors.HexColor("#0B1020")
INK = colors.HexColor("#182033")
MUTED = colors.HexColor("#5E6A82")
BLUE = colors.HexColor("#3767F0")
CYAN = colors.HexColor("#32C5D2")
ORANGE = colors.HexColor("#FF7A45")
GREEN = colors.HexColor("#27AE74")
PURPLE = colors.HexColor("#7A55D6")
PALE = colors.HexColor("#F3F6FC")
LINE = colors.HexColor("#D8DFEC")
WHITE = colors.white


def register_fonts():
    candidates = {
        "Body": Path(r"C:\Windows\Fonts\segoeui.ttf"),
        "BodyBold": Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        "Display": Path(r"C:\Windows\Fonts\bahnschrift.ttf"),
    }
    for name, path in candidates.items():
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
    return (
        "Body" if candidates["Body"].exists() else "Helvetica",
        "BodyBold" if candidates["BodyBold"].exists() else "Helvetica-Bold",
        "Display" if candidates["Display"].exists() else "Helvetica-Bold",
    )


BODY_FONT, BOLD_FONT, DISPLAY_FONT = register_fonts()


class HandbookDoc(BaseDocTemplate):
    def __init__(self, filename):
        super().__init__(filename, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                         topMargin=20 * mm, bottomMargin=18 * mm,
                         title="Hinglish Editor: 12-Tool AI Video Editing System",
                         author="Vineet Kumar",
                         subject="Architecture, implementation and interview guide for the twelve Hinglish Editor tools",
                         keywords="Hinglish Editor, AI video editing, Python, PyAV, captions, motion graphics, portfolio, interview")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="body")
        self.addPageTemplates([
            PageTemplate(id="main", frames=frame, onPage=self._page),
        ])

    def _page(self, canvas, doc):
        page = canvas.getPageNumber()
        canvas.saveState()
        if page == 1:
            canvas.setFillColor(NAVY)
            canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#12204B"))
            canvas.circle(PAGE_W - 18 * mm, PAGE_H - 18 * mm, 58 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#173477"))
            canvas.circle(PAGE_W - 5 * mm, PAGE_H - 35 * mm, 35 * mm, fill=1, stroke=0)
            canvas.setFillColor(ORANGE)
            canvas.rect(0, 0, PAGE_W, 7 * mm, fill=1, stroke=0)
        else:
            canvas.setStrokeColor(LINE)
            canvas.line(18 * mm, PAGE_H - 13 * mm, PAGE_W - 18 * mm, PAGE_H - 13 * mm)
            canvas.setFont(BOLD_FONT, 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(18 * mm, PAGE_H - 9 * mm, "HINGLISH EDITOR - 12 TOOL HANDBOOK")
            canvas.setFont(BODY_FONT, 8)
            canvas.drawRightString(PAGE_W - 18 * mm, PAGE_H - 9 * mm, "LOCAL AI VIDEO EDITING SYSTEM")
            canvas.setFillColor(MUTED)
            canvas.drawCentredString(PAGE_W / 2, 8 * mm, f"Page {page}")
        canvas.restoreState()


styles = getSampleStyleSheet()
S = {
    "cover_kicker": ParagraphStyle("cover_kicker", fontName=BOLD_FONT, fontSize=10, leading=13,
                                    textColor=CYAN, spaceAfter=8, tracking=1.2),
    "cover_title": ParagraphStyle("cover_title", fontName=DISPLAY_FONT, fontSize=31, leading=34,
                                   textColor=WHITE, spaceAfter=14),
    "cover_sub": ParagraphStyle("cover_sub", fontName=BODY_FONT, fontSize=14, leading=20,
                                 textColor=colors.HexColor("#CFD7EA"), spaceAfter=18),
    "cover_meta": ParagraphStyle("cover_meta", fontName=BODY_FONT, fontSize=9.5, leading=14,
                                  textColor=colors.HexColor("#9EB1D8")),
    "h1": ParagraphStyle("h1", fontName=DISPLAY_FONT, fontSize=24, leading=27, textColor=NAVY,
                          spaceBefore=0, spaceAfter=10, keepWithNext=True),
    "h2": ParagraphStyle("h2", fontName=BOLD_FONT, fontSize=15, leading=19, textColor=BLUE,
                          spaceBefore=12, spaceAfter=6, keepWithNext=True),
    "h3": ParagraphStyle("h3", fontName=BOLD_FONT, fontSize=11.5, leading=15, textColor=INK,
                          spaceBefore=8, spaceAfter=4, keepWithNext=True),
    "body": ParagraphStyle("body", fontName=BODY_FONT, fontSize=9.2, leading=13.2, textColor=INK,
                            spaceAfter=6),
    "small": ParagraphStyle("small", fontName=BODY_FONT, fontSize=7.8, leading=10.6, textColor=MUTED),
    "table": ParagraphStyle("table", fontName=BODY_FONT, fontSize=7.7, leading=10.2, textColor=INK),
    "table_bold": ParagraphStyle("table_bold", fontName=BOLD_FONT, fontSize=7.7, leading=10.2, textColor=INK),
    "callout": ParagraphStyle("callout", fontName=BODY_FONT, fontSize=9.3, leading=13.4, textColor=INK),
    "quote": ParagraphStyle("quote", fontName=BOLD_FONT, fontSize=10.2, leading=14.2, textColor=NAVY),
    "toc": ParagraphStyle("toc", fontName=BODY_FONT, fontSize=10, leading=15, textColor=INK),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, level=0, color=BLUE):
    flow = []
    for item in items:
        if isinstance(item, tuple):
            head, rest = item
            text = f"<b>{escape(head)}</b> {rest}"
        else:
            text = item
        flow.append(ListItem(P(text), leftIndent=4 * mm))
    return ListFlowable(flow, bulletType="bullet", start="circle", bulletColor=color,
                        leftIndent=(5 + level * 5) * mm, bulletFontSize=5, spaceAfter=5)


def numbered(items):
    flow = [ListItem(P(item), leftIndent=4 * mm) for item in items]
    return ListFlowable(flow, bulletType="1", leftIndent=7 * mm, bulletFontName=BOLD_FONT,
                        bulletFontSize=8, spaceAfter=6)


def box(title, text, color=BLUE):
    data = [[P(title, "table_bold")], [P(text, "callout")]]
    t = Table(data, colWidths=[170 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), color),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F6F8FD")),
        ("BOX", (0, 0), (-1, -1), .7, color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return KeepTogether([t, Spacer(1, 5)])


def info_table(rows, widths=(40, 130), header=None):
    data = []
    if header:
        data.append([P(str(value), "table_bold") for value in header])
    data.extend([
        [P(str(value), "table_bold" if index == 0 else "table")
         for index, value in enumerate(row)]
        for row in rows
    ])
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0, hAlign="LEFT")
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), .35, LINE),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2FA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), WHITE)]
    t.setStyle(TableStyle(cmds))
    return t


def architecture_table():
    rows = [
        ["USER SURFACES", "Standalone dashboard", "Premiere CEP / UXP", "DaVinci Resolve Studio"],
        ["LOCAL CONTROL", "Local HTTP job server", "Native file picker", "Progress + review actions"],
        ["UNDERSTANDING", "Speech / word timing", "Qwen planning", "Vision / audio understanding"],
        ["FEATURE ENGINES", "12 Python packages", "Shared cache + models", "Rules + recovery paths"],
        ["OUTPUT", "MP4 / MOV / WAV", "FCP 7 XML timelines", "HTML reports + JSON decisions"],
    ]
    data = [[P(c, "table_bold") for c in row] for row in rows]
    t = Table(data, colWidths=[32 * mm, 46 * mm, 46 * mm, 46 * mm], rowHeights=[14 * mm] * len(rows))
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (0, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (0, -1), WHITE),
        ("BACKGROUND", (1, 0), (-1, -1), PALE),
        ("GRID", (0, 0), (-1, -1), .7, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


@dataclass
class Feature:
    number: int
    name: str
    subtitle: str
    problem: str
    inputs: str
    outputs: str
    hardware: str
    workflow: list[str]
    stack: list[tuple[str, str]]
    engineering: list[str]
    quality: list[str]
    limitations: list[str]
    folders: str
    interview: str


features = [
    Feature(1, "Smart Clean", "Script-free silence removal",
        "Talking-head recordings contain long pauses, setup gaps and dead air. Removing them manually is repetitive and error-prone, especially when cuts must protect word edges.",
        "One video or a folder of videos; source, vertical or horizontal output format.",
        "Cleaned MP4, editable timeline.xml, review audio, edit-decisions.json and report.html.",
        "CPU-friendly. Runs locally; GPU is unnecessary.",
        [
            "PyAV inspects orientation, duration, frame rate and audio, then produces a stable local media representation.",
            "Silero VAD 6.2.1 analyses audio in bounded 60-second blocks with overlap so a word crossing a block boundary is protected.",
            "Speech regions are merged; only silence longer than the configured threshold is removed. Default edge padding protects 80 ms before and 120 ms after detected speech.",
            "Every cut is rounded outward to whole video frames. A verification pass proves that all detected speech remains and that ranges are chronological and in bounds.",
            "The tool renders a review MP4 when requested and writes an FCP 7 XML timeline for non-destructive editing.",
        ],
        [("Silero VAD", "Neural speech detection"), ("PyAV", "Media probing, audio decoding and encoding"),
         ("NumPy", "Time and frame calculations"), ("FCP 7 XML", "Editable Premiere/Resolve timeline")],
        ["Bounded-memory processing supports long files.", "Content-addressed caching resumes completed analysis after interruption.",
         "The original video is never modified.", "A no-speech result does not fabricate an empty edit."],
        ["All detected speech is preserved.", "No overlapping or out-of-range frame spans.", "Human review is required for quiet speech and music-heavy recordings."],
        ["It removes silence, not semantic filler words or bad retakes.", "VAD can miss very quiet or heavily masked speech, so the report exposes every removed interval."],
        "hinglish_clean/ + shared hinglish_cut/media.py and xml_export.py",
        "I built a local silence-removal pipeline that uses Silero VAD, protects speech with frame-aware padding, verifies every edit range, and exports both a cleaned MP4 and an editable Premiere/Resolve XML without touching the source."),

    Feature(2, "Script Edit", "Semantic assembly, retakes and Clean+",
        "Creators often record many retakes out of order. The system must find the best complete take for each script idea, remove fillers conservatively, and preserve the intended meaning.",
        "Multiple raw recordings plus a Roman-Hinglish script, or raw recordings alone for Clean+.",
        "EDITED_SEQUENCE.xml, preview.mp4, review page, line-level audio, report data and reusable reviewed choices.",
        "CPU or CUDA. GPU accelerates transcription and local model inference.",
        [
            "Silero VAD finds speech; Oriserve Whisper-Hindi2Hinglish-Swift transcribes Roman Hinglish locally.",
            "The multilingual romanized MMS CTC model produces emissions. A custom NumPy Viterbi aligner estimates word-level timings without a Windows C++ extension.",
            "The script is split into semantic ideas. Token matching, embeddings and bounded candidate search retrieve possible takes across recordings.",
            "A local Qwen semantic verifier checks meaning, entities, numbers and negations; nearby complete later takes are preferred when they are stronger.",
            "Clean+ identifies filler-heavy or incomplete retake regions conservatively, while pacing profiles control how much natural pause remains.",
            "The evaluator reconstructs the edited audio, re-transcribes it, checks coverage and can retry with a safer cut. User-approved take choices become local examples for later decisions.",
        ],
        [("Whisper-Hindi2Hinglish-Swift", "Local Hinglish ASR"), ("MMS CTC + NumPy Viterbi", "Forced word alignment"),
         ("Qwen 2.5 Instruct", "Intent/entity verification"), ("Transformers / PyTorch", "Local model runtime"),
         ("Beam/candidate search", "Non-overlapping script-order selection")],
        ["A script guides matching but is not injected into ASR, reducing hallucinated words.",
         "Negations and numbers receive explicit checks because small mistakes can reverse meaning.",
         "Learning stores approved/rejected examples, not automatic model-weight changes.",
         "Uncertain or missing ideas remain visible for review instead of being silently dropped."],
        ["Coverage, order, repeated frames, numbers, negations, important terms and semantic intent are checked.",
         "A conservative fallback restores more source audio when the aggressive edit fails."],
        ["Highly paraphrased speech can still need manual selection.", "Each intended sentence should exist inside one source file.",
         "ASR and the small local judge can repeat the same misunderstanding, so listening review remains essential."],
        "hinglish_semantic/ + hinglish_cut/ + cache/learning/",
        "I built a semantic video assembler for Roman Hinglish. It combines local transcription, forced alignment, script matching, semantic verification and review-based learning to choose the best retake and produce a non-destructive editor timeline."),

    Feature(3, "Auto Captions", "Nineteen animated caption systems",
        "Ordinary subtitle generators produce readable text but not designed social-video typography. This feature needs accurate timing, responsive layout and reusable styles.",
        "Video or folder, optional reference script, output format and one of 19 caption styles.",
        "Transparent caption MOV, captions.srt, captions.ass, transcript.txt, CAPTIONED_SEQUENCE.xml and an editable report.",
        "CPU works; CUDA accelerates the first transcription.",
        [
            "Shared transcripts provide word start/end times. A rough script can correct names and acronyms without replacing genuinely different speech.",
            "Words are grouped into readable cues using timing, punctuation and width rules.",
            "A custom Pillow/OpenCV renderer draws every animation frame. PyAV encodes transparent QuickTime Animation layers for editor compositing.",
            "Styles include minimal, karaoke, neon, pill, punch, cinematic/editorial systems and Typography 1-5 built from the supplied references.",
            "Typography engines calculate real font ink bounds, preserve letter spacing, control word spacing separately, choose hero words and avoid overlap.",
            "The review page lets the creator fix words, choose fonts, move/resize captions and assign individual word colours before rebuilding.",
        ],
        [("Pillow", "Font measurement, glow, blur, stroke and compositing"), ("OpenCV", "Fast image operations"),
         ("PyAV / qtrle", "Transparent video encoding"), ("SRT + ASS", "Portable subtitle exports"),
         ("Custom typography renderer", "Word-level animation and layout")],
        ["Caption rendering is resolution-independent and supports 9:16, 1:1 and 16:9.",
         "Per-word colour is stored as project data, so highlights remain editable.",
         "Typography 1-5 use different entrance, focus, alignment and hierarchy systems rather than simple presets.",
         "The source video remains on V1/A1 and the transparent caption layer sits on V2."],
        ["Text fit, frame boundaries, overlap, cue duration and required exports are checked.",
         "Acronym fragments such as 'rp' + 'm' can be merged from a reference script while retaining the total time span."],
        ["First-pass ASR still depends on microphone quality.", "Font availability can affect metrics; the project resolves known Windows fonts and applies fallbacks."],
        "hinglish_captions/ (core, renderer, styles, report, subtitles, xml_export)",
        "I built a word-timed caption compositor rather than a subtitle skin. It measures text, animates every frame, supports nineteen styles and per-word colours, exports transparent video plus SRT/ASS, and gives the creator a browser-based correction workflow."),

    Feature(4, "Add B-roll", "Meaning-aware cutaway selection",
        "Generic keyword matching often inserts unrelated stock footage. B-roll should match the exact sentence, respect story pacing and avoid repeating clips.",
        "A video or an existing timeline XML, stock API keys and/or a local footage library.",
        "BROLL_SEQUENCE.xml, conformed muted media, alternatives and report.html with swap/remove/rebuild controls.",
        "CPU-capable. Local language and visual models are faster with a GPU; web access is used for stock search.",
        [
            "The shared transcript becomes phrase-level story units with exact timeline times.",
            "A local Qwen planner summarizes the video, decides which phrases benefit from a cutaway and writes English visual search descriptions.",
            "Candidates come from the creator's local library first, then Pexels and Pixabay when configured.",
            "CLIP-style visual-text ranking compares sampled candidate frames with the requested visual meaning.",
            "Placement logic protects the opening hook, enforces density and spacing, prevents duplicate clips and chooses shorter durations for Reels than long-form video.",
            "Every selected clip is cropped/scaled to the sequence canvas, converted to the correct frame rate, muted, and placed on V2 without changing dialogue.",
        ],
        [("Qwen", "Story summary and visual planning"), ("Pexels / Pixabay", "Stock video search"),
         ("Local media library", "Creator-owned footage"), ("CLIP ranking", "Visual-text similarity"),
         ("PyAV / OpenCV", "Frame sampling and conforming")],
        ["Local footage wins when quality is comparable.", "No asset is reused inside the same run.",
         "XML input preserves the creator's existing edit and adds a new layer.", "The report stores alternatives so replacements do not require a full new analysis."],
        ["Duration, density, overlap, media existence, canvas size and timeline validity are checked."],
        ["Stock results depend on search APIs and their licenses.", "Semantic ranking cannot guarantee creative taste; the review page is part of the design."],
        "hinglish_broll/ (planner, stock, library, ranker, placement, conform, xml_export)",
        "I built a local B-roll assistant that understands the spoken idea, searches owned and stock footage, ranks candidates visually, conforms the selected media and adds it to a new editable sequence with human swap controls."),

    Feature(5, "Smart Visuals", "Verified real people, brands, places and events",
        "When a creator mentions Gandhi, Zomato or a specific temple, a generic stock clip is not enough. The editor needs the exact real entity and proof that the asset actually represents it.",
        "Video/XML, optional script, density, full-screen/pop-up preference, AI-brain and evaluator choices.",
        "VISUALS_SEQUENCE.xml, preview.mp4, report.html, EVALUATION.json, downloaded media and CREDITS.txt.",
        "CPU/GPU local reasoning; web access for search. Vision checking is faster with Ollama on capable hardware.",
        [
            "A local Qwen agent reads the whole story, corrects likely ASR spellings and extracts people, brands, places and events.",
            "Entity resolution finds the exact Wikidata/Wikipedia identity before asset retrieval.",
            "The search layer uses Wikipedia/Wikimedia, DDGS web image search, Pexels/Pixabay and yt-dlp for the needed segment from supported video sites.",
            "A local qwen2.5vl:7b vision evaluator, or a CLIP fallback, rejects wrong identity, wrong asset type, watermarks, screenshots, collages and poor quality.",
            "Full-screen visuals cover story/fact lines; logos and faces can appear as transparent pop-ups timed to the naming word and positioned away from the speaker's face.",
            "The final sequence separates full-screen and overlay tracks and saves source credits for publishing.",
        ],
        [("Qwen3 / built-in Qwen", "Context-aware entity planning"), ("Wikidata / Wikipedia", "Identity resolution and trusted media"),
         ("DDGS + yt-dlp", "Web image/video retrieval"), ("qwen2.5vl:7b", "Local visual verification"),
         ("Pexels / Pixabay", "Licensed stock alternatives")],
        ["The agent carries story context so the same name is not resolved independently on every line.",
         "Every used asset records URL, credit and evaluation evidence.", "Script spelling guidance corrects names without rewriting the speech."],
        ["Identity, category, legibility, watermark, quality, timing, overlap and file existence checks."],
        ["Arbitrary web media may be copyrighted even when technically downloadable.",
         "A vision model can still misidentify difficult subjects; the evidence remains reviewable."],
        "hinglish_visuals/ (brain, planner, gather, websearch, evaluator, layout, render, report)",
        "I built a context-aware research and visual-placement agent. It resolves exact entities, gathers candidate media from trusted and web sources, verifies each asset with a local vision model, saves credits, and places full-screen or transparent visuals on an editable timeline."),

    Feature(6, "Smart Zoom", "Face-aware emphasis on stressed words",
        "Manual zoom keyframing is repetitive, but automatic zooms easily become random or jittery. The system must use zooms sparingly and land them on meaningful words.",
        "Video or timeline XML, style, strength, frequency, face option and optional jump-cut reframing.",
        "ZOOMED_SEQUENCE.xml, preview.mp4 and report.html.",
        "CPU-friendly; local AI planning can use CPU or CUDA.",
        [
            "The transcript and local planner identify important phrases and the stressed word inside each phrase.",
            "Short-form and long-form profiles apply different spacing, hold and easing durations so the pacing matches the format.",
            "OpenCV YuNet samples frames and estimates the speaker's eye position. A zoom is face-directed only when the face is present and stable.",
            "A per-frame curve generates smooth sine easing, punch cuts, 4.5% impact overshoot with settle, zoom-out reveals and slow pushes.",
            "Scale values are quantized to 0.01% to eliminate visible stepping. Position keyframes keep the face centered without exposing frame edges.",
            "The XML writer applies frame-by-frame scale/position values to a copied timeline and leaves audio untouched.",
        ],
        [("Qwen/local planner", "Moment and stressed-word selection"), ("OpenCV YuNet", "Face/eye location"),
         ("NumPy", "Per-frame motion curves"), ("FCP XML keyframes", "Editor-native scale and position animation")],
        ["Zooms do not cross shot changes.", "B-roll-covered regions can be skipped.",
         "When the face is unreliable, the engine safely aims at the frame centre.", "Optional alternating framing helps hide jump cuts."],
        ["Spacing, event bounds, curve continuity, safe framing and XML validity are checked."],
        ["Face detection is less reliable with profiles, occlusion or multiple people.", "Automatic emphasis is a creative suggestion, so density remains user-controlled."],
        "hinglish_zoom/ (planner, events, curve, faces, shots, xml_apply, preview)",
        "I built a semantic zoom engine that chooses meaningful words, detects the speaker's face, generates smooth per-frame curves and writes native editor keyframes. It is deliberately sparse and protects shot boundaries and frame edges."),

    Feature(7, "Sound Design", "Music, effects and transitions by meaning",
        "A professional edit needs motivated sound, voice-safe loudness and musical spacing. Keyword-only effects feel random and peak-only mixing makes effects either inaudible or harsh.",
        "Video or finished XML timeline, local music/SFX libraries, style, density and optional script.",
        "SOUND_SEQUENCE.xml, dialogue/music/effects stems, mixed preview, sound-plan.json and report.html.",
        "Local CPU/GPU. Ollama is used for best planning; CLAP can run on CPU or CUDA.",
        [
            "Ollama qwen3:8b reads the story, line tone, prosody and existing edit events, then designs a sparse music/effect plan with a reason for every cue.",
            "qwen3-embedding:0.6b builds a multilingual vector index over the sound library. Retrieval supplies real candidate files instead of invented names.",
            "LAION CLAP listens to candidate files so selection reflects what they actually sound like, not only filenames and tags.",
            "Effects are peak-synchronised to exact words; B-roll cuts and zoom landings can receive transition sounds within the density budget.",
            "The mixer high-passes dialogue, ducks music under speech, creates a 2 kHz voice pocket, limits transients, targets about -14 loudness and keeps a -2 dB peak ceiling.",
            "The evaluator checks chosen assets and the final mix. Unticked sounds on the report page become local taste examples for future planning.",
        ],
        [("qwen3:8b", "Story and emotion-aware sound direction"), ("qwen3-embedding:0.6b", "Vector retrieval"),
         ("LAION CLAP", "Audio-content understanding"), ("Torch / torchaudio / NumPy", "DSP and mixing"),
         ("FCP XML", "Separate editable music and SFX tracks")],
        ["Every effect needs a semantic reason.", "Sad or serious lines are protected from playful sounds.",
         "Music changes only at real emotional turns.", "Voice-relative loudness and crest control work better than raw peak matching."],
        ["Asset relevance, cue density, spacing, loudness, clipping, speech audibility and final-mix limits are measured."],
        ["Quality depends on the creator's music/SFX library.", "Taste is subjective; the review and learning loop is essential."],
        "hinglish_sound/ (director, vectors, listen, cues, mix, evaluator, learning, xml_export)",
        "I built a semantic sound-design system with retrieval-augmented generation. A local model plans motivated cues, embeddings retrieve candidates, CLAP listens to them, and a DSP mixer protects the voice and exports editable stems and timeline tracks."),

    Feature(8, "Eye Contact", "RTX gaze correction with timeline preservation",
        "Reading a script often pulls the speaker's eyes away from the lens. The correction must look natural and must preserve every edit, audio track and timestamp.",
        "Camera videos or an edited timeline XML, near/far script position, natural-look-away option and eye-size sensitivity.",
        "Eye-contact media copies, relinked EYE_CONTACT_SEQUENCE.xml, side-by-side preview and report.",
        "NVIDIA RTX GPU plus NVIDIA Maxine AR SDK. The GTX 1650 can only run pipeline simulation.",
        [
            "A doctor step checks nvidia-smi, RTX/Tensor-Core support, the Maxine GazeRedirectionApp, DLL paths and model directory.",
            "PyAV/OpenCV prepare upright, constant-frame-rate, 8-bit chunks because the NVIDIA sample ignores phone rotation and does not retain audio.",
            "Maxine processes frames offline with thresholds for near-lens or farther script positions. Natural look-away keeps large intentional glances untouched.",
            "Returned MJPEG frames are mapped back to the source frame timeline; missing frames fall back to the original instead of shortening the file.",
            "The final H.264 copy restores the source audio, timing and metadata. Timeline mode rewrites only file links, so all edits and keyframes stay unchanged.",
        ],
        [("NVIDIA Maxine AR SDK", "Gaze redirection"), ("GazeRedirectionApp", "Offline frame processor"),
         ("PyAV + OpenCV", "CFR preparation and frame reconstruction"), ("NVENC when available", "Efficient final encoding")],
        ["Original files are never overwritten.", "Processing is limited to camera clips in a timeline.",
         "HDR input is explicitly converted to standard 8-bit media for compatibility.", "Scratch-space requirements are calculated before processing."],
        ["GPU/install readiness, frame counts, frame dimensions, output duration and relink validity are checked."],
        ["Requires NVIDIA RTX hardware and the Maxine SDK.", "Extreme gaze angles, glasses and occlusion can reduce realism."],
        "hinglish_eyecontact/ (maxine, media, timeline, pipeline, report)",
        "I built an RTX-only gaze-correction pipeline around NVIDIA Maxine. The difficult engineering work is the media wrapper: correcting rotation and frame rate, restoring audio and timestamps, recovering missing frames and relinking a copied editor timeline without disturbing the edit."),

    Feature(9, "Long to Shorts", "Hook-to-payoff vertical highlight creation",
        "A long video can contain many potential clips, but a good Short must make sense alone, start immediately, end with payoff and fit a vertical social layout.",
        "Finished long video, count/length/pieces, template or face look, optional title/channel/CTA and caption style.",
        "One 1080x1920 MP4 and editable XML per Short, layers, thumbnail, report and project decisions.",
        "CPU supported; CUDA speeds transcription. Local Qwen can run through Ollama or bundled llama.cpp.",
        [
            "The shared transcript is split into approximately five-minute planning parts while preserving global story context.",
            "A local Qwen model proposes a hook, payoff, one to three source pieces, truthful title, reason and shareability score.",
            "Deterministic rules reject connector starts, mid-thought endings, calls to action, invalid lengths, overlapping pieces, duplicated moments and cuts inside words.",
            "The template look creates a dark blurred background, framed source video, glow, red title bar and channel CTA; face look creates a 9:16 face-tracked crop.",
            "PyAV joins video/audio pieces on exact frame/sample boundaries with short fades to avoid clicks. Optional Auto Captions becomes a separate editable layer.",
            "The XML reproduces the render as editable background, source, graphics and caption tracks.",
        ],
        [("Qwen3 / local Qwen", "Editorial moment selection"), ("PyAV", "Frame and audio assembly"),
         ("OpenCV", "Face tracking, blur and composition"), ("Pillow", "Titles, glow and frame graphics"),
         ("Auto Captions engine", "Optional animated text layer")],
        ["The model selects ideas; deterministic code enforces timing and editorial rules.",
         "A short can join separated parts of one story while keeping chronological order.", "Finished MP4 and editable XML are generated together."],
        ["Resolution, sound, length, whole-word cuts, hook quality, finished ending, duplication and timeline integrity."],
        ["A transcript mistake can affect title and moment selection.", "Automatic hook scoring is subjective and benefits from the review page."],
        "hinglish_shorts/ (find, source, render, xml, report, pipeline)",
        "I built a local highlight editor that combines LLM editorial judgment with deterministic constraints. It finds hook-to-payoff stories, enforces whole-word and duration rules, renders vertical social video, and produces matching editable timelines."),

    Feature(10, "AI Images", "Locally generated story illustrations",
        "Some script moments need a custom visual that stock search cannot provide, while privacy and recurring API costs make cloud generation undesirable.",
        "Script and optionally a video/XML, style, density/count, aspect ratio and one to four options per moment.",
        "Chosen PNGs, alternative images, placement clips, AI_IMAGES_SEQUENCE.xml, report and model-check data.",
        "NVIDIA GPU required. Automatic full/offload/low-memory modes support different VRAM sizes; 12 GB RTX is the target.",
        [
            "Qwen reads the story, selects visually useful moments and writes a concrete 20-70 word prompt describing subject, setting, light, camera and composition.",
            "Entity rules prohibit generation of named real people and brands; those are routed to Smart Visuals.",
            "A separate isolated GPU worker loads Z-Image Turbo through Diffusers, uses nine-step generation and seeded jobs, and keeps large models in D:\\HinglishEditorModels.",
            "VRAM detection chooses full, CPU-offload or low-memory mode and releases Ollama GPU memory before diffusion begins.",
            "qwen2.5vl:7b checks relevance, anatomy, text artifacts and accidental real brands/faces. A failed moment is generated once more and the best passing option is selected.",
            "When a source timeline exists, the image receives a gentle push and is placed on V2 for the selected spoken span.",
        ],
        [("Z-Image Turbo", "Apache-2.0 image diffusion model"), ("Hugging Face Diffusers", "Generation pipelines"),
         ("PyTorch CUDA", "GPU inference"), ("qwen2.5vl:7b", "Local visual quality evaluator"),
         ("Separate Python environment", "Dependency and GPU-memory isolation")],
        ["Planning and generation are separate, making prompts reviewable.", "The job protocol survives worker failures and records elapsed time/error per option.",
         "Custom styles are stored locally and added consistently to every prompt."],
        ["Prompt length, density, spacing, forbidden entities, file existence, evaluator verdict and XML placement."],
        ["Small GPUs are extremely slow.", "Generative models can still create visual artifacts; the checker reduces but cannot eliminate them."],
        "hinglish_aiimage/ + shared hinglish_aigen/ + tools/aigen/worker.py",
        "I built a local, reviewable image-generation workflow. A language model chooses moments and prompts, an isolated Z-Image GPU worker generates options, a local vision model rejects bad results, and the chosen assets are placed on an editable timeline."),

    Feature(11, "AI Video", "Locally generated five-second motion clips",
        "A few story beats require movement rather than a still image, but generating every line would be expensive, slow and visually inconsistent.",
        "Script and optionally video/XML, style, sparse count, aspect ratio, first-frame options and text-only/image-to-video mode.",
        "Chosen MP4 clips, first-frame choices, AI_VIDEO_SEQUENCE.xml, report and evaluation data.",
        "NVIDIA RTX recommended. The current GTX 1650 test took about seven hours for two seconds; production target is a 12 GB RTX 5070 Ti.",
        [
            "Qwen selects only moments that benefit from motion: journeys, crowds, weather, transformations, reveals or time passing.",
            "For each moment it writes a static first-frame description plus one simple, physically plausible motion sentence.",
            "By default Z-Image Turbo generates and the vision model approves a sharp first frame. Text-only mode skips this stage.",
            "The isolated worker loads Wan 2.2 TI2V 5B, encodes prompts with UMT5 and generates a five-second 24 fps 720p clip through Diffusers.",
            "Three frames are sampled for visual evaluation. The review page can choose another first frame and regenerate only that clip.",
            "Accepted clips are placed on V2 over the exact story moments in a copied timeline.",
        ],
        [("Wan 2.2 TI2V 5B", "Apache-2.0 text/image-to-video model"), ("Z-Image Turbo", "Optional first frame"),
         ("UMT5", "Video prompt encoder"), ("Diffusers + PyTorch", "Generation runtime"),
         ("qwen2.5vl:7b", "Frame-sampled evaluator")],
        ["Sparse planning controls cost and keeps movement meaningful.", "Text-only and image-to-video paths share planning, review and placement logic.",
         "The heavy models live outside the editor environment to prevent dependency conflicts."],
        ["Motion sentence, duration, frame size/rate, three-frame relevance and placement timeline checks."],
        ["Generation is computationally heavy and not practical on 4 GB VRAM.", "Temporal artifacts can pass a still-frame evaluator; final playback review remains required."],
        "hinglish_aivideo/ + shared hinglish_aigen/ + tools/aigen/worker.py",
        "I built a selective local video-generation pipeline instead of generating everything. It plans only motion-worthy beats, creates or skips a first frame, animates with Wan 2.2, checks multiple frames and regenerates individual clips without redoing the project."),

    Feature(12, "Motion Graphics", "Template-driven animated storytelling",
        "Captions alone cannot explain every idea. Motion graphics need semantic scene planning, real assets, consistent style, clean animation and editable timeline placement.",
        "Script, video or XML; style/theme, full or key-moment coverage, full-screen/overlay mode and web/stock/AI asset strategy.",
        "Full MOTION_GRAPHICS.mp4 when requested, scene MP4s, transparent MOV overlays, stills, assets, MOTION_GRAPHICS_SEQUENCE.xml and report.",
        "CPU + Edge/Chrome for rendering; optional GPU for AI objects and local vision checks.",
        [
            "Qwen converts story beats into structured scenes such as cut-out hero, photo card, spotlight, object drop, collage, versus, clip window, silhouette, route map, chat, stamp, timeline and end card.",
            "Rules enforce spoken numbers only, short viewer-facing text, asset counts, scene variety and real entities only when actually mentioned.",
            "Assets come from Wikipedia/web, Pexels/Pixabay, or the AI Images engine. A vision model rejects wrong or poor assets.",
            "rembg removes backgrounds locally: BiRefNet-style sessions for people and ISNet for objects. Cached cut-outs avoid repeated work.",
            "HTML/CSS templates implement bezier entrances, overshoot, shadows, write-ons, type fitting, camera movement, grain and responsive 16:9/9:16/1:1 layouts.",
            "Playwright drives Microsoft Edge frame by frame. PyAV encodes H.264 full-screen scenes and qtrle transparent overlays; XML places them on V2/V3.",
            "Style memory measures reference colours, texture, type and motion, saves a style card, and only exposes approved cards for production use.",
        ],
        [("Qwen", "Scene and asset planning"), ("Wikipedia / web / stock", "Real-world media"),
         ("AI Images", "Custom symbolic objects"), ("rembg / ONNX", "Local background removal"),
         ("HTML/CSS + Playwright + Edge", "Deterministic animation rendering"), ("PyAV", "MP4/MOV output")],
        ["The semantic plan is separate from the deterministic renderer.", "Missing assets trigger scene fallback rather than blank output.",
         "Layout checks measure actual rendered text.", "The review page rebuilds changed scenes instead of regenerating everything."],
        ["Asset identity/quality, text fit, overlap, spoken-number evidence, scene timing, coverage, audio and timeline validity."],
        ["Web assets require license review.", "AI objects and background removal are slow on small GPUs.",
         "3D model integration and tracked callouts are future work, not current claims."],
        "hinglish_motion/ (plan, assets, style, web/scene.html, render, pipeline, report)",
        "I built a hybrid motion-graphics system: AI handles semantic scene planning and asset intent, while a deterministic HTML/CSS renderer controls typography, animation and layout. The result is frame-rendered locally and exported as editable full-screen or transparent timeline layers."),
]


def feature_story(f: Feature):
    story = [PageBreak(), P(f"{f.number:02d} / 12", "cover_kicker"), P(f.name, "h1"), P(f.subtitle, "h2")]
    story += [box("THE PRODUCT PROBLEM", f.problem, ORANGE)]
    story += [info_table([
        ("Input", f.inputs), ("Output", f.outputs), ("Hardware", f.hardware), ("Code", f.folders)
    ], widths=(31, 139))]
    story += [P("How the feature works", "h2"), numbered(f.workflow)]
    story += [P("Main tools and why they are used", "h2"), info_table(f.stack, widths=(48, 122), header=("Tool / model", "Role in the feature"))]
    story += [P("Important engineering decisions", "h2"), bullets(f.engineering, color=PURPLE)]
    story += [P("Quality checks", "h2"), bullets(f.quality, color=GREEN)]
    story += [P("Honest limitations", "h2"), bullets(f.limitations, color=ORANGE)]
    story += [box("HOW TO EXPLAIN IT IN AN INTERVIEW", f.interview, BLUE)]
    return story


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    story = []

    # Cover
    story += [Spacer(1, 38 * mm), P("PROJECT ARCHITECTURE + INTERVIEW HANDBOOK", "cover_kicker"),
              P("HINGLISH EDITOR", "cover_title"),
              P("A local-first AI video editing system with 12 integrated tools", "cover_sub"),
              Spacer(1, 10 * mm)]
    cover = Table([
        [P("12", "cover_title"), P("TOOLS", "cover_kicker")],
        [P("267", "cover_title"), P("AUTOMATED TESTS PASSING", "cover_kicker")],
        [P("LOCAL", "cover_title"), P("AI + EDITABLE TIMELINES", "cover_kicker")],
    ], colWidths=[52 * mm, 92 * mm])
    cover.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -2), .4, colors.HexColor("#31456F")),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [cover, Spacer(1, 18 * mm), P("Prepared as a clear explanation for interviews, project reviews and portfolio discussions.", "cover_meta"),
              P("Project root: E:\\remove silence  |  Updated: 30 September 2026", "cover_meta")]

    # Executive summary
    story += [PageBreak(), P("Executive summary", "h1"),
              P("Hinglish Editor is a Windows desktop video-editing assistant designed for creators who speak Hindi and English in Roman script. It combines speech understanding, semantic planning, computer vision, audio intelligence, local generative AI and professional timeline export in one application."),
              P("The central engineering idea is <b>AI proposes; deterministic code verifies and renders</b>. Language models decide what an editor might do, while explicit rules check timing, identity, layout, media properties and timeline validity. Every important result remains reviewable and editable."),
              box("ONE-SENTENCE PORTFOLIO DESCRIPTION",
                  "I built a local-first AI video editing suite with twelve tools that understand Roman Hinglish, automate picture and sound decisions, generate or retrieve media, render graphics, and export non-destructive Premiere Pro and DaVinci Resolve timelines.", BLUE),
              P("What makes the project different", "h2"), bullets([
                  "Roman-Hinglish speech is treated as a first-class problem through local ASR, forced word alignment and spelling guidance.",
                  "The system is local-first: videos, transcripts, API keys and model decisions stay on the machine; only requested web/stock searches leave the PC.",
                  "Each feature creates a new result and never overwrites the original source or sequence.",
                  "Finished media and editable XML are produced together, so automation does not lock the creator into a black box.",
                  "A shared Quality Evaluator combines hard rules, model checks and corrective retries.",
                  "Browser-based review pages let the creator correct, swap, remove and rebuild decisions.",
              ])]

    # Contents
    story += [PageBreak(), P("The twelve tools", "h1")]
    grid = []
    for i in range(0, 12, 2):
        left, right = features[i], features[i + 1]
        grid.append([
            P(f"<b>{left.number:02d}. {left.name}</b><br/><font color='#5E6A82'>{left.subtitle}</font>", "toc"),
            P(f"<b>{right.number:02d}. {right.name}</b><br/><font color='#5E6A82'>{right.subtitle}</font>", "toc"),
        ])
    toc = Table(grid, colWidths=[84 * mm, 84 * mm], rowHeights=[24 * mm] * 6)
    toc.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), .5, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    story += [toc, Spacer(1, 8 * mm), P("The rest of the handbook explains the shared architecture, each feature's workflow and technology, testing evidence, hardware strategy, project structure and interview answers.")]

    # Architecture
    story += [PageBreak(), P("System architecture", "h1"),
              P("The twelve tools are separate feature packages connected through a common local application and a common set of media, transcript, evaluation and timeline services."),
              architecture_table(), Spacer(1, 6 * mm),
              P("A typical request moves through six stages", "h2"), numbered([
                  "The user chooses a source video, folder, script or existing editor timeline from the standalone app, Premiere panel or Resolve script.",
                  "The local server validates paths and settings, starts a background job and streams visible progress.",
                  "Shared media and transcript services inspect the source, reuse cached analysis and produce timed words or timeline events.",
                  "The selected feature performs semantic planning, retrieval, generation, rendering or signal processing.",
                  "The Quality Evaluator applies hard rules, asks the model to repair structured decisions when appropriate, and records the checks.",
                  "The system writes media, JSON decisions, a review page and a new editable XML timeline. The original remains untouched.",
              ]),
              P("Shared technical foundation", "h2"), info_table([
                  ("Python 3.10-3.13", "Core application and feature engines."),
                  ("PyAV", "Frame-accurate media probing, audio/video decoding, encoding and timestamp handling."),
                  ("NumPy / OpenCV / Pillow", "Signal processing, computer vision, typography and compositing."),
                  ("PyTorch / Transformers", "Local speech, language, audio and diffusion models."),
                  ("Ollama + llama.cpp", "Optional local reasoning models with a bundled fallback."),
                  ("FCP 7 XML", "Interchange format used to create editable Premiere Pro and Resolve sequences."),
                  ("Local HTTP server", "One bridge shared by the dashboard and editor panels."),
                  ("HTML review pages", "Human-in-the-loop correction and selective rebuild."),
              ], widths=(46, 124), header=("Foundation", "Why it exists"))]

    # Product / integration
    story += [PageBreak(), P("Application and editor integration", "h1"),
              P("The same feature engine is exposed through three user surfaces. This prevents the Premiere, Resolve and standalone workflows from drifting into separate implementations."),
              info_table([
                  ("Standalone app", "A local HTML/CSS/JavaScript dashboard served by Python. Native Windows file pickers return paths without browser upload."),
                  ("Premiere CEP", "Exports the active sequence as Final Cut Pro XML through ExtendScript, sends it to the local engine and imports the generated XML."),
                  ("Premiere UXP", "Uses ProjectConverter APIs on supported Premiere versions and imports the returned sequences into the active project."),
                  ("DaVinci Resolve Studio", "A Python adapter exports the open timeline as FCP 7 XML and imports the generated result."),
              ], widths=(42, 128), header=("Surface", "Integration")),
              P("Local-server safeguards", "h2"), bullets([
                  "The server binds to 127.0.0.1 only.", "Origins and host headers are checked.",
                  "A local token protects state-changing routes.", "Only generated XML paths are accepted for import.",
                  "API keys are stored in machine-local configuration and are not displayed again.",
              ]),
              box("INTERVIEW POINT", "The product is not twelve disconnected scripts. It is one local platform with shared orchestration, analysis, review and timeline-export layers, and twelve feature-specific engines.", PURPLE)]

    # Features
    for feature in features:
        story.extend(feature_story(feature))

    # Shared quality evaluator
    story += [PageBreak(), P("Shared Quality Evaluator", "h1"),
              P("Generative systems fail in different ways: malformed JSON, invented numbers, wrong images, clipped typography, invalid timelines or unsafe audio levels. The project treats quality as a separate system rather than scattering a few assertions inside each feature."),
              P("Evaluation loop", "h2"), numbered([
                  "A feature asks the local model for structured JSON constrained by a schema.",
                  "Feature-specific rules label problems as hard or soft and produce concrete repair instructions.",
                  "The model receives the exact failures and gets another attempt.",
                  "Deterministic repair code fixes safe mechanical issues such as bounds, ordering or missing viewer-facing text.",
                  "Rendered media and timelines receive post-generation checks.",
                  "Every attempt, repair and final result is saved beside the output for review.",
              ]),
              info_table([
                  ("Text/timing", "Required fields, line IDs, duration, word boundaries, ordering, duplication, spoken-number evidence."),
                  ("Visual", "Identity, category, relevance, watermark, collage/screenshot detection, anatomy, legibility and layout."),
                  ("Audio", "Cue relevance, density, speech audibility, loudness, clipping, crest factor and final mix."),
                  ("Media", "File existence, codec, dimensions, frame rate, duration, audio streams and transparency."),
                  ("Timeline", "Valid XML, source references, non-overlap, track placement and preserved original edit."),
              ], widths=(42, 128), header=("Check family", "Examples")),
              box("WHY THIS MATTERS IN AN INTERVIEW", "The evaluator demonstrates that I did not treat an LLM answer as truth. I combined probabilistic planning with deterministic invariants, retry limits, recorded evidence and human review.", GREEN)]

    # Data and folder structure
    story += [PageBreak(), P("Project structure", "h1"),
              P("The repository separates feature behavior, shared infrastructure, model environments, editor adapters and generated results."),
              info_table([
                  ("hinglish_app/", "Dashboard, local HTTP bridge, jobs, settings and editor integration."),
                  ("hinglish_cut/", "Shared media, transcription, alignment, matching and FCP XML foundation."),
                  ("hinglish_clean/", "Smart Clean."), ("hinglish_semantic/", "Script Edit and Clean+."),
                  ("hinglish_captions/", "Auto Captions and Typography 1-5."),
                  ("hinglish_broll/", "B-roll planning, retrieval, ranking and conforming."),
                  ("hinglish_visuals/", "Entity resolution, web research, vision checking and visual placement."),
                  ("hinglish_zoom/", "Semantic zoom planning, face tracking and XML keyframes."),
                  ("hinglish_sound/", "RAG sound planning, audio understanding, DSP mix and learning."),
                  ("hinglish_eyecontact/", "NVIDIA Maxine wrapper and timeline relinking."),
                  ("hinglish_shorts/", "Long-video moment selection, 9:16 render and XML."),
                  ("hinglish_aigen/", "Shared AI Images/Video planning, judge, report and engine protocol."),
                  ("tools/aigen/", "Isolated Diffusers GPU worker."),
                  ("hinglish_motion/", "Scene planning, assets, themes, HTML renderer and reports."),
                  ("hinglish_eval/", "Shared rule/model evaluation and correction records."),
                  ("editor_plugins/", "Premiere CEP/UXP and Resolve-facing integration."),
                  ("cache/", "Reusable transcripts, frames, model decisions, embeddings and local learning."),
                  ("output/", "Dated, non-overwriting result folders for every feature."),
                  ("D:\\HinglishEditorModels", "Large AI image/video models and separate Python environment."),
              ], widths=(48, 122), header=("Path", "Responsibility"))]

    # Hardware matrix
    story += [PageBreak(), P("Hardware and deployment strategy", "h1"),
              P("The application is designed to remain useful on CPU while enabling heavier features on NVIDIA RTX hardware. Hardware checks fail clearly instead of silently using an unsuitable path."),
              info_table([
                  ("Smart Clean", "CPU", "Fast local speech detection."),
                  ("Script Edit", "CPU / CUDA", "CUDA helps ASR, alignment and local model inference."),
                  ("Auto Captions", "CPU / CUDA", "Rendering is CPU; CUDA helps transcription."),
                  ("B-roll", "CPU / optional GPU", "Web/library work is CPU; models benefit from acceleration."),
                  ("Smart Visuals", "CPU / optional GPU", "Web research plus local language/vision models."),
                  ("Smart Zoom", "CPU / CUDA", "YuNet and curve generation are lightweight."),
                  ("Sound Design", "CPU / CUDA", "Ollama and CLAP are the heavier components."),
                  ("Eye Contact", "RTX required", "NVIDIA Maxine needs Tensor Cores."),
                  ("Long to Shorts", "CPU / CUDA", "Rendering works on CPU; CUDA helps transcription."),
                  ("AI Images", "NVIDIA GPU", "Target: 12 GB RTX; low mode works slowly on 4 GB."),
                  ("AI Video", "NVIDIA RTX", "Target: 12 GB; impractical on 4 GB for production."),
                  ("Motion Graphics", "CPU + browser; GPU optional", "Edge renders scenes; GPU is used for AI objects/vision."),
              ], widths=(42, 38, 90), header=("Feature", "Hardware", "Practical note")),
              P("Measured live-test evidence on the GTX 1650 laptop", "h2"), bullets([
                  "Long to Shorts: a 23.20-second 1080x1920 short with H.264 video and stereo AAC audio.",
                  "AI Images: one 832x480 image generated in 461.7 seconds and accepted by the vision reviewer at 8/10.",
                  "Motion Graphics: a clean three-second 1280x720 object-drop scene using a locally generated gear; the AI object took 547 seconds.",
                  "AI Video: intentionally skipped in the latest live test because the previous measured run took about seven hours for two seconds at 832x480.",
              ])]

    # Visual proof page
    story += [PageBreak(), P("Selected output evidence", "h1"),
              P("These images come from real project outputs and demonstrate three different parts of the system: animated captions, generative visuals and deterministic motion graphics.")]
    images = [
        (ROOT / "output/captions/20260920-160836-70fd9b/001-phase2-retake-fixture-6b2647c045747676d91a-semantic-30fps/typography-5-proof.jpg", "Auto Captions: Typography 5 proof"),
        (ROOT / "output/aiimage/20260929-073706-ab78e8/001-as/chosen/01 - Machine-ka-tab-koi-vazan-nahin-rahta.png", "AI Images: locally generated industrial visual"),
        (ROOT / "output/motion/20260929-192259-5cbe3e/001-as/stills/01-object_drop-8d26.jpg", "Motion Graphics: generated object + HTML/CSS animation frame"),
    ]
    for path, caption in images:
        if path.exists():
            from PIL import Image as PILImage
            with PILImage.open(path) as im:
                w, h = im.size
            max_w, max_h = 165 * mm, 64 * mm
            scale = min(max_w / w, max_h / h)
            pic = Image(str(path), width=w * scale, height=h * scale)
            pic.hAlign = "CENTER"
            story += [pic, Spacer(1, 2 * mm), P(caption, "small"), Spacer(1, 5 * mm)]

    # Testing and reliability
    story += [PageBreak(), P("Testing and reliability", "h1"),
              P("The verified project state at the time of this handbook is <b>267 automated tests passing</b>. The suite covers media timing, text grouping, semantic rules, XML construction, layout, generated-media planning, review actions and integration behavior."),
              P("What is tested", "h2"), bullets([
                  "Frame and sample conversions across common frame rates.", "Silence detection ranges and preservation checks.",
                  "Transcript normalization, numeric timing and acronym merging.", "Semantic candidate selection and cleanup rules.",
                  "Caption grouping, style rendering, font fitting, word colours and transparent output.",
                  "B-roll/visual placement, non-overlap, asset ranking and timeline layering.",
                  "Zoom curve continuity, overshoot, safe crop and face-directed framing.",
                  "Sound retrieval, cue placement, loudness calculations and XML stems.",
                  "Shorts constraints, audio joins, vertical layout and editable layers.",
                  "AI generation planning, forbidden entities, retry behavior and vision verdicts.",
                  "Motion scene rules, text layout, browser frame rendering and asset fallbacks.",
                  "Local app request validation, settings and editor-result discovery.",
              ]),
              P("Reliability patterns", "h2"), info_table([
                  ("Caching", "Completed transcripts, embeddings, asset decisions and media analysis are reused by content/settings hash."),
                  ("Atomic writes", "Important JSON and output state are written safely to reduce corruption after interruption."),
                  ("Retry limits", "Model and generation retries are bounded; the system does not loop indefinitely."),
                  ("Graceful fallback", "Missing optional models can use a simpler local path or produce an explicit review state."),
                  ("Evidence", "Decision JSON, model checks, credits and review pages remain beside the media."),
              ], widths=(42, 128), header=("Pattern", "Implementation value"))]

    # Privacy, copyright, limits
    story += [PageBreak(), P("Privacy, copyright and honest boundaries", "h1"),
              P("A strong project explanation includes what the system deliberately does not promise."),
              P("Privacy", "h2"), bullets([
                  "Speech recognition, language reasoning, vision evaluation, audio analysis and generation run locally when the corresponding models are installed.",
                  "Videos and scripts are not uploaded to a hosted AI API.", "Pexels/Pixabay keys remain in local configuration.",
                  "Web searches necessarily send search words to external sites; downloaded web media retains source information.",
              ]),
              P("Copyright", "h2"), bullets([
                  "Creator-owned footage and locally generated media are easiest to clear.",
                  "Pexels/Pixabay assets are used under their platform licenses.",
                  "Arbitrary web images and videos may be copyrighted; the tool saves credits and requires the creator to verify usage rights.",
              ]),
              P("Technical boundaries", "h2"), bullets([
                  "AI output is probabilistic. Rule checks reduce errors but cannot guarantee editorial taste or factual visual identity.",
                  "Word timing is estimated and final cuts land on video frames, not infinitely precise milliseconds.",
                  "Eye Contact and full-quality AI Video depend on suitable RTX hardware.",
                  "AI Video on a 4 GB card is a proof of execution, not a practical production workflow.",
                  "The system creates drafts and reviewable timelines; a creator should still watch and listen before publishing.",
              ]),
              box("GOOD INTERVIEW LANGUAGE", "I designed explicit review points because creative automation is a decision-support system. The goal is to remove repetitive work while keeping the creator responsible for the final editorial and legal decision.", ORANGE)]

    # Interview scripts
    story += [PageBreak(), P("Interview-ready explanations", "h1"),
              P("Thirty-second answer", "h2"), box("SAY THIS",
                  "I built Hinglish Editor, a local-first AI video editing system with twelve tools. It can clean and arrange talking-head footage, create animated captions, add B-roll and verified real-world visuals, design zooms and sound, correct eye contact, turn long videos into Shorts, generate images and video, and create motion graphics. The system combines local speech and language models with deterministic timing, media processing, quality checks, human review pages, and editable Premiere/Resolve XML timelines.", BLUE),
              P("Two-minute answer", "h2"), box("SAY THIS",
                  "The project started with a Roman-Hinglish editing problem: creators record multiple takes and spend hours cleaning pauses, arranging speech and styling captions. I built a Python media foundation around PyAV, Silero VAD, a local Hinglish Whisper model and MMS forced alignment. On top of that I added twelve feature engines. Some features use local language models to make editorial plans; others use computer vision, audio embeddings or diffusion models. I never trust the model output directly: each feature has schemas, hard rules, bounded retries and post-render checks. The application runs locally and exposes the same engines through a standalone dashboard, Premiere panels and Resolve. Every operation creates a new timeline, a review page and machine-readable decision files, so the creator can inspect and change the result. The current suite has 267 passing tests, and I have run live end-to-end tests for the tools this laptop can support.", PURPLE),
              P("Best technical deep-dive", "h2"), box("USE THIS WHEN ASKED FOR A CHALLENGE",
                  "A hard part was word-accurate Roman-Hinglish editing. A transcript alone is not enough because cuts and captions need times, but common Hindi aligners expect Devanagari. I used a multilingual romanized MMS CTC model, wrote a NumPy Viterbi alignment path, and combined it with VAD and frame-aware rounding. That timing layer is reused by captions, B-roll, zoom, Shorts, sound cues and motion placement. It is a good example of solving one foundational problem and turning it into shared infrastructure for many product features.", GREEN)]

    # Interview questions
    story += [PageBreak(), P("Likely interview questions", "h1")]
    qa = [
        ("Why use XML instead of directly controlling Premiere?", "XML keeps the automation editor-independent, inspectable and non-destructive. Premiere and Resolve can import the same timeline structure, and the creator receives an editable result rather than a closed render."),
        ("Why run models locally?", "Privacy, predictable cost and offline reuse matter for long videos. Local execution also lets the project combine many models without per-minute API charges. Web search remains optional and explicit."),
        ("How do you control hallucinations?", "The model returns schema-constrained plans. Feature rules verify IDs, timing, numbers, identity and required fields; exact failures are supplied for a bounded retry; deterministic repair handles safe mechanical issues; rendered output is checked again."),
        ("Why VAD, ASR and forced alignment?", "VAD says where speech exists, ASR says what was said, and forced alignment estimates when each word occurred. All three are needed for safe cuts and word-level effects."),
        ("How is performance managed?", "The system caches expensive analysis, processes long audio in bounded blocks, separates heavyweight diffusion dependencies, chooses VRAM modes automatically and avoids regenerating unchanged scenes or clips."),
        ("How do you preserve user control?", "Originals are untouched; outputs are new XML timelines; every feature writes decisions and a review page; selective rebuild updates only changed items."),
        ("What would you improve next?", "Evaluate on more accents and microphones, test the RTX production target, improve temporal AI-video evaluation, add 3D motion assets and tracked callouts, and build more quantitative visual-quality benchmarks."),
    ]
    for q, a in qa:
        story += [P(q, "h3"), P(a)]

    # Glossary
    story += [PageBreak(), P("Technical glossary", "h1"),
              info_table([
                  ("ASR", "Automatic Speech Recognition: converts speech into words."),
                  ("VAD", "Voice Activity Detection: finds regions that contain speech."),
                  ("Forced alignment", "Maps known transcript words back to estimated audio times."),
                  ("CTC", "A neural sequence objective commonly used for speech alignment."),
                  ("Viterbi", "Dynamic-programming search for the best alignment path."),
                  ("Embedding", "A numeric vector representing meaning; similar items have nearby vectors."),
                  ("RAG", "Retrieval-Augmented Generation: retrieves real candidates before the model decides."),
                  ("CLIP", "A model that compares visual content with text descriptions."),
                  ("CLAP", "An audio-language model that compares sound with text descriptions."),
                  ("Diffusion", "A generative method used by the local image and video models."),
                  ("Inference", "Running a trained model to obtain a result."),
                  ("FCP 7 XML", "A widely supported text representation of video-editing timelines."),
                  ("Alpha channel", "Transparency information used by caption and overlay layers."),
                  ("CFR", "Constant Frame Rate: stable frame timing required by some video processors."),
                  ("LUFS / loudness", "A measure of perceived audio level used for mix targets."),
                  ("Human in the loop", "The system automates suggestions while preserving explicit user review."),
              ], widths=(42, 128), header=("Term", "Plain-language meaning"))]

    # Closing
    story += [PageBreak(), Spacer(1, 28 * mm), P("Closing project statement", "h1"),
              P("Hinglish Editor is a complete local AI media system rather than a single model demo. It combines data pipelines, ML inference, deterministic algorithms, video/audio engineering, browser interfaces, editor interoperability, quality evaluation and human review."),
              P("The strongest project lesson is that useful creative AI needs more than generation. It needs reliable timing, evidence, constraints, recovery paths, editable outputs and honest limits."),
              Spacer(1, 12 * mm), box("FINAL INTERVIEW LINE",
                  "I built the intelligence, the media pipeline and the product workflow around the models. The models make suggestions; the application turns those suggestions into safe, reviewable and editable video work.", ORANGE),
              Spacer(1, 18 * mm), P("Verified project state", "h2"),
              info_table([("Tools", "12 integrated features"), ("Tests", "267 passing"),
                          ("Editors", "Premiere Pro CEP/UXP + DaVinci Resolve Studio"),
                          ("Privacy", "Local-first; web access only for requested media search"),
                          ("Primary output", "Editable timelines plus reviewable media and decision files")], widths=(42, 128))]

    doc = HandbookDoc(str(OUT))
    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    build()
