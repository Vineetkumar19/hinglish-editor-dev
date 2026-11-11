package in.pocketledger.app;
import android.content.*;
import android.database.*;
import android.database.sqlite.*;
import org.json.*;
import java.util.*;
import in.pocketledger.core.*;

public final class Store extends SQLiteOpenHelper {
    private static final Object SMS_LOCK=new Object();
    private static final Map<String,Map<String,Message>> CACHES=new java.util.concurrent.ConcurrentHashMap<>();
    static final java.util.concurrent.atomic.AtomicLong REVISION=new java.util.concurrent.atomic.AtomicLong();
    private final String cacheName;
    public Store(Context c) { this(c,"ledger.db"); }
    Store(Context c,String name) {super(c,name,null,2);cacheName=c.getDatabasePath(name).getAbsolutePath();setWriteAheadLoggingEnabled(true);}
    private static void smsSchema(SQLiteDatabase d){d.execSQL("CREATE TABLE IF NOT EXISTS sms_links(signature TEXT PRIMARY KEY, provider_id TEXT NOT NULL)");}
    @Override public void onCreate(SQLiteDatabase d) { d.execSQL("CREATE TABLE messages(id TEXT PRIMARY KEY, received INTEGER NOT NULL, source TEXT NOT NULL, encrypted TEXT NOT NULL)"); d.execSQL("CREATE INDEX received_idx ON messages(received)");smsSchema(d); }
    @Override public void onUpgrade(SQLiteDatabase d,int old,int version) { if(old<2)smsSchema(d); }
    public boolean putLiveSms(String sender,String body,long sentAt,long receivedAt) throws Exception {
        synchronized(SMS_LOCK){SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            String key=SmsIdentity.key(sender,body,sentAt);
            try(Cursor row=d.rawQuery("SELECT 1 FROM sms_links WHERE signature=?",new String[]{key})){if(row.moveToFirst()){d.setTransactionSuccessful();return false;}}
            // A provider that omits date_sent may finish before this receiver gets CPU time.
            List<String> existing=new ArrayList<>();
            try(Cursor rows=d.rawQuery("SELECT id,encrypted FROM messages WHERE source='SMS' AND id LIKE 'sms:%' AND received BETWEEN ? AND ?",new String[]{String.valueOf(receivedAt-5000),String.valueOf(receivedAt+5000)})){
                while(rows.moveToNext()){JSONObject o=new JSONObject(Crypto.decrypt(rows.getString(1)));if(sender.equals(o.getString("sender"))&&body.equals(o.getString("body")))existing.add(rows.getString(0));}
            }
            if(existing.size()==1){ContentValues link=new ContentValues();link.put("signature",key);link.put("provider_id",existing.get(0));d.insertWithOnConflict("sms_links",null,link,SQLiteDatabase.CONFLICT_IGNORE);d.setTransactionSuccessful();return false;}
            boolean added=put(new Message(key,"SMS",sender,body,receivedAt));d.setTransactionSuccessful();return added;
        }finally{d.endTransaction();}}
    }
    public boolean putProviderSms(Message m,long sentAt) throws Exception {
        synchronized(SMS_LOCK){SQLiteDatabase d=getWritableDatabase();d.beginTransaction();try{
            boolean added=put(m);
            try(Cursor row=d.rawQuery("SELECT 1 FROM messages WHERE id=?",new String[]{m.id})){if(!row.moveToFirst()){d.setTransactionSuccessful();return false;}}
            String key=sentAt>0?SmsIdentity.key(m.sender,m.body,sentAt):"";
            if(key.isEmpty()) {
                // Some providers omit date_sent. Reconcile only one exact-content live receipt.
                List<String> matches=new ArrayList<>();
                try(Cursor rows=d.rawQuery("SELECT id,encrypted FROM messages WHERE id LIKE 'sms-live:%' AND received BETWEEN ? AND ?",new String[]{String.valueOf(m.receivedAt-5000),String.valueOf(m.receivedAt+5000)})){
                    while(rows.moveToNext()){JSONObject o=new JSONObject(Crypto.decrypt(rows.getString(1)));if(m.sender.equals(o.getString("sender"))&&m.body.equals(o.getString("body")))matches.add(rows.getString(0));}
                }
                if(matches.size()==1)key=matches.get(0);
            }
            if(!key.isEmpty()) {if(d.delete("messages","id=?",new String[]{key})>0)REVISION.incrementAndGet();ContentValues v=new ContentValues();v.put("signature",key);v.put("provider_id",m.id);d.insertWithOnConflict("sms_links",null,v,SQLiteDatabase.CONFLICT_IGNORE);}
            d.setTransactionSuccessful();return added;
        }finally{d.endTransaction();}}
    }
    public synchronized boolean put(Message m) throws Exception {
        try(Cursor row=getReadableDatabase().rawQuery("SELECT encrypted FROM messages WHERE id=?",new String[]{m.id})){if(row.moveToFirst()){
            if(!m.safetyLabel.isEmpty()){JSONObject old=new JSONObject(Crypto.decrypt(row.getString(0)));if(!m.safetyLabel.equals(old.optString("safetyLabel"))){old.put("safetyLabel",m.safetyLabel);ContentValues update=new ContentValues();update.put("encrypted",Crypto.encrypt(old.toString()));getWritableDatabase().update("messages",update,"id=?",new String[]{m.id});Map<String,Message> cache=CACHES.get(cacheName);if(cache!=null)cache.remove(m.id);REVISION.incrementAndGet();}}
            return false;}}
        Event e=new Parser().parse(m);
        // Never persist ordinary personal messages or OTPs. Classification occurs locally.
        if(!e.financial&&e.risk.isEmpty()&&!e.kind.equals("Promotional"))return false;
        if(m.body.length()>200000)throw new IllegalArgumentException("Message exceeds size limit");
        JSONObject obj=new JSONObject().put("sender",m.sender).put("body",m.body).put("safetyLabel",m.safetyLabel);
        ContentValues v=new ContentValues(); v.put("id",m.id);v.put("received",m.receivedAt);v.put("source",m.source);v.put("encrypted",Crypto.encrypt(obj.toString()));
        boolean added=getWritableDatabase().insertWithOnConflict("messages",null,v,SQLiteDatabase.CONFLICT_IGNORE)!=-1;
        if(added)REVISION.incrementAndGet();return added;
    }
    public synchronized List<Message> all() throws Exception {
        List<Message> list=new ArrayList<>();Map<String,Message> cache=CACHES.computeIfAbsent(cacheName,k->new java.util.concurrent.ConcurrentHashMap<>());
        try(Cursor c=getReadableDatabase().query("messages",null,null,null,null,null,"received DESC")) {
            while(c.moveToNext()) {String id=c.getString(c.getColumnIndexOrThrow("id"));Message m=cache.get(id);if(m==null){JSONObject o=new JSONObject(Crypto.decrypt(c.getString(c.getColumnIndexOrThrow("encrypted"))));m=new Message(id,c.getString(c.getColumnIndexOrThrow("source")),o.getString("sender"),o.getString("body"),c.getLong(c.getColumnIndexOrThrow("received")),o.optString("safetyLabel"));cache.put(id,m);}list.add(m);}
        }
        return list;
    }
    public Set<String> ids(String source){Set<String> ids=new HashSet<>();try(Cursor c=getReadableDatabase().query("messages",new String[]{"id"},"source=?",new String[]{source},null,null,null)){while(c.moveToNext())ids.add(c.getString(0));}return ids;}
    public synchronized int count() { try(Cursor c=getReadableDatabase().rawQuery("SELECT count(*) FROM messages",null)) { c.moveToFirst(); return c.getInt(0); } }
}
