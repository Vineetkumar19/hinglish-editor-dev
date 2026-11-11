package in.pocketledger.core;
import org.junit.Test;import static org.junit.Assert.*;import java.util.*;
public class BankTemplatesTest {
 private Event parse(String source,String sender,String body){return new Parser().parse(new Message("one",source,sender,body,1793360000000L));}
 @Test public void axisSwiggyFooterDoesNotBecomeMerchant(){
 Event e=parse("SMS","AXISBK","INR 160.00 debited\nA/c no. XX5379\n30-10-26, 13:20:48\nUPI/P2M/123456789012/SWIGGY INSTAMART\nNot you? SMS BLOCKUPI Cust ID to 919900000000 Axis Bank");
 assertTrue(e.issue,e.eligible());assertEquals("SWIGGY INSTAMART",e.merchant);assertEquals("123456789012",e.reference);assertTrue(e.exactTime);
 }
 @Test public void repeatedEmailAmountIsOneEvent(){
 Event e=parse("Email","alerts@axisbank.com","INR 160.00 was debited from your A/c no. XX5379.\nAmount Debited: INR 160.00 Account Number: XX5379 UPI/P2M/123456789012/SWIGGY INSTAMART\nNot you? request help");
 assertTrue(e.issue,e.eligible());assertEquals(16000,e.paise);assertEquals("posted",e.status);
 }
 @Test public void sliceDebitCardSuccessWithoutWordDebited(){
 Event e=parse("Email","noreply@slice.bank.in","Card Transaction Successful!\nHi user, Your transaction of Rs. 123 at SWIGGY using debit card xx3587 is successful. If you have any queries regarding this transaction, please reach support.");
 assertTrue(e.issue,e.eligible());assertEquals("Slice",e.bank);assertEquals("SWIGGY",e.merchant);assertEquals("debit_card",e.instrument);
 }
 @Test public void sliceImpsHasOriginBankNotBeneficiaryBank(){
 Event e=parse("Email","noreply@slice.bank.in","Your IMPS transaction is successful!\nIMPS transaction of ₹20,‌000 from your slice bank a/c xx8960 is successful! Transaction Date28-Oct-26Beneficiary NameFRIENDBeneficiary Acc No.xx5379Beneficiary BankAxis Bank Ltd.IMPS Ref No.123456789012 Reach out to our customer support.");
 assertTrue(e.issue,e.eligible());assertEquals(2000000,e.paise);assertEquals("Slice",e.bank);assertEquals("8960",e.account);assertEquals("FRIEND",e.merchant);
 }
 @Test public void fourEqualSlicePaymentsStaySeparate(){
 List<Message> m=new ArrayList<>();for(int i=0;i<4;i++)m.add(new Message("s"+i,"SMS","SLCSFB","INR 20 debited from slice account xx8960 to SWIGGY. RRN 12345678901"+i,1793360000000L+i*60000));
 assertEquals(4,Ledger.build(m).transactions.size());
 }
 @Test public void cardTypeRequiresEvidence(){
 assertEquals("unknown_card",parse("SMS","Axis","INR 20 spent on card xx1234 at SWIGGY").instrument);
 assertEquals("credit_card",parse("SMS","Axis","INR 20 spent on credit card xx1234 at SWIGGY").instrument);
 assertEquals("debit_card",parse("SMS","Axis","INR 20 spent on debit card xx1234 at SWIGGY").instrument);
 }
 @Test public void equalAmountsDifferentEventsRemainUncertain(){
 assertFalse(parse("Email","bank","INR 20 debited from account xx1234 and INR 20 paid from account xx5678").eligible());
 }

 @Test public void sliceCompletedRefundIsCredit(){
 Event e=parse("SMS","SLCSFB","Refund of Rs. 83.01 from Zomato has been successfully processed to your credit card xxxx0280 - slice");
 assertTrue(e.issue,e.eligible());assertEquals("credit",e.direction);assertEquals("credit_card",e.instrument);
 }
 @Test public void sliceImpsSmsSuccess(){
 Event e=parse("SMS","SLCSFB","IMPS payment of Rs. 20,000 from A/c xx8960 done on 28-Oct-26 to FRIEND is successful (Ref ID: 123456789012). Not you? Call 999999 - slice");
 assertTrue(e.issue,e.eligible());assertEquals("debit",e.direction);
 }
 @Test public void sliceAccountAndDebitCardEvidenceCountOnce(){
 Message a=new Message("s","SMS","SLCSFB","Your transaction of Rs. 54139 at AMAZONPAYINDIAPVTLTD from a/c xx8960 is successful. If not you, call support - slice",1793360000000L);
 Message b=new Message("e","Email","noreply@slice.bank.in","Your transaction of Rs. 54139 at AMAZONPAYINDIAPVTLTD using debit card xx3587 is successful.",1793360001000L);
 Ledger l=Ledger.build(Arrays.asList(a,b));assertEquals(1,l.transactions.size());assertEquals(2,l.transactions.get(0).evidence.size());assertEquals("debit_card",l.transactions.get(0).instrument());
 }

 @Test public void uppercaseMonthDoesNotSplitAtLetterT(){
 Event e=parse("SMS","SLCSFB","Rs. 69 spent on your credit card xx0280 at Swiggy on 28-OCT-26 (UPI Ref: 123456789012). Not you? Call support - slice");
 assertTrue(e.issue,e.eligible());assertEquals(java.time.LocalDate.of(2026,10,28),java.time.Instant.ofEpochMilli(e.time).atZone(Parser.ZONE).toLocalDate());
 }

 @Test public void bankingFooterDoesNotInventCardType(){
 Event e=parse("Email","Axis","INR 100 credited to account xx5379. Please keep your credit card and debit card details private.");
 assertEquals("bank_account",e.instrument);
 }
 @Test public void neftCounterparty(){
 Event e=parse("SMS","AXISBK","INR 100 credited to Axis Bank A/c XX5379 on 30-10-26 at 02:32:50 IST. Ref: NEFT/CITIN12345678900/EMPLOYER .View bal: https://example.com");
 assertEquals("EMPLOYER",e.merchant);
 }
}
