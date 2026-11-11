"""A small PDF writer - stdlib only.

RenderCV compiles resumes through Typst; Typst is a separate binary and this
project has a hard no-dependency rule, so this module generates the PDF
directly. It writes real text operators with the base-14 fonts, which means the
output is selectable and parseable - exactly what an ATS needs. A PDF of images
would be worse than useless for job applications.

Supports: multiple pages, Helvetica/Times in regular/bold/italic, accurate text
measurement for wrapping, headings, bullets, rules, right-aligned text on the
same line, and clickable links.
"""
from __future__ import annotations

import io
import zlib
from dataclasses import dataclass, field

# Base-14 advance widths (per 1000 units) for ASCII 32..126.
_W_HELV = (
    "278 278 355 556 556 889 667 191 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 278 278 584 584 584 556 "
    "1015 667 667 722 722 667 611 778 722 278 500 667 556 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 278 278 278 469 556 "
    "333 556 556 500 556 556 278 556 556 222 222 500 222 833 556 556 "
    "556 556 333 500 278 556 500 722 500 500 500 334 260 334 584")
_W_HELV_BOLD = (
    "278 333 474 556 556 889 722 238 333 333 389 584 278 333 278 278 "
    "556 556 556 556 556 556 556 556 556 556 333 333 584 584 584 611 "
    "975 722 722 722 722 667 611 778 722 278 556 722 611 833 722 778 "
    "667 778 722 667 611 722 667 944 667 667 611 333 278 333 584 556 "
    "333 556 611 556 611 556 333 611 611 278 278 556 278 889 611 611 "
    "611 611 389 556 333 611 556 778 556 556 500 389 280 389 584")
_W_TIMES = (
    "250 333 408 500 500 833 778 180 333 333 500 564 250 333 250 278 "
    "500 500 500 500 500 500 500 500 500 500 278 278 564 564 564 444 "
    "921 722 667 667 722 611 556 722 722 333 389 722 611 889 722 722 "
    "556 722 667 556 611 722 722 944 722 722 611 333 278 333 469 500 "
    "333 444 500 444 500 444 333 500 500 278 278 500 278 778 500 500 "
    "500 500 333 389 278 500 500 722 500 500 444 480 200 480 541")
_W_TIMES_BOLD = (
    "250 333 555 500 500 1000 833 278 333 333 500 570 250 333 250 278 "
    "500 500 500 500 500 500 500 500 500 500 333 333 570 570 570 500 "
    "930 722 667 722 722 667 611 778 778 389 500 778 667 944 722 778 "
    "611 778 722 556 667 722 722 1000 722 722 667 333 278 333 581 500 "
    "333 500 556 444 556 444 333 500 556 278 333 556 278 833 556 500 "
    "556 556 444 389 333 556 500 722 500 500 444 394 220 394 520")

FONTS = {
    "Helvetica": ("Helvetica", _W_HELV),
    "Helvetica-Bold": ("Helvetica-Bold", _W_HELV_BOLD),
    "Helvetica-Oblique": ("Helvetica-Oblique", _W_HELV),
    "Helvetica-BoldOblique": ("Helvetica-BoldOblique", _W_HELV_BOLD),
    "Times-Roman": ("Times-Roman", _W_TIMES),
    "Times-Bold": ("Times-Bold", _W_TIMES_BOLD),
    "Times-Italic": ("Times-Italic", _W_TIMES),
}
_WIDTHS = {name: [int(x) for x in table.split()] for name, (_, table) in FONTS.items()}

A4 = (595.28, 841.89)
LETTER = (612.0, 792.0)


def text_width(text: str, font: str, size: float) -> float:
    widths = _WIDTHS.get(font, _WIDTHS["Helvetica"])
    total = 0
    for ch in text:
        o = ord(ch)
        total += widths[o - 32] if 32 <= o <= 126 else widths[ord("o") - 32]
    return total * size / 1000.0


