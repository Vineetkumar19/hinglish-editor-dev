"""read_pdf / read_docx / read_xlsx — spec section 8.4.

Extracts text locally (+ table cells for xlsx, + best-effort OCR fallback
for scanned PDF pages). Chunks long documents so a chat reply doesn't have
to swallow an entire book into one prompt. Real semantic retrieval over
chunks (embeddings + vector search) is Phase 12 — for now the whole
chunk list comes back and the caller/LLM picks what it needs, which is
fine for the document sizes this laptop's context window can handle.

All three tools are scoped to approved directories via the same
allowlist search_files() uses, so the model can't be tricked into reading
arbitrary filesystem paths outside what you've approved.
"""

from pathlib import Path

from core.app_config import approved_search_roots
from core.tool_registry import tool
from core.permissions import RiskLevel
from tools.files import within_approved_roots

CHUNK_SIZE_CHARS = 2000

# A 3B model on this laptop has a small usable context. Handing back an
# entire 80-page PDF made the model either time out or reply with nothing
# useful, which looked like "reading PDFs doesn't work". Cap what goes
# back to roughly what the model can actually reason over, and say plainly
# that it was truncated so the summary can be honest about its scope.
MAX_RETURNED_CHARS = 8000


class PathNotApproved(Exception):
    pass


def _assert_approved(path: str):
    roots = approved_search_roots()
    if not roots or not within_approved_roots(path, roots):
        raise PathNotApproved(
            f"'{path}' is outside the approved search roots (config/settings.json "
            f"permissions.approved_search_roots / approved_folder_aliases)."
        )


def _chunk(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [text[i : i + CHUNK_SIZE_CHARS] for i in range(0, len(text), CHUNK_SIZE_CHARS)]


def _payload(text: str) -> dict:
    """Chunks plus a truncation flag, sized for what the local model can read."""
    text = (text or "").strip()
    if not text:
        return {"chunks": [], "truncated": False, "note": "No extractable text found in this file."}
    truncated = len(text) > MAX_RETURNED_CHARS
    return {
        "chunks": _chunk(text[:MAX_RETURNED_CHARS]),
        "truncated": truncated,
        "total_chars": len(text),
    }


def read_pdf(path: str) -> dict:
    _assert_approved(path)
    if not Path(path).is_file():
        return {"path": path, "error": "File not found."}

    import pypdf

    reader = pypdf.PdfReader(path)
    pages_text = []
    ocr_used = False

    for page in reader.pages:
        text = (page.extract_text() or "").strip()
        if not text:
            # Best-effort OCR fallback for scanned pages. Requires
            # pytesseract + the Tesseract binary + pdf2image/poppler to be
            # installed separately — if they're not, we just note the page
            # came back empty instead of crashing the whole read.
            try:
                import pytesseract
                from pdf2image import convert_from_path

                page_index = reader.pages.index(page)
                images = convert_from_path(path, first_page=page_index + 1, last_page=page_index + 1)
                if images:
                    text = pytesseract.image_to_string(images[0]).strip()
                    if text:
                        ocr_used = True
            except Exception:
                pass
        pages_text.append(text)

    full_text = "\n\n".join(t for t in pages_text if t)
    return {
        "path": path,
        "pages": len(reader.pages),
        "ocr_used": ocr_used,
        **_payload(full_text),
    }


def read_docx(path: str) -> dict:
    _assert_approved(path)
    if not Path(path).is_file():
        return {"path": path, "error": "File not found."}

    import docx

    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))

    full_text = "\n".join(parts)
    return {"path": path, "paragraphs": len(d.paragraphs), **_payload(full_text)}


def read_xlsx(path: str, max_rows_per_sheet: int = 200) -> dict:
    _assert_approved(path)
    if not Path(path).is_file():
        return {"path": path, "error": "File not found."}

    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheets = {}
    for name in wb.sheetnames:
        ws = wb[name]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows_per_sheet:
                break
            rows.append([("" if c is None else c) for c in row])
        sheets[name] = rows

    as_text = "\n\n".join(
        f"Sheet: {name}\n" + "\n".join(", ".join(str(c) for c in row) for row in rows)
        for name, rows in sheets.items()
    )
    return {"path": path, "sheet_names": wb.sheetnames, **_payload(as_text)}


tool(
    name="read_pdf",
    description="Extract text from a PDF file (with OCR fallback for scanned pages, if OCR is set up).",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute path to the PDF, must be in an approved folder."}},
        "required": ["path"],
    },
)(read_pdf)

tool(
    name="read_docx",
    description="Extract text and table contents from a Word .docx file.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute path to the .docx, must be in an approved folder."}},
        "required": ["path"],
    },
)(read_docx)

tool(
    name="read_xlsx",
    description="Read sheet contents from an Excel .xlsx file (up to a row cap per sheet).",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Absolute path to the .xlsx, must be in an approved folder."}},
        "required": ["path"],
    },
)(read_xlsx)
