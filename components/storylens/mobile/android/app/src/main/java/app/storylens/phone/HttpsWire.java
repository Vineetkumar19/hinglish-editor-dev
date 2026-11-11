package app.storylens.phone;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.URL;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;
import javax.net.ssl.HttpsURLConnection;
import app.storylens.protocol.Json;
import app.storylens.protocol.Pairing;
import app.storylens.protocol.Tunnel;

final class HttpsWire implements Tunnel.Wire,AutoCloseable {
    private final Pairing pairing;
    private final Set<HttpsURLConnection> connections=Collections.synchronizedSet(new HashSet<>());
    private volatile boolean closed;
    HttpsWire(Pairing p){pairing=p;}
    @Override public String exchange(String method,String path,String body)throws Exception{
        if(closed)throw new java.io.IOException("Phone connection closed.");
        if(!path.equals("/v1/push")&&!path.equals("/v1/pull?wait=20"))throw new java.io.IOException("Unsupported relay endpoint.");
        HttpsURLConnection c=(HttpsURLConnection)new URL(pairing.origin+path).openConnection();
        synchronized(connections){if(closed){c.disconnect();throw new java.io.IOException("Connection closed.");}connections.add(c);}
        try{
            c.setRequestMethod(method);c.setConnectTimeout(12000);c.setReadTimeout(30000);c.setInstanceFollowRedirects(false);c.setUseCaches(false);
            c.setRequestProperty("Authorization",pairing.authorization());c.setRequestProperty("Accept","application/json");
            if(body!=null){byte[] bytes=body.getBytes(java.nio.charset.StandardCharsets.UTF_8);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=c.getOutputStream()){out.write(bytes);}}
            int status=c.getResponseCode();if(status<200||status>=300)throw new java.io.IOException("Relay request unavailable ("+status+").");
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] buffer=new byte[8192];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>Json.MAX_JSON)throw new java.io.IOException("Relay message exceeds phone limit.");out.write(buffer,0,n);}return out.toString("UTF-8");
            }
        }finally{connections.remove(c);c.disconnect();}
    }
    @Override public void close(){closed=true;synchronized(connections){for(HttpsURLConnection c:connections)c.disconnect();connections.clear();}}
}
