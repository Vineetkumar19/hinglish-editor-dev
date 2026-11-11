package app.storylens.protocol;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Dependency-free JVM contracts; never contacts a relay. */
public final class ProtocolChecks {
    private static int checks;
    interface Checked { void run() throws Exception; }
    private static void check(boolean value, String name) {
        checks++; if (!value) throw new AssertionError(name);
    }
    private static void reject(Checked action, String name) throws Exception {
        boolean rejected = false;
        try { action.run(); } catch (IllegalArgumentException | java.security.GeneralSecurityException e) { rejected = true; }
        check(rejected, name);
    }
    static String pair(String url, byte[] key) {
        return "SL1." + Codec.encode(Json.stringify(Map.of("v", 1, "url", url, "token", "unit-test-not-a-real-token", "key", Codec.encode(key))).getBytes(StandardCharsets.UTF_8));
    }
    public static void main(String[] args) throws Exception {
        byte[] key = new byte[32]; Arrays.fill(key, (byte) 11);
        Pairing pairing = Pairing.parse(pair("https://personal-test.workers.dev", key));
        check(pairing.origin.equals("https://personal-test.workers.dev"), "canonical relay origin");
        for (String url : new String[]{"http://x.workers.dev", "https://workers.dev", "https://x.workers.dev.evil.test", "https://x.workers.dev@evil.test", "https://x.workers.dev:8443", "https://x.workers.dev/path", "https://x.workers.dev?token=x", "https://x.workers.dev#fragment", "https://127.0.0.1", "https://user@x.workers.dev", "https://bad..workers.dev"}) {
            reject(() -> Pairing.parse(pair(url, key)), "reject untrusted origin " + url);
        }
        reject(() -> Pairing.parse(pair("https://x.workers.dev", new byte[16])), "AES-256 only");
        reject(() -> Pairing.parse("SL1.%%%"), "invalid pairing base64");
        reject(() -> Pairing.parse(pair("https://x.workers.dev", key) + "="), "noncanonical pairing base64");
        reject(() -> Json.parse("{\"v\":1,\"v\":2}"), "duplicate JSON keys");
        reject(() -> Json.parse("{\"x\":NaN}"), "invalid number");
        reject(() -> Json.parse("{\"x\":1} trailing"), "trailing JSON");
        reject(() -> Json.parse("[".repeat(40) + "0" + "]".repeat(40)), "bounded nesting");
        String id = UUID.randomUUID().toString();
        Codec codec = new Codec(pairing.key());
        Map<String,Object> request = Rpc.request(id, "send", Map.of("chat", "c1", "request_id", id, "message", "Hello दुनिया", "attachments", java.util.List.of(), "profile", "general"));
        Map<String,Object> envelope = codec.seal(id, request);
        check(Json.stringify(codec.open(envelope)).equals(Json.stringify(request)), "authenticated UTF8 roundtrip");
        check(Codec.decode(Json.string(envelope, "nonce")).length == 12, "96 bit nonce");
        check(!envelope.get("nonce").equals(codec.seal(id, request).get("nonce")), "fresh random nonce");
        Map<String,Object> tampered = new LinkedHashMap<>(envelope);
        tampered.put("id", UUID.randomUUID().toString());
        final Map<String,Object> badId = tampered;
        reject(() -> codec.open(badId), "AAD binds request ID");
        tampered = new LinkedHashMap<>(envelope);
        byte[] cipher = Codec.decode(Json.string(envelope, "data")); cipher[0] ^= 1;
        tampered.put("data", Codec.encode(cipher));
        final Map<String,Object> badCipher = tampered;
        reject(() -> codec.open(badCipher), "tamper rejected");
        reject(() -> codec.seal(id, Map.of("id", UUID.randomUUID().toString())), "inner outer ID match");
        reject(() -> Rpc.request(id, "execute_shell", Map.of()), "method allowlist");
        reject(() -> Rpc.request("not-a-uuid", "state", Map.of()), "canonical UUID");
        check(Rpc.isReadOnly("state") && Rpc.isReadOnly("chat") && !Rpc.isReadOnly("send"), "read-only distinction");
        reject(() -> Transfer.validateSize(Transfer.MAX_FILE + 1), "file size bound");
        reject(() -> Transfer.validateSize(-1), "negative size");
        byte[] body = {1,2,3};
        check(Arrays.equals(body, Transfer.chunk(Map.of("data",Codec.encode(body),"offset",0,"next_offset",3,"eof",true),0,3,3)), "exact chunk accepted");
        reject(() -> Transfer.chunk(Map.of("data",Codec.encode(body),"offset",1,"next_offset",4,"eof",true),0,3,3), "offset mismatch");
        reject(() -> Transfer.chunk(Map.of("data",Codec.encode(body),"offset",0,"next_offset",2,"eof",true),0,3,3), "next offset mismatch");
        reject(() -> Transfer.chunk(Map.of("data",Codec.encode(body),"offset",0,"next_offset",3,"eof",false),0,3,3), "eof consistency");
        reject(() -> Transfer.chunk(Map.of("data","","offset",0,"next_offset",0,"eof",false),0,3,3), "no-progress chunk");
        check(Transfer.safeName("../../private\\x.txt").equals("x.txt"), "untrusted names not paths");
        check(!pairing.toString().contains("unit-test"), "pairing never prints secrets");
        Map<String,Object> unicode = Json.object(Json.parse(Json.stringify(Map.of("s", "a\n\"\\😀"))));
        check(unicode.get("s").equals("a\n\"\\😀"), "JSON escapes and unicode");
        byte[] vectorKey = new byte[32]; for(int i=0;i<32;i++)vectorKey[i]=(byte)i;
        javax.crypto.Cipher pythonVector=javax.crypto.Cipher.getInstance("AES/GCM/NoPadding");
        pythonVector.init(javax.crypto.Cipher.DECRYPT_MODE,new javax.crypto.spec.SecretKeySpec(vectorKey,"AES"),new javax.crypto.spec.GCMParameterSpec(128,Codec.decode("AAECAwQFBgcICQoL")));
        pythonVector.updateAAD("storylens-personal-v1|vector01-1234-5678-9876-112233445566".getBytes(StandardCharsets.UTF_8));
        String vectorPlain=new String(pythonVector.doFinal(Codec.decode("PCC_f-ff4G3oIuPkw9lJQLLktADdTmlLAErcvSpfLYMwIpzPnPUmrUGSSc-kpUVdmjEP6XjsgalL9l58Os_XnpFOpxeg8xwaYSkMluIqEGlAkA2wvmhABYRq")),StandardCharsets.UTF_8);
        check(vectorPlain.equals("{\"id\":\"vector01-1234-5678-9876-112233445566\",\"method\":\"state\",\"params\":{}}"),"exact Python AES-GCM vector");
        check(Pairing.parse(pair("https://personal.account.workers.dev",key)).origin.equals("https://personal.account.workers.dev"),"normal Workers account subdomain");
        System.out.println("Protocol checks passed: " + checks);
    }
}
