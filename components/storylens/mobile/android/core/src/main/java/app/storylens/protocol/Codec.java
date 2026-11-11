package app.storylens.protocol;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

public final class Codec {
    private final SecretKeySpec key;
    private final SecureRandom random=new SecureRandom();
    public Codec(byte[] raw){if(raw.length!=32)throw new IllegalArgumentException("AES-256 key required.");key=new SecretKeySpec(raw.clone(),"AES");}
    public static String encode(byte[] b){return Base64.getUrlEncoder().withoutPadding().encodeToString(b);}
    public static byte[] decode(String s){
        if(s==null||s.length()>Json.MAX_JSON||!s.matches("[A-Za-z0-9_-]*"))throw new IllegalArgumentException("Invalid base64url.");
        byte[] b=Base64.getUrlDecoder().decode(s);if(!encode(b).equals(s))throw new IllegalArgumentException("Noncanonical base64url.");return b;
    }
    public Map<String,Object> seal(String id,Map<String,Object> data)throws GeneralSecurityException{
        Rpc.validateId(id);if(!id.equals(Json.string(data,"id")))throw new IllegalArgumentException("Message identity differs.");
        byte[] nonce=new byte[12];random.nextBytes(nonce);
        Cipher c=cipher(Cipher.ENCRYPT_MODE,id,nonce);
        Map<String,Object> envelope=new LinkedHashMap<>();envelope.put("v",1);envelope.put("id",id);envelope.put("nonce",encode(nonce));envelope.put("data",encode(c.doFinal(Json.stringify(data).getBytes(StandardCharsets.UTF_8))));return envelope;
    }
    public Map<String,Object> open(Map<String,Object> envelope)throws GeneralSecurityException{
        if(Json.integer(envelope,"v")!=1)throw new IllegalArgumentException("Unsupported message version.");
        String id=Json.string(envelope,"id");Rpc.validateId(id);byte[] nonce=decode(Json.string(envelope,"nonce"));if(nonce.length!=12)throw new IllegalArgumentException("Invalid nonce.");
        byte[] data=decode(Json.string(envelope,"data"));if(data.length<16)throw new IllegalArgumentException("Missing authentication tag.");
        Map<String,Object> message=Json.object(Json.parse(new String(cipher(Cipher.DECRYPT_MODE,id,nonce).doFinal(data),StandardCharsets.UTF_8)));
        if(!id.equals(Json.string(message,"id")))throw new IllegalArgumentException("Message identity differs.");return message;
    }
    private Cipher cipher(int mode,String id,byte[] nonce)throws GeneralSecurityException{
        Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(mode,key,new GCMParameterSpec(128,nonce));c.updateAAD(("storylens-personal-v1|"+id).getBytes(StandardCharsets.UTF_8));return c;
    }
}
