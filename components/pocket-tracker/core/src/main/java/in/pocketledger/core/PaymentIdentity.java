package in.pocketledger.core;
import java.util.*;
import java.util.regex.*;
public final class PaymentIdentity {
 static String grab(String s,String r){Matcher m=Pattern.compile(r,Pattern.CASE_INSENSITIVE).matcher(s);return m.find()?m.group(1).trim():"";}
 static boolean has(String s,String r){return Pattern.compile(r,Pattern.CASE_INSENSITIVE).matcher(s).find();}
 public static String primary(String body){
  return body.replaceAll("(?s)/\\*.*?\\*/"," ").replaceAll("[\\u200B-\\u200D\\uFEFF]","").replaceAll("\\s+"," ")
   .split("(?i)Not you\\?|If you have any quer|If (?:you did not|this transaction was not)|For any quer|Never share|Digital safety tips|If not you|Reach out to our customer|Best,? Team",2)[0].trim();
 }
 public static void apply(Event e,Message m){
  String s=primary(m.body);
  String cardSuffix="(?:\\s*(?:no\\.?|number|ending|ends|with|xx|x|[*:#.=-]))*\\s*[xX*]*[0-9]{3,18}";
  if(has(s,"\\bcredit\\s*card"+cardSuffix+"|\\bcc (?:ending|xx)\\s*[xX*]*[0-9]{3,18}"))e.instrument="credit_card";
  else if(has(s,"\\bdebit\\s*card"+cardSuffix))e.instrument="debit_card";
  else if(has(s,"\\bcard"+cardSuffix))e.instrument="unknown_card";
  else if(has(s,"\\ba/c\\b|\\baccount\\b|\\bacct\\b"))e.instrument="bank_account";
  if(has(s,"\\bUPI\\b"))e.channel="UPI";
  else if(has(s,"\\bIMPS\\b"))e.channel="IMPS";
  else if(has(s,"\\bNEFT\\b"))e.channel="NEFT";
  else if(e.instrument.endsWith("card"))e.channel="Card";
  if(has(s,"(?:debited|paid|sent).{0,50}(?:from|a/c|account).{0,80}(?:credit card bill|card bill)|credit card bill.{0,80}from.{0,20}(?:account|a/c)"))e.instrument="bank_account";
  if(m.source.equals("Payment app")){
   if(has(m.sender,"slice"))e.paymentApp="Slice";
   else if(has(m.sender,"bhim"))e.paymentApp="BHIM";
   else if(has(m.sender,"paytm"))e.paymentApp="Paytm";
  }
  if(has(s,"\\bBHIM\\b"))e.paymentApp="BHIM";
 }
 public static String merchant(String body){
  String s=primary(body);
  String v=grab(s,"\\bUPI/(?:P2M|P2A)/[A-Z0-9]+/([^\\r\\n]+?)(?=\\s+(?:Not you|Ref|Available|Avl)|$)");
  if(!v.isEmpty())return v;
  v=grab(s,"\\b(?:NEFT|IMPS)/[A-Z0-9]+/([^.;]+)");
  if(!v.isEmpty())return v;
  v=grab(s,"refund of.+?\\bfrom\\s+(.+?)\\s+has been successfully");
  if(!v.isEmpty())return v;
  v=grab(s,"\\bat\\s+(.+?)\\s+using\\s+(?:debit|credit)\\s+card");
  if(!v.isEmpty())return v;
  v=grab(s,"\\bat\\s+(.+?)\\s+from\\s+(?:a/c|account)");
  if(!v.isEmpty())return v;
  v=grab(s,"(?:Beneficiary Name|Merchant Name|Merchant)\\s*[:=-]?\\s*(.+?)(?=Beneficiary Acc|RRN|Transaction|\\s+on\\s+\\d|$)");
  if(!v.isEmpty())return v;
  return grab(s,"Transaction date\\s*\\d{1,2}-[A-Za-z]{3}-\\d{2,4}\\s*To\\s*(.+?)\\s*RRN");
 }
 public static String reference(String body){
  String v=grab(body,"\\bUPI/(?:P2M|P2A)/([A-Z0-9]{6,40})/");
  if(v.isEmpty())v=grab(body,"\\b(?:NEFT|IMPS)/([A-Z0-9]{6,40})/");
  return v.toUpperCase(Locale.ROOT);
 }
}