def wrap_text(text: str, font: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    for para in (text or "").split("\n"):
        if not para.strip():
            lines.append("")
            continue
        words, cur = para.split(), ""
        for w in words:
            trial = (cur + " " + w).strip()
            if text_width(trial, font, size) <= max_width or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines


def _escape(text: str) -> str:
    out = []
    for ch in text:
        if ch in "()\\":
            out.append("\\" + ch)
        elif ord(ch) < 32:
            out.append(" ")
        elif ord(ch) > 126:
            # WinAnsi approximations for the punctuation LLMs love
            out.append({"–": "-", "—": "-", "‘": "'", "’": "'",
                        "“": '"', "”": '"', "•": "-",
                        "…": "...", " ": " "}.get(ch, "?"))
        else:
            out.append(ch)
    return "".join(out)


@dataclass
class _Page:
    ops: list = field(default_factory=list)
    links: list = field(default_factory=list)   # (x0,y0,x1,y1,url)


class PDF:
    """A simple top-down document builder."""

    def __init__(self, size=A4, margin: float = 54.0, font: str = "Helvetica",
                 size_pt: float = 10.0, leading: float = 1.35):
        self.width, self.height = size
        self.margin = margin
        self.base_font = font
        self.base_size = size_pt
        self.leading = leading
        self.pages: list[_Page] = []
        self.used_fonts: set[str] = set()
        self._new_page()

    # -- geometry ------------------------------------------------------------
    @property
    def content_width(self) -> float:
        return self.width - 2 * self.margin

    def _new_page(self) -> None:
        self.pages.append(_Page())
        self.y = self.height - self.margin

    def _ensure(self, needed: float) -> None:
        if self.y - needed < self.margin:
            self._new_page()

    @property
    def page(self) -> _Page:
        return self.pages[-1]

    # -- primitives ----------------------------------------------------------
    def _draw(self, text: str, x: float, y: float, font: str, size: float,
              gray: float = 0.0) -> None:
        self.used_fonts.add(font)
        self.page.ops.append(
            f"BT /{font.replace('-', '')} {size:.2f} Tf {gray:.2f} g "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({_escape(text)}) Tj ET")

    def text(self, content: str, *, font: str | None = None, size: float | None = None,
             gray: float = 0.0, space_after: float = 0.0, indent: float = 0.0,
             link: str | None = None) -> None:
        font = font or self.base_font
        size = size or self.base_size
        lh = size * self.leading
        for line in wrap_text(content, font, size, self.content_width - indent):
            if not line:
                self.y -= lh * 0.5
                continue
            self._ensure(lh)
            x = self.margin + indent
            self._draw(line, x, self.y - size, font, size, gray)
            if link:
                w = text_width(line, font, size)
                self.page.links.append((x, self.y - size - 2, x + w,
                                        self.y - size + size, link))
            self.y -= lh
        self.y -= space_after

    def heading(self, content: str, *, size: float = 11.0, rule: bool = True,
                space_before: float = 10.0, space_after: float = 4.0) -> None:
        self._ensure(size * 2 + space_before)
        self.y -= space_before
        self._draw(content.upper(), self.margin, self.y - size,
                   self.base_font + "-Bold" if "-" not in self.base_font
                   else self.base_font, size)
        self.y -= size * 1.15
        if rule:
            self.hrule(gray=0.6)
        self.y -= space_after

    def title(self, name: str, subtitle: str = "") -> None:
        self._ensure(40)
        bold = self.base_font + "-Bold" if "-" not in self.base_font else self.base_font
        self._draw(name, self.margin, self.y - 18, bold, 18)
        self.y -= 22
        if subtitle:
            self.text(subtitle, size=9.5, gray=0.35, space_after=2)

    def row(self, left: str, right: str = "", *, font: str | None = None,
            size: float | None = None, bold_left: bool = False,
            gray_right: float = 0.35) -> None:
        size = size or self.base_size
        lfont = ((self.base_font + "-Bold") if bold_left and "-" not in self.base_font
                 else (font or self.base_font))
        rfont = font or self.base_font
        self._ensure(size * self.leading)
        self._draw(left, self.margin, self.y - size, lfont, size)
        if right:
            w = text_width(right, rfont, size)
            self._draw(right, self.width - self.margin - w, self.y - size,
                       rfont, size, gray_right)
        self.y -= size * self.leading

    def bullet(self, content: str, *, size: float | None = None,
               marker: str = "-", indent: float = 10.0) -> None:
        size = size or self.base_size
        lh = size * self.leading
        lines = wrap_text(content, self.base_font, size,
                          self.content_width - indent - 8)
        for i, line in enumerate(lines):
            self._ensure(lh)
            if i == 0:
                self._draw(marker, self.margin + indent - 8, self.y - size,
                           self.base_font, size)
            self._draw(line, self.margin + indent, self.y - size,
                       self.base_font, size)
            self.y -= lh

    def hrule(self, gray: float = 0.75, thickness: float = 0.6) -> None:
        self._ensure(4)
        self.page.ops.append(
            f"{gray:.2f} G {thickness} w {self.margin:.2f} {self.y:.2f} m "
            f"{self.width - self.margin:.2f} {self.y:.2f} l S")
        self.y -= 4

    def space(self, amount: float = 6.0) -> None:
        self.y -= amount

    # -- output --------------------------------------------------------------
    def build(self, compress: bool = True) -> bytes:
        objects: list[bytes] = []

        def add(body: bytes) -> int:
            objects.append(body)
            return len(objects)

        font_objs = {}
        for name in sorted(self.used_fonts | {self.base_font}):
            if name not in FONTS:
                name = "Helvetica"
            font_objs[name] = add(
                f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} "
                f"/Encoding /WinAnsiEncoding >>".encode())

        pages_id = len(objects) + 1 + 2 * len(self.pages) + 1
        page_ids, kids = [], []
        for pg in self.pages:
            stream = "\n".join(pg.ops).encode("latin-1", "replace")
            if compress:
                data = zlib.compress(stream)
                content_id = add(b"<< /Length " + str(len(data)).encode()
                                 + b" /Filter /FlateDecode >>\nstream\n" + data
                                 + b"\nendstream")
            else:
                content_id = add(b"<< /Length " + str(len(stream)).encode()
                                 + b" >>\nstream\n" + stream + b"\nendstream")
            annots = ""
            if pg.links:
                parts = []
                for x0, y0, x1, y1, url in pg.links:
                    parts.append(
                        f"<< /Type /Annot /Subtype /Link /Border [0 0 0] "
                        f"/Rect [{x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}] "
                        f"/A << /S /URI /URI ({_escape(url)}) >> >>")
                annots = " /Annots [" + " ".join(parts) + "]"
            res = " ".join(f"/{n.replace('-', '')} {i} 0 R"
                           for n, i in font_objs.items())
            page_id = add(
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << {res} >> >> "
                f"/Contents {content_id} 0 R{annots} >>".encode())
            page_ids.append(page_id)
            kids.append(f"{page_id} 0 R")

        real_pages_id = add(
            f"<< /Type /Pages /Count {len(page_ids)} "
            f"/Kids [{' '.join(kids)}] >>".encode())
        catalog_id = add(f"<< /Type /Catalog /Pages {real_pages_id} 0 R >>".encode())

        # fix the forward reference to the Pages object
        for idx, pid in enumerate(page_ids):
            objects[pid - 1] = objects[pid - 1].replace(
                f"/Parent {pages_id} 0 R".encode(),
                f"/Parent {real_pages_id} 0 R".encode())

        buf = io.BytesIO()
        buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, body in enumerate(objects, start=1):
            offsets.append(buf.tell())
            buf.write(f"{i} 0 obj\n".encode() + body + b"\nendobj\n")
        xref = buf.tell()
        n = len(objects) + 1
        buf.write(f"xref\n0 {n}\n".encode())
        buf.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            buf.write(f"{off:010d} 00000 n \n".encode())
        buf.write(f"trailer\n<< /Size {n} /Root {catalog_id} 0 R >>\n"
                  f"startxref\n{xref}\n%%EOF\n".encode())
        return buf.getvalue()

    def save(self, path) -> str:
        import pathlib
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.build())
        return str(p)
