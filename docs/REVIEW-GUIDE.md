# Manager review guide

The review has two parts. Read the code on either operating system, then exercise representative workflows on a configured Windows GPU environment.

## Suggested reading order

1. Desktop startup and application ownership in components/storylens/desktop/Program.cs and hinglish_app/__main__.py.
2. Request handling, input checks, job creation and dispatch in hinglish_app/server.py.
3. Assistant intent schema and durable workflow state in assistant_plan.py, assistant.py and assistant_pipeline.py.
4. A media package such as hinglish_clean, hinglish_shorts or hinglish_sound.
5. Native editor adapters under editor_plugins and tools/editor_link.
6. Voice recognition, action selection and receiving UI in support_call_speech.py, support_call_local.py and static/support-call-actions.js.
7. Connected projects using the source maps.

All paths above are inside components/storylens unless a component is named explicitly.

## Follow a single request

Choose one feature guide. Find the visible control in its HTML and JavaScript. Follow its API path into server.py or the dedicated HTTP module. Follow the implementation's imports into the processor. Inspect validation, state updates, result paths and error handling. Finally open the relevant tests and compare expected outputs with the receiving editor or service.

## Review questions

- Is the source file, timeline, account and requested action identified before execution?
- Does an interrupted task resume the existing job or create duplicate work?
- Are published results checked independently of the request being accepted?
- Does the output preserve the source's timing, frame rate, audio and editable structure where promised?
- Which model is used, where is its input bounded, and which actions can it request?
- Which paths and operating-system assumptions need configuration on another laptop?
- What behavior is demonstrated, what is inferred from source, and what remains unverified?

Use sample media and a dedicated review account for live tests. Review financial calculations with synthetic records first. Publishing and agent delivery require an explicit test scope.
