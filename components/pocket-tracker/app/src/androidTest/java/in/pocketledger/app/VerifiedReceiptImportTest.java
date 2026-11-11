package in.pocketledger.app;
import android.content.Context;import android.os.Bundle;import androidx.test.platform.app.InstrumentationRegistry;
import in.pocketledger.core.*;import org.json.*;import org.junit.*;import java.nio.file.*;import java.time.*;import java.time.format.*;import java.util.*;
import static org.junit.Assert.*;
/** Operator-only recovery of receipts observed in the user's authenticated bank app.
 * No network endpoint or app UI accepts this import; private input is removed after import. */
public class VerifiedReceiptImportTest {
 @Test public void importObservedReceipts()throws Exception{
  Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("verifiedReceipts")));
  Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();
  Path input=new java.io.File(c.getFilesDir(),"verified-receipts.json").toPath();
  JSONArray rows=new JSONArray(new String(Files.readAllBytes(input),java.nio.charset.StandardCharsets.UTF_8).replace("\uFEFF",""));
  assertEquals(5,rows.length());Set<String> refs=new HashSet<>();long expected=0;List<Message> imported=new ArrayList<>();
  DateTimeFormatter date=DateTimeFormatter.ofPattern("dd-MM-uuuu HH:mm:ss");
  for(int i=0;i<rows.length();i++){
   JSONObject r=rows.getJSONObject(i);String ref=r.getString("reference"),account=r.getString("account");
   assertTrue(ref.matches("[0-9]{12}"));assertTrue(refs.add(ref));assertEquals("0280",account);assertEquals("Swiggy",r.getString("merchant"));assertEquals("Verified Slice receipt",r.getString("source"));
   long amount=r.getLong("amount");assertTrue(amount>0);expected+=amount;OffsetDateTime at=OffsetDateTime.parse(r.getString("time"));
   assertEquals(LocalDate.of(2026,10,30),at.toLocalDate());
   String body="Verified bank-app receipt: Slice transaction details screen.\nINR "+java.math.BigDecimal.valueOf(amount,2).toPlainString()+" spent on Slice credit card xx"+account+" at Swiggy on "+at.format(date)+". UPI Ref "+ref+".\nPayment note: "+r.getString("note")+"\nBank transaction ID: "+r.getString("transactionId")+"\nProvenance: read directly from authenticated Slice payment details; recovered locally, not an SMS or Gmail alert.";
   Message m=new Message("receipt:slice:"+account+":debit:"+ref,"Bank app receipt","Slice",body,at.toInstant().toEpochMilli());
   Event e=new Parser().parse(m);assertTrue(e.issue,e.eligible());assertEquals(amount,e.paise);assertEquals("credit_card",e.instrument);assertEquals(ref,e.reference);imported.add(m);
  }
  assertEquals(49000,expected);try(Store s=new Store(c)){for(Message m:imported)s.put(m);}
  Ledger ledger;try(Store s=new Store(c)){ledger=Ledger.build(s.all());}
  int count=0;long sum=0;for(Ledger.Transaction t:ledger.transactions)if(refs.contains(t.event.reference)&&t.event.direction.equals("debit")&&t.event.account.equals("0280")){count++;sum+=t.event.paise;}
  assertEquals(5,count);assertEquals(49000,sum);
  Files.delete(input);LiveUpdates.changed(c);Reports.generate(c,YearMonth.of(2026,10),true);
  Bundle result=new Bundle();result.putString("stream","\nVerified Slice receipts restored: count="+count+", totalPaise="+sum+"\n");InstrumentationRegistry.getInstrumentation().sendStatus(0,result);
 }
}
