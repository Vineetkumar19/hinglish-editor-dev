package in.pocketledger.core;
import org.junit.Test;
import static org.junit.Assert.*;
public class SafetyTest {
 @Test public void spamCannotEnterConfirmedTotals(){Message m=new Message("spam","Email","fake","INR 10 credited to account XX1234. Ref 123456789012",1,"Spam");Ledger l=Ledger.build(java.util.List.of(m));assertEquals(0,l.transactions.size());assertTrue(Safety.categories(new Parser().parse(m)).contains("Spam"));}
 @Test public void phishingAndFraudAreIndicators(){Event phishing=new Parser().parse(new Message("a","Email","sender","Send your password to prevent suspension.",1));assertTrue(Safety.categories(phishing).contains("Phishing"));Event fraud=new Parser().parse(new Message("b","SMS","sender","You won a lottery prize; pay a fee to claim.",1));assertTrue(Safety.categories(fraud).contains("Fraud indicators"));}
 @Test public void ordinaryMessageIsNotSafety(){assertTrue(Safety.categories(new Parser().parse(new Message("c","Email","friend","Lunch tomorrow?",1))).isEmpty());}
}
