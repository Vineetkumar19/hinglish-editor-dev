"""Operator preferences, kept separate from model guesses and market prices."""
from __future__ import annotations

import re
from . import config


def project_floor(currency: str) -> float:
    if currency.upper() == "INR":
        return config.get_float("FREELANCE_MIN_PROJECT_INR", 10000)
    if currency.upper() == "USD":
        return config.get_float("FREELANCE_MIN_PROJECT_USD", 150)
    return 0.0  # Other currencies require a reviewed rate card.


def budget_check(job: dict) -> dict:
    """Reject only an explicitly stated INR ceiling below the relevant floor.

    Unknown pay and ambiguous periods stay reviewable. Never assume a foreign
    exchange rate or confuse hourly/day rates with an entire project budget.
    """
    text = " ".join(str(job.get(k) or "") for k in ("title", "description"))
    project = bool(re.search(r"\b(freelance|project.based|per project|gig)\b", text, re.I))
    ceiling = float(job.get("salary_max") or job.get("salary_min") or 0)
    currency = str(job.get("salary_currency") or "").upper()
    period = str(job.get("salary_period") or "year").lower()
    if not ceiling or currency != "INR":
        match = re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|lpa)?"
                          r"(?:\s*[-–]\s*(?:INR|Rs\.?|₹)?\s*([\d,]+(?:\.\d+)?)\s*(k|lakh|lpa)?)?"
                          r"\s*(?:/|per|a)?\s*(month|monthly|year|annum|project)\b", text, re.I)
        if not match:
            return {"reject": False, "reason": "Pay not comparable; review the stated budget"}
        unit = (match[4] or match[2] or "").lower()
        ceiling = float((match[3] or match[1]).replace(",", "")) * (1000 if unit == "k" else 100000 if unit in ("lakh", "lpa") else 1)
        currency, period = "INR", match[5].lower()
    if project and period == "project":
        floor, comparable = project_floor("INR"), ceiling
        reason = f"Project budget below INR {floor:,.0f} minimum"
    elif not project and period in ("year", "annum", "annual", "month", "monthly"):
        floor = config.get_float("JOB_MIN_MONTHLY_INR", 50000)
        comparable = ceiling / 12 if period in ("year", "annum", "annual") else ceiling
        reason = f"Salary below INR {floor:,.0f} per month minimum"
    else:
        return {"reject": False, "reason": "Budget period needs review"}
    return {"reject": comparable < floor, "reason": reason if comparable < floor else "Meets stated pay minimum"}
