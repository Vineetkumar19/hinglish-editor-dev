package in.pocketledger.app;
import android.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import in.pocketledger.core.Message;

public final class SmsCollector {
    public static boolean allowed(Context c) { return c.checkSelfPermission(Manifest.permission.READ_SMS)==PackageManager.PERMISSION_GRANTED; }
    public static int scan(Context c) throws Exception {
        if(!allowed(c)) { Prefs.set(c,"sms_health","SMS permission not granted");return 0; }
        long now=System.currentTimeMillis(); long checkpoint=Prefs.get(c).getLong("sms_checkpoint",0);
        if(Prefs.get(c).getInt("sms_parser_version",0)<6)checkpoint=0;
        long since=checkpoint==0?now-100L*86400000:Math.max(0,checkpoint-86400000);
        int added=0;
        try(Store store=new Store(c);Cursor rows=c.getContentResolver().query(Uri.parse("content://sms/inbox"),new String[]{"_id","address","body","date","date_sent"},"date >= ?",new String[]{String.valueOf(since)},"date ASC")) {
            if(rows==null)throw new IllegalStateException("SMS provider unavailable");
            while(rows.moveToNext()) {
                Message m=new Message("sms:"+rows.getLong(0),"SMS",rows.getString(1),rows.getString(2),rows.getLong(3));
                if(store.putProviderSms(m,rows.getLong(4)))added++;
            }
        }
        if(checkpoint==0)Prefs.time(c,"sms_coverage_start",since);
        Prefs.get(c).edit().putInt("sms_parser_version",6).apply();
        Prefs.time(c,"sms_checkpoint",now); Prefs.set(c,"sms_health","Connected · live SMS updates enabled");
        LiveUpdates.changed(c);
        return added;
    }
}
