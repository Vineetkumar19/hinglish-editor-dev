"""The connected sales conversation: samples, quotes, counters and reviewed closure."""
from __future__ import annotations

import json
import re

from agents.common import ReplyAgent
from core.store import now
from core.work_policy import project_floor
from core import config

ACCEPT = re.compile(r"\b(accept (?:the |your )?(?:quote|proposal|terms)|"
                    r"agreed|go ahead|let'?s proceed|send (?:the |an? )?invoice|"
                    r"happy to proceed|deal confirmed)\b", re.I)


class SalesReplyAgent(ReplyAgent):
    def _deal(self, state):
        lead = state.get("lead") or {}
        for row in self.store.query(
                "SELECT k,value_json FROM kv WHERE namespace=? AND k LIKE 'deal:%'",
                (self.cfg.agent,)):
            record = json.loads(row["value_json"])
            if lead.get("id") and record.get("lead_id") == lead["id"]:
                return row["k"], record
        data = json.loads(lead.get("data_json") or "{}")
        target = data.get("target") or {"company": lead.get("company", ""),
                                      "description": (data.get("profile") or {}).get("text", ""),
                                      "email": lead.get("email", "")}
        return f"deal:lead:{lead.get('id', state['_thread_id'])}", {
            "gig": target, "lead_id": lead.get("id"), "stage": "opening"}

    def n_draft_reply(self, state):
        key, deal = self._deal(state)
        target = deal.get("gig") or {}
        message = state["message"]
        text = message.get("reply_text") or ""
        paths = []
        description = " ".join(str(target.get(k) or "") for k in
                               ("title", "description", "location"))
        if self.cfg.agent == "video_client":
            from agents.video_client.quote import Quote, build_quote, find_offer, respond_to
            from agents.video_client import pitch
            quote = Quote.from_json(deal["quote"]) if deal.get("quote") else build_quote(description + " " + text)
            quote.floor = max(quote.floor, project_floor(quote.currency))
            quote.ask = max(quote.ask, quote.floor)
            counter = respond_to(find_offer(text, quote.currency), quote)
            if counter.action == "ask_operator":
                draft = {"subject": "Re: " + message.get("subject", ""),
                         "body": "Thanks for the details. I need to review the scope and budget "
                                 "before confirming a price. Could you share the runtime, volume "
                                 "and desired delivery date?", "needs_human": True}
                stage, amount = "needs_operator", 0
            elif ACCEPT.search(text) and deal.get("stage") in ("quoted", "countered", "won"):
                amount = max(float(deal.get("amount") or quote.ask), quote.floor)
                payment = config.get("PAYMENT_DETAILS", "") or self.store.kv_get("operator_preferences", "payment_details", "")
                draft = pitch.rate_reply(target, quote, amount=amount)
                from agents.video_client import docs
                paths = [docs.proposal(target, quote, amount=amount)]
                if payment:
                    paths.append(docs.invoice(target, quote, amount=amount, deposit=True, payment_details=payment))
                    draft["body"] += "\n\nThe proposal and deposit invoice are attached for your review."
                    deal["invoice_status"] = "prepared"
                else:
                    draft["body"] += "\n\nThe proposal is attached. I will share payment instructions separately before work begins."
                    deal["invoice_status"] = "awaiting_payment_details"
                stage = "won"
            elif counter.action == "counter":
                draft = pitch.counter_reply(target, quote, counter)
                stage, amount = "countered", counter.amount
            else:
                amount = counter.amount if counter.action == "accept" else quote.ask
                draft = pitch.rate_reply(target, quote, amount=amount)
                stage = "quoted"
            deal["quote"] = quote.to_json()
        else:
            from agents.fullstack_sales import packages, pitch_replies as pitch
            package = (packages.Package.from_json(deal["package"])
                       if deal.get("package") else packages.build_package(description + " " + text))
            if package is None:
                # Build work uses the same deterministic component quote engine.
                from agents.fullstack_sales.agent import QuoteAgent
                analyser = QuoteAgent(store=self.store, llm=self.llm,
                                      mailer=self.mailer, notifier=self.notifier)
                initial = {**state, "site_text": description}
                analysed = {**initial, **analyser.n_analyse(initial)}
                if not analysed.get("scope") and not deal.get("quote_json"):
                    return {"reply_draft": {"subject": "Re: " + message.get("subject", ""),
                            "body": "Thanks for the enquiry. Before I can give you a defensible "
                                    "estimate, could you share the required features, integrations, "
                                    "existing stack and deadline?", "needs_human": True}}
                if deal.get("quote_json") and ACCEPT.search(text) and deal.get("stage") == "quoted":
                    from agents.fullstack_sales.pricing import Quote as BuildQuote
                    q = BuildQuote.from_json(deal["quote_json"])
                    stage, amount = "won", q.total
                else:
                    priced = {**analysed, **analyser.n_price(analysed)}
                    q = analyser._quote(priced)
                    stage, amount = "quoted", q.total
                draft = {"subject": f"Estimate: {q.currency} {q.total:,.0f}",
                         "body": "Thanks for the scope. Here is the estimate and its assumptions:\n\n"
                                 + q.render() + "\n\nPlease confirm the scope before work starts."}
                deal["quote_json"] = q.to_json()
            else:
                package.floor = max(package.floor, project_floor(package.currency))
                package.ask = max(package.ask, package.floor)
                counter = packages.respond_to(packages.find_offer(text, package.currency), package)
                if counter.action == "ask_operator":
                    draft = {"subject": "Re: scope and budget", "needs_human": True,
                             "body": "Thanks for sharing the budget. That needs a scope review "
                                     "before I can agree. Which deliverables are essential and "
                                     "which can wait for a later phase?"}
                    stage, amount = "needs_operator", 0
                elif ACCEPT.search(text) and deal.get("stage") in ("quoted", "countered"):
                    amount = max(float(deal.get("amount") or package.ask), package.floor)
                    draft = pitch.rate_reply(target, package, amount=amount)
                    stage = "won"
                elif counter.action == "counter":
                    draft = pitch.counter_reply(target, package, counter)
                    stage, amount = "countered", counter.amount
                else:
                    amount = counter.amount if counter.action == "accept" else package.ask
                    draft = pitch.rate_reply(target, package, amount=amount)
                    stage = "quoted"
                deal["package"] = package.to_json()
        draft["subject"] = draft.get("subject") or "Re: " + message.get("subject", "")
        return {"reply_draft": draft, "deal_key": key,
                "deal_update": {**deal, "stage": stage, "amount": amount},
                "reply_attachments": paths,
                "reply_extras": {"proposed_stage": stage, "amount": amount,
                                 "attachments": paths, "invoice_status": deal.get("invoice_status", "")}}

    def n_send_reply(self, state):
        out = super().n_send_reply(state)
        if out.get("outcome") != "replied" or not state.get("deal_update"):
            return out
        deal = state["deal_update"]
        # A simulated delivery is not a closed sale or a real follow-up clock.
        from core import config
        if config.dry_run():
            return {**out, "outcome": "dry_run"}
        self.store.kv_set(self.cfg.agent, state["deal_key"], deal)
        self._learn_outcome(state, "deal_won" if deal["stage"] == "won" else "quoted")
        if deal["stage"] == "won":
            lead = state.get("lead") or {}
            if lead.get("id"):
                self.store.run("UPDATE leads SET status=?,updated_at=? WHERE id=?",
                               ("closed_won", now(), lead["id"]))
            self.notifier.send("Deal agreed - onboarding ready",
                               f"{lead.get('company', '')}: {deal.get('amount')}. "
                               "Review the agreed terms and confirm the deposit before starting.",
                               priority="urgent", tags=(self.cfg.agent,))
        return out
