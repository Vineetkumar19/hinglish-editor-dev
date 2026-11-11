"""Is this an Indian business, or one that sells to Indians?

The channel's audience is Indian and the content is in Hindi and English about
Indian cricket. A brand that does not ship to India, price in rupees or market
to Indians cannot use that audience, so pitching them wastes a slot.

Rather than guess from the domain, this reads the page and looks for the things
an Indian business cannot avoid putting on its own site: rupee prices, a +91
number, a GST number, an Indian address, Devanagari text, Indian payment rails.
Each signal is weak on its own and the combination is not.
"""
from __future__ import annotations

import re

# Rupee prices. Deliberately requires a digit next to the symbol so the word
# "rs" inside other words does not count.
RUPEE = re.compile(r"(?:₹\s?\d|(?<![a-z])(?:rs|inr)\.?\s?\d)", re.I)
PHONE_91 = re.compile(r"(?:\+\s?91|\b0091)[\s\-]?[6-9]\d{4}[\s\-]?\d{5}")
GST = re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b")
PIN = re.compile(r"\b\d{6}\b")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")

STATES = [
    "maharashtra", "karnataka", "tamil nadu", "delhi", "gurugram", "gurgaon",
    "noida", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad",
    "chennai", "kolkata", "ahmedabad", "jaipur", "lucknow", "indore",
    "chandigarh", "kerala", "gujarat", "rajasthan", "telangana", "haryana",
    "uttar pradesh", "west bengal", "punjab", "madhya pradesh", "odisha",
    "andhra pradesh", "bihar", "assam", "goa", "new delhi", "navi mumbai",
    "thane", "surat", "nagpur", "kanpur", "coimbatore", "kochi", "bhopal",
]
PAYMENTS = ["razorpay", "payu", "cashfree", "ccavenue", "instamojo", "phonepe",
            "paytm", "upi", "bhim", "rupay", "simpl", "snapmint", "gokwik"]
WORDS = ["made in india", "shipping across india", "pan india", "india's",
         "indian", "cod available", "cash on delivery", "bharat",
         "free shipping in india", "ships within india", "gst"]
HINDI_MARKERS = ["hindi", "hinglish", "desi", "bharat", "namaste"]

# Explicit negatives: a site that says it does not ship to India is not a lead.
NEGATIVE = ["we do not ship to india", "not available in india",
            "excluding india", "us residents only", "uk only"]


def india_score(text: str, html: str = "", domain: str = "") -> tuple[float, list[str]]:
    """0 to 1, plus the reasons. Above 0.3 is worth keeping."""
    blob = f"{text}\n{html}"[:120000]
    low = blob.lower()
    hits: list[str] = []
    score = 0.0

    dom = (domain or "").lower()
    if dom.endswith(".in") or dom.endswith(".co.in"):
        score += 0.30
        hits.append("Indian domain")

    if RUPEE.search(blob):
        score += 0.30
        hits.append("prices in rupees")
    if PHONE_91.search(blob):
        score += 0.25
        hits.append("+91 phone number")
    if GST.search(blob.upper()):
        score += 0.30
        hits.append("GST number published")
    if DEVANAGARI.search(blob):
        score += 0.20
        hits.append("Hindi text on the page")

    # Word boundaries matter here: "goa" sits inside "goal", "goat" and
    # "goals", which made a London shop look like it was based in Goa.
    state = next((s for s in STATES
                  if re.search(rf"\b{re.escape(s)}\b", low)), "")
    if state:
        score += 0.20
        hits.append(f"address in {state.title()}")
    elif PIN.search(blob) and "india" in low:
        score += 0.10
        hits.append("Indian PIN code")

    pay = next((p for p in PAYMENTS
                if re.search(rf"\b{re.escape(p)}\b", low)), "")
    if pay:
        score += 0.15
        hits.append(f"{pay.title()} checkout")

    word = next((w for w in WORDS if w in low), "")
    if word:
        score += 0.10
        hits.append(f'says "{word}"')

    if any(h in low for h in HINDI_MARKERS):
        score += 0.05
        hits.append("markets to a Hindi audience")

    bad = next((n for n in NEGATIVE if n in low), "")
    if bad:
        score -= 0.6
        hits.append(f'says "{bad}"')

    return max(0.0, min(1.0, score)), hits


def is_indian(text: str, html: str = "", domain: str = "",
              threshold: float = 0.30) -> bool:
    return india_score(text, html, domain)[0] >= threshold
