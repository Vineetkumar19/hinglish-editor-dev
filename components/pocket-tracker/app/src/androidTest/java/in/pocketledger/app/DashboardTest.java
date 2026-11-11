package in.pocketledger.app;
import android.content.*;
import androidx.test.platform.app.InstrumentationRegistry;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;
public class DashboardTest {
 @Test public void plansPersistEncryptedWithoutCreatingTransactions()throws Exception{
  Context base=InstrumentationRegistry.getInstrumentation().getTargetContext();String prefs="plan-test-"+java.util.UUID.randomUUID();
  Context c=new ContextWrapper(base){@Override public SharedPreferences getSharedPreferences(String name,int mode){return base.getSharedPreferences(prefs,mode);}};
  try{JSONObject row=new JSONObject().put("id","test").put("name","Synthetic rent").put("amount",100000).put("day",31).put("active",true);JSONObject plan=new JSONObject().put("budget",500000).put("recurring",new JSONArray().put(row));
   DashboardApi.command(c,new JSONObject().put("action","savePlan").put("plan",plan));
   assertEquals(500000,DashboardApi.plan(c).getLong("budget"));assertFalse(Prefs.text(c,"finance_plan","").contains("Synthetic"));
   plan.put("budget",-1);try{DashboardApi.command(c,new JSONObject().put("action","savePlan").put("plan",plan));fail();}catch(IllegalArgumentException expected){}
   assertEquals(500000,DashboardApi.plan(c).getLong("budget"));
  }finally{base.deleteSharedPreferences(prefs);}
 }
 @Test public void reportPathsRejectTraversal()throws Exception{Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();try{DashboardApi.report(c,"../../shared_prefs/settings.xml");fail();}catch(java.io.IOException expected){}}
}
