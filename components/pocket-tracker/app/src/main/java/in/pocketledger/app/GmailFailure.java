package in.pocketledger.app;

import java.io.*;
import java.net.*;
import javax.net.ssl.SSLException;
import org.json.*;

/** Safe diagnostics only: never display Google's raw response, tokens or message content. */
final class GmailFailure extends IOException {
    final int status;
    final boolean retryable;
    private GmailFailure(int status, String detail, boolean quota) {
        super("Gmail HTTP " + status + ": " + detail);
        this.status = status;
        retryable = quota || status == 408 || status == 429 || status >= 500;
    }

    static GmailFailure fromResponse(int status, InputStream stream) {
        String reason = "";
        if (stream != null) {
            try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[2048]; int n;
                while (out.size() < 65536 && (n = in.read(buffer, 0, Math.min(buffer.length, 65536 - out.size()))) != -1) out.write(buffer, 0, n);
                JSONObject error = new JSONObject(out.toString("UTF-8")).optJSONObject("error");
                if (error != null) {
                    reason = known(error.optString("status"));
                    // New Google ErrorInfo is more specific than the general PERMISSION_DENIED status.
                    for (String key : new String[]{"errors", "details"}) {
                        JSONArray entries = error.optJSONArray(key);
                        if (entries == null) continue;
                        for (int i = 0; i < entries.length(); i++) {
                            JSONObject entry = entries.optJSONObject(i);
                            String candidate = entry == null ? "" : known(entry.optString("reason"));
                            if (!candidate.isEmpty()) reason = candidate;
                        }
                    }
                }
            } catch (IOException | JSONException ignored) { /* Keep HTTP status, never echo raw content. */ }
        }
        String detail;
        switch (reason) {
            case "disabled": detail = "Gmail API is disabled for the project associated with this app. Check Pocket Tracker project noble-mantis-513214-g1, then wait a few minutes and reconnect."; break;
            case "scope": detail = "Read-only Gmail access was not granted. Reconnect and approve the Gmail permission."; break;
            case "policy": detail = "This Google account's administrator blocks Gmail API access. The administrator must allow it."; break;
            case "quota": detail = "Google's request limit was reached. Collection will retry later."; break;
            default:
                if (status == 401) detail = "Google rejected the access token. Reconnect Gmail in Setup.";
                else if (status == 403) detail = "Google denied access. Check Gmail API, the test-user account and read-only permission in the Pocket Tracker Google project.";
                else if (status == 429) detail = "Google's request limit was reached. Collection will retry later.";
                else if (status >= 500) detail = "Google's Gmail service is temporarily unavailable. Try again later.";
                else detail = "Google could not complete this request. Reconnect Gmail; if it repeats, share this HTTP code.";
        }
        return new GmailFailure(status, detail, reason.equals("quota"));
    }

    private static String known(String value) {
        switch (value) {
            case "SERVICE_DISABLED": case "accessNotConfigured": return "disabled";
            case "ACCESS_TOKEN_SCOPE_INSUFFICIENT": case "insufficientPermissions": return "scope";
            case "domainPolicy": return "policy";
            case "rateLimitExceeded": case "userRateLimitExceeded": case "dailyLimitExceeded": case "RESOURCE_EXHAUSTED": return "quota";
            default: return "";
        }
    }

    static String describe(Throwable error) {
        for (Throwable e = error; e != null; e = e.getCause()) {
            if (e instanceof GmailFailure) return e.getMessage();
            if (e instanceof UnknownHostException) return "Gmail server address could not be resolved. Check the phone's internet connection and Private DNS, then reconnect.";
            if (e instanceof SocketTimeoutException || e instanceof java.util.concurrent.TimeoutException) return "The Gmail connection timed out. Check the phone's internet connection and try again.";
            if (e instanceof SSLException) return "The secure connection to Google failed. Check automatic date/time and any VPN or network filtering on the phone.";
            if (e instanceof ConnectException) return "Could not reach Google's Gmail server. Check the phone's internet connection and try again.";
            if (e instanceof SecurityException) return "Gmail needs your permission. Reconnect Gmail in Setup.";
        }
        return "Gmail could not complete the connection (" + error.getClass().getSimpleName() + "). Try again; if it repeats, share this message.";
    }

    static boolean shouldRetry(Throwable error) {
        for (Throwable e = error; e != null; e = e.getCause()) {
            if (e instanceof GmailFailure) return ((GmailFailure)e).retryable;
            if (e instanceof SecurityException) return false;
        }
        return true;
    }
}
