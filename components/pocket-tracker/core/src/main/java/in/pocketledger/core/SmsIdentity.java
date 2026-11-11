package in.pocketledger.core;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
public final class SmsIdentity {
    private SmsIdentity() {}
    public static String key(String sender,String body,long sentAt) {
        return "sms-live:"+digest(sender+"\u0000"+body+"\u0000"+sentAt);
    }
    public static String digest(String value) {
        try {byte[] bytes=MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8));StringBuilder out=new StringBuilder();for(byte b:bytes)out.append(String.format("%02x",b));return out.toString();}
        catch(java.security.NoSuchAlgorithmException e){throw new IllegalStateException(e);}
    }
}
