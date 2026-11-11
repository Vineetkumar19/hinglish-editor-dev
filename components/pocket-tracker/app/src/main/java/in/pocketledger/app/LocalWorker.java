package in.pocketledger.app;
import android.content.Context;
import androidx.work.*;
public final class LocalWorker extends Worker {
    public LocalWorker(Context c,WorkerParameters p) { super(c,p); }
    @Override public Result doWork() {
        Context c=getApplicationContext(); boolean failed=false;
        try { SmsCollector.scan(c); } catch(Exception e) { Prefs.set(c,"sms_health","Collection failed; open Setup to check permissions"); failed=true; }
        try { Reports.generateDue(c); } catch(Exception e) { Prefs.set(c,"report_health","Report failed: "+e.getClass().getSimpleName()+". Check free storage."); failed=true; }
        return failed&&getRunAttemptCount()<3?Result.retry():Result.success();
    }
}
