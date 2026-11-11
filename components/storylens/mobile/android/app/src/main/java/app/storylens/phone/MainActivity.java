package app.storylens.phone;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.database.Cursor;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.MediaController;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.VideoView;
import androidx.core.content.FileProvider;
import app.storylens.protocol.Codec;
import app.storylens.protocol.Json;
import app.storylens.protocol.Pairing;
import app.storylens.protocol.Transfer;
import app.storylens.protocol.Tunnel;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

public final class MainActivity extends Activity {
    private static final int PICK_ATTACHMENT=21, SAVE_FILE=22, PICK_CONNECTION=23;
    private static final int BG=0xff101217, PANEL=0xff1c2029, TEXT=0xfff1f2f5, MUTED=0xffadb3c0, ORANGE=0xffff873d;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final ExecutorService filesWorker=Executors.newSingleThreadExecutor();
    private PairingStore pairingStore;
    private SharedPreferences local;
    private Pairing pairing;
    private HttpsWire wire;
    private Tunnel tunnel;
    private boolean active,resumed,pollingState,pollingChat,uploading,downloading,sending,stopping;
    private int epoch;
    private String chatId="",rendered="",draft="";
    private Runnable stateAfter,chatAfter;
    private List<Map<String,Object>> chats=new ArrayList<>();
    private final List<Map<String,Object>> attachments=new ArrayList<>();
    private final Map<String,File> cachedFiles=new HashMap<>();
    private LinearLayout root,messages,attachRow;
    private TextView connection,stage,title;
    private EditText composer;
    private Spinner profile;
    private ProgressBar progress;
    private ScrollView scroll;
    private Button send,stop,attach,check;
    private Uri pendingUpload,pendingConnection;
    private File pendingSave;
    private MediaPlayer player;
    private VideoView video;
    private AlertDialog preview;
    private final Runnable poll=new Runnable(){@Override public void run(){if(active&&pairing!=null){refreshState(null);refreshChat(null);handler.postDelayed(this,3000);}}};

    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        pairingStore=new PairingStore(this);local=getSharedPreferences("phone_ui",MODE_PRIVATE);
        chatId=local.getString("chat","");
        if(saved!=null){draft=saved.getString("draft","");String attached=saved.getString("attachments","[]");try{attachments.addAll(objects(Json.parse(attached)));}catch(Exception ignored){}String path=saved.getString("save_file","");if(!path.isEmpty()){File candidate=new File(path);try{if(candidate.getCanonicalPath().startsWith(new File(getCacheDir(),"received").getCanonicalPath()+File.separator))pendingSave=candidate;}catch(Exception ignored){}}}
        try{pairing=pairingStore.load();}catch(Exception e){pairing=null;}
        if(pairing==null)showPairing();else showChat();
    }
    @Override protected void onStart(){super.onStart();active=true;if(pairing!=null)connect();}
    @Override protected void onResume(){super.onResume();resumed=true;consumePickers();}
    @Override protected void onPause(){resumed=false;pausePreview();super.onPause();}
    @Override protected void onStop(){active=false;handler.removeCallbacks(poll);disconnect();super.onStop();}
    @Override protected void onDestroy(){filesWorker.shutdownNow();pausePreview();super.onDestroy();}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);state.putString("draft",composer==null?draft:composer.getText().toString());state.putString("attachments",Json.stringify(attachments));if(pendingSave!=null)state.putString("save_file",pendingSave.getAbsolutePath());}
    private void connect(){
        if(tunnel!=null)return;wire=new HttpsWire(pairing);final int generation=++epoch;
        tunnel=new Tunnel(wire,new Codec(pairing.key()),s->{if(s.startsWith("Reconnecting")||s.startsWith("An invalid"))ui(()->{if(epoch==generation&&connection!=null)connection.setText(s);});},65000);
        tunnel.start();pollingState=false;pollingChat=false;handler.removeCallbacks(poll);handler.post(poll);updateButtons();
    }
    private void disconnect(){epoch++;if(wire!=null)wire.close();if(tunnel!=null)tunnel.close();wire=null;tunnel=null;pollingState=false;pollingChat=false;sending=false;stopping=false;}
    private void ui(Runnable r){handler.post(()->{if(!isDestroyed())r.run();});}
    private int dp(float value){return Math.round(value*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int size,int color){TextView t=new TextView(this);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setPadding(dp(4),dp(4),dp(4),dp(4));return t;}
    private LinearLayout column(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private LinearLayout row(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.HORIZONTAL);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private GradientDrawable panel(int color){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(12));return d;}
    private Button button(String label,Runnable action){Button b=new Button(this);b.setText(label);b.setTextColor(TEXT);b.setTextSize(13);b.setAllCaps(false);b.setMinWidth(0);b.setMinimumWidth(0);b.setMinHeight(dp(48));b.setPadding(dp(10),dp(4),dp(10),dp(4));b.setBackgroundTintList(ColorStateList.valueOf(PANEL));b.setOnClickListener(v->action.run());return b;}
    private void base(){root=column();root.setPadding(dp(14),dp(8),dp(14),dp(8));root.setBackgroundColor(BG);root.setFitsSystemWindows(true);setContentView(root);}
    private void showPairing(){
        base();composer=null;root.setGravity(Gravity.CENTER_VERTICAL);TextView brand=text("StoryLens",34,ORANGE);brand.setTypeface(null,Typeface.BOLD);root.addView(brand);
        root.addView(text("Your laptop, in a private native chat.",17,TEXT));root.addView(text("Paste your laptop connection code once, or import its private .slconnect file. No browser or VPN is needed.",14,MUTED));
        EditText input=new EditText(this);input.setHint("SL1 connection code");input.setTextColor(TEXT);input.setHintTextColor(MUTED);input.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD|InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);input.setSingleLine(true);input.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);input.setSaveEnabled(false);input.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(4096)});root.addView(input,new LinearLayout.LayoutParams(-1,dp(64)));
        root.addView(button("Connect",()->{String code=input.getText().toString().trim();try{Pairing parsed=Pairing.parse(code);pairingStore.save(code);input.setText("");pairing=parsed;showChat();if(active)connect();}catch(Exception e){notice("Connection not saved",e instanceof IllegalArgumentException?e.getMessage():"The secure Android key could not be used. Unlock the phone, then try again.");}}));
        root.addView(button("Import connection file",()->{Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(pick,PICK_CONNECTION);}));
        root.addView(text("The code is encrypted with Android Keystore and excluded from backups. Keep the app open to receive replies; laptop jobs continue if you leave.",12,MUTED));
    }
    private void showChat(){
        base();LinearLayout header=row();title=text("StoryLens",24,ORANGE);title.setTypeface(null,Typeface.BOLD);header.addView(title,new LinearLayout.LayoutParams(0,-2,1));header.addView(button("Chats",this::showChats));header.addView(button("+",this::newChat));Button options=button("⋮",this::options);options.setContentDescription("Connection options");header.addView(options);root.addView(header);
        connection=text("Connecting to relay…",12,MUTED);root.addView(connection);stage=text("Keep StoryLens open for replies. Laptop jobs continue in the background.",12,MUTED);root.addView(stage);
        progress=new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal);progress.setProgressTintList(ColorStateList.valueOf(ORANGE));progress.setIndeterminateTintList(ColorStateList.valueOf(ORANGE));progress.setVisibility(View.GONE);root.addView(progress,new LinearLayout.LayoutParams(-1,dp(4)));
        scroll=new ScrollView(this);scroll.setFillViewport(true);messages=column();scroll.addView(messages);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        attachRow=row();root.addView(attachRow);LinearLayout choices=row();profile=new Spinner(this);profile.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"General","Cricket","Gaming"}));profile.setSelection(Math.max(0,Math.min(2,local.getInt("profile",0))));choices.addView(profile,new LinearLayout.LayoutParams(0,dp(48),1));
        check=button("Refresh",this::manualRefresh);choices.addView(check);stop=button("Stop",this::stopChat);choices.addView(stop);root.addView(choices);
        composer=new EditText(this);composer.setTextColor(TEXT);composer.setHintTextColor(MUTED);composer.setHint("Message your laptop…");composer.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_FLAG_MULTI_LINE|InputType.TYPE_TEXT_FLAG_CAP_SENTENCES);composer.setMinLines(1);composer.setMaxLines(5);composer.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(20000)});composer.setText(draft);root.addView(composer,new LinearLayout.LayoutParams(-1,-2));
        LinearLayout controls=row();attach=button("Attach",this::pickAttachment);controls.addView(attach,new LinearLayout.LayoutParams(0,dp(48),1));send=button("Send",this::sendMessage);send.setTextColor(BG);send.setBackgroundTintList(ColorStateList.valueOf(ORANGE));controls.addView(send,new LinearLayout.LayoutParams(0,dp(48),2));root.addView(controls);
        rendered="";if(chatId.isEmpty())messages.addView(text("Choose a chat or tap + to start. All answers come from your laptop.",16,MUTED));renderAttachments();updateButtons();
    }
    private void options(){new AlertDialog.Builder(this).setTitle("StoryLens connection").setItems(new String[]{"Refresh connection","Clear downloaded cache","Forget this connection"},(d,index)->{
        if(index==0){disconnect();if(active)connect();}
        if(index==1){if(downloading||uploading){notice("Transfer running","Wait for this file transfer to finish.");return;}pausePreview();filesWorker.execute(()->{removeTree(new File(getCacheDir(),"received"));ui(()->{cachedFiles.clear();notice("Cache cleared","Saved or shared copies outside StoryLens are unchanged.");});});}
        if(index==2)new AlertDialog.Builder(this).setTitle("Forget connection?").setMessage("This removes the phone's connection and cached files. Laptop chats and jobs stay intact. Revoke this phone on the laptop if the device is lost.").setNegativeButton("Keep",null).setPositiveButton("Forget",(a,b)->{disconnect();try{pairingStore.forget();local.edit().clear().apply();pairing=null;chatId="";attachments.clear();draft="";pausePreview();filesWorker.execute(()->removeTree(new File(getCacheDir(),"received")));cachedFiles.clear();showPairing();}catch(Exception e){notice("Not removed","Secure connection removal failed. Please try again.");}}).show();
    }).show();}
    private static void removeTree(File f){File[] children=f.listFiles();if(children!=null)for(File child:children)removeTree(child);if(f.exists())f.delete();}
    private void request(String method,Map<String,Object> params,Consumer<Map<String,Object>> success,Consumer<Throwable> failure){
        if(tunnel==null){failure.accept(new java.io.IOException("Connection paused. Return to StoryLens and refresh."));return;}final int generation=epoch;tunnel.request(method,params).whenComplete((r,e)->ui(()->{if(generation!=epoch)return;if(e!=null)failure.accept(e);else success.accept(r);}));
    }
    private void refreshState(Runnable after){if(after!=null)stateAfter=after;if(pollingState||tunnel==null)return;pollingState=true;request("state",Map.of(),r->{pollingState=false;connection.setText(Boolean.TRUE.equals(r.get("connected"))?"Laptop connected · encrypted relay":"Laptop offline · waiting for its connection");chats=objects(r.get("chats"));Runnable done=stateAfter;stateAfter=null;if(done!=null)done.run();},e->{pollingState=false;connection.setText("Waiting for laptop · refresh when connected");Runnable done=stateAfter;stateAfter=null;if(done!=null)done.run();});}
    private void refreshChat(Runnable after){if(after!=null)chatAfter=after;if(chatId.isEmpty()||pollingChat||tunnel==null)return;pollingChat=true;final String id=chatId;request("chat",Map.of("chat",id),r->{pollingChat=false;if(!id.equals(chatId))return;Map<String,Object> snapshot=r.get("chat") instanceof Map?Json.object(r.get("chat")):r;renderChat(snapshot);Runnable done=chatAfter;chatAfter=null;if(done!=null)done.run();},e->{pollingChat=false;Runnable done=chatAfter;chatAfter=null;if(done!=null)notice("Chat not refreshed",friendly(e));});}
    private void manualRefresh(){refreshState(null);refreshChat(()->{if(uncertain())new AlertDialog.Builder(this).setTitle("Check the chat above").setMessage("The previous send was not confirmed. Do not repeat it if it already arrived. Clear that draft and continue with a new message?").setNegativeButton("Keep checking",null).setPositiveButton("Clear draft",(d,w)->{local.edit().remove("uncertain_chat").remove("uncertain_id").apply();composer.setText("");attachments.clear();renderAttachments();updateButtons();}).show();});}
    private boolean uncertain(){return chatId.equals(local.getString("uncertain_chat","!"));}
    private void updateButtons(){if(send==null)return;boolean ready=tunnel!=null&&!chatId.isEmpty();send.setEnabled(ready&&!sending&&!uploading&&!uncertain());send.setText(uncertain()?"Check chat first":sending?"Sending…":"Send");attach.setEnabled(ready&&!uploading&&!sending&&!uncertain());stop.setEnabled(ready&&!stopping);check.setText(uncertain()?"Check chat":"Refresh");}
    private void showChats(){if(uploading||sending){notice("Please wait","Finish this send or attachment transfer before changing chats.");return;}refreshState(null);List<String> labels=new ArrayList<>();for(Map<String,Object> c:chats)labels.add(str(c,"title","Untitled chat")+"\n"+str(c,"status",""));new AlertDialog.Builder(this).setTitle("Chats").setItems(labels.toArray(new String[0]),(d,n)->selectChat(str(chats.get(n),"id",""))).setNeutralButton("Refresh",(d,n)->refreshState(this::showChats)).setPositiveButton("New",(d,n)->newChat()).setNegativeButton("Close",null).show();}
    private void selectChat(String id){if(id.isEmpty())return;chatId=id;local.edit().putString("chat",id).apply();composer.setText("");attachments.clear();rendered="";pollingChat=false;messages.removeAllViews();renderAttachments();refreshChat(null);updateButtons();}
    private void newChat(){if(uploading||sending)return;String id=UUID.randomUUID().toString();request("create_chat",Map.of("request_id",id),r->{Object chat=r.get("chat");String created=chat instanceof Map?str(Json.object(chat),"id",""):chat instanceof String?(String)chat:str(r,"id","");if(created.isEmpty()){notice("Chat not confirmed","Refresh the Chats list before creating another chat.");return;}selectChat(created);refreshState(null);},e->notice("Chat creation not confirmed","Refresh Chats before trying again. "+friendly(e)));}
    private void sendMessage(){
        if(sending||uploading||uncertain()||chatId.isEmpty())return;String message=composer.getText().toString().trim();if(message.isEmpty()&&attachments.isEmpty())return;
        String requestId=UUID.randomUUID().toString();List<String> ids=new ArrayList<>();for(Map<String,Object> a:attachments)ids.add(str(a,"id",""));String currentChat=chatId;int selected=profile.getSelectedItemPosition();if(!local.edit().putInt("profile",selected).putString("uncertain_chat",chatId).putString("uncertain_id",requestId).commit()){notice("Send not started","The phone could not save delivery tracking. Free some storage and try again.");return;}sending=true;updateButtons();
        request("send",Map.of("chat",currentChat,"request_id",requestId,"message",message,"attachments",ids,"profile",new String[]{"general","cricket","gaming"}[selected]),r->{sending=false;local.edit().remove("uncertain_chat").remove("uncertain_id").apply();composer.setText("");attachments.clear();renderAttachments();updateButtons();refreshChat(null);},e->{sending=false;updateButtons();notice("Send not confirmed",friendly(e)+" Your message has not been automatically repeated.");refreshChat(null);});
    }
    private void stopChat(){if(stopping||chatId.isEmpty())return;stopping=true;updateButtons();request("stop",Map.of("chat",chatId),r->{stopping=false;updateButtons();refreshChat(null);},e->{stopping=false;updateButtons();notice("Stop not confirmed",friendly(e));});}
    private void renderChat(Map<String,Object> r){
        String name=str(r,"title","StoryLens");title.setText(name.length()>22?name.substring(0,22)+"…":name);String status=str(r,"status",""),operation=str(r,"stage","");if(!uploading&&!downloading)stage.setText(operation.isEmpty()?status:operation);showProgress(r.get("task_progress"),status);
        String signature=Json.stringify(Arrays.asList(r.get("messages"),r.get("files"),r.get("attachments")));if(signature.equals(rendered))return;rendered=signature;
        boolean bottom=scroll.getChildCount()==0||scroll.getScrollY()+scroll.getHeight()+dp(120)>=scroll.getChildAt(0).getHeight();int oldY=scroll.getScrollY();messages.removeAllViews();
        for(Map<String,Object> m:objects(r.get("messages"))){LinearLayout bubble=column();bubble.setPadding(dp(10),dp(8),dp(10),dp(8));bubble.setBackground(panel(str(m,"role","").equals("user")?0xff2c2723:PANEL));LinearLayout.LayoutParams space=new LinearLayout.LayoutParams(-1,-2);space.setMargins(0,dp(6),0,dp(6));TextView role=text(str(m,"role","").equals("user")?"You":"StoryLens",12,ORANGE);bubble.addView(role);TextView content=text(str(m,"text",""),16,TEXT);content.setTextIsSelectable(true);bubble.addView(content);Object err=m.get("error");if(err!=null&&!Boolean.FALSE.equals(err)&&!err.toString().isEmpty())bubble.addView(text(err instanceof String?(String)err:"This step did not finish. Check the laptop for details.",13,0xffffb997));Object details=m.get("error_details");if(details!=null&&!details.toString().isEmpty())bubble.addView(button("Technical details",()->notice("Technical details",details instanceof String?(String)details:Json.stringify(details))));messages.addView(bubble,space);}
        for(Map<String,Object> file:objects(r.get("files"))){String id=str(file,"id","");if(!id.isEmpty())messages.addView(button("↓ "+str(file,"name","File")+" · "+sizeText(number(file.get("size"),0)),()->downloadFile(id)));}
        for(Map<String,Object> a:objects(r.get("attachments")))messages.addView(text("Attached · "+str(a,"name","File"),12,MUTED));
        scroll.post(()->{if(bottom)scroll.fullScroll(View.FOCUS_DOWN);else scroll.scrollTo(0,oldY);});
    }
    private void showProgress(Object raw,String status){
        if(uploading||downloading)return;boolean running=status.matches("(?i).*(running|working|queued|processing|pending).*");Map<String,Object> p=raw instanceof Map?Json.object(raw):Map.of();long total=number(p.get("total"),0),done=number(p.get("completed"),-1);
        progress.setVisibility(running||!p.isEmpty()?View.VISIBLE:View.GONE);if(total>0&&done>=0&&done<=total){progress.setIndeterminate(false);progress.setMax(1000);progress.setProgress((int)(done*1000/total));stage.setText(stage.getText()+" · "+done+"/"+total+" complete · "+(total-done)+" remaining");}else progress.setIndeterminate(true);
    }
    private void transferProgress(String label,long done,long total){ui(()->{if(stage==null)return;stage.setText(label+" · "+sizeText(done)+" / "+sizeText(total));progress.setVisibility(View.VISIBLE);progress.setIndeterminate(total<=0);if(total>0){progress.setMax(1000);progress.setProgress((int)Math.min(1000,done*1000/total));}});}
    private void renderAttachments(){if(attachRow==null)return;attachRow.removeAllViews();for(Map<String,Object> a:new ArrayList<>(attachments)){String name=str(a,"name","File");Button b=button((name.length()>16?name.substring(0,16)+"…":name)+" ×",()->{attachments.remove(a);renderAttachments();});attachRow.addView(b,new LinearLayout.LayoutParams(0,dp(48),1));}}
    private void pickAttachment(){if(attachments.size()>=4){notice("Attachment limit","Send these four attachments before adding more.");return;}Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(pick,PICK_ATTACHMENT);}
    @Override protected void onActivityResult(int request,int result,Intent data){super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;if(request==PICK_ATTACHMENT)pendingUpload=data.getData();if(request==PICK_CONNECTION)pendingConnection=data.getData();if(request==SAVE_FILE&&pendingSave!=null){File source=pendingSave;pendingSave=null;saveFile(source,data.getData());}if(resumed)consumePickers();}
    private void consumePickers(){if(pendingConnection!=null){Uri uri=pendingConnection;pendingConnection=null;filesWorker.execute(()->{try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new java.io.IOException();ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] b=new byte[1024];int n;while((n=in.read(b))!=-1){if(out.size()+n>4096)throw new java.io.IOException("This is not a small StoryLens connection file.");out.write(b,0,n);}String code=out.toString("UTF-8").trim();Pairing next=Pairing.parse(code);pairingStore.save(code);ui(()->{pairing=next;showChat();if(active)connect();});}catch(Exception e){ui(()->notice("Connection file not imported",e instanceof IllegalArgumentException?e.getMessage():"Choose the private .slconnect text file made by your laptop. It must be smaller than 4 KiB."));}});}if(pendingUpload!=null&&tunnel!=null){Uri uri=pendingUpload;pendingUpload=null;upload(uri);}}
    private Map<String,Object> waitFor(Tunnel client,String method,Map<String,Object> params)throws Exception{return client.request(method,params).get(70,TimeUnit.SECONDS);}
    private void upload(Uri uri){
        if(uploading||chatId.isEmpty())return;uploading=true;updateButtons();final Tunnel client=tunnel;final int generation=epoch;final String target=chatId;
        filesWorker.execute(()->{try{
            String name="attachment";long size=-1;try(Cursor c=getContentResolver().query(uri,new String[]{OpenableColumns.DISPLAY_NAME,OpenableColumns.SIZE},null,null,null)){if(c!=null&&c.moveToFirst()){int n=c.getColumnIndex(OpenableColumns.DISPLAY_NAME),s=c.getColumnIndex(OpenableColumns.SIZE);if(n>=0)name=c.getString(n);if(s>=0&&!c.isNull(s))size=c.getLong(s);}}
            if(size<0)throw new IllegalArgumentException("This file provider does not report its size. Save a local copy, then attach that copy.");Transfer.validateSize(size);name=Transfer.safeName(name);String rid=UUID.randomUUID().toString();
            Map<String,Object> begin=waitFor(client,"upload_begin",Map.of("chat",target,"request_id",rid,"name",name,"size",size));String upload=Json.string(begin,"upload");long sent=0;int index=0;
            try(InputStream in=getContentResolver().openInputStream(uri)){if(in==null)throw new java.io.IOException("Cannot read selected file.");byte[] buffer=new byte[Transfer.CHUNK];while(sent<size){if(generation!=epoch)throw new java.io.IOException("Transfer paused. Reattach the file after reconnecting.");int needed=(int)Math.min(buffer.length,size-sent),read=0;while(read<needed){int got=in.read(buffer,read,needed-read);if(got<0)throw new java.io.IOException("The selected file changed while reading.");read+=got;}Map<String,Object> ack=waitFor(client,"upload_chunk",Map.of("upload",upload,"index",index,"data",Codec.encode(Arrays.copyOf(buffer,read))));if(Json.integer(ack,"next_index")!=index+1)throw new java.io.IOException("Attachment acknowledgement is out of order.");index++;sent+=read;transferProgress("Attaching",sent,size);}if(in.read()!=-1)throw new java.io.IOException("The selected file grew while reading.");}
            Map<String,Object> result=waitFor(client,"upload_finish",Map.of("upload",upload));Map<String,Object> attachment=result.get("attachment") instanceof Map?Json.object(result.get("attachment")):result;Json.string(attachment,"id");ui(()->{if(generation==epoch&&target.equals(chatId)){attachments.add(attachment);renderAttachments();stage.setText("Attached · "+str(attachment,"name","File"));}});
        }catch(Exception e){ui(()->notice("Attachment not ready",friendly(e)+" No message was automatically sent."));}finally{ui(()->{uploading=false;updateButtons();if(progress!=null)progress.setVisibility(View.GONE);});}});
    }
    private void downloadFile(String id){
        if(downloading){notice("Download running","Wait for the current file to finish.");return;}File cached=cachedFiles.get(id);if(cached!=null&&cached.isFile()){showFile(cached,mimeFor(cached));return;}if(tunnel==null)return;downloading=true;final Tunnel client=tunnel;final int generation=epoch;
        filesWorker.execute(()->{File output=null;try{Map<String,Object> info=waitFor(client,"file_info",Map.of("file",id));if(!id.equals(Json.string(info,"id")))throw new java.io.IOException("File identity changed.");long size=Json.integer(info,"size");Transfer.validateSize(size);String name=Transfer.safeName(Json.string(info,"name"));String mime=safeMime(str(info,"mime","application/octet-stream"));File folder=new File(getCacheDir(),"received/"+UUID.randomUUID());if(!folder.mkdirs())throw new java.io.IOException("Phone cache is unavailable.");output=new File(folder,name);long offset=0;
            try(OutputStream out=new FileOutputStream(output)){while(offset<size){if(generation!=epoch)throw new java.io.IOException("Download paused. Tap the file again after returning.");int length=(int)Math.min(Transfer.CHUNK,size-offset);Map<String,Object> result=waitFor(client,"file_chunk",Map.of("file",id,"offset",offset,"length",length));byte[] bytes=Transfer.chunk(result,offset,length,size);out.write(bytes);offset+=bytes.length;transferProgress("Downloading",offset,size);}}
            File finished=output;ui(()->{if(generation==epoch){cachedFiles.put(id,finished);showFile(finished,mime);}});
        }catch(Exception e){if(output!=null)output.delete();ui(()->notice("File not downloaded",friendly(e)));}finally{ui(()->{downloading=false;if(progress!=null)progress.setVisibility(View.GONE);});}});
    }
    private void showFile(File file,String mime){
        pausePreview();LinearLayout body=column();body.setPadding(dp(14),dp(8),dp(14),dp(8));body.addView(text(file.getName()+" · "+sizeText(file.length()),14,TEXT));
        if(mime.startsWith("image/")){try{BitmapFactory.Options bounds=new BitmapFactory.Options();bounds.inJustDecodeBounds=true;BitmapFactory.decodeFile(file.getAbsolutePath(),bounds);if(bounds.outWidth<=0||bounds.outHeight<=0)throw new IllegalArgumentException();BitmapFactory.Options options=new BitmapFactory.Options();options.inSampleSize=1;while(bounds.outWidth/options.inSampleSize>1800||bounds.outHeight/options.inSampleSize>1800)options.inSampleSize*=2;Bitmap bitmap=BitmapFactory.decodeFile(file.getAbsolutePath(),options);if(bitmap==null)throw new IllegalArgumentException();ImageView image=new ImageView(this);image.setContentDescription(file.getName());image.setScaleType(ImageView.ScaleType.FIT_CENTER);image.setImageBitmap(bitmap);body.addView(image,new LinearLayout.LayoutParams(-1,dp(300)));}catch(Exception e){body.addView(text("Preview unavailable. Save or share the original file.",14,MUTED));}}
        else if(mime.startsWith("video/")){video=new VideoView(this);video.setVideoURI(Uri.fromFile(file));MediaController controls=new MediaController(this);controls.setAnchorView(video);video.setMediaController(controls);video.setOnErrorListener((p,what,extra)->{notice("Preview unavailable","This phone may not support the file's codec. Save or share the original.");return true;});body.addView(video,new LinearLayout.LayoutParams(-1,dp(280)));body.addView(button("Play / pause",()->{if(video!=null){if(video.isPlaying())video.pause();else video.start();}}));}
        else if(mime.startsWith("audio/")){body.addView(button("Play / pause audio",()->{try{if(player==null){player=new MediaPlayer();player.setDataSource(file.getAbsolutePath());player.setOnPreparedListener(p->p.start());player.setOnErrorListener((p,w,e)->{notice("Audio unavailable","Save the original file to play it in a compatible player.");return true;});player.prepareAsync();}else if(player.isPlaying())player.pause();else player.start();}catch(Exception e){notice("Audio unavailable","Save or share the original file.");}}));}
        else body.addView(text("Save or share this file using Android. Remote links are never opened automatically.",14,MUTED));
        LinearLayout actions=row();actions.addView(button("Save file",()->{pendingSave=file;Intent save=new Intent(Intent.ACTION_CREATE_DOCUMENT).setType(mime).addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE,file.getName());startActivityForResult(save,SAVE_FILE);}));actions.addView(button("Share",()->share(file,mime)));body.addView(actions);preview=new AlertDialog.Builder(this).setView(body).setNegativeButton("Close",null).create();preview.setOnDismissListener(d->pauseMedia());preview.show();
    }
    private void pauseMedia(){if(video!=null){video.stopPlayback();video=null;}if(player!=null){player.release();player=null;}}
    private void pausePreview(){pauseMedia();if(preview!=null){AlertDialog old=preview;preview=null;old.dismiss();}}
    private void share(File file,String mime){try{Uri uri=FileProvider.getUriForFile(this,getPackageName()+".files",file);Intent share=new Intent(Intent.ACTION_SEND).setType(mime).putExtra(Intent.EXTRA_STREAM,uri).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);share.setClipData(android.content.ClipData.newRawUri("StoryLens file",uri));startActivity(Intent.createChooser(share,"Share file"));}catch(Exception e){notice("Share unavailable","Save the file instead.");}}
    private void saveFile(File source,Uri destination){filesWorker.execute(()->{try(InputStream in=new FileInputStream(source);OutputStream out=getContentResolver().openOutputStream(destination,"wt")){if(out==null)throw new java.io.IOException();byte[] b=new byte[32768];int n;while((n=in.read(b))!=-1)out.write(b,0,n);ui(()->notice("Saved",source.getName()));}catch(Exception e){ui(()->notice("Save failed","The destination could not be written. The private downloaded copy is still available; an incomplete destination may need removing."));}});}
    private void notice(String heading,String message){if(!isFinishing()&&!isDestroyed())new AlertDialog.Builder(this).setTitle(heading).setMessage(message==null?"This operation did not finish. Refresh and check the laptop.":message).setPositiveButton("OK",null).show();}
    private static String friendly(Throwable e){while(e.getCause()!=null)e=e.getCause();if(e instanceof Tunnel.RemoteError)return e.getMessage();if(e instanceof IllegalArgumentException||e instanceof java.io.IOException)return e.getMessage();return "The laptop did not confirm this step. Keep the app open, check the connection, and refresh.";}
    private static String str(Map<String,Object> m,String key,String fallback){Object v=m.get(key);return v instanceof String?(String)v:fallback;}
    private static long number(Object v,long fallback){return v instanceof Number?((Number)v).longValue():fallback;}
    private static List<Map<String,Object>> objects(Object value){List<Map<String,Object>> out=new ArrayList<>();if(value instanceof List)for(Object item:(List<?>)value)if(item instanceof Map)out.add(Json.object(item));return out;}
    private static String safeMime(String mime){return mime.matches("[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")?mime:"application/octet-stream";}
    private static String mimeFor(File file){String ext=android.webkit.MimeTypeMap.getFileExtensionFromUrl(Uri.fromFile(file).toString());String mime=android.webkit.MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext.toLowerCase(java.util.Locale.ROOT));return mime==null?"application/octet-stream":mime;}
    private static String sizeText(long bytes){return bytes>=1024*1024?String.format(java.util.Locale.ROOT,"%.1f MiB",bytes/1048576.0):bytes>=1024?String.format(java.util.Locale.ROOT,"%.0f KiB",bytes/1024.0):bytes+" B";}
}
