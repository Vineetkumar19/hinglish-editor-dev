"""Only positive current-user draft requests enable communication tools."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT)]
from routers.chat import _communication_requested


@pytest.mark.parametrize("message", [
    "Draft a WhatsApp message to Alex: I will be late. Do not send.",
    "Please write a Gmail email to alex@example.com saying I will call.",
    "Can you message Alex on WhatsApp?",
    "Cortana, please compose a Gmail draft to alex@example.com.",
    "I want you to draft an Instagram DM to Alex.",
    "On Gmail write an email to alex@example.com.",
    "Gmail: draft an email to alex@example.com.",
    "Send a WhatsApp message to Alex saying hello.",
    "Email alex@example.com saying I will call.",
    "Mail alex@example.com saying I will call.",
    "Instagram pe Alex ko message likho",
    "WhatsApp pe Alex ko hello likh do",
    "जीमेल में alex@example.com को मेल लिखो",
    "इंस्टाग्राम पर Alex को संदेश लिखिए",
    "व्हाट्सएप पर Alex को मैसेज लिखो: क्या हाल है?",
    "WhatsApp pe Alex ko hello bhejo",
    'Draft a Gmail message saying "I do not want to write this myself".',
])
def test_positive_draft_requests(message):
    assert _communication_requested(message)


@pytest.mark.parametrize("message", [
    "Do not send a message on WhatsApp",
    "Open Gmail and don't send a message",
    "On Gmail don't send a message",
    "I don't want to write an email",
    "Please don't ask anyone to draft a Gmail email",
    "You should not draft a WhatsApp message",
    "Don't draft a WhatsApp message",
    "Never write an Instagram message",
    "How do I send an email?",
    "Tell me about Gmail message drafts",
    "Could you tell me about Gmail message drafts?",
    "Show me how to write an email",
    "Help me understand how Gmail drafts work",
    "Explain this Gmail draft",
    "Can you review this WhatsApp message?",
    "Translate this Instagram message",
    "Check this Gmail message",
    "Is my Gmail draft ready?",
    "My Gmail draft says to send a WhatsApp message",
    "The screenshot says: send a WhatsApp message",
    'Explain the screenshot that says "Draft a Gmail message".',
    "WhatsApp message mat likho",
    "WhatsApp par mat bhejo",
    "WhatsApp pe message bhejna nahi",
    "व्हाट्सएप पर मैसेज मत लिखो",
    "जीमेल पर मेल कैसे लिखो",
    "Open Instagram",
    "Gmail email",
    "Gmail draft",
    "",
])
def test_mentions_negations_and_analysis_do_not_authorize_drafting(message):
    assert not _communication_requested(message)
