package in.pocketledger.app;
import android.Manifest;
import android.app.*;
import android.content.*;
import android.os.*;
import android.webkit.*;
import android.view.*;
import android.widget.Toast;
import com.google.android.gms.auth.api.identity.*;
import org.json.*;
import java.util.concurrent.*;

public final class MainActivity extends Activity {
    private WebView web; private final ExecutorService uiData=Executors.newSingleThreadExecutor();
    private final BroadcastReceiver updates=new BroadcastReceiver(){public void onReceive(Context c,Intent i){if(web!=null)web.evaluateJavascript("window.refreshPocket&&window.refreshPocket()",null);}};
    @Override public void onCreate(Bundle b){super.onCreate(b);web=new WebView(this);web.setBackgroundColor(0xfff2f1fa);
        android.widget.FrameLayout host=new android.widget.FrameLayout(this);host.addView(web,new android.widget.FrameLayout.LayoutParams(-1,-1));host.setOnApplyWindowInsetsListener((v,insets)->{int top,bottom;if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars());top=bars.top;bottom=bars.bottom;}else{top=insets.getSystemWindowInsetTop();bottom=insets.getSystemWindowInsetBottom();}v.setPadding(0,top,0,bottom);return insets;});
        WebSettings s=web.getSettings();s.setJavaScriptEnabled(true);s.setDomStorageEnabled(false);s.setAllowFileAccess(false);s.setAllowContentAccess(false);s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);s.setSupportMultipleWindows(false);
        web.setWebViewClient(new WebViewClient(){ @Override public void onPageFinished(WebView v,String url){if("Reports".equals(getIntent().getStringExtra("tab")))v.evaluateJavascript("go('reports')",null);}
            @Override public WebResourceResponse shouldInterceptRequest(WebView v,WebResourceRequest r){String path=r.getUrl().getPath();if(!r.getUrl().getScheme().equals("https")||!r.getUrl().getHost().equals("pocket.local"))return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));try{String name=path.equals("/")?"index.html":path.substring(1);if(!name.matches("[a-zA-Z0-9.-]+"))throw new java.io.IOException();return new WebResourceResponse(name.endsWith("js")?"application/javascript":name.endsWith("css")?"text/css":name.endsWith(".png")?"image/png":name.endsWith(".svg")?"image/svg+xml":"text/html","UTF-8",getAssets().open("dashboard/"+name));}catch(Exception e){return new WebResourceResponse("text/plain","UTF-8",new java.io.ByteArrayInputStream(new byte[0]));}}
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest r){return true;}
        });web.addJavascriptInterface(new Bridge(),"PocketNative");setContentView(host);host.requestApplyInsets();web.loadUrl("https://pocket.local/");LedgerApp.sync(this);
        if(Prefs.get(this).getBoolean("wifi_enabled",false))startForegroundService(new Intent(this,LaptopService.class));
    }
    @Override protected void onResume(){super.onResume();androidx.core.content.ContextCompat.registerReceiver(this,updates,new IntentFilter(LiveUpdates.ACTION),androidx.core.content.ContextCompat.RECEIVER_NOT_EXPORTED);}
    @Override protected void onPause(){unregisterReceiver(updates);super.onPause();}
    @Override protected void onDestroy(){web.removeJavascriptInterface("PocketNative");web.destroy();uiData.shutdown();super.onDestroy();}
    final class Bridge {
        @JavascriptInterface public void request(String id,String body){if(id.length()>30||body.length()>65536)return;uiData.execute(()->{try{JSONObject req=new JSONObject(body);String action=req.optString("action");if(action.equals("native")){runOnUiThread(()->nativeAction(req));reply(id,new JSONObject().put("ok",true),null);}else reply(id,action.equals("snapshot")?DashboardApi.snapshot(MainActivity.this):DashboardApi.command(MainActivity.this,req),null);}catch(Exception e){reply(id,null,"Could not finish. Please retry.");}});}
    }
    private void reply(String id,JSONObject result,String error){runOnUiThread(()->{if(isDestroyed()||isFinishing())return;web.evaluateJavascript("window.pocketReply("+JSONObject.quote(id)+","+(result==null?"null":result.toString())+","+(error==null?"null":JSONObject.quote(error))+")",null);});}
    private void nativeAction(JSONObject r){try{switch(r.getString("name")){
        case "sms":requestPermissions(new String[]{Manifest.permission.READ_SMS,Manifest.permission.RECEIVE_SMS},10);break;
        case "gmail":authorizeGmail();break;
        case "alerts":startActivity(new Intent(android.provider.Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS));break;
        case "battery":startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName())));break;
        case "notifications":if(Build.VERSION.SDK_INT>=33)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},11);break;
        case "report":startActivity(Reports.open(this,DashboardApi.report(this,r.getString("file"))));break;
        case "email":String id=r.getString("id");if(!id.startsWith("gmail:"))break;String messageId=id.substring(id.lastIndexOf(':')+1);if(!messageId.matches("[a-zA-Z0-9]+"))break;startActivity(new Intent(Intent.ACTION_VIEW,android.net.Uri.parse("https://mail.google.com/mail/u/"+android.net.Uri.encode(Prefs.text(this,"gmail_account",""))+"/#all/"+messageId)));break;
        case "wifi":Prefs.get(this).edit().putBoolean("wifi_enabled",true).apply();startForegroundService(new Intent(this,LaptopService.class));uiData.execute(()->{try{JSONObject p=LaptopService.pairing(this);runOnUiThread(()->new AlertDialog.Builder(this).setTitle("Pair your laptop").setMessage("Open the Pocket Tracker laptop companion and paste this pairing code. Keep it private.\n\n"+p.toString()).setPositiveButton("Copy code",(d,w)->{((android.content.ClipboardManager)getSystemService(CLIPBOARD_SERVICE)).setPrimaryClip(ClipData.newPlainText("Pocket Tracker pairing",p.toString()));}).setNegativeButton("Close",null).show());}catch(Exception e){runOnUiThread(()->toast("Connect your phone to Wi-Fi first."));}});break;
        case "wifiStop":Prefs.get(this).edit().putBoolean("wifi_enabled",false).apply();stopService(new Intent(this,LaptopService.class));Prefs.set(this,"wifi_token","");toast("Laptop disconnected. Pair again to reconnect.");break;
    }}catch(Exception e){toast("Could not open this action.");}}
    private void authorizeGmail(){Identity.getAuthorizationClient(this).authorize(GmailClient.request(this)).addOnSuccessListener(r->{if(r.hasResolution()){try{startIntentSenderForResult(r.getPendingIntent().getIntentSender(),20,null,0,0,0);}catch(Exception e){authError(e);}}else finishAuth(r);}).addOnFailureListener(this::authError);}
    private void finishAuth(AuthorizationResult r){String token=r.getAccessToken();if(token==null){toast("Please reconnect Gmail.");return;}uiData.execute(()->{try{GmailClient.connected(this,token);LedgerApp.sync(this);runOnUiThread(()->toast("Gmail connected"));}catch(Exception e){runOnUiThread(()->authError(e));}});}
    private void authError(Exception e){String message=GmailFailure.describe(e);Prefs.set(this,"gmail_health",message);new AlertDialog.Builder(this).setTitle("Gmail connection").setMessage(message).setPositiveButton("OK",null).show();}
    @Override protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);if(req==20&&result==RESULT_OK)try{finishAuth(Identity.getAuthorizationClient(this).getAuthorizationResultFromIntent(data));}catch(Exception e){authError(e);}}
    @Override public void onRequestPermissionsResult(int req,String[] permissions,int[] grants){super.onRequestPermissionsResult(req,permissions,grants);LedgerApp.sync(this);LiveUpdates.changed(this);}
    @Override public void onBackPressed(){web.evaluateJavascript("window.pocketBack&&window.pocketBack()",null);}
    private void toast(String t){Toast.makeText(this,t,Toast.LENGTH_LONG).show();}
}
