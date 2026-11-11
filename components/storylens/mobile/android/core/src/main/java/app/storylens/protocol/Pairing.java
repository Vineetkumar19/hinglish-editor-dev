package app.storylens.protocol;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Map;

public final class Pairing {
    public final String origin;
    private final String token;
    private final byte[] key;
    private Pairing(String origin,String token,byte[] key){this.origin=origin;this.token=token;this.key=key.clone();}
    public static Pairing parse(String input) {
        if(input==null || input.length()>4096 || !input.startsWith("SL1."))throw new IllegalArgumentException("Enter the SL1 pairing code from your laptop.");
        Map<String,Object> data=Json.object(Json.parse(new String(Codec.decode(input.substring(4)),StandardCharsets.UTF_8)));
        if(Json.integer(data,"v")!=1)throw new IllegalArgumentException("Unsupported pairing version.");
        String origin=Json.string(data,"url"); URI uri;
        try {uri=URI.create(origin);}catch(Exception e){throw new IllegalArgumentException("Invalid relay address.");}
        String host=uri.getHost();
        if(!"https".equals(uri.getScheme()) || host==null || !host.equals(host.toLowerCase(java.util.Locale.ROOT)) || !host.endsWith(".workers.dev") || host.length()>253 || !host.matches("(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+workers\\.dev") || uri.getRawUserInfo()!=null || uri.getPort()!=-1 || uri.getRawQuery()!=null || uri.getRawFragment()!=null || !(uri.getRawPath().isEmpty()||uri.getRawPath().equals("/")))throw new IllegalArgumentException("Pair only with an HTTPS workers.dev relay origin.");
        String token=Json.string(data,"token");
        if(token.length()<16 || token.length()>512 || !token.matches("[A-Za-z0-9._~-]+"))throw new IllegalArgumentException("Invalid pairing token.");
        byte[] key=Codec.decode(Json.string(data,"key"));if(key.length!=32)throw new IllegalArgumentException("Pairing requires a 32-byte encryption key.");
        return new Pairing("https://"+host,token,key);
    }
    public byte[] key(){return key.clone();}
    public String authorization(){return "Bearer "+token;}
    @Override public String toString(){return "StoryLens pairing [private]";}
}
