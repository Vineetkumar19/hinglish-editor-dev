package in.pocketledger.app;
import android.content.*;
import androidx.work.*;
import java.util.concurrent.TimeUnit;
import android.provider.Telephony;
import android.telephony.SmsMessage;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
public final class SmsReceiver extends BroadcastReceiver {
    private static final ExecutorService INCOMING=Executors.newSingleThreadExecutor();
    @Override public void onReceive(Context c,Intent i) {
        if(!"android.provider.Telephony.SMS_RECEIVED".equals(i.getAction()))return;
        SmsMessage[] parts=Telephony.Sms.Intents.getMessagesFromIntent(i);if(parts==null||parts.length==0)return;
        StringBuilder body=new StringBuilder();for(SmsMessage part:parts)body.append(part.getMessageBody());
        String sender=parts[0].getOriginatingAddress();if(sender==null)return;
        long sent=parts[0].getTimestampMillis(),received=System.currentTimeMillis();
        PendingResult pending=goAsync();Context app=c.getApplicationContext();
        INCOMING.execute(()->{try(Store store=new Store(app)){
            if(store.putLiveSms(sender,body.toString(),sent,received))LiveUpdates.changed(app);
            Prefs.set(app,"sms_health","Connected · live SMS updates enabled");
        }catch(Exception e){Prefs.set(app,"sms_health","Live capture needs catch-up; automatic inbox scan queued");}
        finally{pending.finish();}});
        // Durable provider reconciliation/catch-up is separate from the immediate display path.
        WorkManager.getInstance(c).enqueueUniqueWork("sms-arrival",ExistingWorkPolicy.APPEND_OR_REPLACE,new OneTimeWorkRequest.Builder(LocalWorker.class).setInitialDelay(10,TimeUnit.SECONDS).build());
    }
}
