"""Deterministic first-milestone checks; real app launches are mocked here."""
import asyncio
import io
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "agent"), str(ROOT)]
from core import db, screen_context, tasks
from core.config import settings
from core.quick_commands import parse_launch
from core.tool_registry import ToolNeedsConfirmation
from core.permissions import RiskLevel
from routers import chat
from tools import apps, web


@pytest.mark.parametrize("message,target", [
    ("Open ChatGPT", ("open_website", {"site": "chatgpt"})),
    ("YouTube kholo", ("open_website", {"site": "youtube"})),
    ("क्रोम खोलो", ("open_application", {"name": "chrome"})),
    ("कृपया यूट्यूब खोल दो", ("open_website", {"site": "youtube"})),
    ("Chrome open kar do", ("open_application", {"name": "chrome"})),
    ("Please open example.com", ("open_website", {"url": "example.com"})),
    ("Open https://www.youtube.com/watch?v=gx8VTa1c8DA", ("open_website", {"url": "https://www.youtube.com/watch?v=gx8VTa1c8DA"})),
    ("Cortana, open calculator", ("open_application", {"name": "calculator"})),
    ("Can you open WhatsApp?", ("open_application", {"name": "whatsapp"})),
    ("Could you open the Instagram app for me?", ("open_application", {"name": "instagram"})),
])
def test_explicit_multilingual_launch(message, target):
    assert parse_launch(message) == target


@pytest.mark.parametrize("message", [
    "Do not open Chrome", "Chrome mat kholo", "Chrome नहीं खोलो",
    "Open Chrome and delete files", "Open YouTube then send my password",
    "What happens if I open Chrome", "open file:///C:/Windows/System32/cmd.exe",
    "open notepad & powershell", "open unknown application",
])
def test_no_partial_or_negative_launch(message):
    assert parse_launch(message) is None


@pytest.mark.parametrize("message", [
    "Don't look at my screen", "How do I take a screenshot?",
    "screen mat dekho", "स्क्रीन मत देखो",
])
def test_screen_feature_mentions_and_negations_are_not_capture_requests(message):
    assert not chat._screen_requested(message)


def test_browser_launch_never_uses_shell(monkeypatch):
    recorded = []
    monkeypatch.setattr(web.platform, "system", lambda: "Windows")
    monkeypatch.setattr(apps, "approved_apps", lambda: {"chrome": ["C:/chrome.exe"]})
    from core import app_config, communication_targets
    monkeypatch.setattr(communication_targets, "preferences", lambda: {"chrome_profile_directory": "Default"})
    monkeypatch.setattr(app_config, "approved_apps", lambda: {"chrome": ["C:/chrome.exe"]})
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(web.subprocess, "Popen", lambda args, **kwargs: recorded.append((args, kwargs)))
    web.open_website(url="https://example.com/?q=%PATH%&x=one")
    assert recorded[0][0] == ["C:/chrome.exe", "--profile-directory=Default", "https://example.com/?q=%PATH%&x=one"]
    assert recorded[0][1]["shell"] is False
    assert not any(key.startswith("CORTANA_") for key in recorded[0][1]["env"])


@pytest.mark.parametrize("url", ["file:///C:/a.exe", "javascript:alert(1)", "https://u:p@example.com", "https://example.com/\r\nbad"])
def test_invalid_navigation_urls(url):
    with pytest.raises(web.UnsafeUrl):
        web._normalize_url(url)


def test_bad_model_json_is_a_tool_error():
    results, used, pending = chat._run_tool_calls([
        {"function": {"name": "open_website", "arguments": "{"}},
    ], {"open_website"})
    assert "error" in json.loads(results[0]["content"])
    assert pending is None


def test_unoffered_tool_cannot_dispatch(monkeypatch):
    monkeypatch.setattr(chat, "dispatch", lambda *_a, **_k: pytest.fail("unoffered tool executed"))
    result, _, _ = chat._run_tool_calls([{"function": {"name": "open_website"}}], {"read_code_file"})
    assert "not offered" in result[0]["content"]


