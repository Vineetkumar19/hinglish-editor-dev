package in.pocketledger.app;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import org.junit.Test;
import static org.junit.Assert.*;

public class GmailFailureTest {
    private GmailFailure response(int status, String body) {
        return GmailFailure.fromResponse(status,new ByteArrayInputStream(body.getBytes(StandardCharsets.UTF_8)));
    }
    @Test public void disabledApiIdentifiedWithoutExposingResponse() {
        GmailFailure e=response(403,"{\"error\":{\"message\":\"private token and user content\",\"status\":\"PERMISSION_DENIED\",\"errors\":[{\"reason\":\"accessNotConfigured\"}],\"details\":[{\"reason\":\"SERVICE_DISABLED\"}]}}");
        assertTrue(e.getMessage().contains("Gmail API is disabled"));
        assertFalse(e.getMessage().contains("private token"));assertFalse(GmailFailure.shouldRetry(e));
    }
    @Test public void missingScopeAndQuotaHaveDifferentRecovery() {
        GmailFailure scope=response(403,"{\"error\":{\"details\":[{\"reason\":\"ACCESS_TOKEN_SCOPE_INSUFFICIENT\"}]}}");
        GmailFailure quota=response(403,"{\"error\":{\"errors\":[{\"reason\":\"userRateLimitExceeded\"}]}}");
        assertTrue(scope.getMessage().contains("Read-only Gmail access"));assertFalse(GmailFailure.shouldRetry(scope));
        assertTrue(quota.getMessage().contains("request limit"));assertTrue(GmailFailure.shouldRetry(quota));
    }
    @Test public void malformedAndAbsentResponseStillShowHttpStatus() {
        GmailFailure e=response(503,"<html>private upstream response</html>");
        assertTrue(e.getMessage().contains("HTTP 503"));assertTrue(GmailFailure.shouldRetry(e));assertFalse(e.getMessage().contains("private upstream"));
        assertTrue(GmailFailure.fromResponse(401,null).getMessage().contains("Reconnect"));
        assertFalse(GmailFailure.shouldRetry(GmailFailure.fromResponse(401,null)));
    }
    @Test public void wrappedNetworkFailuresExplainRecoveryAndHideDetails() {
        assertTrue(GmailFailure.describe(new IOException(new UnknownHostException("private host"))).contains("Private DNS"));
        assertFalse(GmailFailure.describe(new UnknownHostException("private host")).contains("private host"));
        assertTrue(GmailFailure.describe(new SocketTimeoutException()).contains("timed out"));
        assertTrue(GmailFailure.describe(new javax.net.ssl.SSLHandshakeException("private details")).contains("date/time"));
    }
}
