package in.pocketledger.core;
import org.junit.Test;
import static org.junit.Assert.*;
import java.time.*;
import java.util.*;
public class LedgerTest {
    private final long time=LocalDate.of(2026,10,15).atTime(12,0).atZone(Parser.ZONE).toInstant().toEpochMilli();
    private Message msg(String id,String source,String body){return new Message(id,source,"BANK",body,time);}
    private String debit(String ref){return "INR 20.00 debited from A/c XX1234 at STORE on 15-10-2026 12:00. UPI Ref "+ref+". Avl Bal INR 2,000.00";}
    @Test public void amountNotBalance(){Event e=new Parser().parse(msg("a","SMS",debit("123456789001")));assertEquals(2000,e.paise);assertEquals("1234",e.account);assertTrue(e.eligible());}
    @Test public void sameSmsEmailCountOnce(){Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),msg("b","Email",debit("123456789001"))));assertEquals(1,l.transactions.size());assertEquals(2000,l.total(YearMonth.of(2026,10),"debit"));assertEquals(1,l.duplicateEvidence);}
    @Test public void separateReferencesStaySeparate(){Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),msg("b","SMS",debit("123456789002"))));assertEquals(2,l.transactions.size());}
    @Test public void reimportIsIdempotent(){Message m=msg("a","SMS",debit("123456789001"));assertEquals(1,Ledger.build(Arrays.asList(m,m)).transactions.size());}
    @Test public void refundIsCredit(){Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),msg("b","SMS","Refund INR 20 credited to a/c XX1234. Ref 123456789001")));assertEquals(2,l.transactions.size());assertEquals(2000,l.total(YearMonth.of(2026,10),"credit"));}
    @Test public void failedExcluded(){Ledger l=Ledger.build(Collections.singletonList(msg("a","SMS","Payment failed. INR 20 paid from a/c XX1234")));assertEquals(0,l.transactions.size());assertEquals(1,l.nonPosted.size());}
    @Test public void otpNeverExpense(){Event e=new Parser().parse(msg("a","SMS","OTP 123456 for purchase INR 200 on card XX1234. Do not share OTP."));assertFalse(e.financial);assertEquals("",e.risk);}
    @Test public void suspiciousNeverConfirmed(){Ledger l=Ledger.build(Collections.singletonList(msg("a","SMS",debit("123456789001")+" Share your OTP now")));assertEquals(0,l.transactions.size());assertEquals(1,l.safety.size());}
    @Test public void multipleAmountsRequireCaution(){Event e=new Parser().parse(msg("a","SMS","INR 20 debited from a/c XX1234 and INR 30 fee charged"));assertFalse(e.eligible());}
    @Test public void sameReferenceConflictExcluded(){Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),msg("b","Email",debit("123456789001").replace("20.00","30.00"))));assertEquals(1,l.transactions.size());assertEquals(1,l.unresolved.size());}
    @Test public void noReferenceAmbiguityVisible(){String body=debit("123456789001").replace("UPI Ref 123456789001","");Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",body),msg("b","Email",body)));assertEquals(1,l.transactions.size());assertEquals(1,l.unresolved.size());}
    @Test public void unknownAccountNotAssumed(){assertFalse(new Parser().parse(msg("a","SMS","INR 20 debited at STORE")).eligible());}
    @Test public void internalTransferPreservesLegs(){Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),msg("b","SMS","INR 20 credited to a/c XX5678. Ref 123456789001")));assertEquals(2,l.transactions.size());assertTrue(l.transactions.get(0).internalTransfer);}
    @Test public void delayedEmailMatchesTransactionDate(){Message email=new Message("b","Email","bank",debit("123456789001"),time+5*86400000L);Ledger l=Ledger.build(Arrays.asList(msg("a","SMS",debit("123456789001")),email));assertEquals(1,l.transactions.size());}
    @Test public void monthlyBoundariesUseIndia(){Message m=new Message("a","SMS","BANK","INR 20 debited from a/c XX1234",Instant.parse("2026-09-30T20:00:00Z").toEpochMilli());assertEquals(2000,Ledger.build(Collections.singletonList(m)).total(YearMonth.of(2026,10),"debit"));}
    @Test public void pendingNotPosted(){assertEquals(1,Ledger.build(Collections.singletonList(msg("a","SMS","INR 20 payment sent from a/c XX1234 is pending"))).nonPosted.size());}
    @Test public void ownTwoEqualPaymentsNotMergedWithoutReferences(){String text="INR 20 debited from a/c XX1234 at STORE";assertEquals(2,Ledger.build(Arrays.asList(msg("a","SMS",text),msg("b","SMS",text))).transactions.size());}
    @Test public void promotionalNotExpense(){assertFalse(new Parser().parse(msg("a","SMS","Get up to INR 500 cashback when paid with card XX1234")).financial);}
    @Test public void institutionsScopeReferenceAndSuffix(){Message a=new Message("a","SMS","VM-HDFCBK",debit("123456789001"),time);Message b=new Message("b","Email","alerts@icicibank.com",debit("123456789001"),time);assertEquals(2,Ledger.build(Arrays.asList(a,b)).transactions.size());}
    @Test public void merchantAfterAccountExtracted(){assertEquals("STORE",new Parser().parse(msg("a","SMS",debit("123456789001"))).merchant);}
}
