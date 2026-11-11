package in.pocketledger.app;
import android.content.Context;
import org.json.*;
import in.pocketledger.core.*;
import java.io.*;
import java.util.*;

/** Shared, local data contract for bundled mobile UI and the paired laptop. */
public final class DashboardApi {
    private static JSONArray cachedSafety; private static long revision=-1; private static Ledger cached; private static List<Message> messages;
    private static synchronized Ledger ledger(Context c)throws Exception{
        long current=Store.REVISION.get();if(cached==null||revision!=current){try(Store s=new Store(c)){messages=s.all();cached=Ledger.build(messages);cachedSafety=null;revision=current;}}return cached;
    }
    private static JSONObject event(Event e)throws Exception{return new JSONObject().put("id",e.message.id).put("time",e.time).put("amount",e.paise).put("direction",e.direction).put("merchant",e.merchant).put("account",e.account).put("bank",e.bank).put("instrument",e.instrument).put("paymentApp",e.paymentApp).put("channel",e.channel).put("status",e.status).put("kind",e.kind).put("source",e.message.source).put("note",e.note).put("issue",e.risk.isEmpty()?e.issue:e.risk);}
    public static synchronized JSONObject snapshot(Context c)throws Exception{
        Ledger l=ledger(c);JSONArray tx=new JSONArray(),pending=new JSONArray(),safety=new JSONArray(),reports=new JSONArray();
        for(Ledger.Transaction t:l.transactions)tx.put(event(t.event).put("source",t.sources()).put("note",t.notes()).put("bank",t.bank()).put("instrument",t.instrument()).put("paymentApp",t.paymentApp()).put("channel",t.channel()).put("transfer",t.internalTransfer));
        for(Event e:l.unresolved)pending.put(event(e));
        for(Event e:l.nonPosted)pending.put(event(e).put("issue",e.status+" · excluded from totals"));
        if(cachedSafety==null){for(Event e:l.classified){Message m=e.message;List<String> categories=Safety.categories(e);if(!categories.isEmpty())safety.put(new JSONObject().put("id",m.id).put("time",m.receivedAt).put("sender",m.sender).put("subject",m.body.split("\n",2)[0]).put("source",m.source).put("categories",new JSONArray(categories)).put("reason",e.risk));}cachedSafety=safety;}else safety=cachedSafety;
        File[] files=new File(c.getFilesDir(),"reports").listFiles((d,n)->n.endsWith(".pdf"));if(files!=null){Arrays.sort(files,Comparator.comparingLong(File::lastModified).reversed());for(File f:files)reports.put(new JSONObject().put("name",f.getName()).put("size",f.length()).put("time",f.lastModified()));}
        JSONObject health=new JSONObject().put("sms",Prefs.text(c,"sms_health","Permission needed")).put("gmail",Prefs.text(c,"gmail_health","Not connected")).put("gmailTime",Prefs.get(c).getLong("gmail_checkpoint",0)).put("safety",Prefs.text(c,"safety_health","Automatic categorization pending")).put("alerts",PaymentNotifications.allowed(c)).put("smsAllowed",SmsCollector.allowed(c)).put("wifi",Prefs.get(c).getBoolean("wifi_enabled",false));
        return new JSONObject().put("transactions",tx).put("pending",pending).put("safety",safety).put("reports",reports).put("plan",plan(c)).put("health",health).put("generatedAt",System.currentTimeMillis());
    }
    public static synchronized JSONObject plan(Context c)throws Exception{String encrypted=Prefs.text(c,"finance_plan","");return encrypted.isEmpty()?new JSONObject().put("budget",0).put("recurring",new JSONArray()):new JSONObject(Crypto.decrypt(encrypted));}
    public static synchronized JSONObject command(Context c,JSONObject req)throws Exception{
        switch(req.getString("action")){
            case "savePlan":{
                JSONObject p=req.getJSONObject("plan");long budget=p.getLong("budget");if(budget<0||budget>100000000000L)throw new IllegalArgumentException("Invalid budget");
                JSONArray rows=p.getJSONArray("recurring"),clean=new JSONArray();if(rows.length()>200)throw new IllegalArgumentException("Too many recurring payments");
                Set<String> ids=new HashSet<>();for(int i=0;i<rows.length();i++){JSONObject r=rows.getJSONObject(i);String name=r.getString("name").trim(),id=r.getString("id");long amount=r.getLong("amount");int day=r.getInt("day");if(name.isEmpty()||name.length()>100||id.length()>80||!ids.add(id)||amount<=0||amount>100000000000L||day<1||day>31)throw new IllegalArgumentException("Invalid recurring payment");clean.put(new JSONObject().put("id",id).put("name",name).put("amount",amount).put("day",day).put("active",r.getBoolean("active")));}
                JSONObject safe=new JSONObject().put("budget",budget).put("recurring",clean);Prefs.set(c,"finance_plan",Crypto.encrypt(safe.toString()));LiveUpdates.changed(c);return safe;
            }
            case "preview":{
                java.time.YearMonth selected=java.time.YearMonth.parse(req.optString("month",java.time.YearMonth.now(Parser.ZONE).toString()));
                if(selected.isAfter(java.time.YearMonth.now(Parser.ZONE)))throw new IllegalArgumentException("Choose a current or past month");
                File file=Reports.generate(c,selected,true);return new JSONObject().put("ok",true).put("file",file.getName());
            }
            case "sync":LedgerApp.sync(c);return new JSONObject().put("ok",true);
            case "detail":{
                Ledger l=ledger(c);String id=req.getString("id");for(Ledger.Transaction t:l.transactions)if(t.event.message.id.equals(id)){StringBuilder out=new StringBuilder();for(Event e:t.evidence)out.append(e.message.source).append(" · ").append(e.message.sender).append("\n").append(e.message.body).append("\n\n");return new JSONObject().put("body",out.toString());}
                for(Message m:messages)if(m.id.equals(id))return new JSONObject().put("body",m.sender+"\n\n"+m.body);throw new IllegalArgumentException("Message unavailable");
            }
            default:throw new IllegalArgumentException("Unknown action");
        }
    }
    public static File report(Context c,String name)throws IOException{if(!name.matches("PocketTracker_[0-9]{4}-[0-9]{2}(?:_preview)?_v[0-9]+\\.pdf"))throw new IOException("Invalid report");File f=new File(new File(c.getFilesDir(),"reports"),name);if(!f.isFile())throw new FileNotFoundException();return f;}
}
