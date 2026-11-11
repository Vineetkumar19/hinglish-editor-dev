package in.pocketledger.app;
import android.content.Context;
import androidx.work.*;
public final class GmailWorker extends Worker {
    public GmailWorker(Context c,WorkerParameters p){super(c,p);}
    @Override public Result doWork(){
        Context c=getApplicationContext();boolean retry=false;
        try{GmailClient.sync(c);}catch(Exception e){Prefs.set(c,"gmail_health",GmailFailure.describe(e));retry=GmailFailure.shouldRetry(e);}
        if(!retry&&!Prefs.get(c).getBoolean("gmail_more",false))try{GmailClient.syncSafety(c);}catch(Exception e){Prefs.set(c,"safety_health",GmailFailure.describe(e));}
        if(!retry&&Prefs.get(c).getBoolean("gmail_more",false)&&Prefs.get(c).getBoolean("gmail_enabled",false))WorkManager.getInstance(c).enqueueUniqueWork("gmail-continuation",ExistingWorkPolicy.APPEND_OR_REPLACE,new OneTimeWorkRequest.Builder(GmailWorker.class).setInitialDelay(30,java.util.concurrent.TimeUnit.SECONDS).setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build());
        LiveUpdates.changed(c);
        try{Reports.generateDue(c);}catch(Exception e){Prefs.set(c,"report_health","Report could not be saved; check device storage");}
        return retry&&getRunAttemptCount()<3?Result.retry():Result.success();
    }
}
