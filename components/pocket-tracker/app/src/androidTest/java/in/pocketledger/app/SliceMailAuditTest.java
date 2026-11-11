package in.pocketledger.app;
import android.content.Context;import android.os.Bundle;import androidx.test.platform.app.InstrumentationRegistry;import org.junit.*;import org.json.*;import java.net.URLEncoder;import java.util.*;
public class SliceMailAuditTest{
 private void out(String text){Bundle b=new Bundle();b.putString("stream",text+"\n");InstrumentationRegistry.getInstrumentation().sendStatus(0,b);}
 @Test public void traceSliceAlerts()throws Exception{
 Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("sliceAudit")));Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();String token=GmailClient.token(c);
 String day=java.time.LocalDate.now(java.time.ZoneId.of("UTC")).toString();int used=day.equals(Prefs.text(c,"gmail_budget_day",""))?Prefs.get(c).getInt("gmail_budget",0):0;if(used>97000){out("Local request cap prevents extra audit");return;}
 String auditQuery=InstrumentationRegistry.getArguments().getString("auditQuery","newer_than:3d {from:slice subject:slice subject:swiggy}");
 JSONObject list=GmailClient.get("messages?maxResults=40&includeSpamTrash=true&q="+URLEncoder.encode(auditQuery,"UTF-8"),token);used+=5;JSONArray ids=list.optJSONArray("messages");out("MATCHING_EMAILS="+(ids==null?0:ids.length())+", additionalPage="+list.has("nextPageToken"));Set<String> stored;try(Store s=new Store(c)){stored=s.ids("Email");}
 if(ids!=null)for(int n=0;n<ids.length();n++){JSONObject m=GmailClient.get("messages/"+ids.getJSONObject(n).getString("id")+"?format=full",token);used+=60;JSONObject payload=m.getJSONObject("payload");String subject="",sender="";JSONArray headers=payload.optJSONArray("headers");if(headers!=null)for(int j=0;j<headers.length();j++){JSONObject h=headers.getJSONObject(j);if(h.optString("name").equalsIgnoreCase("Subject"))subject=h.optString("value");if(h.optString("name").equalsIgnoreCase("From"))sender=h.optString("value");}
 String body=extract(payload).replaceAll("\\s+"," ");String key="gmail:"+Prefs.text(c,"gmail_account","")+":"+ids.getJSONObject(n).getString("id");
 out("MAIL "+(n+1)+" subject="+subject+", sender="+sender+", stored="+stored.contains(key)+", received="+java.time.Instant.ofEpochMilli(m.getLong("internalDate")).atZone(in.pocketledger.core.Parser.ZONE));
 if(sender.toLowerCase(Locale.ROOT).contains("slice")||subject.toLowerCase(Locale.ROOT).contains("debited"))out("TEMPLATE: "+body.substring(0,Math.min(3000,body.length())).replaceAll("\\b[0-9]{6,}\\b","<ID>").replaceAll("https?://\\S+","<LINK>").replaceAll("[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+","<ADDRESS>"));
 Prefs.get(c).edit().putString("gmail_budget_day",day).putInt("gmail_budget",used).apply();Thread.sleep(1100);
 }
 }
 private String extract(JSONObject p){String type=p.optString("mimeType");JSONObject b=p.optJSONObject("body");if(b!=null&&!b.optString("data").isEmpty()&&(type.equals("text/plain")||type.equals("text/html"))){String raw=new String(android.util.Base64.decode(b.optString("data"),android.util.Base64.URL_SAFE),java.nio.charset.StandardCharsets.UTF_8);return type.equals("text/html")?android.text.Html.fromHtml(raw,0).toString():raw;}StringBuilder out=new StringBuilder();JSONArray a=p.optJSONArray("parts");if(a!=null)for(int i=0;i<a.length();i++)if(a.optJSONObject(i)!=null)out.append(extract(a.optJSONObject(i))).append(' ');return out.toString();}
}
