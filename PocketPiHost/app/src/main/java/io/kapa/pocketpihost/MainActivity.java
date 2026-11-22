package io.kapa.pocketpihost;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
 private final ExecutorService worker=Executors.newSingleThreadExecutor();
 private final int BG=0xff10131e, ROSE=0xfff19cbe, MUTED=0xffb6b7c7;
 private TextView state, output; private EditText token;
 private final String base="http://127.0.0.1:9090";
 @Override public void onCreate(Bundle b) {
  super.onCreate(b);
  getWindow().setStatusBarColor(BG); getWindow().setNavigationBarColor(BG);
  ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(BG);
  LinearLayout root=new LinearLayout(this);root.setPadding(25,28,25,28);root.setOrientation(1);scroll.addView(root);setContentView(scroll);
  title(root,"POCKET PI-HOLE HOST",26,Color.WHITE);
  title(root,"GrapheneOS • Podroid VM controller • v0.1",14,MUTED);
  title(root,"LIVE STATUS",15,ROSE);
  state=title(root,"Not connected",20,Color.WHITE);
  title(root,"Requires Podroid running with two port forwards.",13,MUTED);
  title(root,"ONE-TIME VM TOKEN",15,ROSE);
  token=new EditText(this);
  token.setHint("Paste 64-character token from VM setup");
  token.setHintTextColor(MUTED);token.setTextColor(Color.WHITE);
  token.setSingleLine(true);
  token.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);
  root.addView(token,new LinearLayout.LayoutParams(-1,-2));
  button(root,"Save token securely",()->{
   try { SecretStore.save(this,token.getText().toString().trim());token.setText("");say("Token saved using Android Keystore.");status(); }
   catch(Exception e){say(e.getMessage());}
  });
  title(root,"CONTAINER CONTROLS",15,ROSE);
  button(root,"Check status",this::status);
  button(root,"Start Pi-hole",()->api("POST","/start"));
  button(root,"Stop Pi-hole",()->api("POST","/stop"));
  button(root,"Restart Pi-hole",()->api("POST","/restart"));
  button(root,"Refresh Gravity blocklists",()->api("POST","/gravity"));
  title(root,"SETUP AND DASHBOARD",15,ROSE);
  button(root,"Open Podroid / Start Linux VM",()->{
    Intent i=getPackageManager().getLaunchIntentForPackage("com.excp.podroid");
    if(i!=null) startActivity(i);
    else open("https://github.com/ExTV/Podroid/releases");
  });
  button(root,"Open local Pi-hole dashboard",()->open("http://127.0.0.1:8081/admin/"));
  button(root,"View VM setup instructions",()->open("https://github.com/JamosisKlyde/ApkBridge/tree/pocket-pihole-v0.1-prototype/PocketPiHost"));
  title(root,"ACTIVITY",15,ROSE);
  output=title(root,"Start Podroid, run setup, then save the controller token.",13,MUTED);
  title(root,"VM/Docker startup is managed by Podroid. Android cannot guarantee 24/7 operation or standard home-network DNS on port 53.",12,MUTED);
  status();
 }
 private TextView title(LinearLayout box,String s,int size,int color) {
   TextView t=new TextView(this);t.setText(s);t.setTextSize(size);t.setTextColor(color);
   t.setPadding(1,10,1,10);if(size>=15)t.setTypeface(null,Typeface.BOLD);
   box.addView(t);return t;
 }
 private void button(LinearLayout box,String text,Runnable task) {
   Button b=new Button(this);b.setText(text);b.setAllCaps(false);
   b.setTextColor(BG);b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(ROSE));
   box.addView(b,new LinearLayout.LayoutParams(-1,-2));b.setOnClickListener(v->task.run());
 }
 private void say(String text){runOnUiThread(()->{if(output!=null)output.setText(text);});}
 private void status(){api("GET","/status");}
 private void open(String url){startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}
 private void api(String method,String path) {
   worker.execute(()->{
    HttpURLConnection c=null;
    try{
      String secret=SecretStore.load(this);
      if(secret.isEmpty()){say("Save your VM agent token first.");return;}
      c=(HttpURLConnection)new URL(base+path).openConnection();
      c.setRequestMethod(method);c.setConnectTimeout(4000);c.setReadTimeout(15000);
      c.setRequestProperty("X-Pocket-Token",secret);
      if("POST".equals(method)){c.setDoOutput(true);c.setFixedLengthStreamingMode(0);}
      int code=c.getResponseCode();
      var stream=code<400?c.getInputStream():c.getErrorStream();
      String data=new String(stream.readAllBytes(),StandardCharsets.UTF_8);
      JSONObject obj=new JSONObject(data);
      if(code>=400){say(obj.optString("error","HTTP "+code));return;}
      if("/status".equals(path)){
        boolean docker=obj.optBoolean("docker_running"),running=obj.optBoolean("container_running"),blocking=obj.optBoolean("blocking_enabled");
        runOnUiThread(()->state.setText(!docker?"Docker unavailable":running?(blocking?"Pi-hole running • blocking enabled":"Pi-hole running"):"Pi-hole stopped"));
        say("Docker: "+docker+" | Pi-hole: "+running+" | Blocking: "+blocking+" | Updating: "+obj.optBoolean("updating"));
      }else{say(obj.optString("message","Command sent"));if(!path.equals("/gravity"))status();}
    }catch(Exception e){runOnUiThread(()->state.setText("VM agent unreachable"));say("Start Podroid and check port 9090 forward: "+e.getMessage());}
    finally{if(c!=null)c.disconnect();}
   });
 }
 @Override protected void onDestroy(){worker.shutdownNow();super.onDestroy();}
}
