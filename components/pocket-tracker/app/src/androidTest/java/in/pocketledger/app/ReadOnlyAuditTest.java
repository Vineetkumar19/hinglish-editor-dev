package in.pocketledger.app;
import android.content.Context;
import android.os.Bundle;
import androidx.test.platform.app.InstrumentationRegistry;
import in.pocketledger.core.*;
import java.util.*;
import org.junit.*;
public class ReadOnlyAuditTest {
    @Test public void reportCountsAndTimingOnly()throws Exception {
        Assume.assumeTrue("true".equals(InstrumentationRegistry.getArguments().getString("audit")));
        Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();long started=android.os.SystemClock.elapsedRealtime();List<Message> messages;
        try(Store store=new Store(c)){messages=store.all();}
        long loaded=android.os.SystemClock.elapsedRealtime();Bundle stage=new Bundle();stage.putString("stream","\nLocal load: records="+messages.size()+", decrypt_ms="+(loaded-started)+"\n");InstrumentationRegistry.getInstrumentation().sendStatus(0,stage);Ledger ledger=Ledger.build(messages);long parsed=android.os.SystemClock.elapsedRealtime();
        Map<String,Integer> issues=new TreeMap<>();for(Event e:ledger.unresolved)issues.merge(e.issue,1,Integer::sum);
        Bundle status=new Bundle();status.putString("stream","\nLocal audit: stored="+messages.size()+", confirmed="+ledger.transactions.size()+", unresolved="+ledger.unresolved.size()+", decrypt_ms="+(loaded-started)+", parse_ms="+(parsed-loaded)+", issues="+issues+"\n");InstrumentationRegistry.getInstrumentation().sendStatus(0,status);
    }
}
