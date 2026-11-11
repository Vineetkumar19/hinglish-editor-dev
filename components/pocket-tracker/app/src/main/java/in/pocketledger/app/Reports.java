package in.pocketledger.app;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.*;
import android.graphics.pdf.PdfDocument;
import androidx.core.content.FileProvider;
import in.pocketledger.core.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.util.*;

public final class Reports {
    private static final DateTimeFormatter DATE=DateTimeFormatter.ofPattern("dd MMM yyyy HH:mm",Locale.ENGLISH).withZone(Parser.ZONE);
    public static synchronized void generateDue(Context c) throws Exception {
        if(!SmsCollector.allowed(c)&&!Prefs.get(c).getBoolean("gmail_enabled",false))return;
        ZonedDateTime now=ZonedDateTime.now(Parser.ZONE);
        if(now.getDayOfMonth()==1&&now.getHour()<9)return;
        YearMonth month=YearMonth.from(now).minusMonths(1);
        String saved=Prefs.text(c,"last_report_month","");
        YearMonth first=month;
        if(!saved.isEmpty()) { try { first=YearMonth.parse(saved); } catch(Exception ignored) {} }
        if(first.isBefore(month.minusMonths(12)))first=month.minusMonths(12);
        for(YearMonth cursor=first;!cursor.isAfter(month);cursor=cursor.plusMonths(1))generate(c,cursor,false);
        Prefs.set(c,"last_report_month",month.toString());
    }
    public static synchronized File generate(Context c,YearMonth month,boolean preview) throws Exception {
        List<Message> messages;try(Store s=new Store(c)){messages=s.all();}
        Ledger ledger=Ledger.build(messages);
        long sms=Prefs.get(c).getLong("sms_checkpoint",0),gmail=Prefs.get(c).getLong("gmail_checkpoint",0);
        long end=month.plusMonths(1).atDay(1).atStartOfDay(Parser.ZONE).toInstant().toEpochMilli();
        long start=month.atDay(1).atStartOfDay(Parser.ZONE).toInstant().toEpochMilli();
        boolean partial=!SmsCollector.allowed(c)||sms<end||Prefs.get(c).getLong("sms_coverage_start",Long.MAX_VALUE)>start||!Prefs.get(c).getBoolean("gmail_enabled",false)||gmail<end||Prefs.get(c).getLong("gmail_coverage_start",Long.MAX_VALUE)>start;
        String fingerprint=fingerprint(ledger,month,Prefs.text(c,"sms_health","")+":"+sms+":"+partial,
                Prefs.text(c,"gmail_health","")+":"+gmail+":"+Prefs.text(c,"gmail_query",Prefs.DEFAULT_QUERY));
        String prefix=preview?"preview_":"report_";
        String last=Prefs.text(c,prefix+month+"_hash","");
        File dir=new File(c.getFilesDir(),"reports");if(!dir.exists()&&!dir.mkdirs())throw new IOException("Cannot create report directory");
        String old=Prefs.text(c,prefix+month+"_file","");
        if(fingerprint.equals(last)&&!old.isEmpty()&&new File(dir,old).isFile())return new File(dir,old);
        int revision=Prefs.get(c).getInt(prefix+month+"_revision",0)+1;
        File output=new File(dir,"PocketTracker_"+month+(preview?"_preview":"")+"_v"+revision+".pdf");
        File temp=new File(dir,output.getName()+".tmp");
        PdfDocument pdf=new PdfDocument();
        try {
            Writer w=new Writer(pdf,month.toString());
            List<Ledger.Transaction> transactions=ledger.month(month);
            int unresolvedCount=0,pendingCount=0;
            for(Event e:ledger.unresolved)if(Ledger.inMonth(e.time,month))unresolvedCount++;
            for(Event e:ledger.nonPosted)if(Ledger.inMonth(e.time,month))pendingCount++;
            w.title(month.format(DateTimeFormatter.ofPattern("MMMM yyyy",Locale.ENGLISH)));
            w.line("Your month, accounted for.",14,false);
            w.line((preview?"LIVE PREVIEW":"MONTHLY REPORT")+"  /  Revision "+revision,10,true);
            w.line("Generated "+DATE.format(Instant.now())+" IST",9,false);
            w.overview(ledger.total(month,"credit"),ledger.total(month,"debit"),transactions.size());
            w.wrap("Credits are not necessarily income; debits are not necessarily spending. Internal transfer legs remain in account cash movement. Net movement is not your bank balance.",9);
            w.heading(partial?"PARTIAL SOURCE COVERAGE":"COLLECTION COMPLETE FOR CONFIGURED SOURCES");
            w.wrap("Based on received alerts, not a bank statement. Selected Gmail filters and missing bank alerts may omit transactions. Source collection details appear later in this report.",10);
            w.heading("EXCLUDED FROM ALL TOTALS AND CHARTS");
            w.wrap(unresolvedCount+" unconfirmed / unresolved evidence messages  |  "+pendingCount+" pending / failed alerts",11);
            w.wrap("Only confirmed transactions in the selected month are counted. Unconfirmed evidence may overlap with confirmed entries; excluded amounts must not be added to the totals.",10);
            w.next();
            w.heading("CONFIRMED TRANSACTIONS · "+transactions.size());
            w.wrap("Newest first. Each row is one account event. SMS + Email means supporting evidence, not two amounts. All dates are in IST; all amounts are INR.",9);
            w.transactions(transactions);
            if(transactions.isEmpty())w.wrap("No confirmed transactions for this month. See source coverage and excluded evidence below.",10);
            w.next();
            w.title("Movement details");
            Map<String,long[]> accounts=new TreeMap<>();Map<String,Long> kinds=new TreeMap<>();
            for(Ledger.Transaction tx:transactions){Event e=tx.event;long[] sums=accounts.computeIfAbsent(accountLabel(tx),k->new long[2]);sums[e.direction.equals("credit")?0:1]+=e.paise;String key=(tx.internalTransfer?"Transfer counterpart":e.kind)+" / "+(e.direction.equals("credit")?"Money in":"Money out");kinds.put(key,kinds.getOrDefault(key,0L)+e.paise);}
            w.heading("BY ACCOUNT / CARD SUFFIX");
            w.accounts(accounts);
            if(accounts.isEmpty())w.line("No confirmed account movements this month.",10,false);
            w.wrap("Suffixes can collide across institutions. Check source evidence if you have accounts with identical endings.",9);
            w.heading("CLASSIFIED MOVEMENTS");
            w.classifications(kinds);
            if(kinds.isEmpty())w.line("No confirmed classifications this month.",10,false);
            w.heading("UNCONFIRMED / UNRESOLVED EVIDENCE");
            w.wrap("EXCLUDED from confirmed totals, account summaries and the chart.",10);
            int unresolved=0;for(Event e:ledger.unresolved)if(Ledger.inMonth(e.time,month)){unresolved++;w.wrap(DATE.format(Instant.ofEpochMilli(e.time))+" | "+e.message.source+" | "+(e.paise>0?Ledger.money(e.paise):"Amount uncertain")+" | "+(!e.risk.isEmpty()?e.risk:e.issue)+(e.note.isEmpty()?"":" | Note: "+e.note),10);}
            if(unresolved==0)w.line("No unresolved financial evidence in this month.",10,false);
            else w.wrap("These are evidence amounts, not additional confirmed transactions. They may overlap. Confirmed totals can understate actual activity.",10);
            w.heading("PENDING / FAILED ALERTS — EXCLUDED");
            w.wrap("These alerts are not confirmed movements and are excluded from every total and chart.",10);
            int nonposted=0;for(Event e:ledger.nonPosted)if(Ledger.inMonth(e.time,month)){nonposted++;w.wrap(DATE.format(Instant.ofEpochMilli(e.time))+" | "+e.status+" | "+Ledger.money(e.paise),10);}if(nonposted==0)w.line("No pending or failed alerts found.",10,false);
            w.heading("MESSAGE SAFETY");int safety=0;for(Event e:ledger.safety)if(Ledger.inMonth(e.message.receivedAt,month)){safety++;w.wrap(DATE.format(Instant.ofEpochMilli(e.message.receivedAt))+" | "+e.message.source+" | "+e.risk,10);}if(safety==0)w.line("No suspicious patterns detected. This does not certify safety.",10,false);
            w.wrap("Offline rules identify warning signs; they do not prove fraud or verify links. No messages are deleted or blocked.",9);
            w.heading("SOURCE COVERAGE");
            w.line(partial?"PARTIAL SOURCE COVERAGE":"COLLECTION COMPLETE FOR CONFIGURED SOURCES",10,true);
            w.wrap("SMS last collected: "+(sms==0?"Not connected":DATE.format(Instant.ofEpochMilli(sms))+" IST"),10);
            w.wrap("Gmail last collected: "+(gmail==0?"Initial import not yet complete":DATE.format(Instant.ofEpochMilli(gmail))+" IST"),10);
            w.wrap("SMS: "+Prefs.text(c,"sms_health","Not connected"),9);
            w.wrap("Gmail: "+Prefs.text(c,"gmail_health","Not connected"),9);
            w.wrap("Email selection: "+Prefs.text(c,"gmail_query",Prefs.DEFAULT_QUERY),9);
            w.heading("HOW THIS REPORT WAS MADE");w.wrap("Amounts are stored in integer paise. Strong reference matches merge SMS/email evidence; uncertain matches are retained separately. Account ending and bank-alert coverage need validation. Local rules v0.1. No paid AI or remote analysis. Reporting timezone: Asia/Kolkata.",9);
            w.finish();try(FileOutputStream stream=new FileOutputStream(temp)){pdf.writeTo(stream);stream.getFD().sync();}
        } finally { pdf.close(); }
        if(temp.length()<100)throw new IOException("Incomplete PDF");
        if(!temp.renameTo(output))throw new IOException("Cannot publish PDF");
        Prefs.get(c).edit().putString(prefix+month+"_hash",fingerprint).putString(prefix+month+"_file",output.getName()).putInt(prefix+month+"_revision",revision).apply();
        Prefs.set(c,"report_health","Ready · "+month+(partial?" · partial source coverage":""));
        if(!preview)notifyReady(c,output,revision);
        return output;
    }
    private static String fingerprint(Ledger ledger,YearMonth month,String sms,String gmail) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");digest.update(("v5-polished-pdf"+month+sms+gmail).getBytes(StandardCharsets.UTF_8));
        for(Ledger.Transaction tx:ledger.month(month)){
            digest.update(Boolean.toString(tx.internalTransfer).getBytes(StandardCharsets.UTF_8));
            for(Event e:tx.evidence)fingerprintEvent(digest,e);
        }
        for(List<Event> list:Arrays.asList(ledger.unresolved,ledger.nonPosted,ledger.safety))for(Event e:list)
            if(Ledger.inMonth(list==ledger.safety?e.message.receivedAt:e.time,month))fingerprintEvent(digest,e);
        StringBuilder s=new StringBuilder();for(byte b:digest.digest())s.append(String.format("%02x",b));return s.toString();
    }
    private static void fingerprintEvent(MessageDigest digest,Event e){
        for(String value:Arrays.asList(e.message.id,e.message.source,Long.toString(e.message.receivedAt),Long.toString(e.time),Long.toString(e.paise),
                e.direction,e.account,e.bank,e.reference,e.merchant,e.kind,e.instrument,e.paymentApp,e.channel,e.issue,e.risk,e.status,e.note)){
            digest.update(value.getBytes(StandardCharsets.UTF_8));digest.update((byte)0);
        }
    }
    public static Intent open(Context c,File f) { return new Intent(Intent.ACTION_VIEW).setDataAndType(FileProvider.getUriForFile(c,"in.pocketledger.app.files",f),"application/pdf").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION); }
    private static String accountLabel(Ledger.Transaction tx) {
        Event e=tx.event;
        String suffix=e.account.length()>4?e.account.substring(e.account.length()-4):e.account;
        String bank=tx.bank();
        return (bank.isEmpty()?"Unknown institution":bank)+" / "+(suffix.isEmpty()?"Suffix unavailable":"••"+suffix)+" / "+instrumentLabel(tx.instrument());
    }
    private static String instrumentLabel(String instrument){
        switch(instrument){
            case "credit_card":return "Credit card";
            case "debit_card":return "Debit card";
            case "bank_account":return "Bank account";
            case "unknown_card":return "Card type unconfirmed";
            default:return "Instrument unconfirmed";
        }
    }
    private static void notifyReady(Context c,File f,int revision){if(android.os.Build.VERSION.SDK_INT>=33&&c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return;Intent intent=new Intent(c,MainActivity.class).putExtra("tab","Reports");PendingIntent pending=PendingIntent.getActivity(c,0,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);Notification n=new Notification.Builder(c,"reports").setSmallIcon(in.pocketledger.app.R.drawable.ic_ledger).setContentTitle(revision==1?"Your monthly report is ready":"Your monthly report was updated").setContentText("Saved privately on this phone. Tap to view.").setContentIntent(pending).setAutoCancel(true).build();c.getSystemService(NotificationManager.class).notify(101,n);}
    static final class Writer {
        private static final int INK=Color.rgb(26,43,52),MUTED=Color.rgb(85,101,112);
        private static final int GREEN=Color.rgb(20,116,78),RED=Color.rgb(184,48,58);
        private static final int RULE=Color.rgb(222,230,234),PALE=Color.rgb(245,248,250);
        private static final float LEFT=40,RIGHT=555,TOP=76,BOTTOM=785,ROW_LINE=14;
        final PdfDocument doc;
        final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        final String month;
        PdfDocument.Page page;
        Canvas canvas;
        int pageNo=0;
        float y;

        Writer(PdfDocument d,String m){doc=d;month=m;next();}

        void next(){
            if(page!=null)end();
            page=doc.startPage(new PdfDocument.PageInfo.Builder(595,842,++pageNo).create());
            canvas=page.getCanvas();canvas.drawColor(Color.WHITE);
            rect(LEFT,29,LEFT+4,47,GREEN);
            text("POCKET TRACKER",LEFT+13,42,11,true,INK);
            right(month,RIGHT,42,9,false,MUTED);
            rect(LEFT,56,RIGHT,57,RULE);
            y=TOP;
        }

        void end(){
            if(page==null)return;
            rect(LEFT,800,RIGHT,801,RULE);
            text("Private · Generated on your device",LEFT,818,8,false,MUTED);
            right("Page "+pageNo,RIGHT,818,8,false,MUTED);
            doc.finishPage(page);page=null;
        }

        void ensure(int height){if(y+height>BOTTOM)next();}
        void title(String t){line(t,27,true);spaceSmall();}
        void heading(String t){
            List<String> lines=split(t,11,true,RIGHT-LEFT-12);
            ensure(30+lines.size()*16+28);spaceSmall();
            rect(LEFT,y,LEFT+3,y+lines.size()*16,GREEN);
            for(String part:lines){text(part,LEFT+12,y+12,11,true,INK);y+=16;}
            y+=9;
        }
        void line(String t,int size,boolean bold){
            for(String part:split(t,size,bold,RIGHT-LEFT)){
                ensure(size+9);text(part,LEFT,y+size,size,bold,INK);y+=size+9;
            }
        }
        void wrap(String t,int size){line(t,size,false);}
        void space(){y+=14;}
        void spaceSmall(){y+=6;}
        void finish(){end();}

        private void style(float size,boolean bold,int color){
            paint.setStyle(Paint.Style.FILL);paint.setTextAlign(Paint.Align.LEFT);
            paint.setTextSize(size);paint.setColor(color);
            paint.setTypeface(Typeface.create("sans-serif",bold?Typeface.BOLD:Typeface.NORMAL));
        }
        private void text(String s,float x,float baseline,float size,boolean bold,int color){
            style(size,bold,color);canvas.drawText(s,x,baseline,paint);
        }
        private void right(String s,float x,float baseline,float size,boolean bold,int color){
            style(size,bold,color);canvas.drawText(s,x-paint.measureText(s),baseline,paint);
        }
        private void rect(float l,float t,float r,float b,int color){
            paint.setStyle(Paint.Style.FILL);paint.setColor(color);canvas.drawRect(l,t,r,b,paint);
        }

        // Wrap with measured glyph widths, retaining long identifiers and explicit line breaks.
        private List<String> split(String value,float size,boolean bold,float width){
            style(size,bold,INK);
            List<String> lines=new ArrayList<>();
            for(String paragraph:value.replace('\r',' ').replace('\t',' ').split("\n",-1)){
                String rest=paragraph.trim();
                if(rest.isEmpty()){lines.add("");continue;}
                while(!rest.isEmpty()){
                    int take=paint.breakText(rest,true,width,null);
                    if(take==0)take=Character.charCount(rest.codePointAt(0));
                    if(take<rest.length()){
                        if(Character.isHighSurrogate(rest.charAt(take-1)))take--;
                        int space=rest.lastIndexOf(' ',take);
                        if(space>0)take=space;
                    }
                    if(take==0)take=Character.charCount(rest.codePointAt(0));
                    lines.add(rest.substring(0,take).trim());rest=rest.substring(take).trim();
                }
            }
            return lines;
        }

        void overview(long moneyIn,long moneyOut,int count){
            heading("MONTHLY OVERVIEW · CONFIRMED ONLY");
            ensure(300);
            float cardTop=y;
            card(LEFT,cardTop,165,"Money in",moneyIn,GREEN,Color.rgb(234,247,240));
            card(LEFT+175,cardTop,165,"Money out",moneyOut,RED,Color.rgb(253,239,239));
            card(LEFT+350,cardTop,165,"Net movement",moneyIn-moneyOut,INK,PALE);
            y+=89;
            text("CASH MOVEMENT MIX",LEFT,y+13,10,true,INK);
            text("Share of confirmed money in + money out",LEFT,y+30,9,false,MUTED);
            float cy=y+113,cx=LEFT+76;
            double total=(double)moneyIn+(double)moneyOut;
            RectF ring=new RectF(cx-61,cy-61,cx+61,cy+61);
            paint.setColor(RULE);canvas.drawOval(ring,paint);
            if(total>0){
                float sweep=(float)(360.0*moneyIn/total);
                paint.setColor(GREEN);canvas.drawArc(ring,-90,sweep,true,paint);
                paint.setColor(RED);canvas.drawArc(ring,-90+sweep,360-sweep,true,paint);
            }
            paint.setColor(Color.WHITE);canvas.drawCircle(cx,cy,43,paint);
            String countText=String.valueOf(count);
            style(22,true,INK);text(countText,cx-paint.measureText(countText)/2,cy+3,22,true,INK);
            text("confirmed",cx-23,cy+20,9,false,MUTED);
            legend(LEFT+177,y+71,"Money in",moneyIn,total,GREEN);
            legend(LEFT+177,y+119,"Money out",moneyOut,total,RED);
            if(total==0)text("No confirmed cash movement this month",LEFT+177,y+165,9,false,MUTED);
            y+=191;
        }

        private void card(float x,float top,float width,String label,long amount,int color,int fill){
            paint.setColor(fill);canvas.drawRoundRect(new RectF(x,top,x+width,top+77),8,8,paint);
            text(label,x+13,top+22,11,true,color);
            String value=Ledger.money(amount);float size=19;
            style(size,true,color);
            while(paint.measureText(value)>width-26&&size>9){size-=0.5f;paint.setTextSize(size);}
            text(value,x+13,top+52,size,true,color);
        }

        private void legend(float x,float top,String label,long amount,double total,int color){
            rect(x,top-9,x+9,top,color);
            text(label,x+18,top,11,true,color);
            right(total==0?"—":String.format(Locale.ENGLISH,"%.1f%%",amount/total*100),RIGHT,top,10,true,color);
            text(Ledger.money(amount),x+18,top+18,11,false,INK);
        }

        void transactions(List<Ledger.Transaction> transactions){
            if(transactions.isEmpty())return;
            String[] headers={"Date / IST","Transaction / account","Evidence / reference","Amount / INR"};
            float[] widths={73,191,132,119};
            boolean[] aligned={false,false,false,true};
            tableHeader(headers,widths,aligned,false);
            int index=0;
            for(Ledger.Transaction tx:transactions){
                Event e=tx.event;boolean credit=e.direction.equals("credit");
                String details=(e.merchant.isEmpty()?"Unspecified counterparty":e.merchant)+"\n"+accountLabel(tx)+"\n"+(tx.internalTransfer?"Transfer counterpart":e.kind);
                if(!tx.channel().isEmpty())details+="\nChannel: "+tx.channel();
                if(!tx.paymentApp().isEmpty())details+="\nPayment app: "+tx.paymentApp();
                if(!tx.notes().isEmpty())details+="\nNote: "+tx.notes();
                String date=DateTimeFormatter.ofPattern("dd MMM\nyyyy\nHH:mm",Locale.ENGLISH).withZone(Parser.ZONE).format(Instant.ofEpochMilli(e.time));
                String[] cells={"#"+(++index)+"\n"+date,details,tx.sources()+" ("+tx.evidence.size()+")\nRef: "+(e.reference.isEmpty()?"Unavailable":e.reference),(credit?"Money in":"Money out")+"\n"+Ledger.money(e.paise)};
                tableRow(cells,headers,widths,aligned,new int[]{MUTED,INK,MUTED,credit?GREEN:RED},index);
            }
            spaceSmall();
        }

        void accounts(Map<String,long[]> accounts){
            if(accounts.isEmpty())return;
            String[] headers={"Institution / masked suffix","Money in / INR","Money out / INR"};
            float[] widths={245,135,135};boolean[] aligned={false,true,true};
            tableHeader(headers,widths,aligned,false);int row=0;
            for(Map.Entry<String,long[]> a:accounts.entrySet())
                tableRow(new String[]{a.getKey(),Ledger.money(a.getValue()[0]),Ledger.money(a.getValue()[1])},headers,widths,aligned,new int[]{INK,GREEN,RED},++row);
            spaceSmall();
        }

        void classifications(Map<String,Long> kinds){
            if(kinds.isEmpty())return;
            String[] headers={"Classification / direction","Amount / INR"};
            float[] widths={380,135};boolean[] aligned={false,true};
            tableHeader(headers,widths,aligned,false);int row=0;
            for(Map.Entry<String,Long> k:kinds.entrySet())
                tableRow(new String[]{k.getKey(),Ledger.money(k.getValue())},headers,widths,aligned,new int[]{INK,k.getKey().endsWith("Money in")?GREEN:RED},++row);
            spaceSmall();
        }

        private void tableHeader(String[] headers,float[] widths,boolean[] aligned,boolean continued){
            ensure(continued?80:64);
            if(continued){text("TABLE CONTINUED",LEFT,y+10,8,true,MUTED);y+=19;}
            rect(LEFT,y,RIGHT,y+29,INK);float x=LEFT;
            for(int c=0;c<headers.length;c++){
                if(aligned[c])right(headers[c],x+widths[c]-8,y+18,9,true,Color.WHITE);
                else text(headers[c],x+8,y+18,9,true,Color.WHITE);
                x+=widths[c];
            }
            y+=29;
        }

        // Keep ordinary rows together. Exceptionally long notes continue without truncation,
        // repeating the column headings and identifying the row on each continuation page.
        private void tableRow(String[] cells,String[] headers,float[] widths,boolean[] aligned,int[] colors,int row){
            List<List<String>> columns=new ArrayList<>();int totalLines=1;
            for(int c=0;c<cells.length;c++){
                List<String> lines=split(cells[c],10,aligned[c],widths[c]-16);
                columns.add(lines);totalLines=Math.max(totalLines,lines.size());
            }
            float height=totalLines*ROW_LINE+16;
            if(y+Math.min(height,80)>BOTTOM || (height<=BOTTOM-TOP-48&&y+height>BOTTOM)){
                next();tableHeader(headers,widths,aligned,true);
            }
            int offset=0;
            while(offset<totalLines){
                int available=(int)((BOTTOM-y-16)/ROW_LINE);
                if(available<1){next();tableHeader(headers,widths,aligned,true);continue;}
                int take=Math.min(available,totalLines-offset);
                float top=y,bottom=y+take*ROW_LINE+16;
                rect(LEFT,top,RIGHT,bottom,row%2==0?PALE:Color.WHITE);
                float x=LEFT;
                for(int c=0;c<columns.size();c++){
                    List<String> lines=columns.get(c);
                    for(int i=0;i<take&&offset+i<lines.size();i++){
                        String value=lines.get(offset+i);float baseline=top+18+i*ROW_LINE;
                        if(aligned[c])right(value,x+widths[c]-8,baseline,10,true,colors[c]);
                        else text(value,x+8,baseline,10,false,colors[c]);
                    }
                    x+=widths[c];
                    if(c<columns.size()-1)rect(x-0.5f,top,x,bottom,RULE);
                }
                rect(LEFT,bottom-0.5f,RIGHT,bottom,RULE);y=bottom;offset+=take;
                if(offset<totalLines){
                    next();tableHeader(headers,widths,aligned,true);
                    text("Row "+row+" continued",LEFT+8,y+13,9,true,MUTED);y+=23;
                }
            }
        }
    }
}
