# agents source map

Use this map to jump from a module to its definitions. Links refer to this source snapshot. Static imports and definitions show where code lives. Runtime acceptance is recorded separately.

## adapters/receiver.py

[Open source](../../components/agents/adapters/receiver.py)

Imports __future__, argparse, contextlib, hashlib, hmac, http.server, json, os, pathlib, re, shutil, sqlite3, sys, subprocess, threading, time, urllib.parse, hinglish_shorts.source, hinglish_cinematic.render, hinglish_cut.gpu_lock.

- [canonical](../../components/agents/adapters/receiver.py#L28) — function
- [digest](../../components/agents/adapters/receiver.py#L32) — function
- [file_hash](../../components/agents/adapters/receiver.py#L36) — function
- [Receiver](../../components/agents/adapters/receiver.py#L44) — class
- [main](../../components/agents/adapters/receiver.py#L415) — function
- [__init__](../../components/agents/adapters/receiver.py#L45) — function
- [connect](../../components/agents/adapters/receiver.py#L74) — function
- [capabilities](../../components/agents/adapters/receiver.py#L83) — function
- [verify_refs](../../components/agents/adapters/receiver.py#L92) — function
- [receipt](../../components/agents/adapters/receiver.py#L104) — function
- [save](../../components/agents/adapters/receiver.py#L128) — function
- [commit_result](../../components/agents/adapters/receiver.py#L132) — function
- [cancel](../../components/agents/adapters/receiver.py#L138) — function
- [submit](../../components/agents/adapters/receiver.py#L150) — function
- [execute](../../components/agents/adapters/receiver.py#L179) — function
- [artifact](../../components/agents/adapters/receiver.py#L205) — function
- [storylens](../../components/agents/adapters/receiver.py#L211) — function
- [cortana](../../components/agents/adapters/receiver.py#L255) — function
- [publication](../../components/agents/adapters/receiver.py#L310) — function
- [repository](../../components/agents/adapters/receiver.py#L384) — function
- [Handler](../../components/agents/adapters/receiver.py#L426) — class
- [log_message](../../components/agents/adapters/receiver.py#L427) — function
- [auth](../../components/agents/adapters/receiver.py#L429) — function
- [reply](../../components/agents/adapters/receiver.py#L433) — function
- [do_GET](../../components/agents/adapters/receiver.py#L441) — function
- [do_POST](../../components/agents/adapters/receiver.py#L449) — function

## agents/__init__.py

[Open source](../../components/agents/agents/__init__.py)


## agents/common.py

[Open source](../../components/agents/agents/common.py)

Imports __future__, json, re, textwrap, time, dataclasses, typing, core, core.crawler, core.graph, core.hitl, core.llm, core.log, core.mailer, core.notify, core.search, core.store, core.toolbelt, core.reflect, core.lessons.

- [_offline_intent](../../components/agents/agents/common.py#L89) — function — Deterministic intent classifier used when no LLM is configured.
- [classify_intent](../../components/agents/agents/common.py#L104) — function — Classify a prospect reply. Safety-critical labels are rule-gated.
- [lint_pitch](../../components/agents/agents/common.py#L155) — function — Catch the tells that get cold email marked as spam - or just ignored.
- [outreach_reducers](../../components/agents/agents/common.py#L182) — function
- [OutreachConfig](../../components/agents/agents/common.py#L188) — class — What makes one outreach agent different from another.
- [OutreachAgent](../../components/agents/agents/common.py#L230) — class — Builds the discovery/outreach graph and the reply-handling graph.
- [ReplyConfig](../../components/agents/agents/common.py#L722) — class
- [ReplyAgent](../../components/agents/agents/common.py#L731) — class — Turns an inbound reply into the right next action.
- [__init__](../../components/agents/agents/common.py#L233) — function
- [n_discover](../../components/agents/agents/common.py#L254) — function
- [n_pick_lead](../../components/agents/agents/common.py#L280) — function
- [n_research](../../components/agents/agents/common.py#L288) — function
- [n_qualify](../../components/agents/agents/common.py#L314) — function
- [r_after_qualify](../../components/agents/agents/common.py#L368) — function
- [n_skip](../../components/agents/agents/common.py#L374) — function
- [n_draft](../../components/agents/agents/common.py#L394) — function
- [_reflect](../../components/agents/agents/common.py#L444) — function — Turn what he just said into a standing rule. Never fails a run.
- [learned_block](../../components/agents/agents/common.py#L453) — function — The rules this agent now follows, as prompt text.
- [_pitch_prompt](../../components/agents/agents/common.py#L463) — function
- [n_approve](../../components/agents/agents/common.py#L490) — function
- [r_after_approve](../../components/agents/agents/common.py#L542) — function
- [n_send](../../components/agents/agents/common.py#L546) — function
- [r_more](../../components/agents/agents/common.py#L604) — function
- [n_done](../../components/agents/agents/common.py#L607) — function
- [_company_name](../../components/agents/agents/common.py#L616) — function — What to call this company in an email.
- [_save_lead](../../components/agents/agents/common.py#L642) — function
- [build](../../components/agents/agents/common.py#L661) — function
- [run](../../components/agents/agents/common.py#L697) — function
- [__init__](../../components/agents/agents/common.py#L739) — function
- [n_ingest](../../components/agents/agents/common.py#L749) — function
- [n_classify](../../components/agents/agents/common.py#L772) — function
- [r_route](../../components/agents/agents/common.py#L789) — function
- [n_unsubscribe](../../components/agents/agents/common.py#L801) — function
- [n_bounce](../../components/agents/agents/common.py#L811) — function
- [n_snooze](../../components/agents/agents/common.py#L828) — function
- [n_close](../../components/agents/agents/common.py#L838) — function
- [n_notify](../../components/agents/agents/common.py#L843) — function
- [r_after_notify](../../components/agents/agents/common.py#L866) — function
- [_learn_outcome](../../components/agents/agents/common.py#L869) — function
- [n_draft_reply](../../components/agents/agents/common.py#L891) — function
- [n_approve_reply](../../components/agents/agents/common.py#L933) — function
- [r_after_approve_reply](../../components/agents/agents/common.py#L953) — function
- [n_send_reply](../../components/agents/agents/common.py#L957) — function
- [_set_lead_status](../../components/agents/agents/common.py#L980) — function
- [build](../../components/agents/agents/common.py#L987) — function
- [handle](../../components/agents/agents/common.py#L1015) — function
- [rank](../../components/agents/agents/common.py#L348) — function

## agents/community/__init__.py

[Open source](../../components/agents/agents/community/__init__.py)


## agents/community/agent.py

[Open source](../../components/agents/agents/community/agent.py)

Imports __future__, hashlib, time, xml.etree.ElementTree, pathlib, core, core.crawler, core.delivery, core.graph, core.hitl, core.lessons, core.llm, core.store, core.yamlite, agents.sponsorship.pitch, core.reflect.

- [offline_reply](../../components/agents/agents/community/agent.py#L31) — function
- [CommunityMemory](../../components/agents/agents/community/agent.py#L39) — class
- [CommunityAgent](../../components/agents/agents/community/agent.py#L49) — class
- [make](../../components/agents/agents/community/agent.py#L161) — function
- [__init__](../../components/agents/agents/community/agent.py#L40) — function
- [summary](../../components/agents/agents/community/agent.py#L43) — function
- [__init__](../../components/agents/agents/community/agent.py#L50) — function
- [n_discover](../../components/agents/agents/community/agent.py#L54) — function
- [n_pick](../../components/agents/agents/community/agent.py#L87) — function
- [n_draft](../../components/agents/agents/community/agent.py#L91) — function
- [n_approve](../../components/agents/agents/community/agent.py#L108) — function
- [n_handoff](../../components/agents/agents/community/agent.py#L120) — function
- [build](../../components/agents/agents/community/agent.py#L138) — function
- [run](../../components/agents/agents/community/agent.py#L156) — function

## agents/fullstack_sales/__init__.py

[Open source](../../components/agents/agents/fullstack_sales/__init__.py)


## agents/fullstack_sales/agent.py

[Open source](../../components/agents/agents/fullstack_sales/agent.py)

Imports __future__, textwrap, agents.common, agents.fullstack_sales.gigs, agents.fullstack_sales.pricing, agents.templates, core, core.graph, core.hitl, core.llm, core.log, core.mailer, core.notify, core.store, agents.sales_conversation, time.

- [qualify_bonus](../../components/agents/agents/fullstack_sales/agent.py#L65) — function
- [_offline_pitch](../../components/agents/agents/fullstack_sales/agent.py#L79) — function
- [_offline_reply](../../components/agents/agents/fullstack_sales/agent.py#L112) — function
- [_offline_proposal](../../components/agents/agents/fullstack_sales/agent.py#L143) — function
- [QuoteAgent](../../components/agents/agents/fullstack_sales/agent.py#L172) — class — Scope -> price -> proposal -> mandatory human approval -> send.
- [build_config](../../components/agents/agents/fullstack_sales/agent.py#L343) — function
- [build_reply_config](../../components/agents/agents/fullstack_sales/agent.py#L356) — function
- [DevSalesAgent](../../components/agents/agents/fullstack_sales/agent.py#L366) — class — Answering people who want work done, and cold outreach, in one graph.
- [make](../../components/agents/agents/fullstack_sales/agent.py#L452) — function
- [make_reply](../../components/agents/agents/fullstack_sales/agent.py#L456) — function
- [make_quote](../../components/agents/agents/fullstack_sales/agent.py#L461) — function
- [__init__](../../components/agents/agents/fullstack_sales/agent.py#L175) — function
- [n_analyse](../../components/agents/agents/fullstack_sales/agent.py#L181) — function
- [r_have_scope](../../components/agents/agents/fullstack_sales/agent.py#L192) — function
- [n_ask_scope](../../components/agents/agents/fullstack_sales/agent.py#L195) — function — Refuse to guess. An estimate from nothing is worse than no estimate.
- [n_price](../../components/agents/agents/fullstack_sales/agent.py#L200) — function
- [_quote](../../components/agents/agents/fullstack_sales/agent.py#L214) — function — The live Quote if this pass built it, otherwise rebuilt from state.
- [n_draft_proposal](../../components/agents/agents/fullstack_sales/agent.py#L219) — function
- [n_approve_quote](../../components/agents/agents/fullstack_sales/agent.py#L246) — function — The gate. Nothing priced leaves the machine without a decision.
- [r_after_approve](../../components/agents/agents/fullstack_sales/agent.py#L277) — function
- [n_send](../../components/agents/agents/fullstack_sales/agent.py#L281) — function
- [n_won](../../components/agents/agents/fullstack_sales/agent.py#L303) — function — Terminal celebration node, reached when a reply is classified as accept.
- [build](../../components/agents/agents/fullstack_sales/agent.py#L316) — function
- [handle](../../components/agents/agents/fullstack_sales/agent.py#L335) — function
- [run](../../components/agents/agents/fullstack_sales/agent.py#L374) — function
- [build](../../components/agents/agents/fullstack_sales/agent.py#L383) — function

## agents/fullstack_sales/brain.py

[Open source](../../components/agents/agents/fullstack_sales/brain.py)

Imports __future__, re, uuid, agents.sponsorship.brain, core.log, core.store.

- [_slug](../../components/agents/agents/fullstack_sales/brain.py#L59) — function
- [market_of](../../components/agents/agents/fullstack_sales/brain.py#L63) — function
- [deal_features](../../components/agents/agents/fullstack_sales/brain.py#L70) — function
- [DevMemory](../../components/agents/agents/fullstack_sales/brain.py#L84) — class
- [counts](../../components/agents/agents/fullstack_sales/brain.py#L85) — function
- [record_deal](../../components/agents/agents/fullstack_sales/brain.py#L102) — function
- [score_deal](../../components/agents/agents/fullstack_sales/brain.py#L121) — function
- [summary](../../components/agents/agents/fullstack_sales/brain.py#L124) — function

## agents/fullstack_sales/brief.py

[Open source](../../components/agents/agents/fullstack_sales/brief.py)

Imports __future__, textwrap, core, agents.sponsorship.brief, agents.job_hunter.resume.

- [_fill](../../components/agents/agents/fullstack_sales/brief.py#L87) — function
- [build_prompt](../../components/agents/agents/fullstack_sales/brief.py#L93) — function
- [finish](../../components/agents/agents/fullstack_sales/brief.py#L182) — function — Put back the parts the model is not trusted with.

## agents/fullstack_sales/gigs.py

[Open source](../../components/agents/agents/fullstack_sales/gigs.py)

Imports __future__, json, re, time, core, core.delivery, core.hitl, core.log, ., .brain, core.lessons, core.llm, .agent, core.notify, core.work_policy, core.reflect, agents.job_hunter.resume.

- [_first_real_sentence](../../components/agents/agents/fullstack_sales/gigs.py#L35) — function
- [DevGigMixin](../../components/agents/agents/fullstack_sales/gigs.py#L46) — class — Sweep for open development work, rank it, read it, and pitch it.
- [brain](../../components/agents/agents/fullstack_sales/gigs.py#L50) — function
- [_say](../../components/agents/agents/fullstack_sales/gigs.py#L55) — function
- [sweep_due](../../components/agents/agents/fullstack_sales/gigs.py#L63) — function
- [n_sweep](../../components/agents/agents/fullstack_sales/gigs.py#L74) — function
- [n_pick_gig](../../components/agents/agents/fullstack_sales/gigs.py#L111) — function
- [n_read_gig](../../components/agents/agents/fullstack_sales/gigs.py#L117) — function — Fetch the posting, re-judge it, and price it.
- [r_after_read](../../components/agents/agents/fullstack_sales/gigs.py#L139) — function
- [n_skip_gig](../../components/agents/agents/fullstack_sales/gigs.py#L142) — function
- [n_pitch_gig](../../components/agents/agents/fullstack_sales/gigs.py#L150) — function
- [n_approve_gig](../../components/agents/agents/fullstack_sales/gigs.py#L200) — function
- [r_after_gig_approve](../../components/agents/agents/fullstack_sales/gigs.py#L241) — function
- [n_send_gig](../../components/agents/agents/fullstack_sales/gigs.py#L245) — function
- [r_more_gigs](../../components/agents/agents/fullstack_sales/gigs.py#L274) — function
- [handle_reply](../../components/agents/agents/fullstack_sales/gigs.py#L278) — function — Accept, counter, or stop. The floor is absolute.

## agents/fullstack_sales/packages.py

[Open source](../../components/agents/agents/fullstack_sales/packages.py)

Imports __future__, math, pathlib, re, dataclasses, core, core.log, core.yamlite, core.work_policy.

- [card_path](../../components/agents/agents/fullstack_sales/packages.py#L57) — function
- [load_card](../../components/agents/agents/fullstack_sales/packages.py#L66) — function — Keyed on the file and its mtime, so an edit is picked up at once.
- [currency_for](../../components/agents/agents/fullstack_sales/packages.py#L85) — function
- [package_for](../../components/agents/agents/fullstack_sales/packages.py#L90) — function
- [rules](../../components/agents/agents/fullstack_sales/packages.py#L98) — function
- [Package](../../components/agents/agents/fullstack_sales/packages.py#L103) — class
- [build_package](../../components/agents/agents/fullstack_sales/packages.py#L142) — function — Price what they described, or None when it is a build rather than
- [Counter](../../components/agents/agents/fullstack_sales/packages.py#L183) — class
- [find_offer](../../components/agents/agents/fullstack_sales/packages.py#L200) — function
- [respond_to](../../components/agents/agents/fullstack_sales/packages.py#L222) — function
- [deposit_line](../../components/agents/agents/fullstack_sales/packages.py#L243) — function
- [symbol](../../components/agents/agents/fullstack_sales/packages.py#L115) — function
- [money](../../components/agents/agents/fullstack_sales/packages.py#L118) — function
- [render](../../components/agents/agents/fullstack_sales/packages.py#L124) — function
- [to_json](../../components/agents/agents/fullstack_sales/packages.py#L133) — function
- [from_json](../../components/agents/agents/fullstack_sales/packages.py#L137) — function

## agents/fullstack_sales/pitch_replies.py

[Open source](../../components/agents/agents/fullstack_sales/pitch_replies.py)

Imports __future__, core, .packages, agents.job_hunter.resume.

- [_signature](../../components/agents/agents/fullstack_sales/pitch_replies.py#L15) — function
- [rate_reply](../../components/agents/agents/fullstack_sales/pitch_replies.py#L34) — function
- [counter_reply](../../components/agents/agents/fullstack_sales/pitch_replies.py#L67) — function
- [follow_up](../../components/agents/agents/fullstack_sales/pitch_replies.py#L92) — function
- [due_after_days](../../components/agents/agents/fullstack_sales/pitch_replies.py#L102) — function

## agents/fullstack_sales/pricing.py

[Open source](../../components/agents/agents/fullstack_sales/pricing.py)

Imports __future__, math, pathlib, dataclasses, core, core.log, core.yamlite, core.work_policy, re.

- [QuoteLine](../../components/agents/agents/fullstack_sales/pricing.py#L48) — class
- [Quote](../../components/agents/agents/fullstack_sales/pricing.py#L55) — class
- [load_rate_card](../../components/agents/agents/fullstack_sales/pricing.py#L113) — function
- [rate_card_for](../../components/agents/agents/fullstack_sales/pricing.py#L148) — function — The same card, priced for one market. `market` is "usd" or "inr".
- [_round_to](../../components/agents/agents/fullstack_sales/pricing.py#L172) — function
- [build_quote](../../components/agents/agents/fullstack_sales/pricing.py#L176) — function — Turn a list of scope components into a priced quote. Pure function.
- [infer_scope](../../components/agents/agents/fullstack_sales/pricing.py#L259) — function — Read a prospect's message and site copy for scope and modifiers.
- [render](../../components/agents/agents/fullstack_sales/pricing.py#L67) — function
- [to_json](../../components/agents/agents/fullstack_sales/pricing.py#L85) — function
- [from_json](../../components/agents/agents/fullstack_sales/pricing.py#L99) — function — Rebuild a Quote from its checkpointed form after a resume.

## agents/fullstack_sales/sources.py

[Open source](../../components/agents/agents/fullstack_sales/sources.py)

Imports __future__, re, time, urllib.parse, dataclasses, core, core.log, agents.job_hunter.boards_in.

- [Gig](../../components/agents/agents/fullstack_sales/sources.py#L95) — class
- [is_dev_work](../../components/agents/agents/fullstack_sales/sources.py#L160) — function
- [from_linkedin](../../components/agents/agents/fullstack_sales/sources.py#L182) — function
- [describe](../../components/agents/agents/fullstack_sales/sources.py#L205) — function
- [from_remoteok](../../components/agents/agents/fullstack_sales/sources.py#L212) — function
- [from_weworkremotely](../../components/agents/agents/fullstack_sales/sources.py#L237) — function
- [find_gigs](../../components/agents/agents/fullstack_sales/sources.py#L270) — function
- [key](../../components/agents/agents/fullstack_sales/sources.py#L107) — function
- [_blob](../../components/agents/agents/fullstack_sales/sources.py#L110) — function
- [work_kind](../../components/agents/agents/fullstack_sales/sources.py#L113) — function
- [client_kind](../../components/agents/agents/fullstack_sales/sources.py#L126) — function
- [to_json](../../components/agents/agents/fullstack_sales/sources.py#L133) — function

## agents/job_hunter/__init__.py

[Open source](../../components/agents/agents/job_hunter/__init__.py)


## agents/job_hunter/agent.py

[Open source](../../components/agents/agents/job_hunter/agent.py)

Imports __future__, datetime, json, pathlib, re, textwrap, time, agents.job_hunter, agents.job_hunter.brain, agents.job_hunter.discovery, core, core.calendar, core.graph, core.hitl, core.llm, core.log, core.mailer, core.notify, core.store, core.work_policy.

- [output_dir](../../components/agents/agents/job_hunter/agent.py#L36) — function
- [_fmt_salary](../../components/agents/agents/job_hunter/agent.py#L43) — function — A salary line a person can read. Boards leave this empty more often
- [_fmt_experience](../../components/agents/agents/job_hunter/agent.py#L56) — function
- [JobHunter](../../components/agents/agents/job_hunter/agent.py#L66) — class
- [_sum_stats](../../components/agents/agents/job_hunter/agent.py#L367) — function
- [looks_like_interview_request](../../components/agents/agents/job_hunter/agent.py#L383) — function
- [_offline_interview_reply](../../components/agents/agents/job_hunter/agent.py#L388) — function
- [InterviewScheduler](../../components/agents/agents/job_hunter/agent.py#L402) — class — Detects an interview request, proposes real free slots, books on confirm.
- [make](../../components/agents/agents/job_hunter/agent.py#L550) — function
- [make_scheduler](../../components/agents/agents/job_hunter/agent.py#L554) — function
- [__init__](../../components/agents/agents/job_hunter/agent.py#L67) — function
- [brain](../../components/agents/agents/job_hunter/agent.py#L81) — function
- [n_aggregate](../../components/agents/agents/job_hunter/agent.py#L86) — function
- [n_next_job](../../components/agents/agents/job_hunter/agent.py#L142) — function
- [n_screen](../../components/agents/agents/job_hunter/agent.py#L148) — function
- [r_after_screen](../../components/agents/agents/job_hunter/agent.py#L162) — function
- [n_reject](../../components/agents/agents/job_hunter/agent.py#L165) — function
- [n_tailor](../../components/agents/agents/job_hunter/agent.py#L183) — function
- [n_render](../../components/agents/agents/job_hunter/agent.py#L202) — function
- [n_review](../../components/agents/agents/job_hunter/agent.py#L215) — function
- [r_after_review](../../components/agents/agents/job_hunter/agent.py#L260) — function
- [n_applied](../../components/agents/agents/job_hunter/agent.py#L264) — function
- [n_passed](../../components/agents/agents/job_hunter/agent.py#L295) — function
- [r_more](../../components/agents/agents/job_hunter/agent.py#L305) — function
- [n_done](../../components/agents/agents/job_hunter/agent.py#L308) — function
- [build](../../components/agents/agents/job_hunter/agent.py#L322) — function
- [run](../../components/agents/agents/job_hunter/agent.py#L360) — function
- [__init__](../../components/agents/agents/job_hunter/agent.py#L405) — function
- [n_detect](../../components/agents/agents/job_hunter/agent.py#L417) — function
- [r_detect](../../components/agents/agents/job_hunter/agent.py#L424) — function
- [n_ignore](../../components/agents/agents/job_hunter/agent.py#L427) — function
- [n_slots](../../components/agents/agents/job_hunter/agent.py#L430) — function
- [n_draft](../../components/agents/agents/job_hunter/agent.py#L444) — function
- [n_approve](../../components/agents/agents/job_hunter/agent.py#L470) — function
- [r_after_approve](../../components/agents/agents/job_hunter/agent.py#L488) — function
- [n_send](../../components/agents/agents/job_hunter/agent.py#L492) — function
- [build](../../components/agents/agents/job_hunter/agent.py#L515) — function
- [handle](../../components/agents/agents/job_hunter/agent.py#L534) — function
- [confirm_slot](../../components/agents/agents/job_hunter/agent.py#L539) — function — Called once they pick a time. Creates the calendar event.

## agents/job_hunter/application.py

[Open source](../../components/agents/agents/job_hunter/application.py)

Imports __future__, hashlib, json, re, time, pathlib, core, core.browser, core.graph, core.hitl, core.store, core.yamlite, .resume.

- [normalise](../../components/agents/agents/job_hunter/application.py#L19) — function
- [plan_answers](../../components/agents/agents/job_hunter/application.py#L23) — function
- [ApplicationAgent](../../components/agents/agents/job_hunter/application.py#L58) — class
- [make](../../components/agents/agents/job_hunter/application.py#L142) — function
- [__init__](../../components/agents/agents/job_hunter/application.py#L59) — function
- [n_inspect](../../components/agents/agents/job_hunter/application.py#L63) — function
- [n_review](../../components/agents/agents/job_hunter/application.py#L74) — function
- [n_submit](../../components/agents/agents/job_hunter/application.py#L89) — function
- [build](../../components/agents/agents/job_hunter/application.py#L122) — function
- [run](../../components/agents/agents/job_hunter/application.py#L135) — function
- [before_submit](../../components/agents/agents/job_hunter/application.py#L102) — function

## agents/job_hunter/boards_in.py

[Open source](../../components/agents/agents/job_hunter/boards_in.py)

Imports __future__, html, re, time, urllib.parse, core, core.log, .discovery.

- [_freshness](../../components/agents/agents/job_hunter/boards_in.py#L41) — function
- [_text](../../components/agents/agents/job_hunter/boards_in.py#L49) — function
- [LinkedInSource](../../components/agents/agents/job_hunter/boards_in.py#L53) — class — Public job postings, one search per location he named.
- [NaukriSource](../../components/agents/agents/job_hunter/boards_in.py#L147) — class — Naukri search, using his own logged-in session.
- [fetch](../../components/agents/agents/job_hunter/boards_in.py#L57) — function
- [_search](../../components/agents/agents/job_hunter/boards_in.py#L82) — function
- [parse_cards](../../components/agents/agents/job_hunter/boards_in.py#L93) — function — One Job per <li> in the returned fragment.
- [_describe](../../components/agents/agents/job_hunter/boards_in.py#L131) — function
- [fetch](../../components/agents/agents/job_hunter/boards_in.py#L157) — function
- [_search](../../components/agents/agents/job_hunter/boards_in.py#L169) — function
- [_to_job](../../components/agents/agents/job_hunter/boards_in.py#L192) — function

## agents/job_hunter/booking.py

[Open source](../../components/agents/agents/job_hunter/booking.py)

Imports __future__, datetime, hashlib, time, core, core.calendar, core.graph, core.hitl, core.store.

- [BookingAgent](../../components/agents/agents/job_hunter/booking.py#L15) — class
- [make](../../components/agents/agents/job_hunter/booking.py#L69) — function
- [__init__](../../components/agents/agents/job_hunter/booking.py#L16) — function
- [n_review](../../components/agents/agents/job_hunter/booking.py#L20) — function
- [n_book](../../components/agents/agents/job_hunter/booking.py#L32) — function
- [build](../../components/agents/agents/job_hunter/booking.py#L53) — function
- [run](../../components/agents/agents/job_hunter/booking.py#L63) — function

## agents/job_hunter/brain.py

[Open source](../../components/agents/agents/job_hunter/brain.py)

Imports __future__, re, agents.sponsorship.brain, core.log, core.store, uuid.

- [_slug](../../components/agents/agents/job_hunter/brain.py#L47) — function
- [job_features](../../components/agents/agents/job_hunter/brain.py#L51) — function — The handful of things about a posting that might predict his answer.
- [JobMemory](../../components/agents/agents/job_hunter/brain.py#L94) — class — The sponsorship brain's arithmetic, counting only job evidence.
- [get_brain](../../components/agents/agents/job_hunter/brain.py#L159) — function
- [counts](../../components/agents/agents/job_hunter/brain.py#L97) — function
- [record_job](../../components/agents/agents/job_hunter/brain.py#L114) — function
- [score_job](../../components/agents/agents/job_hunter/brain.py#L135) — function
- [summary](../../components/agents/agents/job_hunter/brain.py#L138) — function

## agents/job_hunter/discovery.py

[Open source](../../components/agents/agents/job_hunter/discovery.py)

Imports __future__, json, pathlib, re, time, dataclasses, core, core.crawler, core.log, .boards_in.

- [Job](../../components/agents/agents/job_hunter/discovery.py#L33) — class
- [_clean](../../components/agents/agents/job_hunter/discovery.py#L60) — function
- [Source](../../components/agents/agents/job_hunter/discovery.py#L64) — class
- [GreenhouseSource](../../components/agents/agents/job_hunter/discovery.py#L71) — class — Public board API. Companies are listed in GREENHOUSE_BOARDS.
- [LeverSource](../../components/agents/agents/job_hunter/discovery.py#L97) — class
- [RemotiveSource](../../components/agents/agents/job_hunter/discovery.py#L125) — class
- [RemoteOKSource](../../components/agents/agents/job_hunter/discovery.py#L143) — class
- [AdzunaSource](../../components/agents/agents/job_hunter/discovery.py#L169) — class — Good coverage of the Indian market, unlike most remote-only boards.
- [JsonFeedSource](../../components/agents/agents/job_hunter/discovery.py#L195) — class
- [FixtureSource](../../components/agents/agents/job_hunter/discovery.py#L205) — class
- [_from_generic](../../components/agents/agents/job_hunter/discovery.py#L215) — function
- [_parse_ts](../../components/agents/agents/job_hunter/discovery.py#L230) — function
- [_register_indian_boards](../../components/agents/agents/job_hunter/discovery.py#L248) — function — Add linkedin and naukri to SOURCES, once.
- [aggregate](../../components/agents/agents/job_hunter/discovery.py#L262) — function — Fan out across boards and return a deduplicated list.
- [key](../../components/agents/agents/job_hunter/discovery.py#L51) — function
- [to_json](../../components/agents/agents/job_hunter/discovery.py#L54) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L67) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L75) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L100) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L128) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L146) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L173) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L198) — function
- [fetch](../../components/agents/agents/job_hunter/discovery.py#L208) — function

## agents/job_hunter/location.py

[Open source](../../components/agents/agents/job_hunter/location.py)

Imports __future__, re, core.

- [wanted_places](../../components/agents/agents/job_hunter/location.py#L74) — function
- [_word](../../components/agents/agents/job_hunter/location.py#L81) — function — A whole-word matcher, cached.
- [_mentions](../../components/agents/agents/job_hunter/location.py#L96) — function
- [acceptable](../../components/agents/agents/job_hunter/location.py#L103) — function — (can he take this job, why).

## agents/job_hunter/read.py

[Open source](../../components/agents/agents/job_hunter/read.py)

Imports __future__, textwrap, core.lessons, core.llm, core.log.

- [_fill](../../components/agents/agents/job_hunter/read.py#L35) — function
- [build_prompt](../../components/agents/agents/job_hunter/read.py#L41) — function
- [read_job](../../components/agents/agents/job_hunter/read.py#L84) — function — The read, or a safe empty one when there is no model.

## agents/job_hunter/relevance.py

[Open source](../../components/agents/agents/job_hunter/relevance.py)

Imports __future__, re, dataclasses, core.

- [Match](../../components/agents/agents/job_hunter/relevance.py#L188) — class
- [wanted_families](../../components/agents/agents/job_hunter/relevance.py#L206) — function
- [max_experience_years](../../components/agents/agents/job_hunter/relevance.py#L211) — function — Your current experience. Jobs asking for more than this are dropped.
- [experience_slack](../../components/agents/agents/job_hunter/relevance.py#L219) — function — How far above your level to still allow through.
- [extract_skills](../../components/agents/agents/job_hunter/relevance.py#L231) — function — Skills the posting actually names, in the order they are mentioned.
- [required_years](../../components/agents/agents/job_hunter/relevance.py#L249) — function — Lowest number of years the posting demands, or None if it never says.
- [title_seniority](../../components/agents/agents/job_hunter/relevance.py#L268) — function
- [_family_for](../../components/agents/agents/job_hunter/relevance.py#L276) — function — Pick the family whose vocabulary fits the title most specifically.
- [classify](../../components/agents/agents/job_hunter/relevance.py#L304) — function — Decide whether this posting is worth your attention, and why.
- [sort_key](../../components/agents/agents/job_hunter/relevance.py#L354) — function
- [to_json](../../components/agents/agents/job_hunter/relevance.py#L198) — function

## agents/job_hunter/resume.py

[Open source](../../components/agents/agents/job_hunter/resume.py)

Imports __future__, pathlib, re, dataclasses, core, core.log, core.pdf, core.schema, core.yamlite.

- [track_violations](../../components/agents/agents/job_hunter/resume.py#L107) — function — Terms from the OTHER track found in this master profile.
- [master_path](../../components/agents/agents/job_hunter/resume.py#L152) — function
- [load_master](../../components/agents/agents/job_hunter/resume.py#L157) — function
- [master_corpus](../../components/agents/agents/job_hunter/resume.py#L196) — function
- [novel_claims](../../components/agents/agents/job_hunter/resume.py#L214) — function — Tokens and figures in `text` with no support anywhere in the master.
- [TailorResult](../../components/agents/agents/job_hunter/resume.py#L239) — class
- [job_keywords](../../components/agents/agents/job_hunter/resume.py#L254) — function
- [coverage](../../components/agents/agents/job_hunter/resume.py#L267) — function
- [_offline_tailor](../../components/agents/agents/job_hunter/resume.py#L278) — function — Deterministic tailoring: rank real entries by keyword overlap.
- [tailor](../../components/agents/agents/job_hunter/resume.py#L314) — function
- [max_projects](../../components/agents/agents/job_hunter/resume.py#L394) — function — How many projects land on the resume. Three fits one page comfortably.
- [featured_projects](../../components/agents/agents/job_hunter/resume.py#L402) — function — The fallback project set when nothing has been ranked against a job.
- [_assemble](../../components/agents/agents/job_hunter/resume.py#L409) — function
- [render_pdf](../../components/agents/agents/job_hunter/resume.py#L457) — function
- [clean](../../components/agents/agents/job_hunter/resume.py#L247) — function
- [score](../../components/agents/agents/job_hunter/resume.py#L285) — function

## agents/job_hunter/scam_filter.py

[Open source](../../components/agents/agents/job_hunter/scam_filter.py)

Imports __future__, re, dataclasses, core.llm, core.log.

- [ScreenResult](../../components/agents/agents/job_hunter/scam_filter.py#L72) — class
- [heuristic_screen](../../components/agents/agents/job_hunter/scam_filter.py#L84) — function
- [_offline_consistency](../../components/agents/agents/job_hunter/scam_filter.py#L150) — function — Deterministic consistency checks - the same logic an LLM is asked for.
- [semantic_screen](../../components/agents/agents/job_hunter/scam_filter.py#L195) — function
- [screen](../../components/agents/agents/job_hunter/scam_filter.py#L224) — function — Full two-stage screen. A heuristic rejection short-circuits.
- [rejected](../../components/agents/agents/job_hunter/scam_filter.py#L80) — function

## agents/saas_sales/__init__.py

[Open source](../../components/agents/agents/saas_sales/__init__.py)


## agents/saas_sales/agent.py

[Open source](../../components/agents/agents/saas_sales/agent.py)

Imports __future__, time, core, core.graph, core.hitl, core.llm, core.log, core.store, ., .brain, core.lessons, core.delivery, core.notify, core.reflect.

- [reducers](../../components/agents/agents/saas_sales/agent.py#L34) — function
- [SaasSalesAgent](../../components/agents/agents/saas_sales/agent.py#L39) — class — Find them, read them, write to them, and never overclaim.
- [make](../../components/agents/agents/saas_sales/agent.py#L353) — function
- [__init__](../../components/agents/agents/saas_sales/agent.py#L42) — function
- [brain](../../components/agents/agents/saas_sales/agent.py#L49) — function
- [_say](../../components/agents/agents/saas_sales/agent.py#L54) — function
- [n_check_product](../../components/agents/agents/saas_sales/agent.py#L63) — function — Refuse to run at all rather than send something half-true.
- [r_ready](../../components/agents/agents/saas_sales/agent.py#L83) — function
- [n_sweep](../../components/agents/agents/saas_sales/agent.py#L86) — function
- [n_pick](../../components/agents/agents/saas_sales/agent.py#L113) — function
- [n_read](../../components/agents/agents/saas_sales/agent.py#L119) — function — Read what they say about themselves, and drop the competitors.
- [r_after_read](../../components/agents/agents/saas_sales/agent.py#L140) — function
- [n_skip](../../components/agents/agents/saas_sales/agent.py#L143) — function
- [n_write](../../components/agents/agents/saas_sales/agent.py#L150) — function
- [_plain_note](../../components/agents/agents/saas_sales/agent.py#L184) — function — No model. Deliberately spare - every sentence is from product.yaml.
- [_directory_card](../../components/agents/agents/saas_sales/agent.py#L202) — function — A submission, not an email. He does this one by hand.
- [n_approve](../../components/agents/agents/saas_sales/agent.py#L216) — function
- [r_after_approve](../../components/agents/agents/saas_sales/agent.py#L256) — function
- [n_blocked](../../components/agents/agents/saas_sales/agent.py#L267) — function
- [n_send](../../components/agents/agents/saas_sales/agent.py#L278) — function
- [r_more](../../components/agents/agents/saas_sales/agent.py#L295) — function
- [n_done](../../components/agents/agents/saas_sales/agent.py#L298) — function
- [build](../../components/agents/agents/saas_sales/agent.py#L303) — function
- [run](../../components/agents/agents/saas_sales/agent.py#L344) — function

## agents/saas_sales/brain.py

[Open source](../../components/agents/agents/saas_sales/brain.py)

Imports __future__, re, uuid, agents.sponsorship.brain, core.log, core.store.

- [_slug](../../components/agents/agents/saas_sales/brain.py#L52) — function
- [size_band](../../components/agents/agents/saas_sales/brain.py#L56) — function — "103K" -> "large". Audience size predicts reply rate more than anything
- [target_features](../../components/agents/agents/saas_sales/brain.py#L74) — function
- [LaunchMemory](../../components/agents/agents/saas_sales/brain.py#L88) — class
- [counts](../../components/agents/agents/saas_sales/brain.py#L89) — function
- [record_target](../../components/agents/agents/saas_sales/brain.py#L106) — function
- [score_target](../../components/agents/agents/saas_sales/brain.py#L125) — function
- [summary](../../components/agents/agents/saas_sales/brain.py#L128) — function

## agents/saas_sales/brief.py

[Open source](../../components/agents/agents/saas_sales/brief.py)

Imports __future__, core, ., agents.sponsorship.brief.

- [_fill](../../components/agents/agents/saas_sales/brief.py#L70) — function
- [build_prompt](../../components/agents/agents/saas_sales/brief.py#L76) — function
- [finish](../../components/agents/agents/saas_sales/brief.py#L150) — function — Attach the signature, and whatever link the stage actually permits.

## agents/saas_sales/product.py

[Open source](../../components/agents/agents/saas_sales/product.py)

Imports __future__, pathlib, re, core, core.log, core.yamlite.

- [profile_path](../../components/agents/agents/saas_sales/product.py#L75) — function
- [load_product](../../components/agents/agents/saas_sales/product.py#L84) — function — Keyed on the file and its mtime, so an edit is picked up at once.
- [stage](../../components/agents/agents/saas_sales/product.py#L103) — function
- [allows](../../components/agents/agents/saas_sales/product.py#L108) — function
- [has_pricing](../../components/agents/agents/saas_sales/product.py#L112) — function
- [has_partner_terms](../../components/agents/agents/saas_sales/product.py#L117) — function
- [ready_to_sell](../../components/agents/agents/saas_sales/product.py#L122) — function — Whether there is enough here to write anything at all.
- [check_claims](../../components/agents/agents/saas_sales/product.py#L139) — function — Everything in this draft that the stage does not support.
- [facts_block](../../components/agents/agents/saas_sales/product.py#L198) — function — The product, as prompt text. Only what the file actually says.
- [stage_rules_block](../../components/agents/agents/saas_sales/product.py#L226) — function — What this stage forbids, written for the model.
- [partner_offer_block](../../components/agents/agents/saas_sales/product.py#L260) — function — What a promoter is actually being offered today.

## agents/saas_sales/research.py

[Open source](../../components/agents/agents/saas_sales/research.py)

Imports __future__, datetime, hashlib, json, re, urllib.parse, core.llm, core.search, core.store, ., core.workflow_contracts.

- [launch_settings](../../components/agents/agents/saas_sales/research.py#L24) — function
- [save_settings](../../components/agents/agents/saas_sales/research.py#L39) — function
- [research_signals](../../components/agents/agents/saas_sales/research.py#L60) — function

## agents/saas_sales/sources.py

[Open source](../../components/agents/agents/saas_sales/sources.py)

Imports __future__, html, re, time, urllib.parse, dataclasses, core, core.log.

- [Target](../../components/agents/agents/saas_sales/sources.py#L88) — class
- [_text](../../components/agents/agents/saas_sales/sources.py#L108) — function
- [from_youtube](../../components/agents/agents/saas_sales/sources.py#L114) — function — Channels publishing about editing tools and workflow.
- [channel_about](../../components/agents/agents/saas_sales/sources.py#L144) — function — What the channel says about itself, plus any published contact.
- [is_competitor](../../components/agents/agents/saas_sales/sources.py#L195) — function
- [classify](../../components/agents/agents/saas_sales/sources.py#L200) — function
- [from_directories](../../components/agents/agents/saas_sales/sources.py#L213) — function — The listing sites. No fetching - the work here is submitting, and that
- [find_targets](../../components/agents/agents/saas_sales/sources.py#L228) — function
- [key](../../components/agents/agents/saas_sales/sources.py#L101) — function
- [to_json](../../components/agents/agents/saas_sales/sources.py#L104) — function

## agents/sales_conversation.py

[Open source](../../components/agents/agents/sales_conversation.py)

Imports __future__, json, re, agents.common, core.store, core.work_policy, core, agents.video_client.quote, agents.video_client, agents.fullstack_sales, agents.fullstack_sales.agent, agents.fullstack_sales.pricing.

- [SalesReplyAgent](../../components/agents/agents/sales_conversation.py#L17) — class
- [_deal](../../components/agents/agents/sales_conversation.py#L18) — function
- [n_draft_reply](../../components/agents/agents/sales_conversation.py#L33) — function
- [n_send_reply](../../components/agents/agents/sales_conversation.py#L133) — function

## agents/sponsorship/__init__.py

[Open source](../../components/agents/agents/sponsorship/__init__.py)


## agents/sponsorship/agent.py

[Open source](../../components/agents/agents/sponsorship/agent.py)

Imports __future__, agents.common, agents.sponsorship, agents.sponsorship.brain, agents.sponsorship.discover, agents.templates, core, core.graph, core.llm, core.log, time.

- [blocked_reason](../../components/agents/agents/sponsorship/agent.py#L69) — function — Empty string when the brand is fine to approach.
- [wanted_deals](../../components/agents/agents/sponsorship/agent.py#L90) — function — Which kinds of deal to work at all. Affiliate is excluded by default.
- [rank](../../components/agents/agents/sponsorship/agent.py#L96) — function — Tier 1 first, then the deals that pay soonest, then cricket-native.
- [_offline_pitch](../../components/agents/agents/sponsorship/agent.py#L109) — function — The pitch itself. Built in code rather than prompted out of a model,
- [message_extras](../../components/agents/agents/sponsorship/agent.py#L134) — function — The other two channels, plus the facts that make the card readable.
- [_offline_reply](../../components/agents/agents/sponsorship/agent.py#L177) — function
- [qualify_bonus](../../components/agents/agents/sponsorship/agent.py#L206) — function — Sponsorship-specific signals, on top of the generic contact score.
- [build_config](../../components/agents/agents/sponsorship/agent.py#L248) — function
- [build_reply_config](../../components/agents/agents/sponsorship/agent.py#L281) — function
- [SponsorshipAgent](../../components/agents/agents/sponsorship/agent.py#L293) — class — The whole thing: find brands, then pitch them, learning from both.
- [make](../../components/agents/agents/sponsorship/agent.py#L462) — function
- [make_reply](../../components/agents/agents/sponsorship/agent.py#L466) — function
- [__init__](../../components/agents/agents/sponsorship/agent.py#L303) — function
- [n_discover](../../components/agents/agents/sponsorship/agent.py#L313) — function — The list, ordered by the brain instead of by a fixed rule.
- [n_approve](../../components/agents/agents/sponsorship/agent.py#L346) — function
- [n_skip](../../components/agents/agents/sponsorship/agent.py#L356) — function
- [n_send](../../components/agents/agents/sponsorship/agent.py#L364) — function
- [n_draft](../../components/agents/agents/sponsorship/agent.py#L370) — function — Say what is happening first.
- [run](../../components/agents/agents/sponsorship/agent.py#L384) — function — Extra arguments go into the STATE, not into invoke().
- [build](../../components/agents/agents/sponsorship/agent.py#L405) — function

## agents/sponsorship/brain.py

[Open source](../../components/agents/agents/sponsorship/brain.py)

Imports __future__, math, random, time, uuid, core.log, core.store.

- [_now](../../components/agents/agents/sponsorship/brain.py#L74) — function
- [features_of](../../components/agents/agents/sponsorship/brain.py#L78) — function — The handful of things about a prospect worth learning from.
- [target_features](../../components/agents/agents/sponsorship/brain.py#L109) — function — The same view of a brand already on the list.
- [Memory](../../components/agents/agents/sponsorship/brain.py#L133) — class — Counts of what worked, and the score that falls out of them.
- [__init__](../../components/agents/agents/sponsorship/brain.py#L136) — function
- [record](../../components/agents/agents/sponsorship/brain.py#L141) — function — File one decision against every feature of the thing decided on.
- [counts](../../components/agents/agents/sponsorship/brain.py#L163) — function — feature -> (evidence for, evidence against).
- [base_rate](../../components/agents/agents/sponsorship/brain.py#L184) — function
- [contribution](../../components/agents/agents/sponsorship/brain.py#L192) — function — How much this feature shifts the log-odds, shrunk toward nothing.
- [score](../../components/agents/agents/sponsorship/brain.py#L206) — function — A 0-1 score, plus the working so it can be argued with.
- [source_weights](../../components/agents/agents/sponsorship/brain.py#L222) — function — Thompson sampling over each source's hit rate.
- [score_target](../../components/agents/agents/sponsorship/brain.py#L236) — function — How promising a brand already on the list is, right now.
- [record_target](../../components/agents/agents/sponsorship/brain.py#L240) — function — File an outreach outcome against a brand on the list.
- [summary](../../components/agents/agents/sponsorship/brain.py#L263) — function

## agents/sponsorship/brief.py

[Open source](../../components/agents/agents/sponsorship/brief.py)

Imports __future__, re, textwrap, core, ..

- [_facts](../../components/agents/agents/sponsorship/brief.py#L66) — function
- [_fill](../../components/agents/agents/sponsorship/brief.py#L86) — function — Dedent a prompt AFTER interpolation, block by block.
- [build_prompt](../../components/agents/agents/sponsorship/brief.py#L101) — function — The brief. `ctx` is what n_draft passes: current, profile, contact.
- [strip_signoff](../../components/agents/agents/sponsorship/brief.py#L196) — function — Remove a sign-off the model added anyway.
- [finish](../../components/agents/agents/sponsorship/brief.py#L224) — function — Attach the signature and the facts the model was not trusted with.

## agents/sponsorship/discover.py

[Open source](../../components/agents/agents/sponsorship/discover.py)

Imports __future__, json, re, time, uuid, agents.sponsorship, core, core.crawler, core.hitl, core.log, core.yamlite, pathlib, core.notify.

- [salesman_reason](../../components/agents/agents/sponsorship/discover.py#L57) — function — Empty string when nothing here is a commission deal.
- [banned_reason](../../components/agents/agents/sponsorship/discover.py#L64) — function
- [sponsor_file](../../components/agents/agents/sponsorship/discover.py#L72) — function
- [listed_domains](../../components/agents/agents/sponsorship/discover.py#L78) — function
- [DiscoveryMixin](../../components/agents/agents/sponsorship/discover.py#L91) — class — Nodes bolted onto the front of the sponsorship graph.
- [_call_source](../../components/agents/agents/sponsorship/discover.py#L390) — function
- [_guess_segment](../../components/agents/agents/sponsorship/discover.py#L429) — function
- [sources](../../components/agents/agents/sponsorship/discover.py#L99) — function
- [sources](../../components/agents/agents/sponsorship/discover.py#L103) — function
- [_discovery_crawler](../../components/agents/agents/sponsorship/discover.py#L106) — function
- [_known](../../components/agents/agents/sponsorship/discover.py#L116) — function
- [_say](../../components/agents/agents/sponsorship/discover.py#L124) — function — A line of progress, so a long sweep is not a silent one.
- [discovery_due](../../components/agents/agents/sponsorship/discover.py#L133) — function
- [n_refresh](../../components/agents/agents/sponsorship/discover.py#L145) — function — Decide whether to go looking, then look.
- [n_screen](../../components/agents/agents/sponsorship/discover.py#L190) — function — Drop the banned, the duplicated, and the ones with no website.
- [n_check](../../components/agents/agents/sponsorship/discover.py#L222) — function — Read each site: real, Indian, contactable? Then rank by the brain.
- [n_pick_find](../../components/agents/agents/sponsorship/discover.py#L288) — function
- [n_add](../../components/agents/agents/sponsorship/discover.py#L294) — function — Ask before touching the list. Either answer teaches the brain.
- [r_more_finds](../../components/agents/agents/sponsorship/discover.py#L337) — function
- [_save_prospects](../../components/agents/agents/sponsorship/discover.py#L341) — function
- [_append_to_list](../../components/agents/agents/sponsorship/discover.py#L359) — function

## agents/sponsorship/india.py

[Open source](../../components/agents/agents/sponsorship/india.py)

Imports __future__, re.

- [india_score](../../components/agents/agents/sponsorship/india.py#L45) — function — 0 to 1, plus the reasons. Above 0.3 is worth keeping.
- [is_indian](../../components/agents/agents/sponsorship/india.py#L104) — function

## agents/sponsorship/pitch.py

[Open source](../../components/agents/agents/sponsorship/pitch.py)

Imports __future__, pathlib, re, urllib.parse, core, core.log, core.yamlite.

- [_sentence](../../components/agents/agents/sponsorship/pitch.py#L29) — function — Upper-case the first letter only.
- [creator_path](../../components/agents/agents/sponsorship/pitch.py#L43) — function
- [load_creator](../../components/agents/agents/sponsorship/pitch.py#L48) — function
- [_channel](../../components/agents/agents/sponsorship/pitch.py#L68) — function
- [_n](../../components/agents/agents/sponsorship/pitch.py#L75) — function
- [human_number](../../components/agents/agents/sponsorship/pitch.py#L82) — function — Indian-audience readable: 12,500 becomes 12.5K, 250000 becomes 2.5L.
- [audience_facts](../../components/agents/agents/sponsorship/pitch.py#L93) — function — Only statements that are true given what has actually been filled in.
- [has_numbers](../../components/agents/agents/sponsorship/pitch.py#L131) — function
- [best_work_links](../../components/agents/agents/sponsorship/pitch.py#L135) — function
- [craft_line](../../components/agents/agents/sponsorship/pitch.py#L140) — function
- [angle_for](../../components/agents/agents/sponsorship/pitch.py#L207) — function
- [_opening](../../components/agents/agents/sponsorship/pitch.py#L214) — function — The first line. Only ever says something the brand itself published.
- [deal_type](../../components/agents/agents/sponsorship/pitch.py#L230) — function — What is realistically on the table with this target.
- [_first_deliverable](../../components/agents/agents/sponsorship/pitch.py#L242) — function
- [_ask_for](../../components/agents/agents/sponsorship/pitch.py#L255) — function — Subject line and closing question, by the kind of deal on offer.
- [email_pitch](../../components/agents/agents/sponsorship/pitch.py#L286) — function — The cold email. Returns subject, body and a note on what it leaned on.
- [signature](../../components/agents/agents/sponsorship/pitch.py#L335) — function — Name, then every way they can reach you.
- [whatsapp_pitch](../../components/agents/agents/sponsorship/pitch.py#L369) — function
- [instagram_dm](../../components/agents/agents/sponsorship/pitch.py#L397) — function — Shorter again. Instagram truncates, and a wall of text is not opened.
- [gmail_link](../../components/agents/agents/sponsorship/pitch.py#L418) — function — A Gmail compose window with everything already filled in.
- [wa_link](../../components/agents/agents/sponsorship/pitch.py#L434) — function — A click-to-chat link with the message already typed in.

## agents/sponsorship/sources.py

[Open source](../../components/agents/agents/sponsorship/sources.py)

Imports __future__, re, time, urllib.parse, dataclasses, core, core.crawler, core.log, core.search.

- [Candidate](../../components/agents/agents/sponsorship/sources.py#L58) — class — Something that might be worth pitching. Unverified.
- [_get](../../components/agents/agents/sponsorship/sources.py#L75) — function
- [_useful_host](../../components/agents/agents/sponsorship/sources.py#L80) — function
- [cuelinks](../../components/agents/agents/sponsorship/sources.py#L95) — function — Brands currently paying commission, straight off the network.
- [admitad](../../components/agents/agents/sponsorship/sources.py#L146) — function
- [_unescape_json](../../components/agents/agents/sponsorship/sources.py#L179) — function
- [youtube_sponsors](../../components/agents/agents/sponsorship/sources.py#L186) — function — Read the sponsor links out of other cricket creators' descriptions.
- [_brand_from_headline](../../components/agents/agents/sponsorship/sources.py#L292) — function
- [trade_press](../../components/agents/agents/sponsorship/sources.py#L309) — function — Brand names lifted out of headlines. Domains are resolved later.
- [resolve_domain](../../components/agents/agents/sponsorship/sources.py#L346) — function — Try the domains a brand of this name would plausibly own.
- [_result_links](../../components/agents/agents/sponsorship/sources.py#L402) — function — Pull the outbound result links out of a search page.
- [search_web](../../components/agents/agents/sponsorship/sources.py#L422) — function — Search the internet for anything. Returns result URLs.
- [open_search](../../components/agents/agents/sponsorship/sources.py#L476) — function — Anything the open web turns up for the standing questions.
- [domain](../../components/agents/agents/sponsorship/sources.py#L70) — function

## agents/templates.py

[Open source](../../components/agents/agents/templates.py)

Imports __future__, re, textwrap, core.

- [_first_sentence](../../components/agents/agents/templates.py#L16) — function
- [observation](../../components/agents/agents/templates.py#L25) — function — One specific, verifiable thing about the prospect - or an honest blank.
- [company_name](../../components/agents/agents/templates.py#L36) — function — Pull a usable company name out of a page title.
- [greeting](../../components/agents/agents/templates.py#L63) — function
- [signature](../../components/agents/agents/templates.py#L68) — function
- [compose](../../components/agents/agents/templates.py#L80) — function

## agents/video_client/__init__.py

[Open source](../../components/agents/agents/video_client/__init__.py)


## agents/video_client/agent.py

[Open source](../../components/agents/agents/video_client/agent.py)

Imports __future__, pathlib, re, textwrap, agents.common, agents.video_client.gigs, agents.templates, core, core.llm, core.log, core.yamlite, agents.sales_conversation, .quote, core.graph, time.

- [rates_path](../../components/agents/agents/video_client/agent.py#L64) — function
- [load_rates](../../components/agents/agents/video_client/agent.py#L69) — function
- [qualify_bonus](../../components/agents/agents/video_client/agent.py#L80) — function
- [_offline_pitch](../../components/agents/agents/video_client/agent.py#L95) — function
- [_offline_reply](../../components/agents/agents/video_client/agent.py#L127) — function
- [portfolio_attachments](../../components/agents/agents/video_client/agent.py#L182) — function — No attachments on first contact - a link keeps you out of the spam folder.
- [build_config](../../components/agents/agents/video_client/agent.py#L187) — function
- [build_reply_config](../../components/agents/agents/video_client/agent.py#L203) — function
- [VideoClientAgent](../../components/agents/agents/video_client/agent.py#L215) — class — Cold outreach and open-gig hunting, sharing one memory.
- [make](../../components/agents/agents/video_client/agent.py#L299) — function
- [make_reply](../../components/agents/agents/video_client/agent.py#L303) — function
- [build](../../components/agents/agents/video_client/agent.py#L225) — function
- [run](../../components/agents/agents/video_client/agent.py#L289) — function

## agents/video_client/brain.py

[Open source](../../components/agents/agents/video_client/brain.py)

Imports __future__, re, uuid, agents.sponsorship.brain, core.log, core.store.

- [_slug](../../components/agents/agents/video_client/brain.py#L55) — function
- [market_of](../../components/agents/agents/video_client/brain.py#L59) — function
- [deal_features](../../components/agents/agents/video_client/brain.py#L66) — function — Kept deliberately few - a handful of deals a month cannot teach more.
- [DealMemory](../../components/agents/agents/video_client/brain.py#L81) — class
- [counts](../../components/agents/agents/video_client/brain.py#L82) — function
- [record_deal](../../components/agents/agents/video_client/brain.py#L99) — function
- [score_deal](../../components/agents/agents/video_client/brain.py#L118) — function
- [summary](../../components/agents/agents/video_client/brain.py#L121) — function

## agents/video_client/brief.py

[Open source](../../components/agents/agents/video_client/brief.py)

Imports __future__, textwrap, core, ., agents.sponsorship.brief.

- [_fill](../../components/agents/agents/video_client/brief.py#L55) — function — Dedent a prompt AFTER interpolation, block by block.
- [build_prompt](../../components/agents/agents/video_client/brief.py#L70) — function — ctx carries the gig, the quote, and the lessons block.
- [finish](../../components/agents/agents/video_client/brief.py#L146) — function — Put back the parts the model is not trusted with.
- [top](../../components/agents/agents/video_client/brief.py#L77) — function

## agents/video_client/docs.py

[Open source](../../components/agents/agents/video_client/docs.py)

Imports __future__, pathlib, time, uuid, core, core.log, core.pdf, .pitch, .quote.

- [output_dir](../../components/agents/agents/video_client/docs.py#L28) — function
- [_slug](../../components/agents/agents/video_client/docs.py#L35) — function
- [_header](../../components/agents/agents/video_client/docs.py#L40) — function
- [proposal](../../components/agents/agents/video_client/docs.py#L58) — function — A scoped proposal an internal approver can actually act on.
- [default_scope](../../components/agents/agents/video_client/docs.py#L156) — function
- [invoice](../../components/agents/agents/video_client/docs.py#L161) — function — The deposit invoice, or the balance one.

## agents/video_client/gigs.py

[Open source](../../components/agents/agents/video_client/gigs.py)

Imports __future__, json, re, time, core, core.delivery, core.hitl, core.log, ., .brain, .quote, core.lessons, core.llm, core.notify, core.work_policy, .sources, core.reflect.

- [_first_real_sentence](../../components/agents/agents/video_client/gigs.py#L40) — function — The first sentence worth quoting back to them, or nothing.
- [GigMixin](../../components/agents/agents/video_client/gigs.py#L55) — class — Sweep for open editing work, rank it, and pitch it.
- [brain](../../components/agents/agents/video_client/gigs.py#L59) — function
- [_say](../../components/agents/agents/video_client/gigs.py#L64) — function
- [sweep_due](../../components/agents/agents/video_client/gigs.py#L72) — function
- [n_sweep](../../components/agents/agents/video_client/gigs.py#L83) — function — Find open editing work across every market he sells into.
- [n_pick_gig](../../components/agents/agents/video_client/gigs.py#L119) — function
- [n_read_gig](../../components/agents/agents/video_client/gigs.py#L125) — function — Pull the ad text. Without it every pitch is generic.
- [n_pitch_gig](../../components/agents/agents/video_client/gigs.py#L141) — function — Write the approach. The model reads their posting; the code owns
- [n_approve_gig](../../components/agents/agents/video_client/gigs.py#L184) — function
- [r_after_gig_approve](../../components/agents/agents/video_client/gigs.py#L224) — function
- [n_send_gig](../../components/agents/agents/video_client/gigs.py#L228) — function — Record it and schedule the chase. Sending itself is the mailer's job.
- [r_more_gigs](../../components/agents/agents/video_client/gigs.py#L264) — function
- [due_follow_ups](../../components/agents/agents/video_client/gigs.py#L268) — function — Deals that have gone quiet long enough to deserve another touch.
- [advance_follow_up](../../components/agents/agents/video_client/gigs.py#L288) — function — Write the next chase and move the clock, or close it out.
- [handle_reply](../../components/agents/agents/video_client/gigs.py#L309) — function — Decide what the reply means and what to send back.
- [win](../../components/agents/agents/video_client/gigs.py#L337) — function — They said yes. Produce the paperwork and file the outcome.

## agents/video_client/pitch.py

[Open source](../../components/agents/agents/video_client/pitch.py)

Imports __future__, pathlib, core, core.log, core.yamlite, .quote.

- [profile_path](../../components/agents/agents/video_client/pitch.py#L28) — function
- [load_profile](../../components/agents/agents/video_client/pitch.py#L34) — function
- [portfolio_links](../../components/agents/agents/video_client/pitch.py#L42) — function
- [signature](../../components/agents/agents/video_client/pitch.py#L52) — function
- [_skill_line](../../components/agents/agents/video_client/pitch.py#L99) — function
- [opening_pitch](../../components/agents/agents/video_client/pitch.py#L108) — function — The first message. Asks for a reply, never quotes a price.
- [rate_reply](../../components/agents/agents/video_client/pitch.py#L143) — function — They replied. Send the number, the scope, and the deposit terms.
- [counter_reply](../../components/agents/agents/video_client/pitch.py#L185) — function — They named a number below the ask but above the floor.
- [follow_up](../../components/agents/agents/video_client/pitch.py#L220) — function — The nth chase, or None when it is time to stop.
- [due_after_days](../../components/agents/agents/video_client/pitch.py#L234) — function

## agents/video_client/quote.py

[Open source](../../components/agents/agents/video_client/quote.py)

Imports __future__, math, pathlib, re, dataclasses, core, core.log, core.yamlite, core.work_policy.

- [rates_path](../../components/agents/agents/video_client/quote.py#L60) — function
- [load_rates](../../components/agents/agents/video_client/quote.py#L73) — function
- [currency_for](../../components/agents/agents/video_client/quote.py#L91) — function — USD unless there is a reason to think they are in India.
- [tier_for](../../components/agents/agents/video_client/quote.py#L97) — function
- [rules](../../components/agents/agents/video_client/quote.py#L105) — function
- [Quote](../../components/agents/agents/video_client/quote.py#L110) — class — One priced offer, and everything needed to defend it.
- [build_quote](../../components/agents/agents/video_client/quote.py#L153) — function — Read what they asked for and price it from the card.
- [Counter](../../components/agents/agents/video_client/quote.py#L205) — class — What to do about a number the client put on the table.
- [find_offer](../../components/agents/agents/video_client/quote.py#L224) — function — The number the client named, if they named one.
- [respond_to](../../components/agents/agents/video_client/quote.py#L247) — function — Accept, counter, or stop and ask him. The floor is absolute.
- [deposit_line](../../components/agents/agents/video_client/quote.py#L272) — function — The sentence that decides whether he gets paid.
- [symbol](../../components/agents/agents/video_client/quote.py#L126) — function
- [money](../../components/agents/agents/video_client/quote.py#L129) — function
- [render](../../components/agents/agents/video_client/quote.py#L135) — function
- [to_json](../../components/agents/agents/video_client/quote.py#L144) — function
- [from_json](../../components/agents/agents/video_client/quote.py#L148) — function

## agents/video_client/sources.py

[Open source](../../components/agents/agents/video_client/sources.py)

Imports __future__, json, re, time, urllib.parse, dataclasses, core, core.log, agents.job_hunter.boards_in.

- [_is_video_editing](../../components/agents/agents/video_client/sources.py#L61) — function
- [Gig](../../components/agents/agents/video_client/sources.py#L82) — class — One piece of work somebody is trying to hire for.
- [is_editing_work](../../components/agents/agents/video_client/sources.py#L109) — function
- [from_linkedin](../../components/agents/agents/video_client/sources.py#L120) — function — Public postings, one search per market he sells into.
- [describe](../../components/agents/agents/video_client/sources.py#L145) — function — Pull the ad text. Needed to price it and to write anything specific.
- [_title_matches](../../components/agents/agents/video_client/sources.py#L153) — function
- [from_remoteok](../../components/agents/agents/video_client/sources.py#L157) — function — RemoteOK, filtered here.
- [from_remotive](../../components/agents/agents/video_client/sources.py#L187) — function
- [from_weworkremotely](../../components/agents/agents/video_client/sources.py#L211) — function
- [find_gigs](../../components/agents/agents/video_client/sources.py#L244) — function — Everything worth writing to today, deduplicated.
- [key](../../components/agents/agents/video_client/sources.py#L95) — function
- [kind](../../components/agents/agents/video_client/sources.py#L98) — function
- [to_json](../../components/agents/agents/video_client/sources.py#L105) — function

## agents/workflows.py

[Open source](../../components/agents/agents/workflows.py)

Imports __future__, datetime, json, re, zoneinfo, core, core.workflow_contracts, core.workflow_store, core.mailer, agents.saas_sales.product, core.workflow_media, agents.saas_sales.research.

- [contact](../../components/agents/agents/workflows.py#L19) — function
- [client_delivery](../../components/agents/agents/workflows.py#L26) — function
- [inbox_commitment](../../components/agents/agents/workflows.py#L95) — function
- [learning_evidence](../../components/agents/agents/workflows.py#L154) — function
- [content_release](../../components/agents/agents/workflows.py#L176) — function
- [saas_demand](../../components/agents/agents/workflows.py#L216) — function

## core/__init__.py

[Open source](../../components/agents/core/__init__.py)


## core/browser.py

[Open source](../../components/agents/core/browser.py)

Imports __future__, contextlib, hashlib, json, re, threading, pathlib, ., playwright.sync_api.

- [browser_page](../../components/agents/core/browser.py#L28) — function
- [page_html](../../components/agents/core/browser.py#L50) — function
- [fingerprint](../../components/agents/core/browser.py#L55) — function
- [inspect_page](../../components/agents/core/browser.py#L61) — function
- [ApplicationBrowser](../../components/agents/core/browser.py#L75) — class
- [inspect](../../components/agents/core/browser.py#L76) — function
- [submit](../../components/agents/core/browser.py#L80) — function

## core/calendar.py

[Open source](../../components/agents/core/calendar.py)

Imports __future__, datetime, dataclasses, zoneinfo, ., .log, .oauth, .store.

- [timezone](../../components/agents/core/calendar.py#L18) — function
- [_rfc3339](../../components/agents/core/calendar.py#L29) — function
- [Slot](../../components/agents/core/calendar.py#L36) — class
- [CalendarClient](../../components/agents/core/calendar.py#L48) — class
- [human](../../components/agents/core/calendar.py#L40) — function
- [__init__](../../components/agents/core/calendar.py#L49) — function
- [_call](../../components/agents/core/calendar.py#L57) — function
- [freebusy](../../components/agents/core/calendar.py#L65) — function
- [find_slots](../../components/agents/core/calendar.py#L80) — function — Propose interview times that do not clash with anything on the calendar.
- [create_event](../../components/agents/core/calendar.py#L114) — function
- [list_events](../../components/agents/core/calendar.py#L143) — function

## core/config.py

[Open source](../../components/agents/core/config.py)

Imports __future__, os, pathlib, re, typing.

- [load_dotenv](../../components/agents/core/config.py#L17) — function — Parse a .env file into os.environ. Returns the parsed mapping.
- [_ensure](../../components/agents/core/config.py#L63) — function
- [get](../../components/agents/core/config.py#L68) — function
- [get_bool](../../components/agents/core/config.py#L74) — function
- [get_int](../../components/agents/core/config.py#L81) — function
- [get_float](../../components/agents/core/config.py#L89) — function
- [get_list](../../components/agents/core/config.py#L97) — function
- [require](../../components/agents/core/config.py#L104) — function
- [data_dir](../../components/agents/core/config.py#L114) — function
- [profiles_dir](../../components/agents/core/config.py#L120) — function
- [dry_run](../../components/agents/core/config.py#L126) — function — Global kill switch. When true nothing leaves the machine.

## core/crawler.py

[Open source](../../components/agents/core/crawler.py)

Imports __future__, html, re, urllib.parse, dataclasses, ., .log, .ratelimit, .schema.

- [Contact](../../components/agents/core/crawler.py#L119) — class
- [PageResult](../../components/agents/core/crawler.py#L144) — class
- [SiteProfile](../../components/agents/core/crawler.py#L163) — class
- [strip_tags](../../components/agents/core/crawler.py#L189) — function
- [to_markdown](../../components/agents/core/crawler.py#L200) — function — Good-enough HTML to Markdown so the LLM sees structure, not tag soup.
- [page_title](../../components/agents/core/crawler.py#L221) — function
- [meta_description](../../components/agents/core/crawler.py#L226) — function
- [detect_tech](../../components/agents/core/crawler.py#L233) — function — Light digital-footprint read, used by the sales agent to size a prospect.
- [normalise_phone](../../components/agents/core/crawler.py#L268) — function
- [extract_emails](../../components/agents/core/crawler.py#L283) — function
- [extract_phones](../../components/agents/core/crawler.py#L314) — function
- [extract_whatsapp](../../components/agents/core/crawler.py#L329) — function — Pull WhatsApp click-to-chat links and turn them into phone numbers.
- [extract_jsonld_contacts](../../components/agents/core/crawler.py#L343) — function — Read email and telephone out of schema.org blocks.
- [has_mx](../../components/agents/core/crawler.py#L357) — function — Does this domain accept mail at all?
- [guessed_contacts](../../components/agents/core/crawler.py#L389) — function
- [extract_socials](../../components/agents/core/crawler.py#L403) — function
- [score_email](../../components/agents/core/crawler.py#L412) — function
- [Crawler](../../components/agents/core/crawler.py#L436) — class
- [label](../../components/agents/core/crawler.py#L135) — function
- [ok](../../components/agents/core/crawler.py#L158) — function
- [best_contact](../../components/agents/core/crawler.py#L176) — function
- [combined_text](../../components/agents/core/crawler.py#L182) — function
- [__init__](../../components/agents/core/crawler.py#L437) — function
- [fetch](../../components/agents/core/crawler.py#L448) — function
- [_links](../../components/agents/core/crawler.py#L486) — function
- [profile_site](../../components/agents/core/crawler.py#L495) — function — Crawl the handful of pages where contact details actually live.
- [_build_contacts](../../components/agents/core/crawler.py#L573) — function — Work down a ladder until something usable is found.
- [semantic_contacts](../../components/agents/core/crawler.py#L667) — function — LLM pass to name the right human, when regex alone is not enough.

## core/delivery.py

[Open source](../../components/agents/core/delivery.py)

Imports __future__, hashlib, json, urllib.parse, .crawler, .mailer, .store.

- [contact_email](../../components/agents/core/delivery.py#L13) — function — Only use supplied or published addresses; never infer a person's address.
- [deliver_reviewed](../../components/agents/core/delivery.py#L23) — function
- [mark_manual_sent](../../components/agents/core/delivery.py#L73) — function — Record an operator-confirmed handoff exactly once.

## core/followups.py

[Open source](../../components/agents/core/followups.py)

Imports __future__, time, ., .graph, .hitl, .mailer, .store.

- [FollowUpAgent](../../components/agents/core/followups.py#L12) — class
- [queue_due](../../components/agents/core/followups.py#L63) — function
- [__init__](../../components/agents/core/followups.py#L13) — function
- [n_review](../../components/agents/core/followups.py#L17) — function
- [n_send](../../components/agents/core/followups.py#L33) — function
- [build](../../components/agents/core/followups.py#L52) — function

## core/gmail.py

[Open source](../../components/agents/core/gmail.py)

Imports __future__, base64, email.utils, html, re, time, dataclasses, typing, ., .log, .oauth, .store.

- [b64url_decode](../../components/agents/core/gmail.py#L37) — function
- [b64url_encode](../../components/agents/core/gmail.py#L44) — function
- [html_to_text](../../components/agents/core/gmail.py#L48) — function
- [strip_quoted](../../components/agents/core/gmail.py#L58) — function — Drop the quoted history so intent classification sees only the new reply.
- [GmailMessage](../../components/agents/core/gmail.py#L76) — class
- [GmailClient](../../components/agents/core/gmail.py#L132) — class
- [subject](../../components/agents/core/gmail.py#L87) — function
- [from_addr](../../components/agents/core/gmail.py#L91) — function
- [from_name](../../components/agents/core/gmail.py#L95) — function
- [to_addr](../../components/agents/core/gmail.py#L99) — function
- [rfc_message_id](../../components/agents/core/gmail.py#L103) — function
- [in_reply_to](../../components/agents/core/gmail.py#L107) — function
- [references](../../components/agents/core/gmail.py#L111) — function
- [reply_text](../../components/agents/core/gmail.py#L115) — function
- [is_auto_reply](../../components/agents/core/gmail.py#L119) — function
- [__init__](../../components/agents/core/gmail.py#L133) — function
- [_call](../../components/agents/core/gmail.py#L142) — function
- [profile](../../components/agents/core/gmail.py#L158) — function
- [watch](../../components/agents/core/gmail.py#L161) — function — Register a Pub/Sub push subscription. Expires after 7 days.
- [stop_watch](../../components/agents/core/gmail.py#L177) — function
- [watch_state](../../components/agents/core/gmail.py#L181) — function
- [watch_expires_in](../../components/agents/core/gmail.py#L184) — function
- [renew_watch_if_needed](../../components/agents/core/gmail.py#L188) — function — Called by the scheduler; the blueprint's 7-day renewal cron.
- [get_cursor](../../components/agents/core/gmail.py#L197) — function
- [set_cursor](../../components/agents/core/gmail.py#L200) — function
- [history_since](../../components/agents/core/gmail.py#L204) — function
- [new_message_ids_since](../../components/agents/core/gmail.py#L222) — function
- [handle_push](../../components/agents/core/gmail.py#L233) — function — Process a Pub/Sub push body.
- [poll](../../components/agents/core/gmail.py#L262) — function — Fallback when there is no public endpoint for Pub/Sub push.
- [get_message](../../components/agents/core/gmail.py#L288) — function
- [parse_message](../../components/agents/core/gmail.py#L293) — function
- [send_raw](../../components/agents/core/gmail.py#L326) — function
- [modify](../../components/agents/core/gmail.py#L332) — function
- [mark_read](../../components/agents/core/gmail.py#L337) — function
- [walk](../../components/agents/core/gmail.py#L299) — function

## core/graph.py

[Open source](../../components/agents/core/graph.py)

Imports __future__, copy, contextvars, json, random, time, traceback, dataclasses, typing, .log, .store.

- [overwrite](../../components/agents/core/graph.py#L48) — function
- [append](../../components/agents/core/graph.py#L52) — function
- [merge_dict](../../components/agents/core/graph.py#L61) — function
- [add_int](../../components/agents/core/graph.py#L67) — function
- [GraphInterrupt](../../components/agents/core/graph.py#L74) — class — Raised by interrupt() to suspend the graph pending human input.
- [GraphRecursionError](../../components/agents/core/graph.py#L82) — class — Circuit breaker: too many super-steps without reaching END.
- [NodeFailure](../../components/agents/core/graph.py#L86) — class
- [Command](../../components/agents/core/graph.py#L94) — class — Resume payload handed back into a suspended graph.
- [Send](../../components/agents/core/graph.py#L102) — class — Fan out to a node with a specific payload (map step).
- [_Resumes](../../components/agents/core/graph.py#L111) — class — Per-execution stack of resume values supplied by the caller.
- [has_resume](../../components/agents/core/graph.py#L133) — function — True when a resume value is queued for the next interrupt() call.
- [interrupt](../../components/agents/core/graph.py#L146) — function — Pause the graph and surface ``payload`` to a human.
- [_Node](../../components/agents/core/graph.py#L169) — class
- [StateGraph](../../components/agents/core/graph.py#L177) — class
- [RunResult](../../components/agents/core/graph.py#L241) — class
- [CompiledGraph](../../components/agents/core/graph.py#L265) — class
- [__init__](../../components/agents/core/graph.py#L77) — function
- [__init__](../../components/agents/core/graph.py#L87) — function
- [__init__](../../components/agents/core/graph.py#L114) — function
- [load](../../components/agents/core/graph.py#L118) — function
- [take](../../components/agents/core/graph.py#L122) — function
- [__init__](../../components/agents/core/graph.py#L178) — function
- [add_node](../../components/agents/core/graph.py#L185) — function
- [add_edge](../../components/agents/core/graph.py#L194) — function
- [add_conditional_edges](../../components/agents/core/graph.py#L200) — function
- [set_entry_point](../../components/agents/core/graph.py#L207) — function
- [set_reducer](../../components/agents/core/graph.py#L211) — function
- [validate](../../components/agents/core/graph.py#L215) — function
- [compile](../../components/agents/core/graph.py#L231) — function
- [complete](../../components/agents/core/graph.py#L251) — function
- [interrupted](../../components/agents/core/graph.py#L255) — function
- [__getitem__](../../components/agents/core/graph.py#L258) — function
- [get](../../components/agents/core/graph.py#L261) — function
- [__init__](../../components/agents/core/graph.py#L266) — function
- [_merge](../../components/agents/core/graph.py#L273) — function
- [_persistable](../../components/agents/core/graph.py#L284) — function — Strip transient keys and verify the rest survives a round trip.
- [_save](../../components/agents/core/graph.py#L306) — function
- [latest_checkpoint](../../components/agents/core/graph.py#L322) — function
- [history](../../components/agents/core/graph.py#L331) — function
- [_resume_values](../../components/agents/core/graph.py#L338) — function
- [_push_resume](../../components/agents/core/graph.py#L341) — function
- [_clear_resume](../../components/agents/core/graph.py#L346) — function
- [_next_node](../../components/agents/core/graph.py#L350) — function
- [_run_node](../../components/agents/core/graph.py#L366) — function
- [invoke](../../components/agents/core/graph.py#L383) — function — Run the graph, resuming this thread if it has a live checkpoint.
- [resume](../../components/agents/core/graph.py#L502) — function — Wake a suspended graph with the human's answer.
- [stream](../../components/agents/core/graph.py#L506) — function — Yield node events as the graph runs (buffered, then replayed).
- [to_mermaid](../../components/agents/core/graph.py#L514) — function

## core/hitl.py

[Open source](../../components/agents/core/hitl.py)

Imports __future__, json, dataclasses, typing, .graph, .log, .store.

- [Decision](../../components/agents/core/hitl.py#L24) — class
- [ApprovalQueue](../../components/agents/core/hitl.py#L51) — class
- [require_approval](../../components/agents/core/hitl.py#L132) — function — Suspend the graph until a human decides.
- [approved](../../components/agents/core/hitl.py#L30) — function
- [apply_to](../../components/agents/core/hitl.py#L33) — function
- [to_json](../../components/agents/core/hitl.py#L38) — function
- [from_json](../../components/agents/core/hitl.py#L42) — function
- [__init__](../../components/agents/core/hitl.py#L52) — function
- [create](../../components/agents/core/hitl.py#L55) — function
- [get](../../components/agents/core/hitl.py#L70) — function
- [pending](../../components/agents/core/hitl.py#L78) — function
- [recent](../../components/agents/core/hitl.py#L91) — function
- [decide](../../components/agents/core/hitl.py#L100) — function
- [approve](../../components/agents/core/hitl.py#L125) — function
- [reject](../../components/agents/core/hitl.py#L128) — function

## core/http.py

[Open source](../../components/agents/core/http.py)

Imports __future__, gzip, json, random, ssl, time, urllib.error, urllib.parse, urllib.request, zlib, dataclasses, typing, ., .log, http.client.

- [Response](../../components/agents/core/http.py#L63) — class
- [HttpError](../../components/agents/core/http.py#L93) — class
- [_decode](../../components/agents/core/http.py#L107) — function
- [_retry_after](../../components/agents/core/http.py#L124) — function
- [request](../../components/agents/core/http.py#L142) — function
- [get](../../components/agents/core/http.py#L204) — function
- [post](../../components/agents/core/http.py#L208) — function
- [post_form](../../components/agents/core/http.py#L212) — function
- [get_json](../../components/agents/core/http.py#L219) — function
- [post_json](../../components/agents/core/http.py#L223) — function
- [text](../../components/agents/core/http.py#L70) — function
- [json](../../components/agents/core/http.py#L77) — function
- [ok](../../components/agents/core/http.py#L83) — function
- [raise_for_status](../../components/agents/core/http.py#L86) — function
- [__init__](../../components/agents/core/http.py#L94) — function
- [json](../../components/agents/core/http.py#L100) — function

## core/imapbox.py

[Open source](../../components/agents/core/imapbox.py)

Imports __future__, email, email.utils, imaplib, time, email.header, ., .gmail, .log, .store.

- [_decode](../../components/agents/core/imapbox.py#L40) — function
- [default_host](../../components/agents/core/imapbox.py#L49) — function
- [ImapBox](../../components/agents/core/imapbox.py#L54) — class — Fetches messages that arrived since the last check.
- [get_inbox](../../components/agents/core/imapbox.py#L219) — function
- [__init__](../../components/agents/core/imapbox.py#L57) — function
- [configured](../../components/agents/core/imapbox.py#L69) — function
- [_connect](../../components/agents/core/imapbox.py#L72) — function
- [check](../../components/agents/core/imapbox.py#L88) — function — One-line health check, for the doctor.
- [_logout](../../components/agents/core/imapbox.py#L104) — function
- [poll](../../components/agents/core/imapbox.py#L114) — function — New messages since the last poll, oldest first.
- [mark_read](../../components/agents/core/imapbox.py#L151) — function — Acknowledge after routing succeeded, so a failed handler can retry.
- [_to_message](../../components/agents/core/imapbox.py#L156) — function

## core/inbox.py

[Open source](../../components/agents/core/inbox.py)

Imports __future__, hashlib, re, ., .log, agents.job_hunter.agent, agents.common, .imapbox, .gmail, agents.job_hunter.booking, agents.fullstack_sales.agent, agents.video_client.agent, agents.sponsorship.agent.

- [process](../../components/agents/core/inbox.py#L13) — function
- [route](../../components/agents/core/inbox.py#L50) — function
- [selected_slot](../../components/agents/core/inbox.py#L101) — function — Recognise an unambiguous choice from previously offered actual slots.

## core/lessons.py

[Open source](../../components/agents/core/lessons.py)

Imports __future__, re, time, uuid, core.log, core.store.

- [_now](../../components/agents/core/lessons.py#L40) — function
- [_norm](../../components/agents/core/lessons.py#L44) — function — For deciding whether two rules are the same rule.
- [_words](../../components/agents/core/lessons.py#L49) — function
- [Lessons](../../components/agents/core/lessons.py#L53) — class — The rules one agent has learned, and the evidence behind each.
- [get_lessons](../../components/agents/core/lessons.py#L173) — function
- [__init__](../../components/agents/core/lessons.py#L56) — function
- [add](../../components/agents/core/lessons.py#L61) — function — Record a rule. Saying the same thing twice strengthens it instead.
- [_same_rule](../../components/agents/core/lessons.py#L84) — function — Near-duplicate detection, so twenty rejections do not make twenty
- [retire](../../components/agents/core/lessons.py#L101) — function
- [forget](../../components/agents/core/lessons.py#L105) — function — He said the rule is wrong. Remove it rather than retire it.
- [all](../../components/agents/core/lessons.py#L111) — function
- [relevant](../../components/agents/core/lessons.py#L117) — function — The rules worth spending prompt space on for this target.
- [mark_used](../../components/agents/core/lessons.py#L144) — function
- [prompt_block](../../components/agents/core/lessons.py#L150) — function — The rules, as text to paste into a prompt. Empty when there are none.
- [summary](../../components/agents/core/lessons.py#L165) — function

## core/llm.py

[Open source](../../components/agents/core/llm.py)

Imports __future__, json, functools, os, re, threading, time, textwrap, dataclasses, typing, ., .log, .schema, .workflow_brain, hashlib, core, .store, msvcrt, fcntl.

- [_serial_local](../../components/agents/core/llm.py#L44) — function — One local generation at a time, including tool turns and model loading.
- [Usage](../../components/agents/core/llm.py#L85) — class
- [Message](../../components/agents/core/llm.py#L97) — class — One turn. Carries tool calls and tool results as well as plain text.
- [LLMError](../../components/agents/core/llm.py#L119) — class
- [extract_json](../../components/agents/core/llm.py#L126) — function
- [json_schema_for](../../components/agents/core/llm.py#L165) — function — Our compact schema shape rewritten as the JSON Schema a local runtime
- [Provider](../../components/agents/core/llm.py#L196) — class
- [AnthropicProvider](../../components/agents/core/llm.py#L205) — class
- [_is_local](../../components/agents/core/llm.py#L236) — function
- [OpenAIProvider](../../components/agents/core/llm.py#L240) — class — OpenAI's API, and every local server that imitates it.
- [OllamaProvider](../../components/agents/core/llm.py#L299) — class — A model running on this machine, through Ollama.
- [offline_handler](../../components/agents/core/llm.py#L445) — function — Register a deterministic stand-in for one LLM task.
- [stub_from_schema](../../components/agents/core/llm.py#L453) — function — Produce a schema-valid placeholder value.
- [OfflineProvider](../../components/agents/core/llm.py#L482) — class — Deterministic provider used for tests and dry runs.
- [_chatgpt_provider](../../components/agents/core/llm.py#L497) — function
- [LLM](../../components/agents/core/llm.py#L516) — class
- [get_llm](../../components/agents/core/llm.py#L772) — function
- [reset_llm](../../components/agents/core/llm.py#L780) — function
- [guarded](../../components/agents/core/llm.py#L47) — function
- [add](../../components/agents/core/llm.py#L90) — function
- [to_api](../../components/agents/core/llm.py#L110) — function
- [complete](../../components/agents/core/llm.py#L199) — function
- [__init__](../../components/agents/core/llm.py#L208) — function
- [complete](../../components/agents/core/llm.py#L214) — function
- [__init__](../../components/agents/core/llm.py#L251) — function
- [complete](../../components/agents/core/llm.py#L258) — function
- [__init__](../../components/agents/core/llm.py#L307) — function
- [complete](../../components/agents/core/llm.py#L322) — function
- [chat](../../components/agents/core/llm.py#L378) — function — One turn, returning the full assistant message.
- [warm](../../components/agents/core/llm.py#L386) — function — Load the model into memory before it is needed.
- [speed](../../components/agents/core/llm.py#L405) — function — Tokens per second on a tiny generation, for the doctor.
- [models](../../components/agents/core/llm.py#L430) — function — What is installed, for the doctor. Empty list if unreachable.
- [deco](../../components/agents/core/llm.py#L447) — function
- [complete](../../components/agents/core/llm.py#L490) — function
- [__init__](../../components/agents/core/llm.py#L517) — function
- [impl](../../components/agents/core/llm.py#L530) — function
- [is_offline](../../components/agents/core/llm.py#L536) — function
- [_cache_key](../../components/agents/core/llm.py#L540) — function
- [_cached](../../components/agents/core/llm.py#L545) — function
- [_store_cache](../../components/agents/core/llm.py#L550) — function
- [complete](../../components/agents/core/llm.py#L555) — function
- [with_tools](../../components/agents/core/llm.py#L578) — function — Let the model go and look things up before it answers.
- [structured_with_tools](../../components/agents/core/llm.py#L646) — function — Look things up first, then answer in the required shape.
- [structured](../../components/agents/core/llm.py#L681) — function — Return JSON matching `schema`, validated, with a repair round-trip.
- [_offline_result](../../components/agents/core/llm.py#L709) — function
- [_structured](../../components/agents/core/llm.py#L714) — function
- [classify](../../components/agents/core/llm.py#L749) — function

## core/log.py

[Open source](../../components/agents/core/log.py)

Imports __future__, json, logging, os, sys, threading, time.

- [set_context](../../components/agents/core/log.py#L14) — function
- [clear_context](../../components/agents/core/log.py#L21) — function
- [get_context](../../components/agents/core/log.py#L25) — function
- [_JsonFormatter](../../components/agents/core/log.py#L29) — class
- [_TextFormatter](../../components/agents/core/log.py#L46) — class
- [configure](../../components/agents/core/log.py#L81) — function
- [get_logger](../../components/agents/core/log.py#L97) — function
- [Logger](../../components/agents/core/log.py#L102) — class — Thin wrapper letting callers pass arbitrary kwargs as structured fields.
- [format](../../components/agents/core/log.py#L30) — function
- [__init__](../../components/agents/core/log.py#L51) — function
- [format](../../components/agents/core/log.py#L55) — function
- [__init__](../../components/agents/core/log.py#L105) — function
- [_emit](../../components/agents/core/log.py#L108) — function
- [debug](../../components/agents/core/log.py#L112) — function
- [info](../../components/agents/core/log.py#L113) — function
- [warn](../../components/agents/core/log.py#L114) — function
- [error](../../components/agents/core/log.py#L116) — function
- [exception](../../components/agents/core/log.py#L117) — function

## core/mailer.py

[Open source](../../components/agents/core/mailer.py)

Imports __future__, email.utils, mimetypes, pathlib, re, smtplib, ssl, textwrap, dataclasses, email.message, ., .log, .ratelimit, .store, hashlib, .gmail, json.

- [valid_email](../../components/agents/core/mailer.py#L48) — function
- [SendBlocked](../../components/agents/core/mailer.py#L56) — class — Raised when a policy check refuses a send.
- [Attachment](../../components/agents/core/mailer.py#L61) — class
- [OutgoingMessage](../../components/agents/core/mailer.py#L68) — class
- [SuppressionList](../../components/agents/core/mailer.py#L86) — class — Anyone here is never contacted again, for any reason, by any agent.
- [unsubscribe_token](../../components/agents/core/mailer.py#L107) — function
- [_reachable_base](../../components/agents/core/mailer.py#L113) — function — The public URL, or empty when it is only reachable from this machine.
- [unsubscribe_url](../../components/agents/core/mailer.py#L122) — function
- [unsubscribe_link](../../components/agents/core/mailer.py#L128) — function — What to put in front of the recipient.
- [compliance_footer](../../components/agents/core/mailer.py#L148) — function
- [Mailer](../../components/agents/core/mailer.py#L158) — class
- [wrap](../../components/agents/core/mailer.py#L396) — function
- [__init__](../../components/agents/core/mailer.py#L89) — function
- [add](../../components/agents/core/mailer.py#L92) — function
- [contains](../../components/agents/core/mailer.py#L97) — function
- [all](../../components/agents/core/mailer.py#L100) — function
- [remove](../../components/agents/core/mailer.py#L103) — function
- [__init__](../../components/agents/core/mailer.py#L159) — function
- [gmail](../../components/agents/core/mailer.py#L171) — function
- [build](../../components/agents/core/mailer.py#L178) — function
- [preflight](../../components/agents/core/mailer.py#L224) — function
- [send](../../components/agents/core/mailer.py#L241) — function
- [_send_smtp](../../components/agents/core/mailer.py#L317) — function
- [record](../../components/agents/core/mailer.py#L373) — function
- [sent_today](../../components/agents/core/mailer.py#L383) — function
- [bounce_rate](../../components/agents/core/mailer.py#L386) — function

## core/notify.py

[Open source](../../components/agents/core/notify.py)

Imports __future__, json, dataclasses, ., .log, server.bot, core.telegram, .mailer, .store.

- [Notification](../../components/agents/core/notify.py#L26) — class
- [Notifier](../../components/agents/core/notify.py#L34) — class
- [get_notifier](../../components/agents/core/notify.py#L144) — function
- [reset_notifier](../../components/agents/core/notify.py#L152) — function
- [alert_reply](../../components/agents/core/notify.py#L157) — function — The blueprint's headline alert.
- [__init__](../../components/agents/core/notify.py#L35) — function
- [send](../../components/agents/core/notify.py#L39) — function
- [_unknown](../../components/agents/core/notify.py#L51) — function
- [_send_console](../../components/agents/core/notify.py#L55) — function
- [_send_store](../../components/agents/core/notify.py#L61) — function
- [_send_telegram](../../components/agents/core/notify.py#L68) — function — Post into the agent's own topic in your Telegram group.
- [_send_ntfy](../../components/agents/core/notify.py#L84) — function
- [_send_webhook](../../components/agents/core/notify.py#L103) — function
- [_send_slack](../../components/agents/core/notify.py#L110) — function
- [_send_discord](../../components/agents/core/notify.py#L123) — function
- [_send_email](../../components/agents/core/notify.py#L131) — function

## core/oauth.py

[Open source](../../components/agents/core/oauth.py)

Imports __future__, json, pathlib, secrets, threading, time, urllib.parse, webbrowser, dataclasses, http.server, ., .log, .store.

- [OAuthError](../../components/agents/core/oauth.py#L44) — class
- [Token](../../components/agents/core/oauth.py#L49) — class
- [GoogleOAuth](../../components/agents/core/oauth.py#L68) — class
- [expired](../../components/agents/core/oauth.py#L57) — function
- [to_json](../../components/agents/core/oauth.py#L60) — function
- [from_json](../../components/agents/core/oauth.py#L64) — function
- [__init__](../../components/agents/core/oauth.py#L69) — function
- [_load_client_secrets_file](../../components/agents/core/oauth.py#L80) — function — Accept the credentials.json Google Cloud Console hands you.
- [_key](../../components/agents/core/oauth.py#L97) — function
- [load](../../components/agents/core/oauth.py#L100) — function
- [save](../../components/agents/core/oauth.py#L103) — function
- [clear](../../components/agents/core/oauth.py#L106) — function
- [authorize_url](../../components/agents/core/oauth.py#L110) — function
- [exchange](../../components/agents/core/oauth.py#L121) — function
- [refresh](../../components/agents/core/oauth.py#L137) — function
- [access_token](../../components/agents/core/oauth.py#L155) — function
- [headers](../../components/agents/core/oauth.py#L164) — function
- [run_installed_flow](../../components/agents/core/oauth.py#L168) — function
- [Handler](../../components/agents/core/oauth.py#L180) — class
- [do_GET](../../components/agents/core/oauth.py#L181) — function
- [log_message](../../components/agents/core/oauth.py#L199) — function

## core/pdf.py

[Open source](../../components/agents/core/pdf.py)

Imports __future__, io, zlib, dataclasses, pathlib.

- [text_width](../../components/agents/core/pdf.py#L64) — function
- [wrap_text](../../components/agents/core/pdf.py#L73) — function
- [_escape](../../components/agents/core/pdf.py#L92) — function
- [_Page](../../components/agents/core/pdf.py#L110) — class
- [PDF](../../components/agents/core/pdf.py#L115) — class — A simple top-down document builder.
- [__init__](../../components/agents/core/pdf.py#L118) — function
- [content_width](../../components/agents/core/pdf.py#L131) — function
- [_new_page](../../components/agents/core/pdf.py#L134) — function
- [_ensure](../../components/agents/core/pdf.py#L138) — function
- [page](../../components/agents/core/pdf.py#L143) — function
- [_draw](../../components/agents/core/pdf.py#L147) — function
- [text](../../components/agents/core/pdf.py#L154) — function
- [heading](../../components/agents/core/pdf.py#L174) — function
- [title](../../components/agents/core/pdf.py#L186) — function
- [row](../../components/agents/core/pdf.py#L194) — function
- [bullet](../../components/agents/core/pdf.py#L209) — function
- [hrule](../../components/agents/core/pdf.py#L224) — function
- [space](../../components/agents/core/pdf.py#L231) — function
- [build](../../components/agents/core/pdf.py#L235) — function
- [save](../../components/agents/core/pdf.py#L308) — function
- [add](../../components/agents/core/pdf.py#L238) — function

## core/ratelimit.py

[Open source](../../components/agents/core/ratelimit.py)

Imports __future__, threading, time, urllib.parse, urllib.request, dataclasses, .log.

- [TokenBucket](../../components/agents/core/ratelimit.py#L15) — class — Classic token bucket. `rate` tokens/second up to `capacity` burst.
- [HostLimiter](../../components/agents/core/ratelimit.py#L52) — class — Per-hostname politeness: a minimum gap between requests, plus robots.txt.
- [_Robots](../../components/agents/core/ratelimit.py#L95) — class
- [DailyCap](../../components/agents/core/ratelimit.py#L169) — class — Per-key daily counter, persisted, used to cap outbound email volume.
- [__init__](../../components/agents/core/ratelimit.py#L18) — function
- [_refill](../../components/agents/core/ratelimit.py#L25) — function
- [try_acquire](../../components/agents/core/ratelimit.py#L30) — function
- [acquire](../../components/agents/core/ratelimit.py#L38) — function
- [__init__](../../components/agents/core/ratelimit.py#L55) — function
- [wait](../../components/agents/core/ratelimit.py#L64) — function
- [allowed](../../components/agents/core/ratelimit.py#L74) — function
- [crawl_delay](../../components/agents/core/ratelimit.py#L87) — function
- [fetch](../../components/agents/core/ratelimit.py#L101) — function
- [parse](../../components/agents/core/ratelimit.py#L113) — function
- [allowed](../../components/agents/core/ratelimit.py#L160) — function
- [__init__](../../components/agents/core/ratelimit.py#L172) — function
- [_key](../../components/agents/core/ratelimit.py#L176) — function
- [count](../../components/agents/core/ratelimit.py#L179) — function
- [remaining](../../components/agents/core/ratelimit.py#L182) — function
- [check_and_increment](../../components/agents/core/ratelimit.py#L185) — function

## core/reflect.py

[Open source](../../components/agents/core/reflect.py)

Imports __future__, difflib, core.lessons, core.llm, core.log, core.store.

- [_diff](../../components/agents/core/reflect.py#L59) — function — What he actually changed, as a readable diff.
- [_describe](../../components/agents/core/reflect.py#L71) — function
- [learn_from_decision](../../components/agents/core/reflect.py#L83) — function — Called after every approval decision. Returns the rules it wrote.

## core/registry.py

[Open source](../../components/agents/core/registry.py)

Imports __future__, typing, .log, .store, agents.fullstack_sales, agents.community, agents.job_hunter, agents.saas_sales, agents.sponsorship, agents.video_client, .followups, .workflow_service, .workflow_store.

- [register](../../components/agents/core/registry.py#L18) — function
- [names](../../components/agents/core/registry.py#L22) — function
- [_load_all](../../components/agents/core/registry.py#L30) — function
- [get_graph](../../components/agents/core/registry.py#L64) — function
- [resume_thread](../../components/agents/core/registry.py#L72) — function — Wake whichever graph owns this thread with the operator's decision.

## core/schema.py

[Open source](../../components/agents/core/schema.py)

Imports __future__, typing.

- [ValidationError](../../components/agents/core/schema.py#L32) — class
- [_coerce](../../components/agents/core/schema.py#L38) — function — Nudge obvious near-misses into the right type (LLMs emit "3" for 3).
- [validate](../../components/agents/core/schema.py#L64) — function
- [describe](../../components/agents/core/schema.py#L134) — function — Render a schema as compact instructions for an LLM prompt.
- [__init__](../../components/agents/core/schema.py#L33) — function

## core/search.py

[Open source](../../components/agents/core/search.py)

Imports __future__, json, pathlib, re, urllib.parse, dataclasses, ., .log, .yamlite, html, xml.etree.ElementTree, ipaddress, .workflow_brain.

- [SearchHit](../../components/agents/core/search.py#L30) — class
- [SearchProvider](../../components/agents/core/search.py#L42) — class
- [SeedsProvider](../../components/agents/core/search.py#L49) — class — Targets curated in a file. Precise, free, and auditable.
- [BraveProvider](../../components/agents/core/search.py#L101) — class
- [SerperProvider](../../components/agents/core/search.py#L117) — class
- [SearxngProvider](../../components/agents/core/search.py#L132) — class
- [ChatGPTWebProvider](../../components/agents/core/search.py#L145) — class — Bounded public discovery through the signed-in Codex web search tool.
- [public_demand_search](../../components/agents/core/search.py#L194) — function — Search an ordinary public feed without an authenticated Reddit session.
- [public_issue_search](../../components/agents/core/search.py#L233) — function — Bounded, public source retrieval independent of ChatGPT and Ollama.
- [public_web_url](../../components/agents/core/search.py#L260) — function
- [get_search](../../components/agents/core/search.py#L291) — function
- [discover](../../components/agents/core/search.py#L299) — function — Run several queries, dedupe by domain, drop aggregators and socials.
- [domain](../../components/agents/core/search.py#L38) — function
- [search](../../components/agents/core/search.py#L45) — function
- [__init__](../../components/agents/core/search.py#L53) — function
- [load](../../components/agents/core/search.py#L58) — function
- [search](../../components/agents/core/search.py#L77) — function
- [search](../../components/agents/core/search.py#L104) — function
- [search](../../components/agents/core/search.py#L120) — function
- [search](../../components/agents/core/search.py#L135) — function
- [search](../../components/agents/core/search.py#L149) — function
- [search_many](../../components/agents/core/search.py#L152) — function
- [query_sources](../../components/agents/core/search.py#L305) — function

## core/store.py

[Open source](../../components/agents/core/store.py)

Imports __future__, contextlib, hashlib, json, pathlib, re, sqlite3, threading, time, uuid, typing, ., .log, psycopg2, psycopg.

- [now](../../components/agents/core/store.py#L199) — function
- [new_id](../../components/agents/core/store.py#L203) — function
- [hash_key](../../components/agents/core/store.py#L207) — function
- [Store](../../components/agents/core/store.py#L212) — class — Small portable SQL wrapper.
- [get_store](../../components/agents/core/store.py#L421) — function
- [reset_store](../../components/agents/core/store.py#L428) — function — Test helper: drop the cached singleton.
- [__init__](../../components/agents/core/store.py#L219) — function
- [_connect](../../components/agents/core/store.py#L243) — function
- [conn](../../components/agents/core/store.py#L277) — function
- [close](../../components/agents/core/store.py#L284) — function
- [_adapt](../../components/agents/core/store.py#L291) — function
- [tx](../../components/agents/core/store.py#L299) — function — Transaction scope. Nested use re-enters the same transaction.
- [execute](../../components/agents/core/store.py#L315) — function
- [run](../../components/agents/core/store.py#L320) — function
- [_rows](../../components/agents/core/store.py#L324) — function
- [query](../../components/agents/core/store.py#L330) — function
- [one](../../components/agents/core/store.py#L333) — function
- [migrate](../../components/agents/core/store.py#L337) — function
- [upsert](../../components/agents/core/store.py#L346) — function
- [kv_get](../../components/agents/core/store.py#L364) — function
- [kv_set](../../components/agents/core/store.py#L369) — function
- [kv_delete](../../components/agents/core/store.py#L375) — function
- [kv_list](../../components/agents/core/store.py#L378) — function
- [seen](../../components/agents/core/store.py#L383) — function
- [mark_seen](../../components/agents/core/store.py#L388) — function — Record the key. Returns True if this is the first time we've seen it.
- [event](../../components/agents/core/store.py#L401) — function — Append an audit event. Positional-only params so that payload
- [recent_events](../../components/agents/core/store.py#L411) — function

## core/telegram.py

[Open source](../../components/agents/core/telegram.py)

Imports __future__, json, mimetypes, pathlib, uuid, dataclasses, typing, ., .log.

- [TelegramError](../../components/agents/core/telegram.py#L38) — class — The API returned ok:false.
- [esc](../../components/agents/core/telegram.py#L57) — function — Escape for Telegram's HTML parse mode.
- [split_message](../../components/agents/core/telegram.py#L63) — function — Break a long message on line boundaries, never mid-line if avoidable.
- [Button](../../components/agents/core/telegram.py#L86) — class — One inline keyboard button. `data` is what comes back on a tap.
- [keyboard](../../components/agents/core/telegram.py#L99) — function
- [Update](../../components/agents/core/telegram.py#L104) — class — One incoming update, flattened to the handful of fields a bot needs.
- [Telegram](../../components/agents/core/telegram.py#L182) — class
- [_multipart](../../components/agents/core/telegram.py#L316) — function — Build a multipart/form-data body. urllib has no such thing built in.
- [__init__](../../components/agents/core/telegram.py#L41) — function
- [is_fatal](../../components/agents/core/telegram.py#L46) — function — Errors that retrying will never fix - a bad token, a kicked bot.
- [to_dict](../../components/agents/core/telegram.py#L92) — function
- [id](../../components/agents/core/telegram.py#L109) — function
- [message](../../components/agents/core/telegram.py#L113) — function
- [callback](../../components/agents/core/telegram.py#L118) — function
- [is_callback](../../components/agents/core/telegram.py#L122) — function
- [text](../../components/agents/core/telegram.py#L126) — function
- [chat_id](../../components/agents/core/telegram.py#L132) — function
- [chat_type](../../components/agents/core/telegram.py#L138) — function
- [thread_id](../../components/agents/core/telegram.py#L143) — function — The forum topic this arrived in, if any.
- [message_id](../../components/agents/core/telegram.py#L149) — function
- [from_id](../../components/agents/core/telegram.py#L154) — function
- [from_name](../../components/agents/core/telegram.py#L159) — function
- [callback_id](../../components/agents/core/telegram.py#L166) — function
- [command](../../components/agents/core/telegram.py#L169) — function — Split "/run jobs" into ("run", "jobs"). Strips any @botname suffix.
- [__init__](../../components/agents/core/telegram.py#L183) — function
- [_url](../../components/agents/core/telegram.py#L194) — function
- [call](../../components/agents/core/telegram.py#L197) — function
- [get_me](../../components/agents/core/telegram.py#L217) — function
- [set_my_commands](../../components/agents/core/telegram.py#L220) — function
- [get_chat](../../components/agents/core/telegram.py#L224) — function
- [get_updates](../../components/agents/core/telegram.py#L228) — function — Long poll. Blocks up to `timeout` seconds waiting for activity.
- [delete_webhook](../../components/agents/core/telegram.py#L236) — function — Polling and webhooks are mutually exclusive; clear any stale webhook.
- [send_message](../../components/agents/core/telegram.py#L241) — function — Send text, splitting anything over Telegram's 4096 character limit.
- [edit_message_text](../../components/agents/core/telegram.py#L264) — function
- [answer_callback](../../components/agents/core/telegram.py#L271) — function — Stops the button's loading spinner. Telegram requires this.
- [send_document](../../components/agents/core/telegram.py#L278) — function
- [create_forum_topic](../../components/agents/core/telegram.py#L300) — function — Create a topic in a group that has Topics enabled.
- [edit_forum_topic](../../components/agents/core/telegram.py#L311) — function

## core/toolbelt.py

[Open source](../../components/agents/core/toolbelt.py)

Imports __future__, json, core, core.log, core.tools, core.search, core.crawler, agents.sponsorship, core.work_policy, core.lessons, agents.saas_sales.product, core.store, agents.video_client.quote, agents.fullstack_sales.packages.

- [_search_web](../../components/agents/core/toolbelt.py#L27) — function — Whatever search provider is configured, as plain text.
- [_read_page](../../components/agents/core/toolbelt.py#L66) — function — One page, as readable text. Honours robots.txt via the crawler.
- [_my_numbers](../../components/agents/core/toolbelt.py#L100) — function — The channel figures the sponsorship pitch is allowed to state.
- [_rate_card](../../components/agents/core/toolbelt.py#L123) — function — What he charges, from the real card. Never a guess.
- [_what_i_learned](../../components/agents/core/toolbelt.py#L175) — function — The rules he has taught this agent by rejecting or rewriting drafts.
- [_check_claims](../../components/agents/core/toolbelt.py#L207) — function — Whether a draft claims something the product cannot back yet.
- [_already_contacted](../../components/agents/core/toolbelt.py#L232) — function — Whether this target has been written to before.
- [belt_for](../../components/agents/core/toolbelt.py#L282) — function
- [describe_belt](../../components/agents/core/toolbelt.py#L286) — function

## core/tools.py

[Open source](../../components/agents/core/tools.py)

Imports __future__, json, time, dataclasses, typing, core.log.

- [Tool](../../components/agents/core/tools.py#L43) — class — One thing the model can do, and what it costs to let it.
- [register](../../components/agents/core/tools.py#L66) — function
- [tool](../../components/agents/core/tools.py#L73) — function — Decorator form. `safe=True` is a claim you are making about the function.
- [get](../../components/agents/core/tools.py#L83) — function
- [all_tools](../../components/agents/core/tools.py#L87) — function
- [bind](../../components/agents/core/tools.py#L91) — function — The tools an agent is handing to the model for one call.
- [CallLog](../../components/agents/core/tools.py#L112) — class — What the model actually did with its hands, for the approval card.
- [execute](../../components/agents/core/tools.py#L136) — function — Run one tool call and return a string the model can read.
- [spec](../../components/agents/core/tools.py#L55) — function — The shape Ollama and the OpenAI dialect both expect.
- [deco](../../components/agents/core/tools.py#L76) — function
- [add](../../components/agents/core/tools.py#L116) — function
- [summary](../../components/agents/core/tools.py#L122) — function
- [to_json](../../components/agents/core/tools.py#L132) — function

## core/work_policy.py

[Open source](../../components/agents/core/work_policy.py)

Imports __future__, re, ..

- [project_floor](../../components/agents/core/work_policy.py#L8) — function
- [budget_check](../../components/agents/core/work_policy.py#L16) — function — Reject only an explicitly stated INR ceiling below the relevant floor.

## core/workflow_brain.py

[Open source](../../components/agents/core/workflow_brain.py)

Imports __future__, json, os, pathlib, shutil, subprocess, re, threading, time, uuid, contextlib, ., .llm, .workflow_contracts, msvcrt.

- [ChatGPTUnavailable](../../components/agents/core/workflow_brain.py#L27) — class — The requested provider cannot serve this request.
- [cloud_failure](../../components/agents/core/workflow_brain.py#L31) — function
- [validate_plan](../../components/agents/core/workflow_brain.py#L70) — function
- [codex_path](../../components/agents/core/workflow_brain.py#L89) — function
- [shared_gpu](../../components/agents/core/workflow_brain.py#L101) — function — Use StoryLens's existing cross-process admission slot, without importing it.
- [_strict_schema](../../components/agents/core/workflow_brain.py#L125) — function
- [ChatGPTProvider](../../components/agents/core/workflow_brain.py#L135) — class — Official CLI session reuse; never reads/copies the authentication token.
- [cloud_unavailable](../../components/agents/core/workflow_brain.py#L218) — function
- [record_outage](../../components/agents/core/workflow_brain.py#L222) — function
- [StorylensProvider](../../components/agents/core/workflow_brain.py#L228) — class — Keep ChatGPT first and retry with a loopback model only for outages.
- [plan](../../components/agents/core/workflow_brain.py#L260) — function
- [__init__](../../components/agents/core/workflow_brain.py#L139) — function
- [complete](../../components/agents/core/workflow_brain.py#L145) — function
- [search](../../components/agents/core/workflow_brain.py#L148) — function — Perform read-only public web research with explicit search evidence.
- [_complete](../../components/agents/core/workflow_brain.py#L153) — function
- [complete](../../components/agents/core/workflow_brain.py#L231) — function
- [selected](../../components/agents/core/workflow_brain.py#L266) — function
- [generate](../../components/agents/core/workflow_brain.py#L292) — function

## core/workflow_broker.py

[Open source](../../components/agents/core/workflow_broker.py)

Imports __future__, json, os, pathlib, time, urllib.parse, urllib.request, ., .hitl, .store, .workflow_contracts, .workflow_store, .mailer.

- [IntegrationUnavailable](../../components/agents/core/workflow_broker.py#L22) — class
- [IntegrationClient](../../components/agents/core/workflow_broker.py#L26) — class
- [ExecutionBroker](../../components/agents/core/workflow_broker.py#L82) — class
- [__init__](../../components/agents/core/workflow_broker.py#L27) — function
- [request](../../components/agents/core/workflow_broker.py#L49) — function
- [capabilities](../../components/agents/core/workflow_broker.py#L64) — function
- [submit](../../components/agents/core/workflow_broker.py#L72) — function
- [reconcile](../../components/agents/core/workflow_broker.py#L75) — function
- [cancel](../../components/agents/core/workflow_broker.py#L78) — function
- [__init__](../../components/agents/core/workflow_broker.py#L83) — function
- [request_review](../../components/agents/core/workflow_broker.py#L88) — function
- [validate_review](../../components/agents/core/workflow_broker.py#L111) — function
- [execute](../../components/agents/core/workflow_broker.py#L129) — function
- [_receipt](../../components/agents/core/workflow_broker.py#L217) — function
- [NoRedirect](../../components/agents/core/workflow_broker.py#L54) — class
- [redirect_request](../../components/agents/core/workflow_broker.py#L55) — function

## core/workflow_contracts.py

[Open source](../../components/agents/core/workflow_contracts.py)

Imports __future__, dataclasses, hashlib, json, math.

- [canonical](../../components/agents/core/workflow_contracts.py#L35) — function
- [digest](../../components/agents/core/workflow_contracts.py#L40) — function
- [input_references](../../components/agents/core/workflow_contracts.py#L44) — function — Collect declared source and artifact identities without copying content.
- [require_fields](../../components/agents/core/workflow_contracts.py#L64) — function
- [TaskEnvelope](../../components/agents/core/workflow_contracts.py#L73) — class
- [ArtifactRef](../../components/agents/core/workflow_contracts.py#L104) — class
- [Opportunity](../../components/agents/core/workflow_contracts.py#L121) — class
- [Approval](../../components/agents/core/workflow_contracts.py#L132) — class
- [Outcome](../../components/agents/core/workflow_contracts.py#L142) — class
- [visit](../../components/agents/core/workflow_contracts.py#L47) — function
- [validate](../../components/agents/core/workflow_contracts.py#L85) — function
- [to_json](../../components/agents/core/workflow_contracts.py#L99) — function
- [to_json](../../components/agents/core/workflow_contracts.py#L116) — function
- [to_json](../../components/agents/core/workflow_contracts.py#L150) — function

## core/workflow_experiment.py

[Open source](../../components/agents/core/workflow_experiment.py)

Imports __future__, collections, json, math, pathlib, platform, re, time, tracemalloc, .workflow_contracts, .workflow_store.

- [tokens](../../components/agents/core/workflow_experiment.py#L21) — function
- [run_experiment](../../components/agents/core/workflow_experiment.py#L25) — function
- [register_result](../../components/agents/core/workflow_experiment.py#L31) — function
- [score](../../components/agents/core/workflow_experiment.py#L80) — function

## core/workflow_health.py

[Open source](../../components/agents/core/workflow_health.py)

Imports __future__, errno, json, pathlib, shutil, socket, ssl, time, urllib.error, urllib.parse, urllib.request, ., .workflow_contracts, .workflow_broker.

- [ProbeNotPerformed](../../components/agents/core/workflow_health.py#L34) — class
- [classify](../../components/agents/core/workflow_health.py#L38) — function
- [inventory](../../components/agents/core/workflow_health.py#L67) — function
- [probe](../../components/agents/core/workflow_health.py#L87) — function
- [run_health](../../components/agents/core/workflow_health.py#L135) — function

## core/workflow_media.py

[Open source](../../components/agents/core/workflow_media.py)

Imports pathlib, json, shutil, subprocess, ..

- [executable](../../components/agents/core/workflow_media.py#L9) — function
- [inspect_video](../../components/agents/core/workflow_media.py#L24) — function

## core/workflow_service.py

[Open source](../../components/agents/core/workflow_service.py)

Imports __future__, json, time, ., .graph, .hitl, .store, .workflow_broker, .workflow_contracts, .workflow_store, .search, .mailer, .workflow_brain, .workflow_health, .workflow_experiment, agents.

- [WorkflowService](../../components/agents/core/workflow_service.py#L16) — class
- [ReviewResumer](../../components/agents/core/workflow_service.py#L311) — class
- [__init__](../../components/agents/core/workflow_service.py#L17) — function
- [create](../../components/agents/core/workflow_service.py#L22) — function
- [prepare](../../components/agents/core/workflow_service.py#L35) — function
- [accept_decision](../../components/agents/core/workflow_service.py#L105) — function
- [request_work](../../components/agents/core/workflow_service.py#L171) — function
- [request_diagnostics](../../components/agents/core/workflow_service.py#L185) — function
- [decide](../../components/agents/core/workflow_service.py#L194) — function
- [dispatch](../../components/agents/core/workflow_service.py#L205) — function
- [control](../../components/agents/core/workflow_service.py#L240) — function
- [dispatch_release](../../components/agents/core/workflow_service.py#L259) — function
- [record_outcome](../../components/agents/core/workflow_service.py#L279) — function
- [__init__](../../components/agents/core/workflow_service.py#L312) — function
- [resume](../../components/agents/core/workflow_service.py#L315) — function
- [guard](../../components/agents/core/workflow_service.py#L60) — function

## core/workflow_store.py

[Open source](../../components/agents/core/workflow_store.py)

Imports __future__, hashlib, json, pathlib, time, ., .store, .workflow_contracts.

- [Conflict](../../components/agents/core/workflow_store.py#L38) — class
- [WorkflowStore](../../components/agents/core/workflow_store.py#L42) — class
- [file_hash](../../components/agents/core/workflow_store.py#L260) — function
- [__init__](../../components/agents/core/workflow_store.py#L43) — function
- [decode](../../components/agents/core/workflow_store.py#L50) — function
- [get](../../components/agents/core/workflow_store.py#L59) — function
- [list](../../components/agents/core/workflow_store.py#L62) — function
- [create](../../components/agents/core/workflow_store.py#L66) — function
- [update](../../components/agents/core/workflow_store.py#L83) — function
- [control](../../components/agents/core/workflow_store.py#L119) — function
- [revise](../../components/agents/core/workflow_store.py#L135) — function
- [acquire](../../components/agents/core/workflow_store.py#L157) — function
- [release](../../components/agents/core/workflow_store.py#L166) — function
- [register_artifact](../../components/agents/core/workflow_store.py#L169) — function
- [artifact](../../components/agents/core/workflow_store.py#L191) — function
- [verify_artifacts](../../components/agents/core/workflow_store.py#L198) — function
- [backup_task](../../components/agents/core/workflow_store.py#L211) — function
- [redact_task](../../components/agents/core/workflow_store.py#L221) — function — Erase task-owned payloads, retaining replay-prevention tombstones.

## core/yamlite.py

[Open source](../../components/agents/core/yamlite.py)

Imports __future__, re, typing.

- [YamlError](../../components/agents/core/yamlite.py#L24) — class
- [_unescape](../../components/agents/core/yamlite.py#L43) — function
- [parse_scalar](../../components/agents/core/yamlite.py#L64) — function
- [_split_flow](../../components/agents/core/yamlite.py#L91) — function
- [_parse_flow](../../components/agents/core/yamlite.py#L120) — function
- [_split_key](../../components/agents/core/yamlite.py#L139) — function — Split 'key: value' honouring quotes and URLs like http://x.
- [_strip_comment](../../components/agents/core/yamlite.py#L159) — function
- [_Line](../../components/agents/core/yamlite.py#L177) — class
- [_tokenize](../../components/agents/core/yamlite.py#L187) — function
- [_block_scalar](../../components/agents/core/yamlite.py#L200) — function
- [_parse_block](../../components/agents/core/yamlite.py#L245) — function
- [_parse_seq](../../components/agents/core/yamlite.py#L256) — function
- [_normalise_indent](../../components/agents/core/yamlite.py#L296) — function
- [_parse_map](../../components/agents/core/yamlite.py#L303) — function
- [load_yaml](../../components/agents/core/yamlite.py#L339) — function
- [_fmt_scalar](../../components/agents/core/yamlite.py#L356) — function
- [_block_header](../../components/agents/core/yamlite.py#L374) — function — Pick the right chomping indicator so a block scalar round-trips.
- [dump_yaml](../../components/agents/core/yamlite.py#L389) — function
- [__init__](../../components/agents/core/yamlite.py#L25) — function
- [__init__](../../components/agents/core/yamlite.py#L180) — function
- [__repr__](../../components/agents/core/yamlite.py#L183) — function

## run.py

[Open source](../../components/agents/run.py)

Imports __future__, argparse, json, pathlib, sys, textwrap, time, core, core.log, core.store, core.mailer, core.oauth, agents.fullstack_sales.packages, agents.saas_sales, core.toolbelt, agents.video_client.quote, agents.job_hunter, core.search, agents.job_hunter.resume, core.gmail.

- [_store](../../components/agents/run.py#L51) — function
- [_banner](../../components/agents/run.py#L56) — function
- [cmd_doctor](../../components/agents/run.py#L61) — function
- [cmd_auth](../../components/agents/run.py#L441) — function
- [cmd_serve](../../components/agents/run.py#L453) — function
- [cmd_run](../../components/agents/run.py#L488) — function
- [_process_inbox](../../components/agents/run.py#L517) — function
- [cmd_inbox](../../components/agents/run.py#L522) — function
- [cmd_watch](../../components/agents/run.py#L534) — function
- [cmd_approvals](../../components/agents/run.py#L545) — function
- [_decide](../../components/agents/run.py#L570) — function
- [cmd_approve](../../components/agents/run.py#L592) — function
- [cmd_reject](../../components/agents/run.py#L596) — function
- [cmd_leads](../../components/agents/run.py#L600) — function
- [cmd_suppress](../../components/agents/run.py#L618) — function
- [cmd_graph](../../components/agents/run.py#L630) — function
- [cmd_test](../../components/agents/run.py#L639) — function
- [cmd_telegram](../../components/agents/run.py#L644) — function — Run the Telegram bot: control all four agents from your phone.
- [_demo_env](../../components/agents/run.py#L667) — function — Hard-wire everything to safe, offline, fixture-backed settings.
- [_demo_reset](../../components/agents/run.py#L702) — function
- [_demo_jobs](../../components/agents/run.py#L713) — function
- [_demo_outreach](../../components/agents/run.py#L793) — function — Run an outreach agent against local stand-in websites.
- [cmd_demo](../../components/agents/run.py#L893) — function — A safe, zero-configuration demonstration of every agent.
- [cmd_sponsors](../../components/agents/run.py#L941) — function — Build a contact sheet for the whole sponsor list.
- [cmd_discover](../../components/agents/run.py#L1023) — function — Run the sponsorship agent with its web sweep forced on.
- [cmd_apply](../../components/agents/run.py#L1054) — function
- [cmd_book](../../components/agents/run.py#L1062) — function
- [cmd_schedule](../../components/agents/run.py#L1069) — function — Simple built-in loop, for when you do not want cron.
- [cmd_workflow](../../components/agents/run.py#L1119) — function
- [main](../../components/agents/run.py#L1144) — function
- [check](../../components/agents/run.py#L67) — function
- [on_push](../../components/agents/run.py#L463) — function
- [one](../../components/agents/run.py#L971) — function

## scripts/audit_project.py

[Open source](../../components/agents/scripts/audit_project.py)

Imports pathlib, ast, hashlib, json.

- [main](../../components/agents/scripts/audit_project.py#L16) — function

## scripts/benchmark_local.py

[Open source](../../components/agents/scripts/benchmark_local.py)

Imports __future__, argparse, json, pathlib, time, urllib.request.

- [call](../../components/agents/scripts/benchmark_local.py#L11) — function
- [main](../../components/agents/scripts/benchmark_local.py#L18) — function

## scripts/check_workflow_receivers.py

[Open source](../../components/agents/scripts/check_workflow_receivers.py)

Imports json, pathlib, time, urllib.request, urllib.error.


## scripts/configure_laptop.py

[Open source](../../components/agents/scripts/configure_laptop.py)

Imports pathlib, json, re, secrets.

- [main](../../components/agents/scripts/configure_laptop.py#L23) — function

## scripts/record_internal_acceptance.py

[Open source](../../components/agents/scripts/record_internal_acceptance.py)

Imports datetime, json, os, pathlib, sys, core, core.store, core.workflow_service, core.workflow_store.

- [main](../../components/agents/scripts/record_internal_acceptance.py#L16) — function

## scripts/run_tests.py

[Open source](../../components/agents/scripts/run_tests.py)

Imports __future__, argparse, io, ipaddress, json, os, pathlib, sys, tempfile, unittest, platform, datetime, re, core.

- [local_only](../../components/agents/scripts/run_tests.py#L26) — function
- [main](../../components/agents/scripts/run_tests.py#L41) — function

## scripts/smoke_local.py

[Open source](../../components/agents/scripts/smoke_local.py)

Imports pathlib, importlib, argparse, json, os, sys, tempfile, time, scripts.run_tests, tests.base, tests.fakes.servers, core.llm.

- [main](../../components/agents/scripts/smoke_local.py#L22) — function
- [decide](../../components/agents/scripts/smoke_local.py#L61) — function

## scripts/smoke_tools.py

[Open source](../../components/agents/scripts/smoke_tools.py)

Imports pathlib, json, os, sys, tempfile, scripts.run_tests, tests.base, core.toolbelt, core.llm.

- [main](../../components/agents/scripts/smoke_tools.py#L15) — function

## scripts/start_workflow_adapters.py

[Open source](../../components/agents/scripts/start_workflow_adapters.py)

Imports json, os, pathlib, secrets, subprocess, sys, time, urllib.request.

- [main](../../components/agents/scripts/start_workflow_adapters.py#L19) — function
- [ready](../../components/agents/scripts/start_workflow_adapters.py#L32) — function

## scripts/storylens_server.py

[Open source](../../components/agents/scripts/storylens_server.py)

Imports __future__, argparse, os, pathlib, sys, server.app.

- [main](../../components/agents/scripts/storylens_server.py#L10) — function

## scripts/validate_documents.py

[Open source](../../components/agents/scripts/validate_documents.py)

Imports pathlib, json, os, sys, core, agents.video_client, agents.video_client.quote, agents.job_hunter, agents.job_hunter.discovery, core.llm.

- [main](../../components/agents/scripts/validate_documents.py#L15) — function

## scripts/verify_integrated_workflows.py

[Open source](../../components/agents/scripts/verify_integrated_workflows.py)

Imports json, os, pathlib, sys, time, datetime, core, core.store, core.workflow_service, core.workflow_store.

- [main](../../components/agents/scripts/verify_integrated_workflows.py#L13) — function
- [prepare](../../components/agents/scripts/verify_integrated_workflows.py#L25) — function
- [approve](../../components/agents/scripts/verify_integrated_workflows.py#L31) — function
- [receive](../../components/agents/scripts/verify_integrated_workflows.py#L33) — function

## scripts/verify_real_delivery.py

[Open source](../../components/agents/scripts/verify_real_delivery.py)

Imports argparse, json, os, pathlib, secrets, sys, threading, time, urllib.request, core, core.store, core.workflow_service, server.app.

- [main](../../components/agents/scripts/verify_real_delivery.py#L20) — function
- [request](../../components/agents/scripts/verify_real_delivery.py#L49) — function
- [action](../../components/agents/scripts/verify_real_delivery.py#L54) — function
- [run_received](../../components/agents/scripts/verify_real_delivery.py#L56) — function

## scripts/verify_receiver_restart.py

[Open source](../../components/agents/scripts/verify_receiver_restart.py)

Imports hashlib, json, os, pathlib, sqlite3, sys, datetime, core.workflow_broker, core.

- [main](../../components/agents/scripts/verify_receiver_restart.py#L16) — function

## scripts/verify_release_draft.py

[Open source](../../components/agents/scripts/verify_release_draft.py)

Imports json, os, pathlib, sys, time, core, core.store, core.workflow_service, core.hitl.


## scripts/verify_workflow_brain.py

[Open source](../../components/agents/scripts/verify_workflow_brain.py)

Imports argparse, json, os, pathlib, sys, time, core, core.store, core.workflow_service.

- [main](../../components/agents/scripts/verify_workflow_brain.py#L13) — function

## scripts/verify_workflows_live.py

[Open source](../../components/agents/scripts/verify_workflows_live.py)

Imports __future__, argparse, json, os, pathlib, sys, threading, time, urllib.error, urllib.request, core, core.store, core.workflow_service, server.app, scripts.workflow_fixtures, core.workflow_media.

- [main](../../components/agents/scripts/verify_workflows_live.py#L22) — function
- [request](../../components/agents/scripts/verify_workflows_live.py#L56) — function
- [check](../../components/agents/scripts/verify_workflows_live.py#L62) — function
- [create](../../components/agents/scripts/verify_workflows_live.py#L66) — function

## scripts/workflow_fixtures.py

[Open source](../../components/agents/scripts/workflow_fixtures.py)

Imports pathlib, subprocess, core.workflow_media.

- [video](../../components/agents/scripts/workflow_fixtures.py#L7) — function

## scripts/write_workflow_acceptance_report.py

[Open source](../../components/agents/scripts/write_workflow_acceptance_report.py)

Imports datetime, json, pathlib, shutil, sqlite3.

- [read](../../components/agents/scripts/write_workflow_acceptance_report.py#L12) — function
- [main](../../components/agents/scripts/write_workflow_acceptance_report.py#L16) — function

## server/__init__.py

[Open source](../../components/agents/server/__init__.py)


## server/app.py

[Open source](../../components/agents/server/app.py)

Imports __future__, html, json, pathlib, re, threading, time, urllib.parse, http.server, core, core.hitl, core.log, core.mailer, core.registry, core.store, server, server.storylens, server.workflows, core.delivery, core.lessons.

- [esc](../../components/agents/server/app.py#L87) — function
- [page](../../components/agents/server/app.py#L91) — function
- [ago](../../components/agents/server/app.py#L98) — function
- [Handler](../../components/agents/server/app.py#L106) — class
- [DashboardServer](../../components/agents/server/app.py#L790) — class
- [serve](../../components/agents/server/app.py#L808) — function
- [store](../../components/agents/server/app.py#L112) — function
- [queue](../../components/agents/server/app.py#L116) — function
- [log_message](../../components/agents/server/app.py#L119) — function
- [_send](../../components/agents/server/app.py#L123) — function
- [_json](../../components/agents/server/app.py#L137) — function
- [_redirect](../../components/agents/server/app.py#L140) — function
- [_body](../../components/agents/server/app.py#L143) — function
- [_form](../../components/agents/server/app.py#L147) — function
- [_authorised](../../components/agents/server/app.py#L157) — function
- [do_GET](../../components/agents/server/app.py#L167) — function
- [do_POST](../../components/agents/server/app.py#L208) — function
- [_token_qs](../../components/agents/server/app.py#L243) — function
- [_counts](../../components/agents/server/app.py#L248) — function — How many cards each agent is holding, for the rail.
- [_rail](../../components/agents/server/app.py#L262) — function
- [_overview](../../components/agents/server/app.py#L266) — function — Everything, across all five. The page he lands on.
- [_demo_note](../../components/agents/server/app.py#L315) — function
- [_agent_page](../../components/agents/server/app.py#L322) — function
- [_agent_state](../../components/agents/server/app.py#L395) — function
- [_run_box](../../components/agents/server/app.py#L410) — function
- [_run_status](../../components/agents/server/app.py#L420) — function
- [_run_agent](../../components/agents/server/app.py#L439) — function — Start an agent in the background and come straight back.
- [_start_agent](../../components/agents/server/app.py#L454) — function
- [_preview](../../components/agents/server/app.py#L491) — function
- [_approval_detail](../../components/agents/server/app.py#L494) — function
- [_context_block](../../components/agents/server/app.py#L607) — function — Why this target, in his words rather than the model's JSON.
- [_decide](../../components/agents/server/app.py#L636) — function
- [_api_state](../../components/agents/server/app.py#L695) — function
- [_serve_attachment](../../components/agents/server/app.py#L710) — function
- [_serve_resume](../../components/agents/server/app.py#L726) — function
- [_gmail_push](../../components/agents/server/app.py#L742) — function — Pub/Sub push. Acknowledge fast; the delta fetch happens inline.
- [_unsubscribe_page](../../components/agents/server/app.py#L767) — function
- [_unsubscribe_post](../../components/agents/server/app.py#L781) — function
- [__init__](../../components/agents/server/app.py#L794) — function
- [work](../../components/agents/server/app.py#L471) — function

## server/bot.py

[Open source](../../components/agents/server/bot.py)

Imports __future__, json, os, pathlib, re, threading, time, traceback, core, core.hitl, core.log, core.store, core.telegram, core.lessons, agents.sponsorship, core.search, collections, agents.sponsorship.brain, agents.job_hunter.agent, agents.job_hunter.

- [_persist_env](../../components/agents/server/bot.py#L107) — function — Change a setting for this process AND for the next restart.
- [_fmt_age](../../components/agents/server/bot.py#L137) — function
- [Bot](../../components/agents/server/bot.py#L148) — class
- [get_bot](../../components/agents/server/bot.py#L1497) — function
- [notify](../../components/agents/server/bot.py#L1504) — function
- [main](../../components/agents/server/bot.py#L1512) — function
- [__init__](../../components/agents/server/bot.py#L149) — function
- [join_workers](../../components/agents/server/bot.py#L157) — function — Wait for background work - resuming a graph, running an agent.
- [_get](../../components/agents/server/bot.py#L165) — function
- [_set](../../components/agents/server/bot.py#L169) — function
- [chat_id](../../components/agents/server/bot.py#L173) — function
- [topics](../../components/agents/server/bot.py#L177) — function
- [owner_id](../../components/agents/server/bot.py#L181) — function
- [topic_for](../../components/agents/server/bot.py#L191) — function — The thread id for an agent's topic, or None to post in the group.
- [say](../../components/agents/server/bot.py#L195) — function
- [send_file](../../components/agents/server/bot.py#L214) — function
- [setup](../../components/agents/server/bot.py#L229) — function — Bind this chat and create one topic per agent.
- [authorised](../../components/agents/server/bot.py#L284) — function
- [handle](../../components/agents/server/bot.py#L291) — function
- [_handle_message](../../components/agents/server/bot.py#L304) — function
- [_reply](../../components/agents/server/bot.py#L320) — function
- [cmd_help](../../components/agents/server/bot.py#L325) — function
- [cmd_id](../../components/agents/server/bot.py#L333) — function
- [cmd_status](../../components/agents/server/bot.py#L339) — function
- [cmd_learned](../../components/agents/server/bot.py#L373) — function — The rules each agent now follows, and where each came from.
- [cmd_pending](../../components/agents/server/bot.py#L407) — function
- [cmd_run](../../components/agents/server/bot.py#L417) — function
- [pending_for](../../components/agents/server/bot.py#L447) — function — Cards waiting on a decision. A stranded card stops its whole run.
- [_run_agent](../../components/agents/server/bot.py#L458) — function
- [cmd_jobs](../../components/agents/server/bot.py#L513) — function
- [cmd_leads](../../components/agents/server/bot.py#L541) — function
- [cmd_brands](../../components/agents/server/bot.py#L557) — function — Where the sponsorship list stands: done, waiting, and what is next.
- [cmd_discover](../../components/agents/server/bot.py#L623) — function — Run the sponsorship agent with the web sweep forced on.
- [cmd_learned](../../components/agents/server/bot.py#L650) — function — What your decisions have taught it.
- [cmd_why](../../components/agents/server/bot.py#L695) — function — Show the arithmetic behind one prospect's score.
- [cmd_mediakit](../../components/agents/server/bot.py#L735) — function — What is still blank in creator.yaml, and what it costs you.
- [cmd_resume](../../components/agents/server/bot.py#L775) — function
- [cmd_exp](../../components/agents/server/bot.py#L789) — function — Your years of experience. Everything above it is filtered out.
- [cmd_roles](../../components/agents/server/bot.py#L816) — function
- [cmd_doctor](../../components/agents/server/bot.py#L842) — function
- [approval_text](../../components/agents/server/bot.py#L858) — function
- [launch_text](../../components/agents/server/bot.py#L885) — function — A launch card. The stage and any blocked claim come first.
- [client_text](../../components/agents/server/bot.py#L930) — function — A freelance gig card. What it is, who they are, and what it is worth.
- [job_text](../../components/agents/server/bot.py#L980) — function — A job card built to be decided on from a phone, in ten seconds.
- [prospect_text](../../components/agents/server/bot.py#L1038) — function — A brand the agent found on the web, and why it thinks you want it.
- [brand_text](../../components/agents/server/bot.py#L1082) — function — A sponsorship card you can decide on from a phone.
- [approval_buttons](../../components/agents/server/bot.py#L1152) — function
- [post_approval](../../components/agents/server/bot.py#L1205) — function — Put one approval in its agent's topic. Never posts the same one twice.
- [push_pending](../../components/agents/server/bot.py#L1227) — function — Post anything new that is waiting. Called on a timer.
- [_ack](../../components/agents/server/bot.py#L1237) — function — Stop the button spinner immediately.
- [_handle_callback](../../components/agents/server/bot.py#L1249) — function
- [_freeze](../../components/agents/server/bot.py#L1318) — function — Replace the buttons with the outcome so it cannot be tapped twice.
- [post_handoffs](../../components/agents/server/bot.py#L1329) — function — Post the messages that need your hand, once each.
- [handoff_text](../../components/agents/server/bot.py#L1354) — function
- [handoff_buttons](../../components/agents/server/bot.py#L1371) — function
- [finished_text](../../components/agents/server/bot.py#L1390) — function — Why the cards stopped coming.
- [_resume](../../components/agents/server/bot.py#L1413) — function
- [poll_once](../../components/agents/server/bot.py#L1440) — function
- [run_forever](../../components/agents/server/bot.py#L1448) — function
- [stop](../../components/agents/server/bot.py#L1487) — function

## server/console.py

[Open source](../../components/agents/server/console.py)

Imports __future__, html, json, re, time, core, urllib.parse.

- [agent_meta](../../components/agents/server/console.py#L94) — function
- [home_for](../../components/agents/server/console.py#L98) — function — Which of the five pages a card with this agent name belongs on.
- [display_name](../../components/agents/server/console.py#L106) — function
- [demo_mode](../../components/agents/server/console.py#L119) — function
- [redact](../../components/agents/server/console.py#L123) — function — Blank out anything that identifies him or lets you act as him.
- [esc](../../components/agents/server/console.py#L139) — function
- [ago](../../components/agents/server/console.py#L146) — function
- [money](../../components/agents/server/console.py#L154) — function
- [shell](../../components/agents/server/console.py#L403) — function — One page. Rail on the left, whatever you asked for on the right.
- [rail](../../components/agents/server/console.py#L421) — function
- [preview](../../components/agents/server/console.py#L477) — function — The two or three lines that tell you what this card is, at a glance.
- [pending_card](../../components/agents/server/console.py#L533) — function
- [how_it_works](../../components/agents/server/console.py#L555) — function — Three steps, for whoever is looking at this for the first time.
- [empty](../../components/agents/server/console.py#L563) — function
- [lessons_block](../../components/agents/server/console.py#L570) — function
- [brain_block](../../components/agents/server/console.py#L589) — function — The scoring, as bars. The point is that the evidence is visible.
- [history_table](../../components/agents/server/console.py#L624) — function
- [verbs](../../components/agents/server/console.py#L654) — function
- [_digits](../../components/agents/server/console.py#L665) — function
- [handoff_links](../../components/agents/server/console.py#L669) — function — Open the message somewhere he can send it himself.
- [bar](../../components/agents/server/console.py#L600) — function

## server/storylens.py

[Open source](../../components/agents/server/storylens.py)

Imports __future__, hmac, json, pathlib, core, core.llm, core.workflow_brain, server, agents.saas_sales, agents.saas_sales.research.

- [_authorised](../../components/agents/server/storylens.py#L23) — function
- [_codex_installed](../../components/agents/server/storylens.py#L38) — function
- [_connection](../../components/agents/server/storylens.py#L46) — function
- [_local_ready](../../components/agents/server/storylens.py#L53) — function
- [_connections](../../components/agents/server/storylens.py#L61) — function
- [_product_status](../../components/agents/server/storylens.py#L104) — function
- [status](../../components/agents/server/storylens.py#L128) — function
- [run](../../components/agents/server/storylens.py#L156) — function

## server/workflows.py

[Open source](../../components/agents/server/workflows.py)

Imports __future__, json, re, time, urllib.parse, core, core.workflow_contracts, core.workflow_service, core.workflow_store, server, pathlib, core.workflow_brain, agents.saas_sales.research, core.search, threading, core.hitl.

- [render_payload](../../components/agents/server/workflows.py#L16) — function — Show reviewable content first; keep contract internals in disclosure.
- [WorkflowViews](../../components/agents/server/workflows.py#L75) — class
- [__init__](../../components/agents/server/workflows.py#L76) — function
- [respond](../../components/agents/server/workflows.py#L82) — function
- [get](../../components/agents/server/workflows.py#L87) — function
- [artifact](../../components/agents/server/workflows.py#L105) — function
- [post](../../components/agents/server/workflows.py#L148) — function
- [home](../../components/agents/server/workflows.py#L255) — function
- [saas_forms](../../components/agents/server/workflows.py#L306) — function
- [detail](../../components/agents/server/workflows.py#L338) — function
- [saas_handoff](../../components/agents/server/workflows.py#L405) — function

## tests/__init__.py

[Open source](../../components/agents/tests/__init__.py)


## tests/base.py

[Open source](../../components/agents/tests/base.py)

Imports __future__, os, pathlib, shutil, sys, tempfile, unittest, core.config, logging, core.store, core.hitl, core.llm, core.notify, contextlib, core.crawler, core.ratelimit, server.bot.

- [SuiteCase](../../components/agents/tests/base.py#L58) — class — Base case: a private temp directory, clean env, fresh singletons.
- [setUp](../../components/agents/tests/base.py#L63) — function
- [tearDown](../../components/agents/tests/base.py#L93) — function
- [_reset_singletons](../../components/agents/tests/base.py#L104) — function
- [env](../../components/agents/tests/base.py#L118) — function — Temporarily set environment variables inside a `with` block.
- [offline_llm](../../components/agents/tests/base.py#L142) — function
- [fast_crawler](../../components/agents/tests/base.py#L146) — function
- [drive](../../components/agents/tests/base.py#L151) — function — Run a graph to completion, calling `decide(payload)` at each gate.
- [_ctx](../../components/agents/tests/base.py#L124) — function

## tests/fakes/__init__.py

[Open source](../../components/agents/tests/fakes/__init__.py)


## tests/fakes/servers.py

[Open source](../../components/agents/tests/fakes/servers.py)

Imports __future__, base64, email, email.policy, json, re, socket, threading, time, urllib.parse, http.server.

- [_patched_getaddrinfo](../../components/agents/tests/fakes/servers.py#L33) — function — Resolve the fake domains to loopback, for this process only.
- [install_dns_override](../../components/agents/tests/fakes/servers.py#L49) — function
- [remove_dns_override](../../components/agents/tests/fakes/servers.py#L57) — function
- [_free_port](../../components/agents/tests/fakes/servers.py#L66) — function
- [_Base](../../components/agents/tests/fakes/servers.py#L72) — class
- [BaseFake](../../components/agents/tests/fakes/servers.py#L77) — class
- [_HTTPHandler](../../components/agents/tests/fakes/servers.py#L122) — class
- [_site_page](../../components/agents/tests/fakes/servers.py#L152) — function
- [register_default_sites](../../components/agents/tests/fakes/servers.py#L157) — function
- [_WebHandler](../../components/agents/tests/fakes/servers.py#L241) — class — Routes by the Host header, exactly like a real virtual-host web server.
- [FakeWebServer](../../components/agents/tests/fakes/servers.py#L270) — class — Serves the fake prospect sites on their real-looking hostnames.
- [_b64](../../components/agents/tests/fakes/servers.py#L298) — function
- [_GoogleState](../../components/agents/tests/fakes/servers.py#L302) — class — In-memory Gmail mailbox with a real history log.
- [_GoogleHandler](../../components/agents/tests/fakes/servers.py#L357) — class
- [FakeGoogleServer](../../components/agents/tests/fakes/servers.py#L471) — class
- [_AnthropicHandler](../../components/agents/tests/fakes/servers.py#L500) — class
- [FakeAnthropicServer](../../components/agents/tests/fakes/servers.py#L523) — class
- [FakeSMTPServer](../../components/agents/tests/fakes/servers.py#L534) — class — A minimal SMTP server that accepts mail and records it.
- [_TelegramState](../../components/agents/tests/fakes/servers.py#L643) — class — Everything the fake Bot API remembers, so a test can assert on it.
- [_TelegramHandler](../../components/agents/tests/fakes/servers.py#L707) — class
- [_TgFail](../../components/agents/tests/fakes/servers.py#L808) — class
- [_parse_multipart](../../components/agents/tests/fakes/servers.py#L814) — function — Pull fields and the uploaded file out of a multipart body.
- [FakeTelegramServer](../../components/agents/tests/fakes/servers.py#L835) — class
- [__init__](../../components/agents/tests/fakes/servers.py#L80) — function
- [url](../../components/agents/tests/fakes/servers.py#L87) — function
- [_make_handler](../../components/agents/tests/fakes/servers.py#L90) — function
- [start](../../components/agents/tests/fakes/servers.py#L101) — function
- [stop](../../components/agents/tests/fakes/servers.py#L111) — function
- [__enter__](../../components/agents/tests/fakes/servers.py#L115) — function
- [__exit__](../../components/agents/tests/fakes/servers.py#L118) — function
- [_read_body](../../components/agents/tests/fakes/servers.py#L125) — function
- [_send](../../components/agents/tests/fakes/servers.py#L129) — function
- [_json](../../components/agents/tests/fakes/servers.py#L139) — function
- [_record](../../components/agents/tests/fakes/servers.py#L142) — function
- [do_GET](../../components/agents/tests/fakes/servers.py#L248) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L279) — function
- [start](../../components/agents/tests/fakes/servers.py#L283) — function
- [stop](../../components/agents/tests/fakes/servers.py#L287) — function
- [site_url](../../components/agents/tests/fakes/servers.py#L291) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L305) — function
- [deliver](../../components/agents/tests/fakes/servers.py#L316) — function
- [_auth_ok](../../components/agents/tests/fakes/servers.py#L358) — function
- [do_POST](../../components/agents/tests/fakes/servers.py#L362) — function
- [do_GET](../../components/agents/tests/fakes/servers.py#L438) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L474) — function
- [state](../../components/agents/tests/fakes/servers.py#L481) — function
- [gmail_base](../../components/agents/tests/fakes/servers.py#L485) — function
- [calendar_base](../../components/agents/tests/fakes/servers.py#L489) — function
- [token_uri](../../components/agents/tests/fakes/servers.py#L493) — function
- [do_POST](../../components/agents/tests/fakes/servers.py#L501) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L526) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L537) — function
- [start](../../components/agents/tests/fakes/servers.py#L548) — function
- [stop](../../components/agents/tests/fakes/servers.py#L552) — function
- [__enter__](../../components/agents/tests/fakes/servers.py#L559) — function
- [__exit__](../../components/agents/tests/fakes/servers.py#L562) — function
- [_serve](../../components/agents/tests/fakes/servers.py#L565) — function
- [_session](../../components/agents/tests/fakes/servers.py#L574) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L646) — function
- [queue_command](../../components/agents/tests/fakes/servers.py#L663) — function — Simulate the user typing a message to the bot.
- [queue_button](../../components/agents/tests/fakes/servers.py#L681) — function — Simulate the user tapping an inline button.
- [texts](../../components/agents/tests/fakes/servers.py#L697) — function
- [last_text](../../components/agents/tests/fakes/servers.py#L700) — function
- [do_POST](../../components/agents/tests/fakes/servers.py#L708) — function
- [m_getMe](../../components/agents/tests/fakes/servers.py#L743) — function
- [m_setMyCommands](../../components/agents/tests/fakes/servers.py#L746) — function
- [m_deleteWebhook](../../components/agents/tests/fakes/servers.py#L750) — function
- [m_getChat](../../components/agents/tests/fakes/servers.py#L753) — function
- [m_getUpdates](../../components/agents/tests/fakes/servers.py#L757) — function
- [m_sendMessage](../../components/agents/tests/fakes/servers.py#L767) — function
- [m_editMessageText](../../components/agents/tests/fakes/servers.py#L778) — function
- [m_answerCallbackQuery](../../components/agents/tests/fakes/servers.py#L782) — function
- [m_sendDocument](../../components/agents/tests/fakes/servers.py#L786) — function
- [m_createForumTopic](../../components/agents/tests/fakes/servers.py#L795) — function
- [m_editForumTopic](../../components/agents/tests/fakes/servers.py#L804) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L809) — function
- [__init__](../../components/agents/tests/fakes/servers.py#L838) — function
- [state](../../components/agents/tests/fakes/servers.py#L845) — function
- [token](../../components/agents/tests/fakes/servers.py#L849) — function
- [Handler](../../components/agents/tests/fakes/servers.py#L93) — class
- [say](../../components/agents/tests/fakes/servers.py#L577) — function
- [log_message](../../components/agents/tests/fakes/servers.py#L96) — function

## tests/test_agents.py

[Open source](../../components/agents/tests/test_agents.py)

Imports __future__, json, pathlib, unittest, tests.base, tests.fakes.servers, agents.sponsorship.agent, os, agents.video_client.agent, core.crawler, agents.video_client.quote, agents.fullstack_sales.agent, agents.fullstack_sales.pricing, agents.job_hunter.agent, agents.job_hunter.discovery, agents.job_hunter.resume, core.oauth, core.calendar, datetime, core.mailer.

- [OutreachCase](../../components/agents/tests/test_agents.py#L12) — class
- [TestSponsorshipAgent](../../components/agents/tests/test_agents.py#L27) — class
- [TestVideoClientAgent](../../components/agents/tests/test_agents.py#L157) — class
- [TestFullstackSales](../../components/agents/tests/test_agents.py#L207) — class
- [TestJobHunter](../../components/agents/tests/test_agents.py#L276) — class
- [TestResumeTracks](../../components/agents/tests/test_agents.py#L351) — class — Software and video are different careers and must not be mixed.
- [TestInterviewScheduling](../../components/agents/tests/test_agents.py#L425) — class
- [TestReplyHandling](../../components/agents/tests/test_agents.py#L485) — class
- [TestJobBrain](../../components/agents/tests/test_agents.py#L552) — class — The job hunter learns from every decision, without disturbing the other.
- [TestVideoQuoting](../../components/agents/tests/test_agents.py#L602) — class — Every number that reaches a client comes off the rate card, and the
- [TestVideoPitchHygiene](../../components/agents/tests/test_agents.py#L678) — class — What must never reach a client.
- [TestVideoChase](../../components/agents/tests/test_agents.py#L716) — class — Most freelance work is lost to silence, not to a no.
- [TestDealBrain](../../components/agents/tests/test_agents.py#L742) — class — Money outweighs opinion, and the three brains stay apart.
- [TestTheLoopCloses](../../components/agents/tests/test_agents.py#L778) — class — A rejection must change the NEXT draft, for a different target.
- [TestDevClientSourcing](../../components/agents/tests/test_agents.py#L859) — class — A client who wants work done, not an employer hiring staff.
- [TestDevPackages](../../components/agents/tests/test_agents.py#L903) — class — Payments work is priced as packages, and the floor is absolute.
- [TestDevBrief](../../components/agents/tests/test_agents.py#L968) — class — What the model is told, and what it is never allowed to put in.
- [TestDevBrain](../../components/agents/tests/test_agents.py#L1014) — class — Money outweighs opinion, and four brains stay apart.
- [TestProductStageGate](../../components/agents/tests/test_agents.py#L1050) — class — The product does not exist yet, so most claims are simply not available.
- [TestLaunchAudiences](../../components/agents/tests/test_agents.py#L1123) — class — Four audiences want four different things.
- [TestCompetitorGuard](../../components/agents/tests/test_agents.py#L1162) — class — Telling a competing plugin what is coming is not outreach.
- [setUp](../../components/agents/tests/test_agents.py#L13) — function
- [tearDown](../../components/agents/tests/test_agents.py#L17) — function
- [agent](../../components/agents/tests/test_agents.py#L21) — function
- [test_full_run](../../components/agents/tests/test_agents.py#L28) — function
- [test_a_brand_with_no_address_still_produces_a_message](../../components/agents/tests/test_agents.py#L54) — function — The old behaviour filed these as manual_followup with nothing
- [test_nothing_is_emailed_on_the_whatsapp_route](../../components/agents/tests/test_agents.py#L75) — function — A handoff must not also fire an email - that would double-contact.
- [test_real_money_gaming_brands_are_refused](../../components/agents/tests/test_agents.py#L85) — function — India banned real-money gaming in 2025. Promoting one is the
- [test_the_card_carries_every_channel](../../components/agents/tests/test_agents.py#L102) — function
- [test_tier_one_targets_are_worked_first](../../components/agents/tests/test_agents.py#L121) — function
- [test_domains_are_not_contacted_twice](../../components/agents/tests/test_agents.py#L129) — function
- [test_rejected_draft_sends_nothing](../../components/agents/tests/test_agents.py#L138) — function
- [test_operator_edits_are_what_get_sent](../../components/agents/tests/test_agents.py#L145) — function
- [test_targets_a_creator_who_needs_an_editor](../../components/agents/tests/test_agents.py#L158) — function
- [test_qualifier_reads_the_need_signal](../../components/agents/tests/test_agents.py#L166) — function
- [test_rate_card_drives_pricing_answers](../../components/agents/tests/test_agents.py#L174) — function
- [test_an_indian_client_is_answered_in_rupees](../../components/agents/tests/test_agents.py#L185) — function
- [test_missing_rate_card_refuses_to_invent_a_price](../../components/agents/tests/test_agents.py#L196) — function
- [test_outreach_flags_a_dated_stack](../../components/agents/tests/test_agents.py#L208) — function
- [_quote_msg](../../components/agents/tests/test_agents.py#L216) — function
- [test_quote_requires_approval_and_survives_restart](../../components/agents/tests/test_agents.py#L224) — function
- [test_operator_can_override_the_total](../../components/agents/tests/test_agents.py#L238) — function
- [test_rejected_quote_is_not_sent](../../components/agents/tests/test_agents.py#L249) — function
- [test_vague_request_does_not_produce_a_number](../../components/agents/tests/test_agents.py#L258) — function
- [test_pricing_is_deterministic](../../components/agents/tests/test_agents.py#L267) — function
- [hunter](../../components/agents/tests/test_agents.py#L277) — function
- [test_full_run_filters_scams_and_builds_resumes](../../components/agents/tests/test_agents.py#L281) — function — No fake posting may reach the approval queue.
- [test_resume_is_tailored_per_job](../../components/agents/tests/test_agents.py#L325) — function
- [test_jobs_are_not_reprocessed](../../components/agents/tests/test_agents.py#L339) — function
- [test_nothing_is_submitted_automatically](../../components/agents/tests/test_agents.py#L344) — function
- [test_both_shipped_profiles_are_clean](../../components/agents/tests/test_agents.py#L362) — function
- [test_a_leak_is_actually_detected](../../components/agents/tests/test_agents.py#L369) — function — The guard must be able to fail, or it is proving nothing.
- [test_a_software_resume_contains_no_video_words](../../components/agents/tests/test_agents.py#L380) — function
- [test_the_current_job_is_listed_first](../../components/agents/tests/test_agents.py#L394) — function — Never order jobs by keyword relevance - a recruiter reads top as now.
- [test_only_three_projects_reach_the_page](../../components/agents/tests/test_agents.py#L406) — function
- [test_the_resume_carries_his_real_details](../../components/agents/tests/test_agents.py#L416) — function
- [setUp](../../components/agents/tests/test_agents.py#L426) — function
- [tearDown](../../components/agents/tests/test_agents.py#L438) — function
- [scheduler](../../components/agents/tests/test_agents.py#L442) — function
- [test_detects_and_proposes_real_free_slots](../../components/agents/tests/test_agents.py#L449) — function
- [test_ignores_a_non_interview_message](../../components/agents/tests/test_agents.py#L466) — function
- [test_confirming_a_slot_creates_a_calendar_event](../../components/agents/tests/test_agents.py#L473) — function
- [reply_agent](../../components/agents/tests/test_agents.py#L486) — function
- [_msg](../../components/agents/tests/test_agents.py#L490) — function
- [test_interested_reply_alerts_and_drafts](../../components/agents/tests/test_agents.py#L498) — function
- [test_unsubscribe_is_honoured_immediately_without_an_llm](../../components/agents/tests/test_agents.py#L509) — function
- [test_hard_no_closes_the_lead_without_a_reply](../../components/agents/tests/test_agents.py#L517) — function
- [test_out_of_office_snoozes](../../components/agents/tests/test_agents.py#L523) — function
- [test_bounce_suppresses_and_warns_on_high_rate](../../components/agents/tests/test_agents.py#L529) — function
- [test_approved_reply_is_threaded](../../components/agents/tests/test_agents.py#L535) — function
- [_job](../../components/agents/tests/test_agents.py#L555) — function
- [test_an_approval_moves_the_score_on_the_first_example](../../components/agents/tests/test_agents.py#L564) — function
- [test_what_an_employer_did_outweighs_what_he_guessed](../../components/agents/tests/test_agents.py#L571) — function
- [test_bangalore_and_bengaluru_are_one_city](../../components/agents/tests/test_agents.py#L579) — function
- [test_job_evidence_does_not_leak_into_the_sponsorship_brain](../../components/agents/tests/test_agents.py#L587) — function
- [test_a_fraudulent_posting_is_the_strongest_negative](../../components/agents/tests/test_agents.py#L597) — function
- [q](../../components/agents/tests/test_agents.py#L608) — function
- [test_the_tier_is_read_from_what_they_asked_for](../../components/agents/tests/test_agents.py#L613) — function
- [test_a_stem_pattern_matches_the_word_it_is_a_stem_of](../../components/agents/tests/test_agents.py#L625) — function
- [test_indian_clients_are_quoted_in_rupees](../../components/agents/tests/test_agents.py#L634) — function
- [test_an_offer_below_the_floor_always_stops_for_him](../../components/agents/tests/test_agents.py#L639) — function
- [test_an_offer_above_the_floor_is_countered_not_simply_taken](../../components/agents/tests/test_agents.py#L645) — function
- [test_a_rush_job_raises_the_floor_with_the_ask](../../components/agents/tests/test_agents.py#L655) — function
- [test_no_rate_card_means_placeholder_and_never_a_number](../../components/agents/tests/test_agents.py#L660) — function
- [test_the_money_the_client_named_is_read_correctly](../../components/agents/tests/test_agents.py#L669) — function
- [test_markup_never_reaches_the_opening_line](../../components/agents/tests/test_agents.py#L686) — function
- [test_job_board_chrome_is_not_quoted_back_at_them](../../components/agents/tests/test_agents.py#L698) — function
- [test_the_four_client_types_get_different_openings](../../components/agents/tests/test_agents.py#L702) — function
- [test_the_first_email_never_carries_a_price](../../components/agents/tests/test_agents.py#L709) — function
- [test_three_touches_then_it_stops_for_good](../../components/agents/tests/test_agents.py#L721) — function
- [test_each_chase_says_something_new](../../components/agents/tests/test_agents.py#L728) — function
- [test_the_gaps_widen](../../components/agents/tests/test_agents.py#L735) — function
- [deal](../../components/agents/tests/test_agents.py#L745) — function
- [test_getting_paid_outweighs_everything_else](../../components/agents/tests/test_agents.py#L752) — function
- [test_the_market_is_read_from_the_location](../../components/agents/tests/test_agents.py#L758) — function
- [test_none_of_the_three_brains_can_see_each_other](../../components/agents/tests/test_agents.py#L765) — function
- [test_a_rejected_sentence_does_not_come_back](../../components/agents/tests/test_agents.py#L786) — function
- [test_the_video_brief_carries_the_rules_into_the_prompt](../../components/agents/tests/test_agents.py#L799) — function
- [test_no_price_ever_appears_in_the_video_brief](../../components/agents/tests/test_agents.py#L811) — function
- [test_the_prompts_reach_the_model_without_ragged_indentation](../../components/agents/tests/test_agents.py#L823) — function
- [test_the_job_read_is_honest_about_the_gap](../../components/agents/tests/test_agents.py#L846) — function
- [gig](../../components/agents/tests/test_agents.py#L862) — function
- [test_a_job_at_stripe_is_not_a_client_for_stripe_work](../../components/agents/tests/test_agents.py#L869) — function
- [test_someone_who_wants_their_checkout_fixed_is_a_client](../../components/agents/tests/test_agents.py#L880) — function
- [test_a_mechanical_engineer_is_a_different_profession](../../components/agents/tests/test_agents.py#L889) — function
- [test_a_title_only_posting_survives_to_be_read_later](../../components/agents/tests/test_agents.py#L895) — function
- [pkg](../../components/agents/tests/test_agents.py#L908) — function
- [test_the_right_package_is_chosen](../../components/agents/tests/test_agents.py#L913) — function
- [test_upi_autopay_is_not_priced_as_full_subscription_billing](../../components/agents/tests/test_agents.py#L924) — function
- [test_a_build_is_not_a_package](../../components/agents/tests/test_agents.py#L931) — function
- [test_indian_clients_are_priced_in_rupees](../../components/agents/tests/test_agents.py#L935) — function
- [test_urgent_work_raises_the_floor_with_the_ask](../../components/agents/tests/test_agents.py#L940) — function
- [test_below_the_floor_always_stops_for_him](../../components/agents/tests/test_agents.py#L946) — function
- [test_a_concession_comes_with_every_discount](../../components/agents/tests/test_agents.py#L951) — function
- [test_no_card_means_placeholder_not_a_number](../../components/agents/tests/test_agents.py#L958) — function
- [prompt](../../components/agents/tests/test_agents.py#L973) — function
- [test_the_price_never_enters_the_prompt](../../components/agents/tests/test_agents.py#L987) — function
- [test_broken_work_gets_the_fault_list_and_a_warning_against_guessing](../../components/agents/tests/test_agents.py#L993) — function
- [test_a_build_does_not_get_the_fault_list](../../components/agents/tests/test_agents.py#L999) — function
- [test_free_trial_work_is_refused_in_the_brief](../../components/agents/tests/test_agents.py#L1005) — function
- [test_no_ragged_indentation_reaches_the_model](../../components/agents/tests/test_agents.py#L1008) — function
- [deal](../../components/agents/tests/test_agents.py#L1017) — function
- [test_getting_paid_outweighs_everything](../../components/agents/tests/test_agents.py#L1024) — function
- [test_the_market_is_read_from_the_location](../../components/agents/tests/test_agents.py#L1032) — function
- [test_none_of_the_four_brains_can_see_each_other](../../components/agents/tests/test_agents.py#L1038) — function
- [setUp](../../components/agents/tests/test_agents.py#L1061) — function
- [check](../../components/agents/tests/test_agents.py#L1066) — function
- [test_a_price_is_blocked_while_it_is_being_built](../../components/agents/tests/test_agents.py#L1070) — function
- [test_a_trial_is_blocked_because_there_is_nothing_to_try](../../components/agents/tests/test_agents.py#L1073) — function
- [test_a_commission_is_blocked_because_it_cannot_be_paid](../../components/agents/tests/test_agents.py#L1076) — function
- [test_a_launch_date_is_refused_at_every_stage](../../components/agents/tests/test_agents.py#L1083) — function
- [test_invented_features_are_caught_even_as_word_stems](../../components/agents/tests/test_agents.py#L1088) — function
- [test_an_honest_message_passes_cleanly](../../components/agents/tests/test_agents.py#L1096) — function
- [test_the_agent_refuses_to_run_without_a_product_name](../../components/agents/tests/test_agents.py#L1102) — function
- [test_a_live_product_may_state_a_price_only_if_one_exists](../../components/agents/tests/test_agents.py#L1108) — function
- [prompt](../../components/agents/tests/test_agents.py#L1128) — function
- [test_each_audience_gets_a_different_brief](../../components/agents/tests/test_agents.py#L1136) — function
- [test_the_promoter_brief_does_not_lead_with_money](../../components/agents/tests/test_agents.py#L1140) — function
- [test_every_brief_says_the_product_is_unfinished](../../components/agents/tests/test_agents.py#L1145) — function
- [test_it_is_told_not_to_invent_a_differentiator](../../components/agents/tests/test_agents.py#L1149) — function
- [test_no_ragged_indentation_reaches_the_model](../../components/agents/tests/test_agents.py#L1152) — function
- [test_competing_tools_are_recognised](../../components/agents/tests/test_agents.py#L1165) — function
- [test_audience_size_is_banded](../../components/agents/tests/test_agents.py#L1173) — function
- [test_asking_to_stop_is_the_worst_outcome](../../components/agents/tests/test_agents.py#L1180) — function
- [test_none_of_the_five_brains_can_see_each_other](../../components/agents/tests/test_agents.py#L1189) — function
- [decide](../../components/agents/tests/test_agents.py#L33) — function
- [decide](../../components/agents/tests/test_agents.py#L107) — function
- [decide](../../components/agents/tests/test_agents.py#L294) — function

## tests/test_core.py

[Open source](../../components/agents/tests/test_core.py)

Imports __future__, json, pathlib, time, unittest, tests.base, core.schema, core.yamlite, sqlite3, core.store, core.graph, core.hitl, core.pdf, core.ratelimit, core.llm, os, core.config, core.imapbox, threading, http.server.

- [TestSchema](../../components/agents/tests/test_core.py#L12) — class
- [TestYaml](../../components/agents/tests/test_core.py#L30) — class
- [TestStore](../../components/agents/tests/test_core.py#L51) — class
- [TestGraph](../../components/agents/tests/test_core.py#L87) — class
- [TestHitl](../../components/agents/tests/test_core.py#L222) — class
- [TestPdf](../../components/agents/tests/test_core.py#L263) — class
- [TestRateLimit](../../components/agents/tests/test_core.py#L293) — class
- [TestLlmLayer](../../components/agents/tests/test_core.py#L316) — class
- [TestDotenvLoading](../../components/agents/tests/test_core.py#L334) — class
- [TestImapInbox](../../components/agents/tests/test_core.py#L375) — class — Replies read over IMAP, using the same app password that sends.
- [TestLocalModel](../../components/agents/tests/test_core.py#L432) — class — A model running on this machine, and what happens when it is not.
- [TestDotenvValues](../../components/agents/tests/test_core.py#L536) — class — A value with spaces in it must survive the .env parser.
- [TestLessons](../../components/agents/tests/test_core.py#L568) — class — The agents change what they write, not only who they write to.
- [TestReflection](../../components/agents/tests/test_core.py#L626) — class — Turning what he said into something the agent obeys.
- [TestToolBinding](../../components/agents/tests/test_core.py#L673) — class — Hands for the model, and the line they must not cross.
- [TestParkedLaunchAgent](../../components/agents/tests/test_core.py#L762) — class — Built, tested, and not running until he says the product is ready.
- [test_validation_and_coercion](../../components/agents/tests/test_core.py#L13) — function
- [test_bool_is_not_a_number](../../components/agents/tests/test_core.py#L24) — function
- [test_round_trip](../../components/agents/tests/test_core.py#L31) — function
- [test_rejects_anchors](../../components/agents/tests/test_core.py#L40) — function
- [test_url_value_is_not_split_as_key](../../components/agents/tests/test_core.py#L45) — function
- [test_kv_and_dedupe](../../components/agents/tests/test_core.py#L52) — function
- [test_event_payload_can_use_reserved_names](../../components/agents/tests/test_core.py#L59) — function
- [test_creates_missing_parent_directory](../../components/agents/tests/test_core.py#L64) — function — A fresh checkout has no data/ folder; sqlite will not make one.
- [_graph](../../components/agents/tests/test_core.py#L88) — function
- [test_interrupt_resume_and_cycle](../../components/agents/tests/test_core.py#L105) — function
- [test_no_stale_resume_replay](../../components/agents/tests/test_core.py#L115) — function
- [test_recursion_limit_is_a_circuit_breaker](../../components/agents/tests/test_core.py#L122) — function
- [test_unserialisable_state_is_rejected_with_a_useful_message](../../components/agents/tests/test_core.py#L132) — function
- [test_transient_keys_are_not_persisted](../../components/agents/tests/test_core.py#L143) — function
- [test_node_failure_is_recorded_not_raised](../../components/agents/tests/test_core.py#L156) — function
- [test_retry_then_succeed](../../components/agents/tests/test_core.py#L170) — function
- [test_crashed_run_resumes_from_last_checkpoint](../../components/agents/tests/test_core.py#L187) — function
- [test_graph_validation_catches_dead_ends](../../components/agents/tests/test_core.py#L213) — function
- [_app](../../components/agents/tests/test_core.py#L223) — function
- [test_approve_with_edits](../../components/agents/tests/test_core.py#L240) — function
- [test_reject_blocks](../../components/agents/tests/test_core.py#L248) — function
- [test_cannot_decide_twice](../../components/agents/tests/test_core.py#L255) — function
- [test_text_is_extractable_and_paginates](../../components/agents/tests/test_core.py#L264) — function
- [test_width_measurement](../../components/agents/tests/test_core.py#L285) — function
- [test_token_bucket](../../components/agents/tests/test_core.py#L294) — function
- [test_robots_precedence](../../components/agents/tests/test_core.py#L301) — function
- [test_daily_cap](../../components/agents/tests/test_core.py#L309) — function
- [test_json_extraction](../../components/agents/tests/test_core.py#L317) — function
- [test_structured_validates_offline](../../components/agents/tests/test_core.py#L324) — function
- [test_the_last_line_wins_when_a_key_is_repeated](../../components/agents/tests/test_core.py#L335) — function — People add a setting by pasting it at the bottom of .env.
- [test_the_real_environment_still_beats_the_file](../../components/agents/tests/test_core.py#L350) — function
- [test_a_commented_line_is_still_ignored](../../components/agents/tests/test_core.py#L363) — function
- [test_it_knows_the_host_for_common_providers](../../components/agents/tests/test_core.py#L378) — function
- [test_a_reply_is_parsed_into_the_shape_the_agents_expect](../../components/agents/tests/test_core.py#L385) — function
- [test_an_out_of_office_is_recognised](../../components/agents/tests/test_core.py#L404) — function
- [test_an_html_only_reply_still_yields_text](../../components/agents/tests/test_core.py#L411) — function
- [test_nothing_is_polled_when_it_is_not_configured](../../components/agents/tests/test_core.py#L422) — function
- [_stub](../../components/agents/tests/test_core.py#L441) — function — A one-request Ollama stand-in. Returns (base_url, seen_bodies).
- [test_the_context_window_is_big_enough_for_a_brands_own_words](../../components/agents/tests/test_core.py#L479) — function
- [test_the_schema_is_sent_as_a_grammar_not_just_described](../../components/agents/tests/test_core.py#L490) — function
- [test_a_switched_off_model_falls_back_instead_of_ending_the_run](../../components/agents/tests/test_core.py#L506) — function
- [test_a_local_openai_server_does_not_demand_an_api_key](../../components/agents/tests/test_core.py#L522) — function
- [_msg](../../components/agents/tests/test_core.py#L531) — function
- [_parse](../../components/agents/tests/test_core.py#L544) — function
- [test_spaces_are_kept](../../components/agents/tests/test_core.py#L550) — function
- [test_an_inline_comment_is_still_removed](../../components/agents/tests/test_core.py#L557) — function
- [test_a_hash_inside_a_quoted_value_is_not_a_comment](../../components/agents/tests/test_core.py#L563) — function
- [lessons](../../components/agents/tests/test_core.py#L576) — function
- [test_a_rule_reaches_the_next_prompt](../../components/agents/tests/test_core.py#L580) — function
- [test_no_rules_means_no_block_at_all](../../components/agents/tests/test_core.py#L587) — function
- [test_saying_the_same_thing_twice_strengthens_one_rule](../../components/agents/tests/test_core.py#L592) — function
- [test_each_agent_learns_only_its_own_rules](../../components/agents/tests/test_core.py#L600) — function
- [test_a_rule_he_rejects_can_be_removed](../../components/agents/tests/test_core.py#L605) — function
- [test_the_prompt_budget_is_capped](../../components/agents/tests/test_core.py#L611) — function
- [test_following_a_rule_is_counted](../../components/agents/tests/test_core.py#L619) — function
- [test_a_rejection_note_becomes_a_rule_without_a_model](../../components/agents/tests/test_core.py#L629) — function
- [test_an_approval_with_nothing_said_teaches_nothing](../../components/agents/tests/test_core.py#L642) — function
- [test_an_edit_is_learned_from_even_with_no_note](../../components/agents/tests/test_core.py#L652) — function
- [test_the_diff_shows_what_he_changed](../../components/agents/tests/test_core.py#L664) — function
- [setUp](../../components/agents/tests/test_core.py#L682) — function
- [test_the_toolbelt_is_registered](../../components/agents/tests/test_core.py#L686) — function
- [test_a_tool_that_can_act_is_never_bindable](../../components/agents/tests/test_core.py#L691) — function
- [test_executing_an_unsafe_tool_refuses_rather_than_running_it](../../components/agents/tests/test_core.py#L700) — function
- [test_every_bound_tool_in_every_belt_is_read_only](../../components/agents/tests/test_core.py#L710) — function
- [test_a_tool_that_raises_hands_back_an_error_not_an_exception](../../components/agents/tests/test_core.py#L720) — function
- [test_wrong_arguments_are_explained_back_to_the_model](../../components/agents/tests/test_core.py#L729) — function
- [test_an_unknown_tool_lists_the_real_ones](../../components/agents/tests/test_core.py#L735) — function
- [test_the_call_log_records_what_it_did](../../components/agents/tests/test_core.py#L739) — function
- [test_offline_falls_back_to_a_plain_call](../../components/agents/tests/test_core.py#L746) — function
- [test_a_message_without_tools_looks_exactly_as_it_did_before](../../components/agents/tests/test_core.py#L753) — function
- [test_it_refuses_to_run_while_parked](../../components/agents/tests/test_core.py#L765) — function
- [test_the_switch_turns_it_back_on](../../components/agents/tests/test_core.py#L772) — function
- [b](../../components/agents/tests/test_core.py#L93) — function
- [boom](../../components/agents/tests/test_core.py#L160) — function
- [flaky](../../components/agents/tests/test_core.py#L174) — function
- [a](../../components/agents/tests/test_core.py#L191) — function
- [b](../../components/agents/tests/test_core.py#L195) — function
- [gate](../../components/agents/tests/test_core.py#L227) — function
- [H](../../components/agents/tests/test_core.py#L449) — class
- [_written](../../components/agents/tests/test_core.py#L513) — function
- [log_message](../../components/agents/tests/test_core.py#L450) — function
- [do_GET](../../components/agents/tests/test_core.py#L453) — function
- [do_POST](../../components/agents/tests/test_core.py#L460) — function

## tests/test_discovery.py

[Open source](../../components/agents/tests/test_discovery.py)

Imports __future__, tests.base, tests.fakes.servers, agents.sponsorship.india, agents.sponsorship.sources, agents.sponsorship.discover, agents.sponsorship.brain, math, os, agents.sponsorship.agent, pathlib, importlib.

- [TestIndiaFilter](../../components/agents/tests/test_discovery.py#L14) — class
- [TestHeadlineExtraction](../../components/agents/tests/test_discovery.py#L56) — class
- [TestBannedCategories](../../components/agents/tests/test_discovery.py#L82) — class
- [TestMemory](../../components/agents/tests/test_discovery.py#L97) — class
- [TestDiscoveryRun](../../components/agents/tests/test_discovery.py#L181) — class — The whole graph, against fixture websites rather than the real web.
- [TestOneAgentOneBrain](../../components/agents/tests/test_discovery.py#L303) — class — The merge: finding and pitching are one agent sharing one memory.
- [test_rupee_prices_and_a_91_number_are_enough](../../components/agents/tests/test_discovery.py#L15) — function
- [test_an_american_shop_does_not_pass](../../components/agents/tests/test_discovery.py#L23) — function
- [test_saying_it_does_not_ship_to_india_overrides_the_rest](../../components/agents/tests/test_discovery.py#L31) — function
- [test_an_in_domain_alone_is_not_enough](../../components/agents/tests/test_discovery.py#L38) — function
- [test_hindi_text_counts](../../components/agents/tests/test_discovery.py#L43) — function
- [test_a_word_like_transfer_is_not_a_rupee_price](../../components/agents/tests/test_discovery.py#L49) — function
- [test_it_finds_the_brand_in_a_campaign_headline](../../components/agents/tests/test_discovery.py#L57) — function
- [test_it_does_not_mistake_a_person_for_a_brand](../../components/agents/tests/test_discovery.py#L66) — function
- [test_section_labels_are_stripped](../../components/agents/tests/test_discovery.py#L76) — function
- [test_betting_never_reaches_the_list](../../components/agents/tests/test_discovery.py#L83) — function
- [test_a_clean_name_with_a_dirty_page_is_still_caught](../../components/agents/tests/test_discovery.py#L91) — function
- [prospect](../../components/agents/tests/test_discovery.py#L98) — function
- [test_one_decision_changes_the_next_score](../../components/agents/tests/test_discovery.py#L105) — function
- [test_a_rejection_pushes_it_the_other_way](../../components/agents/tests/test_discovery.py#L114) — function
- [test_a_reply_counts_for_more_than_an_approval](../../components/agents/tests/test_discovery.py#L123) — function
- [test_the_explanation_adds_up_to_the_score](../../components/agents/tests/test_discovery.py#L135) — function
- [test_one_lucky_approval_does_not_dominate](../../components/agents/tests/test_discovery.py#L148) — function
- [test_sources_that_work_get_more_of_the_budget](../../components/agents/tests/test_discovery.py#L155) — function
- [test_it_says_what_it_learned](../../components/agents/tests/test_discovery.py#L170) — function
- [setUp](../../components/agents/tests/test_discovery.py#L184) — function
- [tearDown](../../components/agents/tests/test_discovery.py#L188) — function
- [sponsor_file](../../components/agents/tests/test_discovery.py#L192) — function — Every test gets its own list. The shared fixture already contains
- [build](../../components/agents/tests/test_discovery.py#L201) — function
- [test_a_find_is_proposed_before_anything_is_added](../../components/agents/tests/test_discovery.py#L220) — function
- [test_approving_writes_it_into_the_list_and_teaches_the_memory](../../components/agents/tests/test_discovery.py#L229) — function
- [test_rejecting_writes_nothing_but_still_teaches](../../components/agents/tests/test_discovery.py#L245) — function
- [test_a_brand_already_on_the_list_is_not_proposed_again](../../components/agents/tests/test_discovery.py#L260) — function
- [test_a_betting_brand_is_dropped_without_being_shown](../../components/agents/tests/test_discovery.py#L273) — function
- [test_a_site_that_is_not_indian_is_dropped](../../components/agents/tests/test_discovery.py#L284) — function
- [setUp](../../components/agents/tests/test_discovery.py#L306) — function
- [tearDown](../../components/agents/tests/test_discovery.py#L310) — function
- [agent](../../components/agents/tests/test_discovery.py#L314) — function
- [test_there_is_no_separate_prospector_left](../../components/agents/tests/test_discovery.py#L321) — function
- [test_one_run_can_both_find_and_pitch](../../components/agents/tests/test_discovery.py#L328) — function
- [test_approving_a_pitch_teaches_the_same_brain_as_adding_a_brand](../../components/agents/tests/test_discovery.py#L362) — function
- [test_a_rejected_pitch_is_filed_as_a_negative](../../components/agents/tests/test_discovery.py#L380) — function
- [test_what_it_learns_from_one_brand_moves_the_other_kind](../../components/agents/tests/test_discovery.py#L395) — function — The point of one brain: a reply from a nutrition brand should lift
- [test_the_queue_order_shifts_with_what_it_has_learned](../../components/agents/tests/test_discovery.py#L420) — function

## tests/test_end_to_end.py

[Open source](../../components/agents/tests/test_end_to_end.py)

Imports __future__, concurrent.futures, datetime, importlib.util, json, os, pathlib, threading, unittest.mock, tests.base, tests.fakes.servers, core.mailer, core.delivery, agents.video_client.agent, agents.video_client.quote, core.inbox, types, core.work_policy, agents.fullstack_sales.packages, agents.community.agent.

- [DeliveryCase](../../components/agents/tests/test_end_to_end.py#L17) — class
- [WorkflowCase](../../components/agents/tests/test_end_to_end.py#L125) — class
- [ApplicationCase](../../components/agents/tests/test_end_to_end.py#L279) — class
- [setUp](../../components/agents/tests/test_end_to_end.py#L18) — function
- [tearDown](../../components/agents/tests/test_end_to_end.py#L27) — function
- [deliver](../../components/agents/tests/test_end_to_end.py#L31) — function
- [test_reviewed_email_is_delivered_once_with_edits](../../components/agents/tests/test_end_to_end.py#L38) — function
- [test_unapproved_email_never_sends](../../components/agents/tests/test_end_to_end.py#L45) — function
- [test_form_handoff_is_not_reported_as_a_sent_email](../../components/agents/tests/test_end_to_end.py#L51) — function
- [test_mailer_receipt_survives_a_delivery_replay](../../components/agents/tests/test_end_to_end.py#L59) — function
- [test_unknown_delivery_attempt_is_not_automatically_retried](../../components/agents/tests/test_end_to_end.py#L67) — function
- [test_video_close_sends_the_agreed_amount_and_two_attachments](../../components/agents/tests/test_end_to_end.py#L74) — function
- [test_dry_run_does_not_spend_the_live_send_cap](../../components/agents/tests/test_end_to_end.py#L97) — function
- [test_missing_payment_details_hold_invoice_but_allow_deal_closure](../../components/agents/tests/test_end_to_end.py#L104) — function
- [test_inbox_failure_preserves_the_message_for_a_later_poll](../../components/agents/tests/test_end_to_end.py#L126) — function
- [test_recruiter_choice_only_matches_an_offered_slot](../../components/agents/tests/test_end_to_end.py#L145) — function
- [test_approval_can_only_be_decided_once_under_concurrency](../../components/agents/tests/test_end_to_end.py#L153) — function
- [test_salary_and_project_limits_use_the_correct_period](../../components/agents/tests/test_end_to_end.py#L164) — function
- [test_project_floor_survives_first_project_discount](../../components/agents/tests/test_end_to_end.py#L173) — function
- [test_community_always_discloses_affiliation_and_stays_a_handoff](../../components/agents/tests/test_end_to_end.py#L182) — function
- [test_graph_resume_values_do_not_cross_threads](../../components/agents/tests/test_end_to_end.py#L197) — function
- [test_skipping_a_resumed_gate_cannot_approve_the_next_gate](../../components/agents/tests/test_end_to_end.py#L214) — function
- [test_followup_waits_for_approval_and_stops_if_a_reply_arrives](../../components/agents/tests/test_end_to_end.py#L234) — function
- [test_calendar_hours_are_local_not_utc](../../components/agents/tests/test_end_to_end.py#L252) — function
- [test_booking_requires_review_and_checks_for_calendar_conflicts](../../components/agents/tests/test_end_to_end.py#L263) — function
- [test_a_changed_form_requires_a_fresh_approval](../../components/agents/tests/test_end_to_end.py#L280) — function
- [test_unknown_sponsorship_answer_is_never_invented](../../components/agents/tests/test_end_to_end.py#L297) — function
- [test_reviewed_answers_are_the_only_ones_submitted](../../components/agents/tests/test_end_to_end.py#L306) — function
- [test_dry_run_does_not_upload_files_or_even_open_browser](../../components/agents/tests/test_end_to_end.py#L324) — function
- [test_real_browser_reaches_local_ats_only_after_review](../../components/agents/tests/test_end_to_end.py#L329) — function
- [decide](../../components/agents/tests/test_end_to_end.py#L155) — function
- [node](../../components/agents/tests/test_end_to_end.py#L200) — function
- [first](../../components/agents/tests/test_end_to_end.py#L217) — function
- [Handler](../../components/agents/tests/test_end_to_end.py#L335) — class
- [log_message](../../components/agents/tests/test_end_to_end.py#L336) — function
- [do_GET](../../components/agents/tests/test_end_to_end.py#L338) — function
- [do_POST](../../components/agents/tests/test_end_to_end.py#L345) — function

## tests/test_io.py

[Open source](../../components/agents/tests/test_io.py)

Imports __future__, base64, datetime, json, unittest, tests.base, tests.fakes.servers, os, core.oauth, core.gmail, core.mailer, core.calendar, core.llm.

- [GoogleCase](../../components/agents/tests/test_io.py#L14) — class
- [TestOAuth](../../components/agents/tests/test_io.py#L37) — class
- [TestGmail](../../components/agents/tests/test_io.py#L61) — class
- [TestCalendar](../../components/agents/tests/test_io.py#L116) — class
- [TestSmtp](../../components/agents/tests/test_io.py#L136) — class
- [TestLlmOverHttp](../../components/agents/tests/test_io.py#L180) — class
- [TestCrawlerLive](../../components/agents/tests/test_io.py#L216) — class
- [TestUnsubscribeRoute](../../components/agents/tests/test_io.py#L248) — class — A link the brand cannot open is worse than no link.
- [setUp](../../components/agents/tests/test_io.py#L15) — function
- [tearDown](../../components/agents/tests/test_io.py#L28) — function
- [gmail](../../components/agents/tests/test_io.py#L32) — function
- [test_exchange_and_refresh](../../components/agents/tests/test_io.py#L38) — function
- [test_bad_refresh_token_is_an_error](../../components/agents/tests/test_io.py#L47) — function
- [test_missing_token_message_is_actionable](../../components/agents/tests/test_io.py#L53) — function
- [test_watch_registers_and_reports_expiry](../../components/agents/tests/test_io.py#L62) — function
- [test_history_delta_returns_only_new_messages](../../components/agents/tests/test_io.py#L68) — function
- [test_push_notification_fetches_the_delta](../../components/agents/tests/test_io.py#L78) — function
- [test_quoted_history_is_stripped_and_auto_replies_flagged](../../components/agents/tests/test_io.py#L88) — function
- [test_send_threads_the_reply](../../components/agents/tests/test_io.py#L102) — function
- [test_slots_avoid_busy_blocks_and_event_creation](../../components/agents/tests/test_io.py#L117) — function
- [setUp](../../components/agents/tests/test_io.py#L137) — function
- [tearDown](../../components/agents/tests/test_io.py#L145) — function
- [mailer](../../components/agents/tests/test_io.py#L149) — function
- [test_send_includes_compliance_headers_and_footer](../../components/agents/tests/test_io.py#L153) — function
- [test_hard_bounce_suppresses_the_address](../../components/agents/tests/test_io.py#L170) — function
- [test_anthropic_provider_real_request_and_repair_loop](../../components/agents/tests/test_io.py#L181) — function
- [test_missing_api_key_is_a_clear_error](../../components/agents/tests/test_io.py#L206) — function
- [setUp](../../components/agents/tests/test_io.py#L217) — function
- [tearDown](../../components/agents/tests/test_io.py#L221) — function
- [test_profiles_a_real_site](../../components/agents/tests/test_io.py#L225) — function
- [test_robots_disallow_is_honoured](../../components/agents/tests/test_io.py#L233) — function
- [test_phone_only_site_keeps_the_lead](../../components/agents/tests/test_io.py#L238) — function
- [test_a_localhost_dashboard_asks_for_a_reply_instead_of_linking](../../components/agents/tests/test_io.py#L251) — function
- [test_a_real_public_url_is_linked](../../components/agents/tests/test_io.py#L258) — function
- [test_the_example_postal_address_is_not_printed_as_if_it_were_real](../../components/agents/tests/test_io.py#L264) — function
- [responder](../../components/agents/tests/test_io.py#L185) — function

## tests/test_relevance.py

[Open source](../../components/agents/tests/test_relevance.py)

Imports __future__, unittest, agents.job_hunter, agents.job_hunter.discovery, tests.base, os, json, pathlib, agents.job_hunter.agent.

- [job](../../components/agents/tests/test_relevance.py#L16) — function
- [TestRoleFiltering](../../components/agents/tests/test_relevance.py#L20) — class
- [TestExperienceGate](../../components/agents/tests/test_relevance.py#L64) — class
- [TestExtraction](../../components/agents/tests/test_relevance.py#L114) — class
- [TestAgentIntegration](../../components/agents/tests/test_relevance.py#L143) — class — The filter has to actually be wired into the run, not just exist.
- [TestSalaryDisplay](../../components/agents/tests/test_relevance.py#L194) — class
- [TestWhereHeCanWork](../../components/agents/tests/test_relevance.py#L212) — class — Nothing filtered by location before this, so a run tailored a resume
- [test_rejects_the_exact_junk_that_got_through_before](../../components/agents/tests/test_relevance.py#L21) — function
- [test_keeps_the_roles_he_asked_for](../../components/agents/tests/test_relevance.py#L32) — function
- [test_sales_engineer_is_not_a_sales_job](../../components/agents/tests/test_relevance.py#L49) — function — 'Solutions Engineer' is an FDE role; 'Sales Engineer' is not.
- [test_role_families_can_be_narrowed](../../components/agents/tests/test_relevance.py#L54) — function
- [test_a_fresher_does_not_see_senior_roles](../../components/agents/tests/test_relevance.py#L65) — function
- [test_years_are_read_out_of_the_description](../../components/agents/tests/test_relevance.py#L73) — function
- [test_silence_about_experience_is_not_a_rejection](../../components/agents/tests/test_relevance.py#L86) — function — Most postings never state years. Dropping them all would be wrong.
- [test_a_bit_above_your_level_still_gets_through](../../components/agents/tests/test_relevance.py#L93) — function — 0 years + 2 slack: a '2+ years' posting is still worth seeing.
- [test_raising_your_experience_opens_more_up](../../components/agents/tests/test_relevance.py#L102) — function
- [test_a_company_age_is_not_an_experience_demand](../../components/agents/tests/test_relevance.py#L107) — function
- [test_skills_come_out_of_the_posting](../../components/agents/tests/test_relevance.py#L115) — function
- [test_the_broader_term_is_dropped_when_the_specific_one_is_there](../../components/agents/tests/test_relevance.py#L122) — function
- [test_ai_vocabulary_is_recognised](../../components/agents/tests/test_relevance.py#L127) — function
- [test_fresher_roles_rank_above_ones_that_merely_tolerate_you](../../components/agents/tests/test_relevance.py#L134) — function
- [test_off_target_jobs_never_reach_the_queue](../../components/agents/tests/test_relevance.py#L148) — function
- [test_the_queued_job_carries_what_the_card_needs](../../components/agents/tests/test_relevance.py#L175) — function
- [test_an_unknown_salary_says_so_instead_of_zero](../../components/agents/tests/test_relevance.py#L195) — function
- [test_a_real_range_is_formatted_with_separators](../../components/agents/tests/test_relevance.py#L200) — function
- [ok](../../components/agents/tests/test_relevance.py#L216) — function
- [test_his_cities_pass](../../components/agents/tests/test_relevance.py#L220) — function
- [test_foreign_offices_do_not](../../components/agents/tests/test_relevance.py#L226) — function
- [test_indianapolis_is_not_in_india](../../components/agents/tests/test_relevance.py#L231) — function
- [test_a_us_address_is_recognised_without_being_listed](../../components/agents/tests/test_relevance.py#L236) — function
- [test_remote_that_is_not_open_to_india_is_refused](../../components/agents/tests/test_relevance.py#L242) — function
- [test_the_location_field_beats_a_mention_lower_down](../../components/agents/tests/test_relevance.py#L248) — function
- [test_remote_with_no_country_is_shown_but_flagged](../../components/agents/tests/test_relevance.py#L255) — function
- [test_a_blank_location_falls_back_to_the_ad_text](../../components/agents/tests/test_relevance.py#L261) — function

## tests/test_safety.py

[Open source](../../components/agents/tests/test_safety.py)

Imports __future__, unittest, tests.base, tests.fakes.servers, core.mailer, os, unittest.mock, agents.sponsorship.agent, core.registry, agents.job_hunter.discovery, agents.job_hunter.resume, core.crawler, agents.fullstack_sales.pricing, agents.job_hunter.scam_filter, agents.common.

- [TestSendPolicy](../../components/agents/tests/test_safety.py#L11) — class
- [TestNothingSendsWithoutApproval](../../components/agents/tests/test_safety.py#L76) — class
- [TestDedupe](../../components/agents/tests/test_safety.py#L121) — class
- [TestHallucinationGuards](../../components/agents/tests/test_safety.py#L133) — class
- [TestScamFilter](../../components/agents/tests/test_safety.py#L195) — class
- [TestRobotsAndPoliteness](../../components/agents/tests/test_safety.py#L250) — class
- [TestPromptLint](../../components/agents/tests/test_safety.py#L268) — class
- [TestIntentClassification](../../components/agents/tests/test_safety.py#L288) — class
- [mailer](../../components/agents/tests/test_safety.py#L12) — function
- [msg](../../components/agents/tests/test_safety.py#L16) — function
- [test_suppression_is_permanent_and_global](../../components/agents/tests/test_safety.py#L23) — function
- [test_daily_cap_stops_sending](../../components/agents/tests/test_safety.py#L34) — function
- [test_role_addresses_are_never_contacted](../../components/agents/tests/test_safety.py#L46) — function
- [test_empty_or_trivial_messages_are_refused](../../components/agents/tests/test_safety.py#L54) — function
- [test_bulk_mail_carries_a_working_opt_out](../../components/agents/tests/test_safety.py#L62) — function
- [test_unsubscribe_token_is_not_forgeable](../../components/agents/tests/test_safety.py#L70) — function
- [setUp](../../components/agents/tests/test_safety.py#L77) — function
- [tearDown](../../components/agents/tests/test_safety.py#L81) — function
- [test_outreach_suspends_before_every_send](../../components/agents/tests/test_safety.py#L85) — function
- [test_every_outbound_kind_has_a_gate](../../components/agents/tests/test_safety.py#L95) — function — Each agent's graph must route outbound work through an approval node.
- [test_same_address_is_not_mailed_twice_across_agents](../../components/agents/tests/test_safety.py#L122) — function
- [test_job_dedupe_is_by_company_and_title](../../components/agents/tests/test_safety.py#L126) — function
- [test_resume_guard_strips_invented_facts](../../components/agents/tests/test_safety.py#L134) — function
- [test_tailoring_falls_back_when_the_model_invents](../../components/agents/tests/test_safety.py#L142) — function
- [test_crawler_drops_emails_the_model_invents](../../components/agents/tests/test_safety.py#L169) — function
- [test_quotes_never_come_from_a_model](../../components/agents/tests/test_safety.py#L188) — function
- [job](../../components/agents/tests/test_safety.py#L196) — function
- [test_rejects_fee_requests](../../components/agents/tests/test_safety.py#L200) — function
- [test_rejects_document_harvesting](../../components/agents/tests/test_safety.py#L208) — function
- [test_passes_a_genuine_posting](../../components/agents/tests/test_safety.py#L216) — function
- [test_free_email_domain_for_a_named_company_is_a_flag](../../components/agents/tests/test_safety.py#L231) — function
- [test_inconsistent_seniority_and_pay](../../components/agents/tests/test_safety.py#L240) — function
- [setUp](../../components/agents/tests/test_safety.py#L251) — function
- [tearDown](../../components/agents/tests/test_safety.py#L255) — function
- [test_disallowed_site_is_not_crawled](../../components/agents/tests/test_safety.py#L259) — function
- [test_lint_catches_spam_signals](../../components/agents/tests/test_safety.py#L269) — function
- [test_clean_pitch_passes](../../components/agents/tests/test_safety.py#L280) — function
- [test_offline_classifier_accuracy](../../components/agents/tests/test_safety.py#L302) — function
- [test_opt_out_beats_the_model](../../components/agents/tests/test_safety.py#L310) — function — An explicit opt-out must never be overridden by an LLM.
- [LyingLLM](../../components/agents/tests/test_safety.py#L146) — class
- [FakeLLM](../../components/agents/tests/test_safety.py#L172) — class
- [WrongLLM](../../components/agents/tests/test_safety.py#L314) — class
- [structured](../../components/agents/tests/test_safety.py#L149) — function
- [structured](../../components/agents/tests/test_safety.py#L173) — function
- [structured](../../components/agents/tests/test_safety.py#L317) — function

## tests/test_server.py

[Open source](../../components/agents/tests/test_server.py)

Imports __future__, base64, json, threading, time, unittest, urllib.parse, tests.base, tests.fakes.servers, core.store, server.app, core, agents.sponsorship.agent, core.mailer, os, server, core.lessons, socket.

- [ServerCase](../../components/agents/tests/test_server.py#L15) — class
- [TestDashboard](../../components/agents/tests/test_server.py#L49) — class
- [TestUnsubscribeEndpoint](../../components/agents/tests/test_server.py#L126) — class
- [TestGmailWebhook](../../components/agents/tests/test_server.py#L156) — class
- [TestConsole](../../components/agents/tests/test_server.py#L188) — class — The two-pane console: the rail, the per-agent pane, and running.
- [TestDemoMode](../../components/agents/tests/test_server.py#L336) — class — Safe to put on a screen in front of a stranger.
- [TestRedaction](../../components/agents/tests/test_server.py#L382) — class — The redactor itself, without a server in the way.
- [TestReviewedAttachments](../../components/agents/tests/test_server.py#L408) — class
- [setUp](../../components/agents/tests/test_server.py#L18) — function
- [tearDown](../../components/agents/tests/test_server.py#L35) — function
- [get](../../components/agents/tests/test_server.py#L40) — function
- [post](../../components/agents/tests/test_server.py#L44) — function
- [setUp](../../components/agents/tests/test_server.py#L50) — function
- [tearDown](../../components/agents/tests/test_server.py#L73) — function
- [test_health_needs_no_token](../../components/agents/tests/test_server.py#L77) — function
- [test_token_is_enforced](../../components/agents/tests/test_server.py#L80) — function
- [test_pending_item_is_listed_and_openable](../../components/agents/tests/test_server.py#L86) — function
- [test_approving_through_the_form_resumes_the_graph](../../components/agents/tests/test_server.py#L93) — function
- [test_rejecting_sends_nothing](../../components/agents/tests/test_server.py#L106) — function
- [test_a_decided_item_cannot_be_decided_again](../../components/agents/tests/test_server.py#L112) — function
- [test_api_state_is_machine_readable](../../components/agents/tests/test_server.py#L120) — function
- [test_valid_link_suppresses](../../components/agents/tests/test_server.py#L127) — function
- [test_forged_link_is_refused](../../components/agents/tests/test_server.py#L135) — function
- [test_one_click_post_works](../../components/agents/tests/test_server.py#L141) — function
- [test_unsubscribe_needs_no_dashboard_token](../../components/agents/tests/test_server.py#L148) — function
- [test_push_is_dispatched](../../components/agents/tests/test_server.py#L157) — function
- [test_handler_failure_still_acks](../../components/agents/tests/test_server.py#L168) — function
- [test_token_protected_when_configured](../../components/agents/tests/test_server.py#L177) — function
- [setUp](../../components/agents/tests/test_server.py#L191) — function
- [test_rail_lists_every_agent_on_every_page](../../components/agents/tests/test_server.py#L202) — function
- [test_rail_counts_what_is_waiting](../../components/agents/tests/test_server.py#L209) — function
- [test_agent_pane_shows_only_that_agents_cards](../../components/agents/tests/test_server.py#L215) — function
- [test_agent_pane_shows_what_it_learned](../../components/agents/tests/test_server.py#L225) — function
- [test_a_retired_agent_name_still_has_a_home](../../components/agents/tests/test_server.py#L236) — function — The prospector was folded into the sponsorship agent. Its old
- [test_pages_are_never_cached](../../components/agents/tests/test_server.py#L251) — function — A stale approval queue is worse than none - he would act on it.
- [test_a_running_agent_makes_the_page_refresh_itself](../../components/agents/tests/test_server.py#L261) — function
- [test_a_run_that_went_quiet_stops_claiming_to_work](../../components/agents/tests/test_server.py#L274) — function
- [test_the_page_says_what_the_agent_just_did](../../components/agents/tests/test_server.py#L285) — function
- [test_a_paused_agent_says_a_card_is_waiting](../../components/agents/tests/test_server.py#L291) — function
- [test_unknown_agent_is_a_404_not_a_crash](../../components/agents/tests/test_server.py#L300) — function
- [test_agent_pane_needs_the_token](../../components/agents/tests/test_server.py#L304) — function
- [test_card_opens_with_handoff_buttons](../../components/agents/tests/test_server.py#L308) — function
- [test_api_state_reports_every_agent](../../components/agents/tests/test_server.py#L314) — function
- [test_running_a_parked_agent_is_refused](../../components/agents/tests/test_server.py#L321) — function
- [test_running_an_unknown_agent_is_refused](../../components/agents/tests/test_server.py#L326) — function
- [test_run_needs_the_token](../../components/agents/tests/test_server.py#L330) — function
- [setUp](../../components/agents/tests/test_server.py#L340) — function
- [test_addresses_and_numbers_are_hidden](../../components/agents/tests/test_server.py#L351) — function
- [test_nothing_can_be_decided](../../components/agents/tests/test_server.py#L359) — function
- [test_nothing_can_be_run](../../components/agents/tests/test_server.py#L365) — function
- [test_the_resume_is_not_downloadable](../../components/agents/tests/test_server.py#L371) — function
- [test_there_are_no_send_buttons](../../components/agents/tests/test_server.py#L375) — function
- [_with](../../components/agents/tests/test_server.py#L385) — function
- [test_off_by_default_leaves_text_alone](../../components/agents/tests/test_server.py#L393) — function
- [test_on_hides_emails_phones_and_keys](../../components/agents/tests/test_server.py#L397) — function
- [test_reviewed_pdf_requires_token_and_is_downloadable](../../components/agents/tests/test_server.py#L409) — function
- [test_attachment_cannot_expose_a_file_outside_data_directory](../../components/agents/tests/test_server.py#L420) — function
- [boom](../../components/agents/tests/test_server.py#L169) — function

## tests/test_sponsorship.py

[Open source](../../components/agents/tests/test_sponsorship.py)

Imports __future__, tests.base, agents.sponsorship, re, urllib.parse, core.yamlite, agents.sponsorship.agent, core.crawler, agents.common, collections, agents.sponsorship.discover, core.schema, core.telegram, server.bot, tests.fakes.servers.

- [TestPitchHonesty](../../components/agents/tests/test_sponsorship.py#L11) — class
- [TestSponsorList](../../components/agents/tests/test_sponsorship.py#L105) — class — The shipped list itself, not the fixture.
- [TestContactLadder](../../components/agents/tests/test_sponsorship.py#L152) — class — Which route gets picked when several are available.
- [TestDealTypes](../../components/agents/tests/test_sponsorship.py#L202) — class — At 1-2K followers the deal that earns is rarely a cash sponsorship, so
- [TestBigList](../../components/agents/tests/test_sponsorship.py#L281) — class
- [TestModelWrittenPitch](../../components/agents/tests/test_sponsorship.py#L347) — class — What the model is allowed to decide, and what it is not.
- [test_an_empty_profile_produces_a_pitch_with_no_numbers](../../components/agents/tests/test_sponsorship.py#L29) — function
- [test_a_filled_profile_states_exactly_what_is_in_it](../../components/agents/tests/test_sponsorship.py#L43) — function
- [test_numbers_are_never_rounded_upward](../../components/agents/tests/test_sponsorship.py#L53) — function
- [test_each_segment_gets_its_own_argument](../../components/agents/tests/test_sponsorship.py#L64) — function
- [test_an_agency_is_asked_a_different_question_to_a_brand](../../components/agents/tests/test_sponsorship.py#L74) — function
- [test_the_whatsapp_message_fits_a_phone_screen](../../components/agents/tests/test_sponsorship.py#L84) — function
- [test_the_whatsapp_link_carries_the_message](../../components/agents/tests/test_sponsorship.py#L94) — function
- [setUp](../../components/agents/tests/test_sponsorship.py#L108) — function
- [test_it_is_actually_a_list_worth_running](../../components/agents/tests/test_sponsorship.py#L115) — function
- [test_every_entry_is_complete](../../components/agents/tests/test_sponsorship.py#L119) — function
- [test_no_brand_appears_twice](../../components/agents/tests/test_sponsorship.py#L126) — function
- [test_no_real_money_gaming_survived_into_the_list](../../components/agents/tests/test_sponsorship.py#L135) — function — India banned it in 2025. A list built from older advice is full of
- [test_the_reachable_ones_are_ranked_first](../../components/agents/tests/test_sponsorship.py#L143) — function
- [test_a_published_phone_beats_a_guessed_address](../../components/agents/tests/test_sponsorship.py#L155) — function
- [test_a_published_address_still_wins_overall](../../components/agents/tests/test_sponsorship.py#L174) — function
- [test_a_guess_is_only_made_when_nothing_was_published](../../components/agents/tests/test_sponsorship.py#L190) — function
- [test_an_affiliate_target_is_asked_to_be_joined_not_to_pay](../../components/agents/tests/test_sponsorship.py#L212) — function
- [test_a_barter_target_is_offered_a_video_for_product](../../components/agents/tests/test_sponsorship.py#L221) — function
- [test_a_cash_target_is_asked_about_partnerships](../../components/agents/tests/test_sponsorship.py#L230) — function
- [test_the_four_deal_types_produce_four_different_asks](../../components/agents/tests/test_sponsorship.py#L238) — function
- [test_an_unknown_deal_type_falls_back_to_a_paid_partnership](../../components/agents/tests/test_sponsorship.py#L248) — function
- [test_the_short_channels_change_too](../../components/agents/tests/test_sponsorship.py#L253) — function
- [test_brands_that_pay_are_worked_first](../../components/agents/tests/test_sponsorship.py#L262) — function — The point of the agent is brands paying to be promoted, so that
- [test_affiliate_is_not_worked_at_all_by_default](../../components/agents/tests/test_sponsorship.py#L274) — function
- [setUp](../../components/agents/tests/test_sponsorship.py#L282) — function
- [test_the_list_is_big_enough_to_be_a_real_income_source](../../components/agents/tests/test_sponsorship.py#L289) — function
- [test_every_entry_declares_what_deal_is_on_offer](../../components/agents/tests/test_sponsorship.py#L292) — function
- [test_the_list_is_mostly_brands_that_can_pay](../../components/agents/tests/test_sponsorship.py#L298) — function
- [test_nothing_on_the_list_is_there_for_its_affiliate_programme](../../components/agents/tests/test_sponsorship.py#L311) — function — The label is not the point - the evidence is.
- [test_no_shopping_link_schemes_are_on_the_list](../../components/agents/tests/test_sponsorship.py#L325) — function — Affiliate networks and marketplaces make you a salesman for someone
- [test_no_duplicate_names_or_domains](../../components/agents/tests/test_sponsorship.py#L333) — function
- [test_still_no_real_money_gaming](../../components/agents/tests/test_sponsorship.py#L341) — function
- [_ctx](../../components/agents/tests/test_sponsorship.py#L354) — function
- [test_the_brief_carries_the_brands_own_words_and_the_real_numbers](../../components/agents/tests/test_sponsorship.py#L365) — function
- [test_an_unreadable_site_is_admitted_rather_than_filled_in](../../components/agents/tests/test_sponsorship.py#L377) — function
- [test_the_signature_is_the_codes_job_not_the_models](../../components/agents/tests/test_sponsorship.py#L383) — function
- [test_signing_an_already_signed_message_does_not_double_it](../../components/agents/tests/test_sponsorship.py#L401) — function
- [test_the_written_fallback_answers_the_same_shape_as_the_model](../../components/agents/tests/test_sponsorship.py#L412) — function
- [test_the_card_shows_what_the_model_read_before_you_approve](../../components/agents/tests/test_sponsorship.py#L422) — function
- [test_the_card_says_so_when_the_model_was_not_reachable](../../components/agents/tests/test_sponsorship.py#L432) — function
- [_bot](../../components/agents/tests/test_sponsorship.py#L439) — function

## tests/test_telegram.py

[Open source](../../components/agents/tests/test_telegram.py)

Imports __future__, pathlib, time, unittest, tests.base, tests.fakes.servers, core.telegram, server.bot, os, core.store, agents.job_hunter.agent, core.notify, core.config, agents.job_hunter, agents.job_hunter.discovery, re.

- [BotCase](../../components/agents/tests/test_telegram.py#L22) — class
- [TestClient](../../components/agents/tests/test_telegram.py#L57) — class
- [TestSetup](../../components/agents/tests/test_telegram.py#L98) — class
- [TestAuthorisation](../../components/agents/tests/test_telegram.py#L133) — class
- [TestCommands](../../components/agents/tests/test_telegram.py#L158) — class
- [TestApprovalFlow](../../components/agents/tests/test_telegram.py#L240) — class
- [TestNotifierChannel](../../components/agents/tests/test_telegram.py#L310) — class
- [TestJobControls](../../components/agents/tests/test_telegram.py#L336) — class — The controls Vineet asked for: set my level, pick my roles.
- [TestJobCard](../../components/agents/tests/test_telegram.py#L418) — class
- [TestBrandCard](../../components/agents/tests/test_telegram.py#L474) — class — The sponsorship card is what the whole agent is for - if it does not
- [TestSponsorshipCommands](../../components/agents/tests/test_telegram.py#L548) — class
- [TestDealTypeOnCard](../../components/agents/tests/test_telegram.py#L575) — class
- [TestHandoff](../../components/agents/tests/test_telegram.py#L611) — class — The messages the agent cannot send itself must reach you.
- [TestBothRoutesOnEveryCard](../../components/agents/tests/test_telegram.py#L661) — class — Mail and WhatsApp, on the same card, both one tap from sent.
- [TestRunEndsOutLoud](../../components/agents/tests/test_telegram.py#L709) — class — Four cards out of forty brands is not a crash - but it looked like one.
- [TestStrandedCards](../../components/agents/tests/test_telegram.py#L727) — class — A card you never answered parks its whole run, permanently.
- [setUp](../../components/agents/tests/test_telegram.py#L23) — function
- [tearDown](../../components/agents/tests/test_telegram.py#L31) — function
- [send](../../components/agents/tests/test_telegram.py#L36) — function
- [tap](../../components/agents/tests/test_telegram.py#L41) — function
- [make_approval](../../components/agents/tests/test_telegram.py#L46) — function
- [all_text](../../components/agents/tests/test_telegram.py#L53) — function
- [test_talks_the_real_protocol](../../components/agents/tests/test_telegram.py#L58) — function
- [test_rejects_a_bad_token](../../components/agents/tests/test_telegram.py#L61) — function
- [test_long_messages_are_split_not_truncated](../../components/agents/tests/test_telegram.py#L68) — function
- [test_html_in_user_content_cannot_break_the_message](../../components/agents/tests/test_telegram.py#L80) — function
- [test_sends_a_real_file](../../components/agents/tests/test_telegram.py#L84) — function
- [test_missing_file_fails_loudly](../../components/agents/tests/test_telegram.py#L93) — function
- [test_start_creates_one_topic_per_agent](../../components/agents/tests/test_telegram.py#L99) — function
- [test_start_twice_does_not_duplicate_topics](../../components/agents/tests/test_telegram.py#L107) — function
- [test_group_without_topics_gets_an_explanation_not_a_crash](../../components/agents/tests/test_telegram.py#L114) — function
- [test_first_user_to_start_becomes_the_owner](../../components/agents/tests/test_telegram.py#L122) — function
- [test_commands_are_registered_with_telegram](../../components/agents/tests/test_telegram.py#L126) — function
- [test_a_stranger_cannot_drive_the_bot](../../components/agents/tests/test_telegram.py#L134) — function
- [test_a_stranger_cannot_approve_anything](../../components/agents/tests/test_telegram.py#L141) — function
- [test_owner_from_config_overrides_the_claimed_one](../../components/agents/tests/test_telegram.py#L148) — function
- [setUp](../../components/agents/tests/test_telegram.py#L159) — function
- [test_help_lists_every_command](../../components/agents/tests/test_telegram.py#L163) — function
- [test_status_reports_what_is_waiting](../../components/agents/tests/test_telegram.py#L170) — function
- [test_pending_posts_each_item_with_buttons](../../components/agents/tests/test_telegram.py#L178) — function
- [test_pending_when_there_is_nothing](../../components/agents/tests/test_telegram.py#L190) — function
- [test_unknown_command_does_not_crash](../../components/agents/tests/test_telegram.py#L194) — function
- [test_run_needs_a_name_it_recognises](../../components/agents/tests/test_telegram.py#L198) — function
- [test_id_reports_the_ids_you_need](../../components/agents/tests/test_telegram.py#L204) — function
- [test_jobs_and_leads_read_the_right_rows](../../components/agents/tests/test_telegram.py#L209) — function
- [test_resume_sends_the_pdf_file](../../components/agents/tests/test_telegram.py#L226) — function
- [test_resume_says_so_when_there_are_none](../../components/agents/tests/test_telegram.py#L235) — function
- [setUp](../../components/agents/tests/test_telegram.py#L241) — function
- [test_approval_lands_in_its_own_agent_topic](../../components/agents/tests/test_telegram.py#L245) — function
- [test_sub_flows_share_their_parent_topic](../../components/agents/tests/test_telegram.py#L253) — function
- [test_push_pending_posts_each_approval_exactly_once](../../components/agents/tests/test_telegram.py#L259) — function
- [test_approve_button_decides_and_freezes_the_message](../../components/agents/tests/test_telegram.py#L265) — function
- [test_reject_button_decides_the_other_way](../../components/agents/tests/test_telegram.py#L274) — function
- [test_the_same_button_cannot_be_tapped_twice](../../components/agents/tests/test_telegram.py#L282) — function
- [test_a_stale_approval_id_is_handled](../../components/agents/tests/test_telegram.py#L293) — function
- [test_the_decision_note_records_it_came_from_telegram](../../components/agents/tests/test_telegram.py#L297) — function
- [_settle](../../components/agents/tests/test_telegram.py#L305) — function — The graph is resumed on a background thread; wait for it to finish.
- [test_agents_can_push_into_their_own_topic](../../components/agents/tests/test_telegram.py#L311) — function
- [test_a_failed_notification_never_kills_the_run](../../components/agents/tests/test_telegram.py#L324) — function
- [setUp](../../components/agents/tests/test_telegram.py#L339) — function
- [tearDown](../../components/agents/tests/test_telegram.py#L349) — function
- [test_exp_shows_the_current_level](../../components/agents/tests/test_telegram.py#L356) — function
- [test_exp_changes_the_level_and_says_what_changed](../../components/agents/tests/test_telegram.py#L361) — function
- [test_exp_survives_a_restart](../../components/agents/tests/test_telegram.py#L367) — function — It is written back to .env, not just held in memory.
- [test_exp_rejects_nonsense_without_crashing](../../components/agents/tests/test_telegram.py#L373) — function
- [test_raising_experience_actually_opens_jobs_up](../../components/agents/tests/test_telegram.py#L379) — function — The command has to change what the filter does, not just a setting.
- [test_roles_lists_what_is_on](../../components/agents/tests/test_telegram.py#L389) — function
- [test_roles_narrows_the_search](../../components/agents/tests/test_telegram.py#L395) — function
- [test_roles_all_turns_everything_back_on](../../components/agents/tests/test_telegram.py#L406) — function
- [test_an_unknown_role_name_is_refused](../../components/agents/tests/test_telegram.py#L413) — function
- [test_the_card_leads_with_what_decides_it](../../components/agents/tests/test_telegram.py#L419) — function
- [test_a_job_card_offers_the_resume_and_the_application](../../components/agents/tests/test_telegram.py#L439) — function
- [test_an_email_card_has_no_resume_button](../../components/agents/tests/test_telegram.py#L451) — function
- [test_the_resume_button_sends_the_pdf](../../components/agents/tests/test_telegram.py#L460) — function
- [_card](../../components/agents/tests/test_telegram.py#L478) — function
- [test_the_card_shows_who_why_and_how_to_reach_them](../../components/agents/tests/test_telegram.py#L493) — function
- [test_a_guessed_address_is_labelled_as_one](../../components/agents/tests/test_telegram.py#L504) — function
- [test_a_whatsapp_lead_shows_the_whatsapp_message_not_the_email](../../components/agents/tests/test_telegram.py#L512) — function
- [test_the_dm_version_is_one_tap_away](../../components/agents/tests/test_telegram.py#L526) — function
- [test_asking_for_the_dm_does_not_decide_the_approval](../../components/agents/tests/test_telegram.py#L532) — function
- [test_a_pitch_with_no_numbers_says_so_on_the_card](../../components/agents/tests/test_telegram.py#L540) — function
- [test_brands_reports_the_pipeline](../../components/agents/tests/test_telegram.py#L549) — function
- [test_mediakit_names_what_is_missing](../../components/agents/tests/test_telegram.py#L567) — function
- [_card](../../components/agents/tests/test_telegram.py#L576) — function
- [test_the_card_says_what_is_being_asked_for](../../components/agents/tests/test_telegram.py#L585) — function
- [test_an_unknown_deal_type_does_not_break_the_card](../../components/agents/tests/test_telegram.py#L600) — function
- [test_brands_breaks_the_pipeline_down_by_deal](../../components/agents/tests/test_telegram.py#L604) — function
- [setUp](../../components/agents/tests/test_telegram.py#L620) — function
- [_state](../../components/agents/tests/test_telegram.py#L624) — function
- [test_a_whatsapp_handoff_is_posted_with_its_link](../../components/agents/tests/test_telegram.py#L636) — function
- [test_the_whatsapp_wording_is_used_not_the_email_body](../../components/agents/tests/test_telegram.py#L646) — function
- [test_a_dm_handoff_uses_the_dm_wording](../../components/agents/tests/test_telegram.py#L651) — function
- [test_the_same_handoff_is_not_posted_twice](../../components/agents/tests/test_telegram.py#L655) — function
- [_card](../../components/agents/tests/test_telegram.py#L664) — function
- [test_a_whatsapp_card_still_offers_the_email_route](../../components/agents/tests/test_telegram.py#L678) — function
- [test_the_card_names_the_route_it_did_not_pick](../../components/agents/tests/test_telegram.py#L688) — function
- [test_a_brand_with_only_an_email_gets_only_that_button](../../components/agents/tests/test_telegram.py#L692) — function
- [test_telegram_only_ever_gets_https_button_links](../../components/agents/tests/test_telegram.py#L699) — function
- [setUp](../../components/agents/tests/test_telegram.py#L712) — function
- [test_the_end_of_a_run_says_why_the_rest_got_no_card](../../components/agents/tests/test_telegram.py#L716) — function
- [setUp](../../components/agents/tests/test_telegram.py#L735) — function
- [_pending](../../components/agents/tests/test_telegram.py#L739) — function
- [test_run_reposts_the_open_card_instead_of_starting_over](../../components/agents/tests/test_telegram.py#L746) — function
- [test_pending_reposts_everything_waiting](../../components/agents/tests/test_telegram.py#L753) — function
- [test_the_bot_says_on_startup_how_many_are_holding_up_a_run](../../components/agents/tests/test_telegram.py#L759) — function

## tests/test_workflow_brain.py

[Open source](../../components/agents/tests/test_workflow_brain.py)

Imports copy, json, unittest.mock, tests.base, core.workflow_service, core.workflow_brain, core.llm.

- [BrainBoundaryTests](../../components/agents/tests/test_workflow_brain.py#L14) — class
- [task](../../components/agents/tests/test_workflow_brain.py#L15) — function
- [test_proposed_step_empty_quote_is_valid](../../components/agents/tests/test_workflow_brain.py#L21) — function
- [test_missing_evidence_quote_fails_without_fallback](../../components/agents/tests/test_workflow_brain.py#L24) — function
- [test_plan_cache_does_not_execute_tools_or_call_model_again](../../components/agents/tests/test_workflow_brain.py#L31) — function
- [test_planning_failure_is_visible_and_does_not_create_approval](../../components/agents/tests/test_workflow_brain.py#L39) — function
- [test_reading_remains_reading_after_brain_plan](../../components/agents/tests/test_workflow_brain.py#L47) — function

## tests/test_workflow_receivers.py

[Open source](../../components/agents/tests/test_workflow_receivers.py)

Imports json, pathlib, time, unittest.mock, tests.base, adapters.receiver, core.workflow_service, core.workflow_broker, core.workflow_brain, core.llm, tests.test_workflow_brain, scripts.backup_workflow_database, core.hitl.

- [ReceivingBoundaryTests](../../components/agents/tests/test_workflow_receivers.py#L11) — class
- [test_result_journal_recovers_lost_database_acknowledgement](../../components/agents/tests/test_workflow_receivers.py#L12) — function
- [test_restart_does_not_replay_unfinished_execution](../../components/agents/tests/test_workflow_receivers.py#L24) — function
- [test_model_cannot_add_an_execution_field](../../components/agents/tests/test_workflow_receivers.py#L35) — function
- [test_secret_artifact_registration_is_rejected](../../components/agents/tests/test_workflow_receivers.py#L41) — function
- [test_consistent_backup_restores_action_tombstones](../../components/agents/tests/test_workflow_receivers.py#L47) — function
- [test_expired_approval_can_reconcile_but_not_submit_again](../../components/agents/tests/test_workflow_receivers.py#L60) — function
- [ReadOnlyClient](../../components/agents/tests/test_workflow_receivers.py#L71) — class
- [reconcile](../../components/agents/tests/test_workflow_receivers.py#L72) — function
- [submit](../../components/agents/tests/test_workflow_receivers.py#L75) — function

## tests/test_workflows.py

[Open source](../../components/agents/tests/test_workflows.py)

Imports __future__, errno, json, socket, time, urllib.error, unittest.mock, tests.base, core.workflow_contracts, core.workflow_store, core.workflow_service, core.workflow_broker, scripts.workflow_fixtures, core.workflow_health, http.server, threading, pathlib, core.store, core.mailer, tests.fakes.servers.

- [WorkflowTests](../../components/agents/tests/test_workflows.py#L19) — class
- [setUp](../../components/agents/tests/test_workflows.py#L20) — function
- [create](../../components/agents/tests/test_workflows.py#L28) — function
- [brief](../../components/agents/tests/test_workflows.py#L33) — function
- [artifact](../../components/agents/tests/test_workflows.py#L38) — function
- [video_artifact](../../components/agents/tests/test_workflows.py#L43) — function
- [package](../../components/agents/tests/test_workflows.py#L48) — function
- [test_duplicate_task_and_changed_key_conflict](../../components/agents/tests/test_workflows.py#L62) — function
- [test_content_deletion_retains_replay_tombstone_and_shared_contact](../../components/agents/tests/test_workflows.py#L69) — function
- [test_health_preserves_wrapped_socket_error_and_unverified_model](../../components/agents/tests/test_workflows.py#L84) — function
- [test_versioned_adapter_over_real_loopback_http_reuses_action](../../components/agents/tests/test_workflows.py#L95) — function
- [test_review_restart_revision_and_scope_expansion](../../components/agents/tests/test_workflows.py#L145) — function
- [test_artifact_mutation_invalidates_approval](../../components/agents/tests/test_workflows.py#L156) — function
- [test_cancelled_queued_action_never_runs](../../components/agents/tests/test_workflows.py#L163) — function
- [test_resource_claim_is_shared_between_connections](../../components/agents/tests/test_workflows.py#L171) — function
- [test_receiver_crash_reconciles_without_second_submission](../../components/agents/tests/test_workflows.py#L185) — function
- [test_role_permissions_and_expiry](../../components/agents/tests/test_workflows.py#L208) — function
- [test_health_failure_classification_and_incident_cooldown](../../components/agents/tests/test_workflows.py#L220) — function
- [test_stale_worker_is_not_completed](../../components/agents/tests/test_workflows.py#L236) — function
- [test_inbox_reimports_deduplicate_and_ambiguous_date_stays_open](../../components/agents/tests/test_workflows.py#L243) — function
- [test_learning_cannot_turn_reading_into_work_experience](../../components/agents/tests/test_workflows.py#L256) — function
- [test_three_intro_release_package_preserves_identity](../../components/agents/tests/test_workflows.py#L261) — function
- [test_experiment_reproduces_metrics_from_exact_dataset](../../components/agents/tests/test_workflows.py#L273) — function
- [test_experiment_registration_interruption_reuses_measured_bytes](../../components/agents/tests/test_workflows.py#L289) — function
- [test_cross_agent_contact_claim_prevents_second_initial_send](../../components/agents/tests/test_workflows.py#L311) — function
- [test_release_destinations_review_separately_and_reuse_verified_receipts](../../components/agents/tests/test_workflows.py#L328) — function
- [Receiver](../../components/agents/tests/test_workflows.py#L100) — class
- [Receiver](../../components/agents/tests/test_workflows.py#L188) — class
- [interrupted](../../components/agents/tests/test_workflows.py#L297) — function
- [dispatch](../../components/agents/tests/test_workflows.py#L341) — function
- [log_message](../../components/agents/tests/test_workflows.py#L101) — function
- [reply](../../components/agents/tests/test_workflows.py#L103) — function
- [do_GET](../../components/agents/tests/test_workflows.py#L108) — function
- [do_POST](../../components/agents/tests/test_workflows.py#L116) — function
- [capabilities](../../components/agents/tests/test_workflows.py#L190) — function
- [submit](../../components/agents/tests/test_workflows.py#L192) — function
- [reconcile](../../components/agents/tests/test_workflows.py#L196) — function

## Frontend and native source files
