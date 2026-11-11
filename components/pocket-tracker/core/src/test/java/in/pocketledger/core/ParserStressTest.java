package in.pocketledger.core;
import org.junit.Test;
import static org.junit.Assert.*;
public class ParserStressTest {
    @Test(timeout=2000) public void htmlWhitespaceDoesNotBlockPaymentParsing(){
        String text="INR 10 debited from a/c XX1234. UPI Ref 123456789012.\n"+" \n".repeat(20000)+"Help and support";
        Event e=new Parser().parse(new Message("a","Email","BANK",text,1793370000000L));assertTrue(e.eligible());assertEquals(1000,e.paise);
    }
}
