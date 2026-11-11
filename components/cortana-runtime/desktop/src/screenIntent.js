// Only direct requests capture automatically. Other questions can use the
// visible "Ask about my screen" button; mentioning screens is not consent.
export function wantsScreenContext(text) {
  // Quoted dictation and message body clauses are data, not a request to
  // inspect the desktop. In particular, never capture for a quoted email.
  const request = String(text).replace(/"[^"]*"|“[^”]*”/gu, " ")
    .split(/\b(?:saying\b|body\s*:|subject\s*:|message\s*:)/iu)[0]
    .trim().toLowerCase().replace(/[.!?।]+$/u, "").trim()
    .replace(/^(?:(?:hey )?cortana[, ]*|please )+/u, "").trim();
  if (/\b(?:don['’]?t|do not|never|stop|without|mat|nahi|nahin)\b|(?:मत|नहीं|बिना)/iu.test(request)) return false;
  const visibleReference = /\b(?:on|in) (?:my|this|the|current) screen\b|\b(?:visible|shown|displayed) (?:here|on screen)\b|\b(?:meri|is|iss) screen (?:par|pe|mein|me)\b|(?:मेरी|इस) स्क्रीन (?:पर|में)/iu.test(request);
  const requestAboutVisible = /^(?:(?:can|could|would|will) (?:you|u) )?(?:please )?(?:tell me|what|which|why|how|is|are|does|do|explain|describe|check|review|read|look|see|inspect|fix|correct|change|open|select|click|prepare|draft|message|type)\b/iu.test(request)
    || /(?:batao|samjhao|dekho|theek karo|sahi karo|बताओ|समझाओ|देखो|ठीक करो|सही करो)/iu.test(request);
  if (visibleReference && requestAboutVisible) return true;
  return [
    /^(?:now )?(?:can|could) (?:you|u) see(?: (?:it|this|that|now))?$/u,
    /^(?:what (?:do|can) (?:you|u) see)(?: (?:here|now))?$/u,
    /^(?:what|which)(?: is|'s) (?:the )?(?:first|second|third|last|selected|current) (?:chat|message|window|button|app)$/u,
    /^(?:see|look at|read|check|describe) (?:the |this |that )?(?:first|second|third|last|selected|current) (?:chat|message|window|button|app)$/u,
    /^(?:look at|read|inspect|check|explain|describe|analy[sz]e) (?:my|this|the) screen(?: please)?$/u,
    /^what(?:'s| is) on (?:my|this|the) screen$/u,
    /^(?:can|could) (?:you|u) (?:see|look at|read|explain|check) (?:my|this|the) screen$/u,
    /^(?:what(?:'s| is) (?:this|the)|explain this) error(?: on (?:my|this|the) screen)?$/u,
    /^(?:meri|ye|is|iss) screen (?:dekho|dekh kar batao|samjhao)$/u,
    /^(?:(?:meri|is|iss) )?screen (?:par|pe|me|mein) kya (?:hai|dikh raha hai|problem hai|error hai)$/u,
    /^(?:मेरी|यह|इस) स्क्रीन (?:देखो|समझाओ|पढ़ो)$/u,
    /^(?:(?:मेरी|इस) )?स्क्रीन (?:पर|में) क्या (?:है|दिख रहा है|समस्या है)$/u,
  ].some((pattern) => pattern.test(request));
}
