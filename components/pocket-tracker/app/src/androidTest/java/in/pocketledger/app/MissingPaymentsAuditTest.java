package in.pocketledger.app;
import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import androidx.test.platform.app.InstrumentationRegistry;
import in.pocketledger.core.*;
import org.junit.*;
import java.util.*;
public class MissingPaymentsAuditTest {
 private void emit(String s){Bundle b=new Bundle();b.putString("stream",s+"\n");InstrumentationRegistry.getInstrumentation().sendStatus(0,b);}
 @Test public void inspectRequestedMerchantOnly()throws Exception{
  Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("merchantAudit")));
  Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();
  long today=java.time.LocalDate.now(Parser.ZONE).atStartOfDay(Parser.ZONE).toInstant().toEpochMilli();
  List<Message> saved;try(Store s=new Store(c)){saved=s.all();}
  Set<String> ids=new HashSet<>();for(Message m:saved)ids.add(m.id);
  int count=0;
  try(Cursor r=c.getContentResolver().query(Uri.parse("content://sms/inbox"),new String[]{"_id","address","body","date"},"date >= ? AND (body LIKE ? OR body LIKE ?)",new String[]{String.valueOf(today),"%swiggy%","%bundl%"},"date ASC")){
   while(r!=null&&r.moveToNext()){count++;Message m=new Message("sms:"+r.getLong(0),"SMS",r.getString(1),r.getString(2),r.getLong(3));Event e=new Parser().parse(m);
    String template=m.body.replaceAll("\\b[0-9]{6,}\\b","<ID>").replaceAll("(?i)[a-z0-9._%+-]+@[a-z0-9.-]+","<ADDRESS>").replaceAll("https?://\\S+","<LINK>");
    emit("Requested merchant SMS "+count+": stored="+ids.contains(m.id)+", amountPaise="+e.paise+", financial="+e.financial+", kind="+e.kind+", direction="+e.direction+", status="+e.status+", issue="+e.issue+", risk="+e.risk+"\nTemplate: "+template);
   }
  }
  emit("TODAY_MATCHING_SMS="+count);
  try(Cursor r=c.getContentResolver().query(Uri.parse("content://sms/inbox"),new String[]{"_id","address","body","date"},"date >= ?",new String[]{String.valueOf(today)},"date ASC")){
 while(r!=null&&r.moveToNext()){String b=r.getString(2);if(b.toLowerCase(Locale.ROOT).contains("swiggy")||!b.matches("(?is).*(INR|Rs\\.?|₹)\\s*[0-9].*"))continue;
 Message m=new Message("sms:"+r.getLong(0),"SMS",r.getString(1),b,r.getLong(3));Event e=new Parser().parse(m);
 if(e.kind.equals("OTP / service")||e.kind.equals("Promotional"))continue;
 emit("Other monetary SMS: stored="+ids.contains(m.id)+", amount="+e.paise+", status="+e.status+", issue="+e.issue+", template="+b.replaceAll("\\b[0-9]{6,}\\b","<ID>").replaceAll("https?://\\S+","<LINK>"));
 }
}
try(Cursor r=c.getContentResolver().query(Uri.parse("content://sms/inbox"),new String[]{"_id","address","body","date"},"date >= ? AND (body LIKE ? OR address LIKE ?)",new String[]{String.valueOf(today-2L*86400000),"%slice%","%slc%"},"date ASC")){
 while(r!=null&&r.moveToNext()){Message m=new Message("sms:"+r.getLong(0),"SMS",r.getString(1),r.getString(2),r.getLong(3));Event e=new Parser().parse(m);if(e.kind.equals("OTP / service"))continue;
 emit("SLICE_SMS "+java.time.Instant.ofEpochMilli(m.receivedAt).atZone(Parser.ZONE)+" stored="+ids.contains(m.id)+" eligible="+e.eligible()+" issue="+e.issue+" TEMPLATE "+m.body.replaceAll("\\b[0-9]{6,}\\b","<ID>").replaceAll("https?://\\S+","<LINK>"));
 }
}
int mail=0;for(Message m:saved)if(m.receivedAt>=today&&m.source.equals("Email")&&m.body.toLowerCase(Locale.ROOT).matches("(?s).*(swiggy|bundl).*")){Event e=new Parser().parse(m);mail++;emit("EMAIL_TEMPLATE: "+m.body.replaceAll("\\s+"," ").substring(0,Math.min(5000,m.body.replaceAll("\\s+"," ").length())).replaceAll("\\b[0-9]{6,}\\b","<ID>").replaceAll("https?://\\S+","<LINK>"));emit("Stored matching email: amountPaise="+e.paise+", issue="+e.issue+", kind="+e.kind+", status="+e.status);}
  emit("TODAY_STORED_MATCHING_EMAIL="+mail);
 }
}
