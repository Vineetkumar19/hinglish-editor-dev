package in.pocketledger.app;
import android.app.Notification;
import android.content.*;
import android.os.Bundle;
import android.service.notification.*;
import androidx.core.app.NotificationManagerCompat;
import in.pocketledger.core.*;
import java.util.concurrent.*;

public final class PaymentNotifications extends NotificationListenerService {
    private static final ExecutorService INCOMING=Executors.newSingleThreadExecutor();
    static String appName(String pkg){switch(pkg){case "net.one97.paytm":return "Paytm";case "indwin.c3.shareapp":return "Slice";case "in.org.npci.upiapp":return "BHIM";default:return "";}}
    static boolean allowed(Context c){return NotificationManagerCompat.getEnabledListenerPackages(c).contains(c.getPackageName());}
    @Override public void onListenerConnected(){Prefs.set(this,"payment_alert_health","Connected · Paytm, Slice and BHIM alerts");LiveUpdates.changed(this);}
    @Override public void onListenerDisconnected(){Prefs.set(this,"payment_alert_health","Reconnecting payment alerts");requestRebind(new ComponentName(this,PaymentNotifications.class));}
    @Override public void onNotificationPosted(StatusBarNotification posted){
        String name=appName(posted.getPackageName());if(name.isEmpty())return;
        Notification n=posted.getNotification();if((n.flags&Notification.FLAG_GROUP_SUMMARY)!=0)return;
        Bundle extras=n.extras;if(extras==null)return;
        String title=String.valueOf(extras.getCharSequence(Notification.EXTRA_TITLE,""));
        String body=String.valueOf(extras.getCharSequence(Notification.EXTRA_BIG_TEXT,extras.getCharSequence(Notification.EXTRA_TEXT,"")));
        if(body.isEmpty())return;
        String text=title+"\n"+body;long at=posted.getPostTime();
        String id="notification:"+SmsIdentity.digest(posted.getPackageName()+"\u0000"+posted.getKey()+"\u0000"+(n.when>0?n.when:at)+"\u0000"+text);
        Message message=new Message(id,"Payment app",name,text,at);
        Event parsed=new Parser().parse(message);if(!parsed.financial||parsed.kind.equals("OTP / service"))return;
        INCOMING.execute(()->{try(Store store=new Store(this)){if(store.put(message))LiveUpdates.changed(this);}catch(Exception e){Prefs.set(this,"payment_alert_health","A payment alert could not be stored; bank SMS/email catch-up remains active");}});
    }
}
