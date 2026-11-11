package in.pocketledger.core;

import java.math.BigDecimal;
import java.time.*;
import java.time.format.*;
import java.util.*;
import java.util.regex.*;

public final class Parser {
    public static final ZoneId ZONE = ZoneId.of("Asia/Kolkata");
    private static final String MONEY="(?:INR|Rs\\.?|₹)\\s*([0-9][0-9,]*(?:\\.[0-9]{1,2})?)";
    private static final Pattern AMOUNT=Pattern.compile(MONEY,Pattern.CASE_INSENSITIVE);
    private static boolean has(String s,String regex) { return Pattern.compile(regex,Pattern.CASE_INSENSITIVE).matcher(s).find(); }
    private static String grab(String s,String regex) { Matcher m=Pattern.compile(regex,Pattern.CASE_INSENSITIVE).matcher(s); return m.find()?m.group(1).trim():""; }
    public Event parse(Message msg) {
        Event e=new Event(msg); PaymentIdentity.apply(e,msg);
        // A user-written memo is evidence, not banking status or a second amount.
        Matcher note=Pattern.compile("(?im)(?:^|[\\n.;])[\\t ]{0,16}(?:payment note|note|remarks?|message to recipient|memo)[\\t ]*[:=-][\\t ]*([^\\r\\n]+)").matcher(msg.body);
        String analysisBody=msg.body;
        if(note.find()) {String raw=note.group(1).trim();String[] pieces=raw.split("(?i)[.;]\\s*(?=(?:UPI|UTR|RRN|Ref|Avl|Available|Balance|Txn|Transaction|Never|Do not)\\b)",2);e.note=pieces[0].trim();if(e.note.length()>500)e.note=e.note.substring(0,500);analysisBody=msg.body.substring(0,note.start())+" "+(pieces.length>1?pieces[1]:"")+msg.body.substring(note.end());}
        String text=analysisBody.replace('\u00a0',' ').replaceAll("[\\t\\r\\n]+"," ");
        String t=text.toLowerCase(Locale.ROOT);
        String identity=(msg.sender+" "+text).toLowerCase(Locale.ROOT);
        String[][] institutions={{"slice|slcsfb|slcfin","Slice"},{"hdfc","HDFC"},{"icici","ICICI"},{"axis","Axis"},{"kotak","Kotak"},{"idfc","IDFC First"},{"state bank|sbi(?:inb|upi|bnk)?|sbipsg","SBI"},{"canara|canbnk","Canara"},{"punjab national|pnb","PNB"},{"bank of baroda|bobtxn","Bank of Baroda"},{"union bank|unionb","Union"},{"indusind","IndusInd"},{"yes bank|yesbnk","Yes Bank"}};
        Set<String> banks=new HashSet<>();for(String[] institution:institutions)if(has(identity,institution[0]))banks.add(institution[1]);if(banks.size()==1)e.bank=banks.iterator().next();
        Set<String> senderBanks=new HashSet<>();for(String[] institution:institutions)if(has(msg.sender,institution[0]))senderBanks.add(institution[1]);if(senderBanks.size()==1)e.bank=senderBanks.iterator().next();
        List<String> risks=new ArrayList<>();
        if(has(t,"(?:share|send|tell|provide).{0,35}\\b(?:otp|pin|password)\\b") && !has(t,"(?:never|do not|don't|not to)\\s+(?:share|send|tell|provide)")) risks.add("Requests a secret code or password");
        if(has(t,"anydesk|teamviewer|quick ?support") && has(t,"install|download")) risks.add("Requests remote-access software");
        if(has(t,"(?:block|suspend|expire|disconnect).{0,70}(?:https?://|click)|(?:https?://|click).{0,70}(?:block|suspend|expire|disconnect)")) risks.add("Threat or urgency with a link");
        if(has(t,"(?:won|winner|lottery|prize).{0,80}(?:pay|fee|deposit|claim)")) risks.add("Prize or payment solicitation");
        // Memo text cannot change an amount/direction, but its suspicious requests still count.
        String memo=e.note.toLowerCase(Locale.ROOT);
        if(has(memo,"(?:share|send|tell|provide).{0,35}\\b(?:otp|pin|password)\\b")&&!has(memo,"never|do not|don't"))risks.add("Memo requests a secret code or password");
        e.risk=String.join("; ",risks);
        if(msg.safetyLabel.equals("Spam")){e.risk=e.risk.isEmpty()?"Gmail marked this message as spam":e.risk+"; Gmail marked this message as spam";}
        text=PaymentIdentity.primary(analysisBody); t=text.toLowerCase(Locale.ROOT);
        boolean debit=has(t,"\\b(?:debited|spent|withdrawn|paid|sent|transferred|purchase(?:d)?|used)\\b|खर्च|डेबिट");
        if(e.bank.equals("Slice")&&has(t,"(?:transaction|payment) of.+(?:using (?:debit|credit) card|from (?:your slice bank )?(?:a/c|account)).+successful"))debit=true;
        boolean credit=has(t,"\\b(?:credited|received|deposited|refunded)\\b|क्रेडिट|जमा");
        if(has(t,"refund of.+successfully processed to (?:your )?(?:credit card|debit card|account|a/c)"))credit=true;
        boolean otp=has(t,"\\b(?:otp|one.time.password|verification code)\\b");
        if(otp && !has(t,"\\b(?:debited|credited|withdrawn)\\b")) { e.kind="OTP / service"; return e; }
        if(has(t,"\\b(?:cashback offer|pre.approved|apply now|up to|upto|discount|loan offer)\\b") && !has(t,"\\b(?:debited|credited)\\b")) { e.kind="Promotional"; return e; }
        e.financial=debit||credit;
        if(!e.financial) { e.kind=has(t,"offer|sale|discount|unsubscribe")?"Promotional":"Other message"; return e; }
        if(debit&&credit) e.issue="Both debit and credit appear; may contain multiple events";
        e.direction=credit&&!debit?"credit":debit&&!credit?"debit":"";
        if(has(t,"\\b(?:failed|declined|unsuccessful|not processed)\\b")) e.status="failed";
        else if(has(t,"\\b(?:pending|processing|scheduled|initiated|will be|(?:payment|transfer|refund) request(?:ed)?)\\b")) e.status="pending";
        List<Long> values=new ArrayList<>(); Matcher m=AMOUNT.matcher(text);
        while(m.find()) {
            String before=t.substring(Math.max(0,m.start()-35),m.start());
            if(has(before,"(?:balance|bal|limit|outstanding|due|otp)\\s*(?:is|of|:|=|-)?\\s*$")) continue;
            try { long v=new BigDecimal(m.group(1).replace(",","")).movePointRight(2).longValueExact(); if(v>0) values.add(v); } catch(Exception ignored) { e.issue="Invalid or oversized amount"; }
        }
        boolean repeatedEmail=msg.source.equals("Email") && new HashSet<>(values).size()==1 && has(t,"(?:amount debited|amount credited|transaction amount|debited from your slice|credited to your slice)");
        if(values.size()==1 || repeatedEmail) e.paise=values.get(0);
        else if(values.isEmpty()) e.issue="Transaction amount not found";
        else e.issue="Several monetary amounts; not safe to select one automatically";
        e.account=grab(text,"(?:a/c|acct?|account|card)(?:\\s*(?:no\\.?|number|ending|ends|xx|x|[*:#.=-]))*\\s*([xX*]*[0-9]{3,18})").replaceAll("[^0-9]","");
        if(e.account.length()>4) e.account=e.account.substring(e.account.length()-4);
        e.reference=grab(text,"(?:UPI\\s*(?:ref(?:erence)?|txn|transaction)|UTR|RRN|ref(?:erence)?(?:\\s*(?:no|id|number))?|txn\\s*(?:id|no)|transaction\\s*(?:id|no))\\s*[.:#=-]*\\s*([a-zA-Z0-9-]{6,40})").toUpperCase(Locale.ROOT);
        e.merchant=grab(text,"(?:\\bat\\s+|\\bto\\s+|\\bfrom\\s+)([a-zA-Z0-9@._ -]{2,50}?)(?=\\s+(?:on|via|using|ref|UPI|UTR|a/c|account|avl|bal|txn|is)\\b|[.;]|$)");
        if(e.merchant.matches("(?i)(?:your|a/c|account|card).*")) e.merchant="";
        if(e.merchant.isEmpty())e.merchant=grab(text,"\\bat\\s+([a-zA-Z0-9@._ -]{2,50}?)(?=\\s+(?:on|via|using|ref|UPI|UTR|avl|bal|txn)\\b|[.;]|$)");
        String structuredMerchant=PaymentIdentity.merchant(analysisBody);
        if(!structuredMerchant.isEmpty())e.merchant=structuredMerchant;
        String structuredReference=PaymentIdentity.reference(analysisBody);
        if(!structuredReference.isEmpty())e.reference=structuredReference;
        if(has(t,"refund|reversal|reversed")) e.kind="Refund / reversal";
        else if(has(t,"salary|payroll")) e.kind="Income";
        else if(has(t,"\\batm\\b|cash withdrawal")) e.kind="Cash withdrawal";
        else if(has(t,"credit card (?:bill|payment)|card bill|card payment")) e.kind="Card settlement";
        else if(has(t,"repayment|repaid|returned money")) e.kind="Repayment";
        else e.kind=e.direction.equals("debit")?"Unclassified debit":"Unclassified credit";
        String date=grab(text,"\\b(?:on|dated)\\s+(\\d{1,2}[-/]\\d{1,2}[-/]\\d{2,4}(?:[ T]\\d{1,2}:\\d{2}(?::\\d{2})?)?)");
        if(date.isEmpty()&&(!structuredMerchant.isEmpty()||msg.source.equals("Email")))date=grab(text,"\\b(\\d{1,2}[-/]\\d{1,2}[-/]\\d{2,4}(?:,?\\s+\\d{1,2}:\\d{2}(?::\\d{2})?)?)").replace(",","");
        if(date.isEmpty())date=grab(text,"(?:\\bon\\s+|Transaction Date\\s*)(\\d{1,2}-[A-Za-z]{3}-\\d{2,4})");
        if(!date.isEmpty()) {
            String[] parts=date.split("\\s+|T(?=\\d)",2); String normalized=parts[0].replace('/','-');
            try {
                DateTimeFormatter f=new DateTimeFormatterBuilder().parseCaseInsensitive().appendPattern("d-"+(normalized.matches(".*[A-Za-z].*")?"MMM":"M")+"-"+(normalized.split("-")[2].length()==2?"uu":"uuuu")).toFormatter(Locale.ENGLISH).withResolverStyle(ResolverStyle.STRICT);
                LocalDate d=LocalDate.parse(normalized,f); LocalTime time=parts.length==2?LocalTime.parse(parts[1],DateTimeFormatter.ofPattern(parts[1].length()>5?"H:mm:ss":"H:mm")):Instant.ofEpochMilli(msg.receivedAt).atZone(ZONE).toLocalTime();
                e.time=d.atTime(time).atZone(ZONE).toInstant().toEpochMilli(); e.exactTime=parts.length==2;
            } catch(Exception ex) { e.issue="Unrecognized transaction date"; }
        }
        if(e.account.isEmpty()) e.issue=e.issue.isEmpty()?"Account/card not identified":e.issue;
        return e;
    }
}
