package in.pocketledger.core;

import java.time.*;
import java.util.*;

public final class Ledger {
    public static final class Transaction {
        public final Event event;
        public final List<Event> evidence=new ArrayList<>();
        public boolean internalTransfer;
        Transaction(Event e) { event=e; evidence.add(e); }
        public String sources() { Set<String> s=new LinkedHashSet<>(); for(Event e:evidence)s.add(e.message.source); return String.join(" + ",s); }
        public String instrument(){Set<String> known=new LinkedHashSet<>();for(Event e:evidence)if(!e.instrument.equals("unknown")&&!e.instrument.equals("unknown_card"))known.add(e.instrument);if(known.size()==2&&known.contains("bank_account")&&known.contains("debit_card"))return "debit_card";return known.size()==1?known.iterator().next():known.size()>1?"unknown":event.instrument;}
        public String paymentApp(){for(Event e:evidence)if(!e.paymentApp.isEmpty())return e.paymentApp;return "";}
        public String bank(){for(Event e:evidence)if(!e.bank.isEmpty())return e.bank;return "";}
        public String channel(){for(Event e:evidence)if(!e.channel.isEmpty())return e.channel;return "";}
        public String notes() {Set<String> notes=new LinkedHashSet<>();for(Event e:evidence)if(!e.note.isEmpty())notes.add(e.note);return String.join(" | ",notes);}
    }
    public final List<Transaction> transactions=new ArrayList<>();
    public final List<Event> unresolved=new ArrayList<>(), safety=new ArrayList<>(), nonPosted=new ArrayList<>();
    public final List<Event> classified=new ArrayList<>(); public int duplicateEvidence, promotions;
    public static Ledger build(List<Message> messages) {
        Ledger ledger=new Ledger(); Parser parser=new Parser(); Set<String> seen=new HashSet<>();
        List<Event> events=new ArrayList<>();
        for(Message msg:messages) { if(!seen.add(msg.id))continue; Event e=parser.parse(msg); events.add(e);ledger.classified.add(e); }
        events.sort(Comparator.comparing((Event e)->!e.message.source.equals("SMS")).thenComparingLong(e->e.time).thenComparing(e->e.message.id));
        List<Event> notificationAlerts=new ArrayList<>();
        for(Event e:events) {
            if(!e.risk.isEmpty())ledger.safety.add(e);
            if(e.kind.equals("Promotional"))ledger.promotions++;
            if(!e.financial)continue;
            if(e.message.source.equals("Payment app")) {notificationAlerts.add(e);continue;}
            if(!e.status.equals("posted")) { ledger.nonPosted.add(e); continue; }
            if(!e.eligible()) { ledger.unresolved.add(e); continue; }
            List<Transaction> strong=new ArrayList<>(), possible=new ArrayList<>(); boolean conflict=false;
            for(Transaction tx:ledger.transactions) {
                Event p=tx.event;
                // Slice pairs an account SMS with a debit-card email using different suffixes.
                // Match only a unique, tightly timed merchant/amount pair, never amount alone.
                boolean slicePair=p.bank.equals("Slice")&&e.bank.equals("Slice")&&!p.message.source.equals(e.message.source)
                    &&p.direction.equals(e.direction)&&p.paise==e.paise&&!p.merchant.isEmpty()&&p.merchant.equalsIgnoreCase(e.merchant)
                    &&Math.abs(p.time-e.time)<=15000&&p.reference.isEmpty()&&e.reference.isEmpty()
                    &&((p.instrument.equals("bank_account")&&e.instrument.equals("debit_card"))||(e.instrument.equals("bank_account")&&p.instrument.equals("debit_card")));
                if(slicePair){strong.add(tx);continue;}
                if(!p.account.equals(e.account)||!p.direction.equals(e.direction))continue;
                if(!p.bank.isEmpty()&&!e.bank.isEmpty()&&!p.bank.equals(e.bank))continue;
                long delta=Math.abs(p.time-e.time);
                if(!e.reference.isEmpty()&&e.reference.equals(p.reference)) {
                    if(p.paise==e.paise && delta<=90L*86400000)strong.add(tx); else conflict=true;
                } else if(p.paise==e.paise && (p.reference.isEmpty()||e.reference.isEmpty()) && delta<=2L*86400000 && !p.message.source.equals(e.message.source)) possible.add(tx);
            }
            if(strong.size()==1&&!conflict) { strong.get(0).evidence.add(e); ledger.duplicateEvidence++; }
            else if(conflict||strong.size()>1||!possible.isEmpty()) { e.issue=conflict?"Conflicting evidence for the same reference":"Possible duplicate without a unique reference match"; ledger.unresolved.add(e); }
            else ledger.transactions.add(new Transaction(e));
        }
        // App notifications are provisional; attach only with unique strong banking evidence.
        for(Event e:notificationAlerts) {
            if(!e.status.equals("posted")){ledger.nonPosted.add(e);continue;}
            List<Transaction> matches=new ArrayList<>();
            if(e.risk.isEmpty()&&!e.reference.isEmpty()&&e.paise>0&&!e.direction.isEmpty())for(Transaction tx:ledger.transactions){Event p=tx.event;if(p.reference.equals(e.reference)&&p.paise==e.paise&&p.direction.equals(e.direction)&&(e.account.isEmpty()||p.account.equals(e.account))&&Math.abs(p.time-e.time)<=2L*86400000)matches.add(tx);}
            if(matches.size()==1){matches.get(0).evidence.add(e);ledger.duplicateEvidence++;}
            else {e.issue="Payment-app alert · awaiting matching bank SMS/email";ledger.unresolved.add(e);}
        }
        // Exact reference + two different known account suffixes: retain both cash-flow legs.
        for(Transaction a:ledger.transactions) for(Transaction b:ledger.transactions) {
            if(a==b)continue;
            Event x=a.event,y=b.event;
            if(!x.reference.isEmpty()&&x.reference.equals(y.reference)&&x.paise==y.paise&&!x.account.equals(y.account)&&!x.direction.equals(y.direction)&&Math.abs(x.time-y.time)<86400000) { a.internalTransfer=true; b.internalTransfer=true; }
        }
        ledger.transactions.sort(Comparator.comparingLong((Transaction t)->t.event.time).reversed());
        return ledger;
    }
    public List<Transaction> month(YearMonth month) { List<Transaction> out=new ArrayList<>(); for(Transaction t:transactions)if(inMonth(t.event.time,month))out.add(t); return out; }
    public static boolean inMonth(long millis,YearMonth month) { return YearMonth.from(Instant.ofEpochMilli(millis).atZone(Parser.ZONE)).equals(month); }
    public long total(YearMonth m,String direction) { long sum=0; for(Transaction t:month(m))if(t.event.direction.equals(direction))sum=Math.addExact(sum,t.event.paise); return sum; }
    public static String money(long paise) { return String.format(Locale.forLanguageTag("en-IN"),"₹%,.2f",paise/100.0); }
}