def test_batch_stops_at_first_approval(monkeypatch):
    calls = []
    def pending(name, args, **kwargs):
        calls.append(name)
        raise ToolNeedsConfirmation(name, RiskLevel.HIGH, 42, "review this")
    monkeypatch.setattr(chat, "dispatch", pending)
    result, used, approval = chat._run_tool_calls([
        {"function": {"name": "edit_code_file", "arguments": {}}},
        {"function": {"name": "open_website", "arguments": {}}},
    ], {"edit_code_file", "open_website"})
    assert calls == ["edit_code_file"]
    assert approval["id"] == 42


def test_cloud_flags_cannot_enable_network_fallback(monkeypatch):
    monkeypatch.setattr(settings, "primary_backend", "cloud")
    monkeypatch.setattr(settings, "cloud_fallback_enabled", True)
    async def unavailable(*_a, **_k):
        raise chat.OllamaUnavailable("offline")
    monkeypatch.setattr(chat, "_call_ollama_raw", unavailable)
    async def run():
        with pytest.raises(chat.HTTPException) as err:
            await chat._call_model(None, [])
        assert err.value.status_code == 503
        assert "Nothing was sent" in err.value.detail
    asyncio.run(run())


def test_cancellation_interrupts_model_and_rejects_replay(monkeypatch):
    started = asyncio.Event()
    async def waiting(req):
        started.set()
        await asyncio.sleep(60)
    monkeypatch.setattr(chat, "_perform", waiting)
    async def run():
        request_id = str(uuid4())
        task = asyncio.create_task(chat.chat(chat.ChatRequest(message="hello", request_id=request_id)))
        await started.wait()
        assert tasks.cancel(request_id)["cancelled"]
        with pytest.raises(chat.HTTPException) as err:
            await task
        assert err.value.status_code == 409
        with pytest.raises(chat.HTTPException):
            tasks.begin(request_id)
        assert not tasks._active
    asyncio.run(run())


def test_screen_capture_is_single_use_and_expires():
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "black").save(buf, format="PNG")
    key = "test-capture"
    screen_context._captures[key] = screen_context.Capture(buf.getvalue(), 8, 8, time.monotonic())
    assert screen_context.encode(screen_context.consume(key))
    with pytest.raises(ValueError):
        screen_context.consume(key)
    screen_context._captures[key] = screen_context.Capture(buf.getvalue(), 8, 8, time.monotonic() - 301)
    with pytest.raises(ValueError):
        screen_context.consume(key)


def test_arbitrary_image_path_cannot_be_read(monkeypatch):
    from tools.screenshot import analyze_screenshot
    monkeypatch.setattr(tasks, "may_capture_screen", lambda: True)
    assert "error" in analyze_screenshot("C:/private.png")


def test_ollama_payload_is_local_bounded_and_no_thinking(monkeypatch):
    from contextlib import nullcontext
    monkeypatch.setattr('core.resource_broker.gpu_slot',nullcontext)
    monkeypatch.setattr('core.model_profiles.prepare_inference',lambda _target:None)
    async def residency(*args):
        return {'size':10, 'size_vram':10}
    monkeypatch.setattr('core.model_profiles.ensure_gpu_residency',residency)
    seen = []
    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "hello"}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await chat._call_ollama_raw(client, [{"role": "user", "content": "hi"}])
            assert result["message"]["content"] == "hello"
    asyncio.run(run())
    assert seen[0]["think"] is False
    assert seen[0]["options"]["num_ctx"] == settings.ollama_num_ctx


def test_direct_launch_does_not_need_model(monkeypatch):
    monkeypatch.setattr(chat, "dispatch", lambda *_a, **_k: {"opened": True})
    monkeypatch.setattr(chat, "_call_model", lambda *_a, **_k: pytest.fail("model used for simple launch"))
    async def run():
        result = await chat._perform(chat.ChatRequest(message="Open YouTube"))
        assert result.answered_by == "local command"
        assert result.reply == "Opening youtube."
    asyncio.run(run())


