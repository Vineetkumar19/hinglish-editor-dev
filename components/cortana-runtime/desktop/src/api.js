// Fetch-shaped adapter over the narrow preload bridge. Neither the local port
// nor the authentication token ever enters renderer JavaScript.
export async function apiFetch(route, options = {}) {
  if (!window.cortana?.request) {
    throw new Error("Open Cortana using the desktop launcher. The browser preview cannot control your laptop.");
  }
  if (options.signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
  const id = crypto.randomUUID();
  const payload = { method: options.method || "GET" };
  if (options.body instanceof FormData) {
    payload.form = [];
    for (const [name, value] of options.body.entries()) {
      payload.form.push(value instanceof Blob
        ? { name, bytes: await value.arrayBuffer(), type: value.type, filename: value.name || "recording.webm" }
        : { name, value });
    }
  } else if (options.body !== undefined) {
    payload.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
  }
  if (options.signal?.aborted) throw new DOMException("Request cancelled", "AbortError");
  let rejectAborted;
  const aborted = new Promise((_, reject) => { rejectAborted = reject; });
  const onAbort = () => {
    window.cortana.abortRequest(id).catch(() => {});
    rejectAborted(new DOMException("Request cancelled", "AbortError"));
  };
  options.signal?.addEventListener("abort", onAbort, { once: true });
  try {
    const result = await Promise.race([window.cortana.request(id, route, payload), aborted]);
    if (result.cancelled) throw new DOMException("Request stopped", "AbortError");
    return new Response(result.bytes, {
      status: result.status,
      headers: { "Content-Type": result.contentType || "application/json" },
    });
  } finally {
    options.signal?.removeEventListener("abort", onAbort);
  }
}
