package in.pocketledger.app;
import android.accounts.Account;
import android.content.Context;
import android.text.Html;
import android.util.Base64;
import com.google.android.gms.auth.api.identity.*;
import com.google.android.gms.common.api.Scope;
import com.google.android.gms.tasks.Tasks;
import org.json.*;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;
import in.pocketledger.core.Message;

public final class GmailClient {
    public static final String SCOPE="https://www.googleapis.com/auth/gmail.readonly";
    public static AuthorizationRequest request(Context c) {
        AuthorizationRequest.Builder b=AuthorizationRequest.builder().setRequestedScopes(Collections.singletonList(new Scope(SCOPE)));
        String email=Prefs.text(c,"gmail_account","");if(!email.isEmpty()) b.setAccount(new Account(email,"com.google"));
        return b.build();
    }
    public static String token(Context c) throws Exception {
        AuthorizationResult r=Tasks.await(Identity.getAuthorizationClient(c).authorize(request(c)),45,TimeUnit.SECONDS);
        if(r.hasResolution())throw new SecurityException("Gmail requires authorization in Setup");
        if(r.getAccessToken()==null)throw new SecurityException("No Gmail access token");
        return r.getAccessToken();
    }
    public static JSONObject get(String path,String token) throws Exception {
        // Only fixed Gmail API paths are supplied by this class. Never follow message links.
        URL url=new URL("https://gmail.googleapis.com/gmail/v1/users/me/"+path);
        HttpURLConnection conn=(HttpURLConnection)url.openConnection();conn.setInstanceFollowRedirects(false);conn.setConnectTimeout(20000);conn.setReadTimeout(20000);conn.setRequestProperty("Authorization","Bearer "+token);
        try {
            int code=conn.getResponseCode(); if(code!=200)throw GmailFailure.fromResponse(code,conn.getErrorStream());
            try(InputStream in=conn.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()) {
                byte[] bytes=new byte[8192];int n;
                while((n=in.read(bytes))!=-1) { if(out.size()+n>2_000_000)throw new IOException("Email response exceeds local size limit");out.write(bytes,0,n); }
                return new JSONObject(out.toString("UTF-8"));
            }
        } finally { conn.disconnect(); }
    }
    public static void connected(Context c,String token) throws Exception {
        JSONObject profile=get("profile",token);
        Prefs.set(c,"gmail_account",profile.getString("emailAddress"));Prefs.get(c).edit().putBoolean("gmail_enabled",true).apply();
        Prefs.set(c,"gmail_health","Connected · first sync pending");
    }
    private static String enc(String s) { try{return URLEncoder.encode(s,"UTF-8");}catch(Exception e){throw new IllegalStateException(e);} }
    private static String body(JSONObject p) {
        String type=p.optString("mimeType");
        if(type.equals("text/plain")||type.equals("text/html")) {
            String data=p.optJSONObject("body")==null?"":p.optJSONObject("body").optString("data");
            if(!data.isEmpty()) { String v=new String(Base64.decode(data,Base64.URL_SAFE),StandardCharsets.UTF_8); return type.equals("text/html")?Html.fromHtml(v.replaceAll("(?is)<(?:style|script)\\b[^>]*>.*?</(?:style|script)>"," ").replaceAll("(?i)</(?:td|th|div|p|tr)>","$0 "),Html.FROM_HTML_MODE_LEGACY).toString():v; }
        }
        JSONArray parts=p.optJSONArray("parts");if(parts==null)return "";
        if(type.equals("multipart/alternative")) { for(int i=0;i<parts.length();i++) { JSONObject part=parts.optJSONObject(i); if(part!=null&&part.optString("mimeType").equals("text/plain"))return body(part); } }
        StringBuilder text=new StringBuilder();for(int i=0;i<parts.length();i++){JSONObject part=parts.optJSONObject(i);if(part!=null&&part.optString("filename").isEmpty())text.append(body(part)).append('\n');}
        return text.toString();
    }
    public static synchronized void sync(Context c) throws Exception {
        if(!Prefs.get(c).getBoolean("gmail_enabled",false))return;
        Prefs.get(c).edit().putBoolean("gmail_more",false).apply();
        String token=token(c);long now=System.currentTimeMillis();
        String query=Prefs.text(c,"gmail_query",Prefs.DEFAULT_QUERY).trim();
        if(query.equals(Prefs.LEGACY_QUERY)){query=Prefs.DEFAULT_QUERY;Prefs.set(c,"gmail_query",query);}
        if(Prefs.get(c).getInt("finance_parser_version",0)<6){
            Prefs.get(c).edit().remove("gmail_processed").remove("gmail_scan_started").remove("gmail_scan_page").putInt("finance_parser_version",6).apply();
        }if(query.isEmpty())throw new IllegalArgumentException("Choose a Gmail query first");
        String scanKey=Prefs.text(c,"gmail_account","")+"\n"+query;
        boolean resume=scanKey.equals(Prefs.text(c,"gmail_scan_rule",""))&&Prefs.get(c).getLong("gmail_scan_started",0)>0;
        long started=resume?Prefs.get(c).getLong("gmail_scan_started",now):now;
        long since=started-100L*86400000;
        if(!resume)Prefs.get(c).edit().putString("gmail_scan_rule",scanKey).putLong("gmail_scan_started",started).putString("gmail_scan_page","").apply();
        Prefs.set(c,"gmail_health","Collecting selected emails…");
        // Resume bounded batches automatically; retain a fixed query window until completion.
        String day=java.time.LocalDate.now(java.time.ZoneId.of("UTC")).toString();
        int used=day.equals(Prefs.text(c,"gmail_budget_day",""))?Prefs.get(c).getInt("gmail_budget",0):0;
        String page=Prefs.text(c,"gmail_scan_page","");int pages=0, fetched=0;
        Set<String> ids;try(Store s=new Store(c)){ids=s.ids("Email");}
        // Also remember processed non-financial mail without retaining its content.
        Set<String> processed=new HashSet<>(Prefs.get(c).getStringSet("gmail_processed",Collections.emptySet()));
        do {
            if(used+5>100000){Prefs.set(c,"gmail_health","Daily local request cap reached; resumes automatically tomorrow");return;}
            used+=5;saveBudget(c,day,used);
            JSONObject list=get("messages?maxResults=100&q="+enc("("+query+") after:"+(since/1000))+(page.isEmpty()?"":"&pageToken="+enc(page)),token);
            JSONArray arr=list.optJSONArray("messages");if(arr!=null)for(int i=0;i<arr.length();i++) {
                String id=arr.getJSONObject(i).getString("id");String key="gmail:"+Prefs.text(c,"gmail_account","")+":"+id;
                if(ids.contains(key)||processed.contains(key))continue;
                if(used+60>100000){Prefs.set(c,"gmail_health","Daily local request cap reached; resumes automatically tomorrow");return;}
                if(fetched>=250) {continueSoon(c,page);return;}
                used+=60;saveBudget(c,day,used);
                JSONObject mail=get("messages/"+enc(id)+"?format=full",token);JSONObject payload=mail.getJSONObject("payload");
                String sender="",subject="";JSONArray headers=payload.optJSONArray("headers");
                if(headers!=null)for(int j=0;j<headers.length();j++){JSONObject h=headers.getJSONObject(j);if(h.optString("name").equalsIgnoreCase("From"))sender=h.optString("value");if(h.optString("name").equalsIgnoreCase("Subject"))subject=h.optString("value");}
                String content=body(payload);if(content.trim().isEmpty())throw new IOException("Email body unavailable; message retained for retry");
                try(Store s=new Store(c)){s.put(new Message(key,"Email",sender,subject+"\n"+content,mail.getLong("internalDate")));}
                processed.add(key);Prefs.get(c).edit().putStringSet("gmail_processed",new HashSet<>(processed)).apply();fetched++;
                if(fetched%10==0){Prefs.set(c,"gmail_health","Collecting selected emails · "+fetched+" processed in this batch");LiveUpdates.changed(c);}
                Thread.sleep(1100); // At most about 55 full-message requests/minute, below 6,000 units.
            }
            page=list.optString("nextPageToken");pages++;Prefs.set(c,"gmail_scan_page",page);
            if(pages>=10&&!page.isEmpty()){continueSoon(c,page);return;}
        }while(!page.isEmpty());
        Prefs.time(c,"gmail_checkpoint",started);Prefs.time(c,"gmail_coverage_start",since);Prefs.set(c,"gmail_health","Connected · selected emails up to date");
        Prefs.get(c).edit().remove("gmail_scan_started").remove("gmail_scan_page").apply();LiveUpdates.changed(c);
    }
    public static synchronized void syncSafety(Context c)throws Exception{
        if(!Prefs.get(c).getBoolean("gmail_enabled",false))return;
        long now=System.currentTimeMillis(),since=Prefs.get(c).getLong("safety_since",now-86400000L),until=Prefs.get(c).getLong("safety_until",now);
        Prefs.time(c,"safety_since",since);Prefs.time(c,"safety_until",until);
        String page=Prefs.text(c,"safety_page",""),account=Prefs.text(c,"gmail_account","");
        String token=token(c),day=java.time.LocalDate.now(java.time.ZoneId.of("UTC")).toString();
        int used=day.equals(Prefs.text(c,"gmail_budget_day",""))?Prefs.get(c).getInt("gmail_budget",0):0;
        if(used+3005>100000){Prefs.set(c,"safety_health","Daily local cap · resumes tomorrow");return;}
        Set<String> seen=new HashSet<>(Prefs.get(c).getStringSet("safety_processed",Collections.emptySet()));
        used+=5;saveBudget(c,day,used);
        JSONObject list=get("messages?maxResults=50&includeSpamTrash=true&q="+enc("-in:sent -in:drafts -in:trash after:"+(since/1000)+" before:"+(until/1000+1))+(page.isEmpty()?"":"&pageToken="+enc(page)),token);
        JSONArray rows=list.optJSONArray("messages");int count=0;
        if(rows!=null)for(int i=0;i<rows.length();i++){
            String id=rows.getJSONObject(i).getString("id"),key="gmail:"+account+":"+id;if(seen.contains(key))continue;
            used+=60;saveBudget(c,day,used);JSONObject mail=get("messages/"+enc(id)+"?format=full",token),payload=mail.getJSONObject("payload");
            String sender="",subject="";JSONArray headers=payload.optJSONArray("headers");if(headers!=null)for(int j=0;j<headers.length();j++){JSONObject h=headers.getJSONObject(j);if(h.optString("name").equalsIgnoreCase("From"))sender=h.optString("value");if(h.optString("name").equalsIgnoreCase("Subject"))subject=h.optString("value");}
            boolean spam=false;JSONArray labels=mail.optJSONArray("labelIds");if(labels!=null)for(int j=0;j<labels.length();j++)if(labels.optString(j).equals("SPAM"))spam=true;
            Message m=new Message(key,"Email",sender,subject+"\n"+body(payload),mail.getLong("internalDate"),spam?"Spam":"");
            in.pocketledger.core.Event e=new in.pocketledger.core.Parser().parse(m);
            // Retain financial alerts received here as well, so unfamiliar subjects are not lost.
            if(e.financial||!in.pocketledger.core.Safety.categories(e).isEmpty())try(Store s=new Store(c)){s.put(m);}
            seen.add(key);Prefs.get(c).edit().putStringSet("safety_processed",new HashSet<>(seen)).apply();count++;Thread.sleep(1100);
        }
        page=list.optString("nextPageToken");Prefs.set(c,"safety_page",page);
        if(page.isEmpty()){Prefs.time(c,"safety_since",until-3600000L);Prefs.get(c).edit().remove("safety_until").apply();Prefs.set(c,"safety_health","Incoming email categorized automatically");}
        else Prefs.set(c,"safety_health","Categorizing incoming email · more on next sync");LiveUpdates.changed(c);
    }
    private static void continueSoon(Context c,String page){Prefs.get(c).edit().putString("gmail_scan_page",page).putBoolean("gmail_more",true).apply();Prefs.set(c,"gmail_health","Import continuing automatically in the next batch");}
    private static void saveBudget(Context c,String day,int used){Prefs.get(c).edit().putString("gmail_budget_day",day).putInt("gmail_budget",used).apply();}
}