def test_social_greeting_never_waits_for_the_reasoning_model(monkeypatch):
    monkeypatch.setattr(chat, '_call_model', lambda *_a, **_k: pytest.fail('model used for greeting'))
    result = asyncio.run(chat._perform(chat.ChatRequest(message='How are you doing?')))
    assert result.answered_by == 'local greeting'


def test_compound_gmail_instruction_is_routed_to_drafting():
    assert chat._communication_requested('Okay, so open a Chrome browser and open a Gmail into it and then write a formal message that Vineet Kumar you have to come to the meeting on 21st January.')
    assert not chat._communication_requested('Okay, so explain how Gmail messages work.')
    assert chat._communication_requested('So stop and now what I want is that open a draft email to Vineet Kumar and write the formal message.')
    assert not chat._communication_requested("So now what I want is that do not draft an email in Gmail.")


def test_partial_launch_is_not_executed(monkeypatch):
    monkeypatch.setattr(chat, 'dispatch', lambda *_a, **_k: pytest.fail('partial command executed'))
    result = asyncio.run(chat._perform(chat.ChatRequest(message='Open WhatsApp and')))
    assert 'finish the command' in result.reply


def test_gmail_followup_keeps_recipient_and_formal_body_until_email_is_given(monkeypatch):
    from core import communication_targets
    monkeypatch.setattr(communication_targets, 'preferences', lambda: {})
    session = 'draft-context-regression'
    chat._pending_draft_bodies.pop(session, None)
    formal = 'Dear Vineet Kumar, please ensure your attendance at our important high-level meeting on 21 January.'
    async def extract(_client, messages, **_kwargs):
        assert 'Vineet Kumar' in messages[-1]['content']
        return {'message': {'content': json.dumps({'platform': 'gmail', 'recipient': 'Vineet Kumar',
            'body': formal, 'subject': 'Meeting on 21 January', 'question': ''})}}
    monkeypatch.setattr(chat, '_call_ollama_raw', extract)
    recorded = []
    def prepare(calls, *_a):
        recorded.append(calls[0]['function']['arguments'])
        return ([{'content': json.dumps({'status': 'draft_ready', 'draft_id': 'kept-draft', 'note': 'Draft ready.'})}],
                ['prepare_message_draft'], None)
    monkeypatch.setattr(chat, '_run_tool_calls', prepare)
    async def run():
        first = await chat._perform(chat.ChatRequest(message='Write in Gmail to Vineet Kumar.', session_id=session))
        assert 'What should I write' in first.reply
        second = await chat._perform(chat.ChatRequest(message='Please attend on 21 January. Write in formal language.', session_id=session))
        assert 'email address' in second.reply
        assert chat._pending_draft_bodies[session]['body'] == formal
        await chat._perform(chat.ChatRequest(message='vineetkd132@gmail.com', session_id=session))
    try:
        asyncio.run(run())
        assert recorded == [{'platform': 'gmail', 'recipient': 'vineetkd132@gmail.com',
            'body': formal, 'subject': 'Meeting on 21 January'}]
    finally:
        chat._pending_draft_bodies.pop(session, None)


@pytest.mark.parametrize('correction', ['The recipient is Rohit.', 'Spell the recipient as R O H I T.',
                                        'Bell the recipient as Romeo Oscar Hotel India Tango.',
                                        'Tell the recipient as R-O-H-I-T. R-O-H-I-T.'])
