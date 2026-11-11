package in.pocketledger.app;
import android.app.*;
import android.content.*;
import android.os.*;
import android.security.keystore.*;
import javax.net.ssl.*;
import javax.security.auth.x500.X500Principal;
import java.security.*;
import java.math.BigInteger;
import java.net.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Authenticated TLS endpoint; browser access goes through the paired localhost companion. */
public final class LaptopService extends Service {
    public static final int PORT=43821; private SSLServerSocket server;private volatile boolean running;
    private final ExecutorService clients=new ThreadPoolExecutor(2,2,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(8));
    private static final String ALIAS="pocket-laptop-tls-ec-v2";
    public static synchronized JSONObject pairing(Context c)throws Exception{
        KeyStore keys=KeyStore.getInstance("AndroidKeyStore");keys.load(null);
        if(!keys.containsAlias(ALIAS)){KeyPairGenerator g=KeyPairGenerator.getInstance("EC","AndroidKeyStore");g.initialize(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_SIGN|KeyProperties.PURPOSE_VERIFY).setAlgorithmParameterSpec(new java.security.spec.ECGenParameterSpec("secp256r1")).setDigests(KeyProperties.DIGEST_NONE,KeyProperties.DIGEST_SHA256).setCertificateSubject(new X500Principal("CN=Pocket Tracker local companion")).setCertificateSerialNumber(BigInteger.ONE).setCertificateNotBefore(new Date(0)).setCertificateNotAfter(new Date(4102444800000L)).build());g.generateKeyPair();keys.load(null);}
        String token=Prefs.text(c,"wifi_token","");if(token.isEmpty()){byte[] random=new byte[32];new SecureRandom().nextBytes(random);token=android.util.Base64.encodeToString(random,android.util.Base64.NO_WRAP|android.util.Base64.URL_SAFE);Prefs.set(c,"wifi_token",token);}
        StringBuilder fingerprint=new StringBuilder();for(byte b:MessageDigest.getInstance("SHA-256").digest(keys.getCertificate(ALIAS).getEncoded()))fingerprint.append(String.format(Locale.ROOT,"%02x",b&255));
        String host="";Enumeration<NetworkInterface> networks=NetworkInterface.getNetworkInterfaces();while(networks.hasMoreElements()){NetworkInterface n=networks.nextElement();if(!n.isUp()||n.isLoopback()||!n.getName().startsWith("wlan"))continue;Enumeration<InetAddress> addresses=n.getInetAddresses();while(addresses.hasMoreElements()){InetAddress a=addresses.nextElement();if(a instanceof Inet4Address&&a.isSiteLocalAddress())host=a.getHostAddress();}}
        JSONObject p=new JSONObject().put("host",host).put("port",PORT).put("fingerprint",fingerprint.toString()).put("token",token);
        try(FileOutputStream f=c.openFileOutput("laptop-pairing.json",MODE_PRIVATE)){f.write(p.toString().getBytes(StandardCharsets.UTF_8));}return p;
    }
    @Override public int onStartCommand(Intent i,int flags,int id){
        if(i!=null&&"stop".equals(i.getAction())){Prefs.get(this).edit().putBoolean("wifi_enabled",false).apply();stopSelf();return START_NOT_STICKY;}
        NotificationManager nm=getSystemService(NotificationManager.class);nm.createNotificationChannel(new NotificationChannel("laptop","Laptop connection",NotificationManager.IMPORTANCE_LOW));
        PendingIntent open=PendingIntent.getActivity(this,32,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop=PendingIntent.getService(this,33,new Intent(this,LaptopService.class).setAction("stop"),PendingIntent.FLAG_IMMUTABLE|PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notification=new Notification.Builder(this,"laptop").setSmallIcon(R.drawable.ic_ledger).setContentTitle("Pocket Tracker · laptop connection").setContentText("Paired access on your Wi-Fi").setContentIntent(open).addAction(new Notification.Action.Builder(null,"Disconnect",stop).build()).setOngoing(true).build();
        if(Build.VERSION.SDK_INT>=29)startForeground(32,notification,android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE);else startForeground(32,notification);
        if(!running){running=true;new Thread(this::listen,"pocket-laptop").start();}return START_STICKY;
    }
    private void listen(){try{
        pairing(this);KeyStore keys=KeyStore.getInstance("AndroidKeyStore");keys.load(null);javax.net.ssl.X509ExtendedKeyManager km=new javax.net.ssl.X509ExtendedKeyManager(){public String[] getClientAliases(String t,java.security.Principal[] i){return null;}public String chooseClientAlias(String[] t,java.security.Principal[] i,Socket s){return null;}public String[] getServerAliases(String t,java.security.Principal[] i){return t.equals("EC")?new String[]{ALIAS}:null;}public String chooseServerAlias(String t,java.security.Principal[] i,Socket s){return t.equals("EC")?ALIAS:null;}public java.security.cert.X509Certificate[] getCertificateChain(String a){try{return new java.security.cert.X509Certificate[]{(java.security.cert.X509Certificate)keys.getCertificate(ALIAS)};}catch(Exception e){return null;}}public PrivateKey getPrivateKey(String a){try{return (PrivateKey)keys.getKey(ALIAS,null);}catch(Exception e){return null;}}};SSLContext ssl=SSLContext.getInstance("TLS");ssl.init(new KeyManager[]{km},null,new SecureRandom());
        server=(SSLServerSocket)ssl.getServerSocketFactory().createServerSocket(PORT);server.setEnabledProtocols(new String[]{"TLSv1.2"});
        while(running){SSLSocket socket=(SSLSocket)server.accept();try{clients.execute(()->serve(socket));}catch(RejectedExecutionException e){socket.close();}}
    }catch(Exception e){Prefs.set(this,"wifi_health","Connection unavailable: "+e.getClass().getSimpleName());running=false;stopSelf();}}
    private static String line(InputStream in)throws IOException{ByteArrayOutputStream b=new ByteArrayOutputStream();for(int i=0;i<8192;i++){int x=in.read();if(x==-1)throw new EOFException();if(x=='\n')return b.toString("US-ASCII").trim();b.write(x);}throw new IOException("Header too long");}
    private void serve(SSLSocket socket){try(socket){socket.setSoTimeout(15000);socket.startHandshake();InputStream in=socket.getInputStream();String[] first=line(in).split(" ");if(first.length!=3)return;Map<String,String> headers=new HashMap<>();for(int i=0;i<40;i++){String h=line(in);if(h.isEmpty())break;int colon=h.indexOf(':');if(colon<=0)return;headers.put(h.substring(0,colon).toLowerCase(Locale.ROOT),h.substring(colon+1).trim());if(i==39)return;}
        String expected="Bearer "+Prefs.text(this,"wifi_token","");if(headers.containsKey("origin")||!MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8),headers.getOrDefault("authorization","").getBytes(StandardCharsets.UTF_8))){respond(socket,401,"application/json","{\"error\":\"Pairing required\"}".getBytes(StandardCharsets.UTF_8));return;}
        int length=Integer.parseInt(headers.getOrDefault("content-length","0"));if(length<0||length>65536||headers.containsKey("transfer-encoding"))return;byte[] body=new byte[length];int offset=0;while(offset<length){int n=in.read(body,offset,length-offset);if(n<0)return;offset+=n;}
        String path=first[1];byte[] result;String type="application/json";
        if(first[0].equals("GET")&&path.equals("/api/snapshot"))result=DashboardApi.snapshot(this).toString().getBytes(StandardCharsets.UTF_8);
        else if(first[0].equals("POST")&&path.equals("/api/command"))result=DashboardApi.command(this,new JSONObject(new String(body,StandardCharsets.UTF_8))).toString().getBytes(StandardCharsets.UTF_8);
        else if(first[0].equals("GET")&&path.startsWith("/api/report/")){File f=DashboardApi.report(this,path.substring(12));result=java.nio.file.Files.readAllBytes(f.toPath());type="application/pdf";}
        else {respond(socket,404,"application/json","{}".getBytes(StandardCharsets.UTF_8));return;}respond(socket,200,type,result);
    }catch(Exception problem){Prefs.set(this,"wifi_health","Connection: "+problem.getClass().getSimpleName());}}
    private static void respond(SSLSocket s,int status,String type,byte[] body)throws IOException{OutputStream out=s.getOutputStream();out.write(("HTTP/1.1 "+status+" Response\r\nContent-Type: "+type+"\r\nContent-Length: "+body.length+"\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n").getBytes(StandardCharsets.US_ASCII));out.write(body);out.flush();}
    @Override public IBinder onBind(Intent i){return null;}
    @Override public void onDestroy(){running=false;try{if(server!=null)server.close();}catch(IOException ignored){}clients.shutdownNow();super.onDestroy();}
}
