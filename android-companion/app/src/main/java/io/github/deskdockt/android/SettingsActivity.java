package io.github.deskdockt.android;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.view.inputmethod.InputMethodManager;
import android.widget.*;

/** Newly written setup UI; no original app classes or licensing code. */
public final class SettingsActivity extends Activity {
    private Button debugging, other;
    private Switch wifi;private EditText port;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(36,32,36,32);
        ScrollView scroll=new ScrollView(this);scroll.addView(content);setContentView(scroll);
        content.setOnApplyWindowInsetsListener((view,insets)->{
            if(android.os.Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars());view.setPadding(36+bars.left,32+bars.top,36+bars.right,32+bars.bottom);}
            else view.setPadding(36,32+insets.getSystemWindowInsetTop(),36,32+insets.getSystemWindowInsetBottom());
            return insets;
        });
        ImageView icon=new ImageView(this);icon.setImageResource(R.drawable.app_icon);content.addView(icon,new LinearLayout.LayoutParams(180,180));
        TextView title=new TextView(this);title.setText("Settings");title.setTextSize(30);content.addView(title);
        button(content,"Back",this::finish);
        other=new Button(this);other.setOnClickListener(view->startActivity(new Intent(this,WelcomeActivity.class).putExtra("details",true).putExtra("wifi",!getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false))));content.addView(other);
        button(content,"Connection setup guide",()->startActivity(new Intent(this,WelcomeActivity.class)));
        TextView intro=new TextView(this);intro.setText("USB / ADB is always available. Authorize USB debugging on your phone, then connect from the desktop. No app pairing code is needed.");
        content.addView(intro);
        debugging=new Button(this);debugging.setOnClickListener(view->SetupLinks.debugging(this));content.addView(debugging);
        TextView help=new TextView(this);help.setText("USB setup: enable Developer options and USB debugging, then approve your desktop when Android asks. Wi-Fi does not need debugging.");content.addView(help);
        if(android.os.Build.VERSION.SDK_INT>=26)button(content,"Notification settings",()->SetupLinks.open(this,new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName())));

        Switch startup=new Switch(this);startup.setText("Connect on start");
        startup.setChecked(getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("connect_on_start",false));
        startup.setOnCheckedChangeListener((button,enabled)->getSharedPreferences("pairing",MODE_PRIVATE).edit().putBoolean("connect_on_start",enabled).apply());
        content.addView(startup);
        TextView startupHelp=new TextView(this);startupHelp.setText("Prepare sharing when you launch this app. Android input-control permission must be enabled first.");content.addView(startupHelp);
        EditText trial=new EditText(this);trial.setHint("Click here and type to test your keyboard");trial.setSingleLine(true);content.addView(trial);
        button(content,"Enable input control",()->SetupLinks.open(this,new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        wifi=new Switch(this);wifi.setText("Set up direct Wi-Fi (optional)");
        wifi.setChecked(getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false));content.addView(wifi);
        LinearLayout wifiOptions=new LinearLayout(this);wifiOptions.setOrientation(LinearLayout.VERTICAL);content.addView(wifiOptions);
        port=new EditText(this);port.setHint("Wi-Fi port");port.setText(String.valueOf(getSharedPreferences("pairing",MODE_PRIVATE).getInt("wifi_port",19674)));
        port.setInputType(android.text.InputType.TYPE_CLASS_NUMBER);wifiOptions.addView(port);
        TextView code=new TextView(this);code.setText("Wi-Fi pairing code: "+ServerService.pairingCode(this));code.setTextIsSelectable(true);wifiOptions.addView(code);
        TextView address=new TextView(this);address.setTextIsSelectable(true);wifiOptions.addView(address);
        Runnable identity=()->{
            try {StringBuilder ips=new StringBuilder();java.util.Enumeration<java.net.NetworkInterface> interfaces=java.net.NetworkInterface.getNetworkInterfaces();
                while(interfaces.hasMoreElements()){java.util.Enumeration<java.net.InetAddress> entries=interfaces.nextElement().getInetAddresses();while(entries.hasMoreElements()){java.net.InetAddress ip=entries.nextElement();if(ip instanceof java.net.Inet4Address && !ip.isLoopbackAddress())ips.append(ip.getHostAddress()).append("\n");}}
                address.setText("Phone addresses:\n"+ips+"TLS certificate SHA-256 (copy into desktop):\n"+TlsIdentity.fingerprint());
            }catch(Exception failure){address.setText("Wi-Fi identity unavailable. Try opening Settings again.");}
        };
        button(wifiOptions,"Wi-Fi network settings",()->SetupLinks.open(this,new Intent(Settings.ACTION_WIFI_SETTINGS)));
        button(wifiOptions,"Keyboard settings",()->SetupLinks.open(this,new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        button(wifiOptions,"Select desk dockt keyboard",()->getSystemService(InputMethodManager.class).showInputMethodPicker());
        button(wifiOptions,"Save Wi-Fi port",()->{
            try{int number=Integer.parseInt(port.getText().toString());if(number<1024||number>65535)throw new NumberFormatException();
                getSharedPreferences("pairing",MODE_PRIVATE).edit().putInt("wifi_port",number).apply();
                Toast.makeText(this,"Saved. Connection changes apply the next time sharing starts.",Toast.LENGTH_LONG).show();
            }catch(NumberFormatException invalid){Toast.makeText(this,"Choose a port from 1024 to 65535",Toast.LENGTH_LONG).show();}
        });
        wifiOptions.setVisibility(wifi.isChecked()?android.view.View.VISIBLE:android.view.View.GONE);
        if(wifi.isChecked())identity.run();
        wifi.setOnCheckedChangeListener((button,enabled)->{
            if(enabled && android.os.Build.VERSION.SDK_INT>=37 && checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK")!=android.content.pm.PackageManager.PERMISSION_GRANTED){
                wifi.setChecked(false);requestPermissions(new String[]{"android.permission.ACCESS_LOCAL_NETWORK"},2);return;
            }
            getSharedPreferences("pairing",MODE_PRIVATE).edit().putBoolean("wifi_enabled",enabled).apply();
            wifiOptions.setVisibility(enabled?android.view.View.VISIBLE:android.view.View.GONE);
            if(enabled)identity.run();
            updateOther();
        });
        Switch share=new Switch(this);share.setText("Share clipboard");share.setChecked(getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("share_clipboard",false));
        share.setOnCheckedChangeListener((button,enabled)->getSharedPreferences("pairing",MODE_PRIVATE).edit().putBoolean("share_clipboard",enabled).apply());content.addView(share);
        TextView clipboardHelp=new TextView(this);clipboardHelp.setText("Share text with your desktop automatically. Enable Share clipboard on the desktop too. Keep the desk dockt keyboard selected to share phone text while other apps are open.");content.addView(clipboardHelp);
        TextView notice=new TextView(this);notice.setText("New implementation by the desk dockt project, inspired by DeskDock by Florian Draschbacher. MIT licensed. No activation server, subscription or analytics. Only paired desktop clients can control input. ADB uses a local listener; optional Wi-Fi uses certificate verification and a pairing code.");content.addView(notice);
    }
    private void updateOther(){other.setText(getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("wifi_enabled",false)?"Other connection: LOCAL (cable / ADB)":"Other connection: WiFi (net)");}
    @Override public void onResume(){super.onResume();updateOther();debugging.setText(SetupLinks.debuggingEnabled(this)?"USB debugging enabled · Open settings":"Set up USB debugging");}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] results){
        super.onRequestPermissionsResult(request,permissions,results);
        if(request==2 && results.length>0 && results[0]==android.content.pm.PackageManager.PERMISSION_GRANTED)wifi.setChecked(true);
    }
    private void button(LinearLayout layout,String text,Runnable action) {
        Button button=new Button(this);button.setText(text);button.setOnClickListener(view->action.run());layout.addView(button);
    }
}
