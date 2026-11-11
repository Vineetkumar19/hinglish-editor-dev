package in.pocketledger.app;
import android.app.Activity;
import android.content.Intent;
import android.webkit.WebView;
import android.view.ViewGroup;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import org.json.JSONObject;
import java.util.concurrent.*;
import static org.junit.Assert.*;
public class DashboardUiTest {
 @Test public void phoneDashboardFitsViewportAndKeepsSetupInMenu()throws Exception{
  android.app.Instrumentation i=InstrumentationRegistry.getInstrumentation();
  Activity a=i.startActivitySync(new Intent(i.getTargetContext(),MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));
  try{
   WebView[] holder=new WebView[1];i.runOnMainSync(()->{ViewGroup root=a.findViewById(android.R.id.content);holder[0]=(WebView)((ViewGroup)root.getChildAt(0)).getChildAt(0);});
   JSONObject value=new JSONObject();for(int n=0;n<100;n++){
    CountDownLatch latch=new CountDownLatch(1);String[] result={"{}"};
    i.runOnMainSync(()->holder[0].evaluateJavascript("(function(){return {ready:!!document.querySelector('.balance'),fits:document.documentElement.scrollWidth<=innerWidth,setupInMenu:!!document.querySelector('#sidebar [data-nav=setup]'),setupInBottom:!!document.querySelector('#mobile-nav [data-nav=setup]')};})()",s->{result[0]=s;latch.countDown();}));
    assertTrue(latch.await(5,TimeUnit.SECONDS));if(!result[0].equals("null"))value=new JSONObject(result[0]);if(value.optBoolean("ready"))break;Thread.sleep(500);
   }
   assertTrue("Dashboard loaded: "+value,value.optBoolean("ready"));assertTrue("No horizontal overflow",value.optBoolean("fits"));assertTrue(value.optBoolean("setupInMenu"));assertFalse(value.optBoolean("setupInBottom"));
  }finally{i.runOnMainSync(a::finish);}
 }
}
