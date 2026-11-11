package app.storylens.protocol;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

public final class TunnelChecks {
    public static void main(String[] args)throws Exception {
        byte[] key=new byte[32];Codec codec=new Codec(key);
        AtomicInteger pushes=new AtomicInteger();List<Map<String,Object>> inbox=new ArrayList<>();
        Tunnel.Wire wire=(method,path,body)->{
            if(method.equals("POST")){
                pushes.incrementAndGet();Map<String,Object> env=Json.object(Json.parse(body));Map<String,Object> req=codec.open(env);
                Map<String,Object> response=codec.seal(Json.string(req,"id"),Map.of("id",req.get("id"),"ok",true,"result",Map.of("connected",true)));
                synchronized(inbox){inbox.add(response);}return "{\"ok\":true}";
            }
            Thread.sleep(15);synchronized(inbox){List<Map<String,Object>> copy=new ArrayList<>(inbox);inbox.clear();return Json.stringify(Map.of("messages",copy));}
        };
        Tunnel t=new Tunnel(wire,codec,s->{},1200);t.start();
        Map<String,Object> got=t.request("state",Map.of()).get(2,TimeUnit.SECONDS);
        if(!Boolean.TRUE.equals(got.get("connected")))throw new AssertionError("pull dispatch");
        t.close();
        if(pushes.get()!=1)throw new AssertionError("one push per request");
        AtomicInteger failures=new AtomicInteger();
        Tunnel broken=new Tunnel((method,path,body)->{if(method.equals("POST")){failures.incrementAndGet();throw new IOException("socket closed");}Thread.sleep(20);return "{\"messages\":[]}";},codec,s->{},100);
        broken.start();CompletableFuture<Map<String,Object>> pending=broken.request("send",Map.of());
        try{pending.get(1,TimeUnit.SECONDS);throw new AssertionError("failed send reported as success");}catch(java.util.concurrent.ExecutionException expected){}
        Thread.sleep(150);broken.close();if(failures.get()!=1)throw new AssertionError("blind action retry");
        Tunnel stopped=new Tunnel(wire,codec,s->{},100);stopped.start();stopped.close();
        if(!stopped.request("state",Map.of()).isCompletedExceptionally())throw new AssertionError("closed transport accepts command");
        System.out.println("Tunnel integration checks passed: dispatch, exactly-once push, no action retry, lifecycle close");
    }
}
