package in.pocketledger.core;
import java.util.*;
/** Warning categories are local indicators, never a verdict of authenticity. */
public final class Safety {
    public static List<String> categories(Event e) {
        List<String> out=new ArrayList<>();String r=e.risk.toLowerCase(Locale.ROOT);
        if(e.message.safetyLabel.equals("Spam"))out.add("Spam");
        if(!r.isEmpty())out.add("Suspicious");
        if(r.contains("secret")||r.contains("password")||r.contains("urgency"))out.add("Phishing");
        if(r.contains("prize")||r.contains("remote-access"))out.add("Fraud indicators");
        if(e.kind.equals("Promotional"))out.add("Promotions");
        return out;
    }
}
