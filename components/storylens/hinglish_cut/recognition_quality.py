"""Reject invalid recognizer output before it can become an approved edit."""
import re


class InvalidRecognitionError(ValueError):
    """The recognizer produced a placeholder rather than a transcript."""


def placeholder_transcript(text):
    words=re.findall(r'[a-z]+',str(text).casefold())
    return bool(words) and all(word in {'nan','null','undefined','none'} for word in words)


def checked_transcript(text):
    text=str(text).strip()
    if placeholder_transcript(text):
        raise InvalidRecognitionError('The recognizer returned invalid placeholder text instead of speech. Retry with the installed independent speech model; do not use this text for editing.')
    return text
