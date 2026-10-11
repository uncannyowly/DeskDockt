package io.github.deskdockt.android;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.view.View;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

/** First-launch connection choice and native setup shortcuts. */
public final class WelcomeActivity extends Activity {
    private LinearLayout content;
    private boolean wifi, details;
    private CheckBox startup;
    private TextView readiness;
    private int space;
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        SharedPreferences preferences=getSharedPreferences("pairing",MODE_PRIVATE);
        wifi=state==null?getIntent().getBooleanExtra("wifi",preferences.getBoolean("wifi_enabled",false)):state.getBoolean("wifi");
        details=state==null?getIntent().getBooleanExtra("details",false):state.getBoolean("details");
        space=(int)(24*getResources().getDisplayMetrics().density);
        content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(space,space,space,space);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.addView(content);setContentView(scroll);
        content.setOnApplyWindowInsetsListener((view,insets)->{
            if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars());view.setPadding(space+bars.left,space+bars.top,space+bars.right,space+bars.bottom);}
            else view.setPadding(space,space+insets.getSystemWindowInsetTop(),space,space+insets.getSystemWindowInsetBottom());
            return insets;
        });
        render();
    }
    private void text(String value,int size){
        TextView label=new TextView(this);label.setText(value);label.setTextSize(size);
        label.setPadding(0,space/3,0,space/3);content.addView(label);
    }
    private void button(String label,Runnable action){
        Button button=new Button(this);button.setText(label);button.setOnClickListener(view->action.run());content.addView(button);
    }
    private void render(){
        readiness=null;content.removeAllViews();
        ImageView icon=new ImageView(this);icon.setImageResource(R.drawable.app_icon);
        content.addView(icon,new LinearLayout.LayoutParams(space*3,space*3));
        text(details?"Make it yours":"Welcome to desk dockt",30);
        text(details?"2 of 2 · Prepare your phone":"1 of 2 · Choose your connection",16);
        if(!details){
            text("One mouse and keyboard, across your desktop and phone. Free, open source, and ready for your setup.",18);
            RadioGroup choices=new RadioGroup(this);
            RadioButton cable=new RadioButton(this);cable.setId(View.generateViewId());cable.setText("LOCAL (cable)\nUSB connection · no app pairing code");
            RadioButton network=new RadioButton(this);network.setId(View.generateViewId());network.setText("WiFi (net)\nSame network · secure pairing · no USB debugging");
            for(RadioButton choice:new RadioButton[]{cable,network}){
                choice.setTextSize(18);choice.setPadding(space/2,space,space/2,space);
                choice.setBackgroundTintList(android.content.res.ColorStateList.valueOf(Color.rgb(233,243,247)));
                choices.addView(choice,new RadioGroup.LayoutParams(-1,-2));
            }
            choices.check(wifi?network.getId():cable.getId());
            choices.setOnCheckedChangeListener((group,id)->wifi=id==network.getId());
            content.addView(choices);
            text("You can change this later in Settings. Cable access remains available when Wi-Fi is configured.",16);
            button("Continue",()->{details=true;render();});
            return;
        }
        text(wifi?"WiFi (net)":"LOCAL (cable)",22);
        button(wifi?"Other connection: LOCAL (cable / ADB)":"Other connection: WiFi (net)",()->{wifi=!wifi;readiness=null;render();});
        text("Enable desk dockt input control so your desktop can move, click and interact with your phone. Android will ask you to approve it.",16);
        button("Enable input control",()->SetupLinks.open(this,new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        if(wifi){
            text("Connect both devices to the same network. Enable and select the desk dockt keyboard for typing. Your pairing code and certificate fingerprint will be in Settings.",16);
            button("Wi-Fi network settings",()->SetupLinks.open(this,new Intent(Settings.ACTION_WIFI_SETTINGS)));
            button("Enable desk dockt keyboard",()->SetupLinks.open(this,new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
            button("Select desk dockt keyboard",()->getSystemService(InputMethodManager.class).showInputMethodPicker());
        }else{
            text("Connect a USB cable, enable USB debugging, and approve your desktop when Android asks. The desktop sets up the keyboard automatically.",16);
            button("Set up USB debugging",()->SetupLinks.debugging(this));
        }
        readiness=new TextView(this);readiness.setPadding(0,space/2,0,space/2);content.addView(readiness);updateReadiness();
        startup=new CheckBox(this);startup.setText("Connect on start");
        startup.setChecked(getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("connect_on_start",false));content.addView(startup);
        startup.setOnCheckedChangeListener((view,enabled)->getSharedPreferences("pairing",MODE_PRIVATE).edit().putBoolean("connect_on_start",enabled).apply());
        text("Prepare sharing whenever you launch the app. You can finish setup permissions later if needed.",16);
        button(wifi?"Finish · View Wi-Fi pairing":"Finish setup",this::complete);
        button("Change connection",()->{details=false;render();});
    }
    private void updateReadiness(){
        if(readiness==null)return;
        boolean input=ControlService.instance!=null;
        boolean keyboard=String.valueOf(Settings.Secure.getString(getContentResolver(),"default_input_method")).startsWith(getPackageName()+"/");
        readiness.setText("Input control: "+(input?"enabled":"needs setup")+"\n"+(wifi?"Keyboard: "+(keyboard?"selected":"needs setup"):"USB debugging: "+(SetupLinks.debuggingEnabled(this)?"enabled":"needs setup")));
    }
    private void complete(){
        if(wifi && android.os.Build.VERSION.SDK_INT>=37 && checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK")!=android.content.pm.PackageManager.PERMISSION_GRANTED){
            requestPermissions(new String[]{"android.permission.ACCESS_LOCAL_NETWORK"},3);return;
        }
        boolean restart=ServerService.isRunning() && wifi!=getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false);
        getSharedPreferences("pairing",MODE_PRIVATE).edit().putBoolean("wifi_enabled",wifi).putBoolean("setup_complete",true).apply();
        if(restart){
            stopService(new Intent(this,ServerService.class));
            if(ControlService.instance!=null)startForegroundService(new Intent(this,ServerService.class).putExtra("wifi",wifi).putExtra("port",getSharedPreferences("pairing",MODE_PRIVATE).getInt("wifi_port",19674)));
            Toast.makeText(this,"Connection changed. Reconnect from your desktop.",Toast.LENGTH_LONG).show();
        }
        Intent home=new Intent(this,MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP|Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(home);
        if(wifi)startActivity(new Intent(this,SettingsActivity.class));
        finish();
    }
    @Override public void onResume(){super.onResume();updateReadiness();}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==3){
            if(results.length>0 && results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED)complete();
            else Toast.makeText(this,"Wi-Fi needs local network permission. Try again or choose LOCAL (cable).",Toast.LENGTH_LONG).show();
        }
    }
    @Override public void onSaveInstanceState(Bundle state){state.putBoolean("wifi",wifi);state.putBoolean("details",details);super.onSaveInstanceState(state);}
}
