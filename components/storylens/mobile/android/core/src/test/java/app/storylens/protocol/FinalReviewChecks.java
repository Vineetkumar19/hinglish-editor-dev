package app.storylens.protocol;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Bounded final probes, isolated from any real relay, phone or owner data. */
public final class FinalReviewChecks {
    private static int checks;
    interface Probe { void run()throws Exception; }
    static void reject(Probe p)throws Exception{boolean rejected=false;try{p.run();}catch(IllegalArgumentException|java.security.GeneralSecurityException e){rejected=true;}if(!rejected)throw new AssertionError("unsafe input accepted");checks++;}
    public static void main(String[] args)throws Exception{
        byte[] key=new byte[32];
        for(String url:new String[]{"https://x.workers.dev.","https://x.workers.dev/%2e%2e","https://x.workers.dev:443","https://x.workers.dev\\@127.0.0.1","https://xn--foo.workers.dev.evil.invalid"})reject(()->Pairing.parse(ProtocolChecks.pair(url,key)));
        reject(()->Transfer.chunk(Map.of("data","AA","offset",false,"next_offset",1,"eof",true),0,1,1));
        reject(()->Transfer.chunk(Map.of("data",Codec.encode(new byte[Transfer.CHUNK+1]),"offset",0,"next_offset",Transfer.CHUNK+1,"eof",true),0,Transfer.CHUNK,Transfer.CHUNK+1));
        Codec codec=new Codec(key);AtomicInteger pushed=new AtomicInteger(),warned=new AtomicInteger();List<Map<String,Object>> inbox=new ArrayList<>();
        Tunnel invalid=new Tunnel((method,path,body)->{
            if(method.equals("POST")){pushed.incrementAndGet();Map<String,Object> request=codec.open(Json.object(Json.parse(body)));Map<String,Object> forged=new java.util.LinkedHashMap<>(codec.seal(Json.string(request,"id"),Map.of("id",request.get("id"),"ok",true,"result",Map.of("success",true))));byte[] bytes=Codec.decode((String)forged.get("data"));bytes[0]^=1;forged.put("data",Codec.encode(bytes));synchronized(inbox){inbox.add(forged);}return "{}";}
            Thread.sleep(10);synchronized(inbox){List<Map<String,Object>> copy=new ArrayList<>(inbox);inbox.clear();return Json.stringify(Map.of("messages",copy));}
        },codec,s->{if(s.startsWith("An invalid"))warned.incrementAndGet();},350);
        invalid.start();try{invalid.request("send",Map.of()).get(2,TimeUnit.SECONDS);throw new AssertionError("forged response completed action");}catch(java.util.concurrent.ExecutionException expected){}finally{invalid.close();}
        if(pushed.get()!=1||warned.get()!=1)throw new AssertionError("forged reply handling or action retry");checks++;
        if(!Transfer.safeName("..\\..\\outside.txt").equals("outside.txt"))throw new AssertionError("path escape");checks++;
        if(!Transfer.safeName("\u0000bad:name.pdf").equals("_bad_name.pdf"))throw new AssertionError("unsafe filename");checks++;
        boolean bomRejected=false;
        try{Pairing.parse(("\uFEFF"+ProtocolChecks.pair("https://test.account.workers.dev",key)).trim());}catch(IllegalArgumentException expected){bomRejected=true;}
        if(!bomRejected)throw new AssertionError("BOM finding changed; update review receipt");
        System.out.println("Final isolated boundary probes passed: "+checks+".");
        System.out.println("CONFIRMED F1 (unfixed): UTF-8 BOM-prefixed .slconnect text is rejected. Parent must write UTF-8 without BOM. Reproduced in JVM using the importer trim path; not a device test.");
    }
}
