package in.pocketledger.app;
import android.content.Context;
import android.graphics.*;
import android.graphics.pdf.*;
import android.os.ParcelFileDescriptor;
import androidx.test.platform.app.InstrumentationRegistry;
import org.junit.Test;
import static org.junit.Assert.*;
import java.io.*;
public class DeviceSmokeTest {
    @Test public void encryptionRoundTripAndRandomNonce() throws Exception {
        String plain="Synthetic bank alert: INR 20.00 debited. Not real user data.";
        String a=Crypto.encrypt(plain),b=Crypto.encrypt(plain);
        assertNotEquals(a,b);assertFalse(a.contains("debited"));assertEquals(plain,Crypto.decrypt(a));
    }
    @Test public void corruptedCiphertextFailsClosed() throws Exception {
        String value=Crypto.encrypt("synthetic");String[] p=value.split(":");byte[] bytes=android.util.Base64.decode(p[1],0);bytes[0]^=1;
        try{Crypto.decrypt(p[0]+":"+android.util.Base64.encodeToString(bytes,2));fail("Tamper must fail authentication");}catch(javax.crypto.AEADBadTagException expected){}
    }
    @Test public void multipagePdfRendersOffline() throws Exception {
        Context c=InstrumentationRegistry.getInstrumentation().getTargetContext();File f=new File(c.getCacheDir(),"synthetic-report-test.pdf");
        PdfDocument doc=new PdfDocument();try{Reports.Writer w=new Reports.Writer(doc,"TEST DATA");w.title("Synthetic report");for(int i=0;i<160;i++)w.wrap("Test row "+i+": INR 20.00 / sender / account / evidence. This is not a real transaction.",10);w.finish();try(FileOutputStream out=new FileOutputStream(f)){doc.writeTo(out);}}finally{doc.close();}
        try(ParcelFileDescriptor fd=ParcelFileDescriptor.open(f,ParcelFileDescriptor.MODE_READ_ONLY);PdfRenderer renderer=new PdfRenderer(fd)){assertTrue(renderer.getPageCount()>1);try(PdfRenderer.Page page=renderer.openPage(0)){Bitmap image=Bitmap.createBitmap(595,842,Bitmap.Config.ARGB_8888);page.render(image,null,null,PdfRenderer.Page.RENDER_MODE_FOR_DISPLAY);assertEquals(595,page.getWidth());image.recycle();}}
        assertTrue(f.delete());
    }
}
