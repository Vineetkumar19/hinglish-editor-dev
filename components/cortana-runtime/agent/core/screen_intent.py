"""Classify the user's request, never commands embedded in visual evidence."""
import re


def screen_action_requested(message):
    # Interrogative requests such as "Can you fix..." still authorize an
    # action. A screenshot alone never does. Tool permissions remain enforced.
    text = re.sub(r'"[^"]*"|“[^”]*”', ' ', message or '')
    text = re.sub(r"^(?:(?:hey\s+)?cortana[,\s]+|please\s+|now\s+)+", '', text.strip(), flags=re.I)
    if re.search(r"\b(?:don't|do not|never|without|mat|nahi|nahin)\b|मत|नहीं|बिना", text, re.I):
        return False
    lead = r'^(?:(?:can|could|would|will)\s+(?:you|u)\s+)?(?:please\s+)?'
    return bool(re.search(
        lead + r'(?:click|select|open|edit|change|fix|correct|type|scroll|close|replace|update|repair)\b'
        r'|\b(?:theek|sahi)\s+karo\b|(?:ठीक|सही|बदल)\s*(?:करो|कर दीजिए)|क्लिक\s*करो',
        text, re.I))
