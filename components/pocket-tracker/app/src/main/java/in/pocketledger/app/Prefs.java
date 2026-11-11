package in.pocketledger.app;
import android.content.*;
public final class Prefs {
    public static final String LEGACY_QUERY="{subject:debited subject:credited subject:\"transaction alert\" subject:\"payment successful\" subject:refund subject:\"payment received\"}";
    public static final String DEFAULT_QUERY="{subject:debited subject:credited subject:\"transaction alert\" subject:\"payment successful\" subject:refund subject:\"payment received\" subject:\"card transaction successful\" subject:\"IMPS transaction\" from:slice.bank.in from:sliceit.com}";
    public static SharedPreferences get(Context c) { return c.getSharedPreferences("settings",Context.MODE_PRIVATE); }
    public static String text(Context c,String k,String fallback) { return get(c).getString(k,fallback); }
    public static void set(Context c,String k,String v) { get(c).edit().putString(k,v).apply(); }
    public static void time(Context c,String k,long v) { get(c).edit().putLong(k,v).apply(); }
}
