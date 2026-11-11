"""Exact, bounded launch commands in English, Hindi and Hinglish.

No model is involved. Ambiguous, negative or compound requests fall through
to the assistant instead of launching a partially matched target.
"""
import re
from core.app_config import approved_apps, approved_folder_aliases

ALIASES = {
    "चैट जीपीटी": "chatgpt", "चैटजीपीटी": "chatgpt", "चैट जी पी टी": "chatgpt",
    "chat gpt": "chatgpt", "यूट्यूब": "youtube", "यू ट्यूब": "youtube",
    "you tube": "youtube", "क्रोम": "chrome", "गूगल क्रोम": "chrome",
    "google chrome": "chrome", "नोटपैड": "notepad", "कैलकुलेटर": "calculator",
    "वीएस कोड": "vs code", "वी एस कोड": "vs code", "visual studio code": "vs code",
    "डाउनलोड्स": "downloads", "डॉक्यूमेंट्स": "documents", "डेस्कटॉप": "desktop",
    "गूगल": "google",
    "पोस्टमैन": "postman", "इंटेलीज": "intellij", "इंटेलिजे": "intellij",
    "ओबीएस": "obs studio", "फोटोशॉप": "photoshop", "वर्ड": "word",
    "एक्सेल": "excel", "पावरपॉइंट": "powerpoint",
    "व्हाट्सएप": "whatsapp", "व्हाट्सऐप": "whatsapp",
    "इंस्टाग्राम": "instagram", "जीमेल": "gmail",
}
OPEN = r"(?:open|launch|start|kholo|khol|kholna|खोलो|खोलें|खोल|ओपन)"


def command_text(message):
    text = message.strip()
    for _ in range(5):
        previous = text
        text = re.sub(r'^(?:okay|ok|alright|well|so|now)[,\s]+', '', text, flags=re.I)
        text = re.sub(r'^stop\s+and\s+', '', text, flags=re.I)
        text = re.sub(r'^(?:what\s+I\s+(?:want|need)\s+is(?:\s+that)?|I\s+(?:want|need)\s+(?:you\s+)?to)\s+', '', text, flags=re.I)
        if text == previous:
            break
    return text


def parse_launch(message: str) -> tuple[str, dict] | None:
    from tools.web import SITE_HOMES
    text = command_text(message).strip(" .!?।")
    text = re.sub(r"^(?:(?:hey |हे )?(?:cortana|gotana|gortana|courtana|cortona|कॉर्टाना|कोर्टाना)[, ]+)", "", text, flags=re.I)
    text = re.sub(r"^(?:please|कृपया|zara|jara|ज़रा)\s+", "", text, flags=re.I)
    text = re.sub(r"^(?:can|could|would|will)\s+(?:you|u)\s+(?:please\s+)?", "", text, flags=re.I)
    text = re.sub(r"\s+for me$", "", text, flags=re.I)
    text = re.sub(r"\s+(?:please|प्लीज)$", "", text, flags=re.I)
    patterns = [
        rf"{OPEN}\s+(.+)",
        rf"(.+?)\s+(?:ko\s+|को\s+)?{OPEN}(?:\s+(?:karo|kar do|do|करो|कर दो|दो|करें))?",
    ]
    target = None
    for pattern in patterns:
        match = re.fullmatch(pattern, text, flags=re.I)
        if match:
            target = match.group(1).strip()
            break
    if not target:
        return None
    target = re.sub(r'^(?:the|my)\s+', '', target, flags=re.I)
    target = re.sub(r'\s+(?:app|application)$', '', target, flags=re.I)
    path_target = target.strip('\"')
    if re.fullmatch(r'[a-z]:[\\/].*', path_target, flags=re.I):
        return "open_path", {"path": path_target}
    # These are not valid single launch targets.
    if re.search(r"\b(?:and|then|but|don't|not|mat|nahi|nahin|aur)\b|मत|नहीं|और", target, flags=re.I):
        return None
    if re.fullmatch(r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?", target, flags=re.I):
        return "open_website", {"url": target}
    target = " ".join(target.casefold().split())
    target = ALIASES.get(target, target)
    apps = {k.casefold(): k for k in approved_apps()}
    folders = {k.casefold(): k for k in approved_folder_aliases()}
    if target == 'gmail' or (target in {'whatsapp','instagram'} and target not in apps):
        return 'open_communication_app', {'platform':target}
    if target in apps:
        return "open_application", {"name": apps[target]}
    if target in SITE_HOMES:
        return "open_website", {"site": target}
    if target in folders:
        return "open_folder", {"name": folders[target]}
    return None


def parse_close(message):
    text = re.sub(r'\s+', ' ', command_text(message).casefold()).strip(' .!?।')
    text = re.sub(r'^(?:please|can you|could you)\s+', '', text)
    match = re.fullmatch(r'(?:close|band karo)\s+(?:the\s+)?(.+?)(?:\s+app)?', text)
    if not match:
        return None
    target = ALIASES.get(match[1], match[1])
    apps = {key.casefold(): key for key in approved_apps()}
    if target in apps:
        return 'close_application', {'name': apps[target]}
    from tools.web import SITE_HOMES
    if target in SITE_HOMES:
        return 'close_website', {'site': target}
    if re.fullmatch(r'(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s]*)?', target):
        return 'close_website', {'site': target}
    return None
