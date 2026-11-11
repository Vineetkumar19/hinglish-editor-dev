// Opening a window is never evidence that speech is addressed to Cortana.
export const COMMAND_WINDOW_MS = 12000;

export function commandWindowOpen(conversation, now = Date.now()) {
  return Boolean(conversation.open && (conversation.continuous || now < conversation.expiresAt));
}

export function addressedSpeech(result, awaitingCommand) {
  if (result.detected) return (result.remainder || "").trim();
  return awaitingCommand ? (result.transcript || "").trim() : "";
}
