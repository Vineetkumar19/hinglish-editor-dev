"""The two documents that turn a conversation into money.

A proposal is what an agency or a brand needs before anyone can sign off
internally - a verbal rate in an email thread is not something a finance team
can act on. An invoice is what gets him paid, and the deposit line on it is the
difference between doing the work and hoping.

Both are built from the rate card and the agreed number. Nothing is calculated
here that is not either on the card or in the deal, so there is no path by
which a document carries a price nobody agreed to.
"""
from __future__ import annotations

import pathlib
import time
import uuid

from core import config
from core.log import get_logger
from core.pdf import PDF

from .pitch import load_profile, portfolio_links
from .quote import Quote, rules

log = get_logger("video.docs")


def output_dir() -> pathlib.Path:
    d = pathlib.Path(config.get("VIDEO_DOC_DIR",
                                str(config.data_dir() / "video_docs")))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(text: str) -> str:
    keep = "".join(c if c.isalnum() else "-" for c in str(text or "").lower())
    return "-".join(p for p in keep.split("-") if p)[:50] or "client"


def _header(doc: PDF, title: str) -> None:
    p = load_profile()
    contact = p.get("contact") or {}
    doc.title(p.get("name") or config.get("OPERATOR_NAME", "Vineet"),
              p.get("headline", "Video Editor and Motion Graphics Artist"))
    bits = [contact.get("email", ""), contact.get("phone", ""),
            contact.get("location", "")]
    line = "  |  ".join(b for b in bits if b)
    if line:
        doc.text(line, size=9, gray=0.35)
    links = portfolio_links()
    if links:
        doc.text("  |  ".join(links[:2]), size=9, gray=0.35)
    doc.space(10)
    doc.heading(title)


# --------------------------------------------------------------------------
def proposal(gig: dict, quote: Quote, *, amount: float | None = None,
             scope: list[str] | None = None) -> str:
    """A scoped proposal an internal approver can actually act on."""
    total = quote.ask if amount is None else amount
    company = gig.get("company") or "Client"
    doc = PDF(margin=50, font="Helvetica", size_pt=10, leading=1.35)
    _header(doc, f"Proposal for {company}")

    doc.row("Prepared", time.strftime("%d %B %Y"))
    doc.row("For", f"{company} - {gig.get('title', 'video editing')}")
    doc.row("Engagement", quote.tier_name)
    doc.space(8)

    doc.heading("What you get")
    for line in (scope or default_scope(quote.tier_id)):
        doc.bullet(line)
    doc.space(6)

    doc.heading("Turnaround")
    doc.text(quote.turnaround or "Agreed per batch.")
    r = rules()
    if r.get("revisions_included"):
        doc.text(f"{r['revisions_included']} rounds of revisions are included. "
                 f"Further rounds are billed at the same rate pro rata.")
    doc.space(6)

    doc.heading("Price")
    if quote.missing:
        doc.text("PLACEHOLDER - no rate card configured. Do not send.")
    else:
        doc.row(quote.tier_name, f"{quote.money(total)} {quote.unit}")
        for adj in quote.adjustments:
            doc.text(f"Includes: {adj}", size=9, gray=0.35)
        pct = float(r.get("deposit_pct") or 0)
        if pct:
            doc.space(4)
            doc.row(f"Deposit to start ({pct:g}%)", quote.money(total * pct / 100))
            doc.row("Balance on delivery", quote.money(total * (100 - pct) / 100))
            doc.text(f"Payable within {int(r.get('payment_terms_days', 7))} days "
                     f"of invoice.", size=9, gray=0.35)
    doc.space(8)

    doc.heading("How it works")
    doc.bullet("You send the footage and any brand assets, however you prefer "
               "to share them.")
    doc.bullet("First cut comes back for approval before anything is locked.")
    doc.bullet("Revisions, then final delivery in the formats you need.")
    doc.space(6)
    doc.text("Project files are handed over on request. Work is delivered "
             "without watermarks and is yours on final payment.",
             size=9, gray=0.35)

    path = output_dir() / f"proposal-{_slug(company)}-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}.pdf"
    doc.save(str(path))
    log.info("proposal written", path=str(path), total=total)
    return str(path)