def test_spoken_contact_correction_preserves_pending_message(monkeypatch, correction):
    session = 'contact-correction-regression'
    chat._pending_draft_bodies[session] = dict(platform='whatsapp', recipient='Rohi', body='Demo only.',
                                             subject='', created=time.monotonic())
    def prepare(calls, *_args):
        payload = calls[0]['function']['arguments']
        assert payload['recipient'].casefold() == 'rohit'
        assert {key: value for key, value in payload.items() if key != 'recipient'} == dict(
            platform='whatsapp', body='Demo only.', subject='')
        return ([{'content': json.dumps({'status': 'draft_ready', 'note': 'Draft ready.'})}],
                ['prepare_message_draft'], None)
    monkeypatch.setattr(chat, '_run_tool_calls', prepare)
    try:
        result = asyncio.run(chat._perform(chat.ChatRequest(message=correction, session_id=session)))
        assert result.reply == 'Draft ready.'
    finally:
        chat._pending_draft_bodies.pop(session, None)


def test_open_voice_draft_does_not_treat_unrelated_speech_as_its_message():
    session = 'ambient-voice-draft-regression'
    chat._pending_draft_bodies[session] = dict(platform='whatsapp', recipient='Rohit', body='',
                                             subject='', created=time.monotonic())
    try:
        assert not chat._pending_draft_reply(chat.ChatRequest(message='Everything should be verbal.',
                                                             session_id=session, input_mode='voice'))
        assert chat._pending_draft_reply(chat.ChatRequest(message='Write, this is a test.',
                                                         session_id=session, input_mode='voice'))
    finally:
        chat._pending_draft_bodies.pop(session, None)


@pytest.mark.parametrize('clock', ['15.00', '15:00', '3 p.m.'])
def test_spoken_calendar_time_preserves_tomorrow_and_start_time(clock):
    from core.architecture_commands import parse
    assert parse(f'Prepare calendar event Project sync tomorrow at {clock} for 30 minutes.') == (
        'create_calendar_event', {'title': 'Project sync', 'when': 'tomorrow at 15:00', 'duration_minutes': 30})


def test_computer_input_routing_includes_inspection_and_focus():
    from core.tools_loader import load_all_tools
    from core.tool_router import select_tools
    load_all_tools()
    names = {spec["function"]["name"] for spec in select_tools("type hello in notepad")}
    assert {"type_text", "list_windows", "focus_window"} <= names
    assert "look_at_screen" not in names


@pytest.mark.parametrize("message", [
    "Draft a WhatsApp message to Alex: I will be late. Do not send.",
    "WhatsApp message Rohit saying this is a voice demo.",
    "Instagram message Alex.",
    "Instagram pe Alex ko message likho",
    "जीमेल में alex@example.com को मेल लिखो",
])
def test_explicit_draft_intent_allows_manual_send_boundary(message):
    assert chat._communication_requested(message)


@pytest.mark.parametrize("message", [
    "Don't draft a WhatsApp message", "How do I send an email?",
    "WhatsApp message mat likho", "Open Instagram", "Explain this screen",
    "Explain this Gmail draft", "Can you review this WhatsApp message?",
    "Is my Gmail draft ready?", "Gmail email",
])
def test_draft_mentions_are_not_automatic_authorization(message):
    assert not chat._communication_requested(message)


def test_draft_batch_stops_before_any_further_action(monkeypatch):
    seen = []
    def draft(name, args, **kwargs):
        seen.append(name)
        return {"status": "draft_ready", "draft_id": "fixture"}
    monkeypatch.setattr(chat, "dispatch", draft)
    chat._run_tool_calls([
        {"function": {"name": "prepare_message_draft", "arguments": {}}},
        {"function": {"name": "press_keys", "arguments": {"keys": "enter"}}},
    ], {"prepare_message_draft", "press_keys"})
    assert seen == ["prepare_message_draft"]


def test_draft_requests_offer_no_generic_input(monkeypatch):
    seen = []
    monkeypatch.setattr(chat, "to_ollama_tools", lambda names: seen.extend(names) or [])
    monkeypatch.setattr(chat, "select_tools", lambda _: pytest.fail("generic controls offered"))
    chat._offered_tools("Write a Gmail message to alex@example.com")
    assert seen == ["prepare_message_draft"]
