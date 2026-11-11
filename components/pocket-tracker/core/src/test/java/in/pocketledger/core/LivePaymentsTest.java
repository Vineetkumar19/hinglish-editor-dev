package in.pocketledger.core;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.*;
public class LivePaymentsTest {
    private Message message(String id,String source,String body){return new Message(id,source,"BANK",body,1793370000000L);}
    private String debit="INR 10 debited from a/c XX1234 to FRIEND. UPI Ref 123456789012.";
    @Test public void debitWithNoteIsStillTenRupees(){Event e=new Parser().parse(message("a","SMS",debit+" Note: Lunch share"));assertTrue(e.eligible());assertEquals(1000,e.paise);assertEquals("debit",e.direction);assertEquals("Lunch share",e.note);}
    @Test public void creditWithNote(){Event e=new Parser().parse(message("a","SMS","INR 10 credited to a/c XX1234 from FRIEND. Ref 123456789013. Remarks: Tea"));assertTrue(e.eligible());assertEquals("credit",e.direction);assertEquals("Tea",e.note);}
    @Test public void noteDoesNotAlterAmountOrStatus(){Event e=new Parser().parse(message("a","SMS",debit+"\nNote: paid back INR 500 received yesterday, payment pending"));assertTrue(e.eligible());assertEquals(1000,e.paise);assertEquals("debit",e.direction);assertEquals("posted",e.status);}
    @Test public void referenceAfterNoteSurvives(){Event e=new Parser().parse(message("a","SMS","INR 10 debited from a/c XX1234. Note: lunch. UPI Ref 123456789012. Avl Bal INR 300"));assertEquals("lunch",e.note);assertEquals("123456789012",e.reference);assertTrue(e.eligible());}
    @Test public void missingNoteIsNotInvented(){assertEquals("",new Parser().parse(message("a","SMS",debit)).note);}
    @Test public void matchedEmailAddsNoteWithoutAddingAmount(){Ledger l=Ledger.build(Arrays.asList(message("a","SMS",debit),message("b","Email",debit+" Note: Shared dinner")));assertEquals(1,l.transactions.size());assertEquals(1000,l.transactions.get(0).event.paise);assertEquals("Shared dinner",l.transactions.get(0).notes());}
    @Test public void appAlertWaitsForBank(){Ledger l=Ledger.build(Collections.singletonList(message("n","Payment app","INR 10 paid to FRIEND. UPI Ref 123456789012. Note: Tea")));assertTrue(l.transactions.isEmpty());assertEquals(1,l.unresolved.size());assertEquals("Tea",l.unresolved.get(0).note);}
    @Test public void appNoteAttachesOnlyToStrongMatch(){Ledger l=Ledger.build(Arrays.asList(message("n","Payment app","INR 10 paid to FRIEND. UPI Ref 123456789012. Note: Tea"),message("a","SMS",debit)));assertEquals(1,l.transactions.size());assertEquals(2,l.transactions.get(0).evidence.size());assertEquals("Tea",l.transactions.get(0).notes());assertTrue(l.unresolved.isEmpty());}
    @Test public void sameAmountWithoutReferenceIsNotMerged(){Ledger l=Ledger.build(Arrays.asList(message("n","Payment app","INR 10 paid to FRIEND. Note: Tea"),message("a","SMS",debit)));assertEquals(1,l.transactions.size());assertEquals(1,l.unresolved.size());assertEquals("",l.transactions.get(0).notes());}
    @Test public void smsIdentityPreservesSeparateReceipts(){assertEquals(SmsIdentity.key("BANK",debit,10),SmsIdentity.key("BANK",debit,10));assertNotEquals(SmsIdentity.key("BANK",debit,10),SmsIdentity.key("BANK",debit,11));}
}
