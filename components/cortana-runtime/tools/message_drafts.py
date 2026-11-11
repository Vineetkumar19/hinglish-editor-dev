"""The sole messaging capability prepares a draft and never sends it."""
from core.desktop_drafts import draft_request
from core.draft_adapters import validate_payload
from core.permissions import RiskLevel
from core.tasks import may_prepare_communication
from core.tool_registry import tool, ToolDenied


@tool(name='open_communication_app',
      description='Open the configured Gmail account or installed WhatsApp/Instagram app.',
      risk=RiskLevel.LOW,
      parameters={'type':'object','properties':{'platform':{'type':'string',
          'enum':['gmail','whatsapp','instagram']}},'required':['platform']})
def open_communication_app(platform):
    return draft_request('open', {'platform':platform})


@tool(
    name="prepare_message_draft",
    description="Prepare a WhatsApp, Gmail or Instagram draft for the user to review and manually send. Requires the user's explicit recipient and message. Gmail requires one exact email address and an English subject/body; translate Hindi or Hinglish faithfully first. WhatsApp/Instagram require English or Roman Hinglish, with Hindi transliterated first. Preserve dates, times and meaning. Never sends; returns login or recipient selection when needed.",
    risk=RiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "platform": {"type": "string", "enum": ["whatsapp", "gmail", "instagram"]},
            "recipient": {"type": "string", "minLength": 1, "maxLength": 160},
            "body": {"type": "string", "minLength": 1, "maxLength": 6000},
            "subject": {"type": "string", "maxLength": 300},
        },
        "required": ["platform", "recipient", "body"],
    },
)
def prepare_message_draft(platform, recipient, body, subject=""):
    if not may_prepare_communication():
        raise ToolDenied("prepare_message_draft", RiskLevel.CRITICAL)
    data = validate_payload({"platform": platform, "recipient": recipient, "body": body, "subject": subject})
    return draft_request("prepare", data)
