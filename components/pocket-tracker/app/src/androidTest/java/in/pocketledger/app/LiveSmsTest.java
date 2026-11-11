package in.pocketledger.app;
import android.content.*;
import androidx.test.platform.app.InstrumentationRegistry;
import in.pocketledger.core.*;
import org.junit.*;
import static org.junit.Assert.*;

public class LiveSmsTest {
    Context c;Store store;String name;
    final String body="INR 10 debited from a/c XX1234 to FRIEND. Note: Synthetic test lunch";
    @Before public void setup(){c=InstrumentationRegistry.getInstrumentation().getTargetContext();name="synthetic-live-"+java.util.UUID.randomUUID()+".db";store=new Store(c,name);}
    @After public void cleanup(){store.close();c.deleteDatabase(name);}
    @Test public void liveReceiptIsImmediateAndProviderCatchupDoesNotDuplicate()throws Exception{
        long sent=1793370000000L,received=sent+500;
        assertTrue(store.putLiveSms("BANK",body,sent,received));
        Ledger l=Ledger.build(store.all());assertEquals(1,l.transactions.size());assertEquals(1000,l.transactions.get(0).event.paise);assertEquals("Synthetic test lunch",l.transactions.get(0).notes());
        store.putProviderSms(new Message("sms:101","SMS","BANK",body,received),sent);
        assertEquals(1,store.count());assertFalse(store.putLiveSms("BANK",body,sent,received));assertEquals("sms:101",store.all().get(0).id);
    }
    @Test public void providerBeforeBroadcastDoesNotDuplicate()throws Exception{
        long at=1793370000000L;store.putProviderSms(new Message("sms:102","SMS","BANK",body,at),at);
        assertFalse(store.putLiveSms("BANK",body,at,at+10));assertEquals(1,store.count());
    }
    @Test public void identicalSeparatePaymentsRemainSeparate()throws Exception{
        long at=1793370000000L;store.putLiveSms("BANK",body,at,at);store.putLiveSms("BANK",body,at+1000,at+1000);
        store.putProviderSms(new Message("sms:1","SMS","BANK",body,at),at);store.putProviderSms(new Message("sms:2","SMS","BANK",body,at+1000),at+1000);
        assertEquals(2,store.count());assertEquals(2,Ledger.build(store.all()).transactions.size());
    }
    @Test public void missingProviderSentTimeReconcilesUniqueReceipt()throws Exception{
        long at=1793370000000L;store.putLiveSms("BANK",body,at,at+500);store.putProviderSms(new Message("sms:104","SMS","BANK",body,at+500),0);assertEquals(1,store.count());
    }
    @Test public void personalSmsIsNotRetained()throws Exception{assertFalse(store.putLiveSms("FRIEND","See you tomorrow",10,11));assertEquals(0,store.count());}
    @Test public void providerWithoutSentTimeArrivesBeforeReceiver()throws Exception{long at=1793370000000L;store.putProviderSms(new Message("sms:105","SMS","BANK",body,at),0);assertFalse(store.putLiveSms("BANK",body,at,at+500));assertEquals(1,store.count());}
    @Test public void onlySelectedPaymentAppsAreAllowed(){assertEquals("Paytm",PaymentNotifications.appName("net.one97.paytm"));assertEquals("Slice",PaymentNotifications.appName("indwin.c3.shareapp"));assertEquals("BHIM",PaymentNotifications.appName("in.org.npci.upiapp"));assertEquals("",PaymentNotifications.appName("com.example.other"));}
}
