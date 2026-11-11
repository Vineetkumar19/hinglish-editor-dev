package app.storylens.protocol;

import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

/** Foreground request/reply transport. Only the read-only pull loop reconnects automatically. */
public final class Tunnel implements AutoCloseable {
    public interface Wire { String exchange(String method,String path,String body)throws Exception; }
    public static final class RemoteError extends IOException {
        public final String code;
        public RemoteError(String code,String message){super(message);this.code=code;}
    }
    private final Wire wire;
    private final Codec codec;
    private final Consumer<String> status;
    private final long timeout;
    private final ConcurrentHashMap<String,CompletableFuture<Map<String,Object>>> pending=new ConcurrentHashMap<>();
    private final ExecutorService posts=Executors.newFixedThreadPool(2);
    private final ScheduledExecutorService clock=Executors.newSingleThreadScheduledExecutor();
    private volatile boolean active,closed;
    private Thread reader;
    public Tunnel(Wire wire,Codec codec,Consumer<String> status,long timeout){this.wire=wire;this.codec=codec;this.status=status;this.timeout=timeout;}
    public synchronized void start(){if(closed||active)return;active=true;reader=new Thread(this::pull,"StoryLens-pull");reader.start();}
    public CompletableFuture<Map<String,Object>> request(String method,Map<String,Object> params){return request(UUID.randomUUID().toString(),method,params);}
    public synchronized CompletableFuture<Map<String,Object>> request(String id,String method,Map<String,Object> params){
        CompletableFuture<Map<String,Object>> future=new CompletableFuture<>();
        if(!active||closed){future.completeExceptionally(new IOException("Connection is paused. Reopen StoryLens and check the chat."));return future;}
        final Map<String,Object> plain;
        try{plain=Rpc.request(id,method,params);}catch(Exception e){future.completeExceptionally(e);return future;}
        if(pending.putIfAbsent(id,future)!=null){future.completeExceptionally(new IOException("This request is already awaiting its reply."));return future;}
        java.util.concurrent.ScheduledFuture<?> timer=clock.schedule(()->{if(pending.remove(id,future))future.completeExceptionally(new IOException(Rpc.isReadOnly(method)?"Laptop has not replied. Check its connection and refresh.":"Delivery is not confirmed. Check the chat before trying another action; the laptop may have received this one."));},timeout,TimeUnit.MILLISECONDS);
        future.whenComplete((r,e)->timer.cancel(false));
        posts.execute(()->{
            try{String reply=wire.exchange("POST","/v1/push",Json.stringify(codec.seal(id,plain)));
                // A relay acknowledgement is not a completed laptop action.
                if(reply!=null&&!reply.isEmpty()){Map<String,Object> value=Json.object(Json.parse(reply));if(value.containsKey("nonce"))deliver(value);}
            }catch(Exception e){if(pending.remove(id,future))future.completeExceptionally(new IOException(Rpc.isReadOnly(method)?"Relay unavailable. Reconnect and refresh.":"Delivery is not confirmed. Refresh the chat before sending again."));}
        });return future;
    }
    private void deliver(Map<String,Object> envelope)throws Exception{
        Map<String,Object> plain=codec.open(envelope);String id=Json.string(plain,"id");CompletableFuture<Map<String,Object>> f=pending.get(id);if(f==null)return;
        boolean ok=Boolean.TRUE.equals(plain.get("ok"));
        if(ok){Map<String,Object> result=Json.object(plain.get("result"));if(pending.remove(id,f))f.complete(result);}
        else if(Boolean.FALSE.equals(plain.get("ok"))){Map<String,Object> error=Json.object(plain.get("error"));String message=Json.string(error,"message"),code=Json.string(error,"code");if(pending.remove(id,f))f.completeExceptionally(new RemoteError(code,message));}
        else throw new IllegalArgumentException("Missing response status.");
    }
    private void pull(){int failures=0;while(active){try{
        Map<String,Object> reply=Json.object(Json.parse(wire.exchange("GET","/v1/pull?wait=20",null)));
        Object messages=reply.get("messages");if(!(messages instanceof List))throw new IOException("Invalid relay response.");
        for(Object item:(List<?>)messages){try{deliver(Json.object(item));}catch(Exception bad){status.accept("An invalid encrypted reply was rejected. Refresh the chat.");}}
        failures=0;status.accept("Relay connected · checking laptop");Thread.sleep(150);
    }catch(Exception e){if(!active)break;failures=Math.min(failures+1,5);status.accept("Reconnecting to relay · laptop work continues");try{Thread.sleep(Math.min(15000,500L*(1<<failures)));}catch(InterruptedException stopped){break;}}}}
    @Override public synchronized void close(){if(closed)return;closed=true;active=false;if(reader!=null)reader.interrupt();posts.shutdownNow();clock.shutdownNow();for(CompletableFuture<Map<String,Object>> f:pending.values())f.completeExceptionally(new IOException("Phone connection paused. Laptop work continues; refresh on return."));pending.clear();}
}
