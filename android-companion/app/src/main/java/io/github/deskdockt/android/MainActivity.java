package io.github.deskdockt.android;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.*;

/** ADB-first home screen. Configuration lives in Settings. */
public final class MainActivity extends Activity {
    private TextView status;
    private Button start, permission, debugging, other;
    private boolean autoStarted, onboarding;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Runnable refresh=new Runnable(){public void run(){
        boolean enabled=getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("connect_on_start",false);
        if(enabled && !autoStarted && ControlService.instance!=null){autoStarted=true;startSharing();}
        String message=ServerService.isConnected()?"Connected to desktop":ServerService.isRunning()?"Ready for your desktop":ControlService.instance==null?"Enable input control to get started":"Ready to start sharing";
        if(!message.contentEquals(status.getText()))status.setText(message);
        String action=ServerService.isRunning()?"Stop sharing":"Start sharing";
        if(!action.contentEquals(start.getText()))start.setText(action);
        permission.setVisibility(ControlService.instance==null?android.view.View.VISIBLE:android.view.View.GONE);
        debugging.setVisibility((SetupLinks.debuggingEnabled(MainActivity.this) || getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false))?android.view.View.GONE:android.view.View.VISIBLE);
        String otherLabel=getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false)?"Other connection: LOCAL (cable / ADB)":"Other connection: WiFi (net)";
        if(!otherLabel.contentEquals(other.getText()))other.setText(otherLabel);
        handler.postDelayed(this,1000);
    }};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        android.content.SharedPreferences preferences=getSharedPreferences("pairing",MODE_PRIVATE);
        // Existing installations keep their setup; new installs see the welcome flow.
        if(!preferences.contains("setup_complete") && (preferences.contains("code") || preferences.contains("connect_on_start") || preferences.contains("wifi_enabled")))
            preferences.edit().putBoolean("setup_complete",true).apply();
        if(!preferences.getBoolean("setup_complete",false)){
            preferences.edit().putBoolean("setup_complete",false).apply();
            onboarding=true;startActivity(new Intent(this,WelcomeActivity.class));finish();return;
        }
        autoStarted=state!=null && state.getBoolean("autoStarted");
        int padding=(int)(24*getResources().getDisplayMetrics().density);
        LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(padding,padding,padding,padding);
        ScrollView scroll=new ScrollView(this);scroll.addView(content);setContentView(scroll);
        content.setOnApplyWindowInsetsListener((view,insets)->{
            if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars());view.setPadding(padding+bars.left,padding+bars.top,padding+bars.right,padding+bars.bottom);}
            else view.setPadding(padding,padding+insets.getSystemWindowInsetTop(),padding,padding+insets.getSystemWindowInsetBottom());
            return insets;
        });
        ImageView icon=new ImageView(this);icon.setImageResource(R.drawable.app_icon);content.addView(icon,new LinearLayout.LayoutParams(padding*4,padding*4));
        TextView title=new TextView(this);title.setText("desk dockt");title.setTextSize(30);content.addView(title);
        TextView intro=new TextView(this);intro.setText("Your desktop mouse and keyboard, on your phone.\n\nConnect USB, authorize USB debugging, and connect from your desktop. Wi-Fi is optional and can be configured in Settings.");content.addView(intro);
        status=new TextView(this);status.setTextSize(20);content.addView(status);
        permission=new Button(this);permission.setText("Enable input control");permission.setOnClickListener(view->SetupLinks.open(this,new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));content.addView(permission);
        debugging=new Button(this);debugging.setText("Set up USB debugging");debugging.setOnClickListener(view->SetupLinks.debugging(this));content.addView(debugging);
        start=new Button(this);start.setOnClickListener(view->{
            autoStarted=true;
            if(ServerService.isRunning())stopService(new Intent(this,ServerService.class));else startSharing();
        });content.addView(start);
        other=new Button(this);other.setOnClickListener(view->startActivity(new Intent(this,WelcomeActivity.class).putExtra("details",true).putExtra("wifi",!getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false))));content.addView(other);
        Button settings=new Button(this);settings.setText("Settings");settings.setOnClickListener(view->startActivity(new Intent(this,SettingsActivity.class)));content.addView(settings);
    }
    private void startSharing(){
        if(ControlService.instance==null){Toast.makeText(this,"Enable desk dockt input control first",Toast.LENGTH_LONG).show();return;}
        android.content.SharedPreferences preferences=getSharedPreferences("pairing",MODE_PRIVATE);
        boolean wifi=preferences.getBoolean("wifi_enabled",false);
        if(wifi && android.os.Build.VERSION.SDK_INT>=37 && checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK")!=android.content.pm.PackageManager.PERMISSION_GRANTED)wifi=false;
        if(android.os.Build.VERSION.SDK_INT>=33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},1);
        startForegroundService(new Intent(this,ServerService.class).putExtra("wifi",wifi).putExtra("port",preferences.getInt("wifi_port",19674)));
    }
    @Override public void onResume(){super.onResume();if(!onboarding)handler.post(refresh);}
    @Override public void onPause(){handler.removeCallbacks(refresh);super.onPause();}
    @Override public void onSaveInstanceState(Bundle state){state.putBoolean("autoStarted",autoStarted);super.onSaveInstanceState(state);}
}
