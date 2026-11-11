package in.pocketledger.app;
import android.app.*;
import androidx.work.*;
import java.util.concurrent.*;
public final class LedgerApp extends Application {
    public static final ExecutorService IO=Executors.newSingleThreadExecutor();
    @Override public void onCreate() {
        super.onCreate();
        getSystemService(NotificationManager.class).createNotificationChannel(new NotificationChannel("reports","Monthly reports",NotificationManager.IMPORTANCE_DEFAULT));
        WorkManager w=WorkManager.getInstance(this);
        w.enqueueUniquePeriodicWork("local-maintenance",ExistingPeriodicWorkPolicy.KEEP,new PeriodicWorkRequest.Builder(LocalWorker.class,6,TimeUnit.HOURS).build());
        w.enqueueUniquePeriodicWork("gmail-sync",ExistingPeriodicWorkPolicy.UPDATE,new PeriodicWorkRequest.Builder(GmailWorker.class,15,TimeUnit.MINUTES).setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build());
    }
    public static void sync(android.content.Context c) {
        WorkManager w=WorkManager.getInstance(c);
        w.enqueueUniqueWork("local-now",ExistingWorkPolicy.KEEP,new OneTimeWorkRequest.Builder(LocalWorker.class).build());
        w.enqueueUniqueWork("gmail-now",ExistingWorkPolicy.KEEP,new OneTimeWorkRequest.Builder(GmailWorker.class).setConstraints(new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()).build());
    }
}