DEFAULT_SCOPE = {
    "long_form": ["Full edit from your raw footage, cut for retention",
                  "Colour grade in DaVinci Resolve",
                  "Sound design, dialogue cleanup and music balance",
                  "Motion graphics titles and lower thirds",
                  "Delivery in your channel's format, with subtitles"],
    "documentary": ["Story structure pass before the edit begins",
                    "Full edit including archive and B-roll integration",
                    "Colour grade and film-style look development",
                    "Sound design and music selection",
                    "Custom title sequence built in After Effects"],
    "short_form": ["Vertical edit cut for the first two seconds",
                   "Burned-in captions styled to your brand",
                   "Motion graphics and sound design",
                   "Delivery for Reels, Shorts and TikTok"],
    "short_form_pack": ["Eight vertical edits a month",
                        "Consistent caption and title system across all of them",
                        "Motion graphics and sound design on each",
                        "Delivery for Reels, Shorts and TikTok"],
    "motion_asset": ["Concept and storyboard for your approval",
                     "Animation built in After Effects",
                     "Sound design to match",
                     "Delivery with alpha channel and in your required formats"],
    "explainer": ["Script review and storyboard for approval",
                  "Full 2D animation in After Effects",
                  "Voiceover integration, sound design and music",
                  "Delivery in every aspect ratio you need"],
    "grade_only": ["Colour correction and grade in DaVinci Resolve",
                   "Shot matching across the timeline",
                   "Delivery as graded master or as a LUT"],
    "sound_only": ["Dialogue cleanup and levelling",
                   "Sound design and effects",
                   "Music selection and mix balance"],
    "retainer": ["Four long-form edits a month",
                 "Eight short-form verticals a month",
                 "One consistent design system across everything",
                 "Priority turnaround ahead of one-off work"],
}


def default_scope(tier_id: str) -> list[str]:
    return DEFAULT_SCOPE.get(tier_id, DEFAULT_SCOPE["long_form"])


# --------------------------------------------------------------------------
def invoice(gig: dict, quote: Quote, *, amount: float | None = None,
            deposit: bool = True, number: str = "", payment_details: str = "") -> str:
    """The deposit invoice, or the balance one."""
    total = quote.ask if amount is None else amount
    r = rules()
    pct = float(r.get("deposit_pct") or 0)
    company = gig.get("company") or "Client"
    due = (total * pct / 100) if (deposit and pct) else total

    doc = PDF(margin=50, font="Helvetica", size_pt=10, leading=1.35)
    _header(doc, "Invoice" + (" - deposit" if deposit and pct else ""))
    num = number or f"{time.strftime('%Y%m%d')}-{_slug(company)[:12]}-{uuid.uuid4().hex[:8]}"
    doc.row("Invoice number", num)
    doc.row("Date", time.strftime("%d %B %Y"))
    doc.row("Billed to", company)
    doc.row("Terms", f"{int(r.get('payment_terms_days', 7))} days")
    doc.space(10)

    doc.heading("Work")
    doc.row(quote.tier_name, f"{quote.money(total)} {quote.unit}")
    if deposit and pct:
        doc.row(f"Deposit due now ({pct:g}%)", quote.money(due))
        doc.row("Balance on delivery", quote.money(total - due))
    doc.space(8)
    doc.hrule()
    doc.row("AMOUNT DUE", quote.money(due), bold_left=True, gray_right=0.0)
    doc.space(10)

    doc.heading("Payment")
    bank = (payment_details or config.get("PAYMENT_DETAILS", "")).strip()
    doc.text(bank or "PLACEHOLDER - set PAYMENT_DETAILS in .env with how you "
                     "want to be paid. Nothing should be sent without it.")
    doc.space(6)
    doc.text("Work begins once the deposit clears." if deposit and pct else
             "Thank you.", size=9, gray=0.35)

    path = output_dir() / f"invoice-{num}.pdf"
    doc.save(str(path))
    log.info("invoice written", path=str(path), due=due)
    return str(path)
