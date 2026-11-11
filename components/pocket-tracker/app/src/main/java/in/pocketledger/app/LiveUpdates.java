package in.pocketledger.app;
import android.content.*;
final class LiveUpdates {
    static final String ACTION="in.pocketledger.app.LEDGER_CHANGED";
    static void changed(Context c){c.sendBroadcast(new Intent(ACTION).setPackage(c.getPackageName()));}
}
