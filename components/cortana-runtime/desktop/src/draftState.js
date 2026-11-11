export const PLATFORMS = [
  { id: "whatsapp", label: "WhatsApp", initials: "W", recipientHint: "Contact name as shown in WhatsApp" },
  { id: "gmail", label: "Gmail", initials: "G", recipientHint: "Recipient email address" },
  { id: "instagram", label: "Instagram", initials: "I", recipientHint: "Exact account username" },
];

export function platformInfo(id) {
  return PLATFORMS.find((item) => item.id === id) || { id: "", label: "App", initials: "?", recipientHint: "Recipient" };
}

export function connectionLabel(status) {
  return {
    not_open: "Not opened",
    needs_login: "Sign in required",
    connected: "Connected",
    error: "Connection error",
    available: "Ready to open",
    opened: "Opened in your session",
  }[status] || "Not checked";
}

export function draftLabel(status) {
  return {
    needs_login: "Sign in to continue",
    choose_recipient: "Choose the recipient",
    draft_ready: "Draft ready for your review",
    error: "Draft needs attention",
    needs_app: "Continue in your app",
  }[status] || "Draft status not verified";
}

export function draftRequest({ platform, recipient, body, subject }) {
  if (!PLATFORMS.some((item) => item.id === platform)) throw new Error("Choose WhatsApp, Gmail, or Instagram.");
  if (!recipient.trim()) throw new Error("Enter a recipient.");
  if (!body.trim()) throw new Error("Enter the exact message to prepare.");
  const messageText = body + (platform === "gmail" ? subject || "" : "");
  if ([...messageText].some((character) => /\p{L}/u.test(character) && !/\p{Script=Latin}/u.test(character))) {
    throw new Error(platform === "gmail"
      ? "Write the Gmail message and subject in English."
      : "Write the message in English or Hinglish using Roman letters.");
  }
  // Message and subject are preserved byte-for-byte as typed. Only recipient
  // whitespace is normalized; browser adapters own identity verification.
  return { platform, recipient: recipient.trim(), body, ...(platform === "gmail" ? { subject: subject || "" } : {}) };
}

export function previewParts(draft) {
  if (typeof draft?.preview === "string") return { body: draft.preview, subject: "" };
  return {
    body: typeof draft?.preview?.body === "string" ? draft.preview.body : "",
    subject: typeof draft?.preview?.subject === "string" ? draft.preview.subject : "",
  };
}

export function stoppedDraft(draft) {
  if (!draft) return draft;
  return {
    ...draft, draft_id: "", status: "error", candidates: [],
    note: "Draft session stopped. Prepare the message again to continue. Text already saved by the app may remain there.",
  };
}
