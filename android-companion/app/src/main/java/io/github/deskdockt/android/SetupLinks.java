package io.github.deskdockt.android;

import android.app.Activity;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.provider.Settings;
import android.widget.Toast;

/** Shortcuts only: Android keeps control of system settings and consent. */
final class SetupLinks {
    static boolean debuggingEnabled(Activity activity){
        return Settings.Global.getInt(activity.getContentResolver(),Settings.Global.ADB_ENABLED,0)!=0;
    }
    static void open(Activity activity,Intent intent){
        try{activity.startActivity(intent);}
        catch(ActivityNotFoundException unavailable){
            try{activity.startActivity(new Intent(Settings.ACTION_SETTINGS));}
            catch(ActivityNotFoundException missing){Toast.makeText(activity,"Open Android Settings to complete setup",Toast.LENGTH_LONG).show();}
        }
    }
    static void debugging(Activity activity){
        boolean developer=Settings.Global.getInt(activity.getContentResolver(),Settings.Global.DEVELOPMENT_SETTINGS_ENABLED,0)!=0;
        if(developer)open(activity,new Intent(Settings.ACTION_APPLICATION_DEVELOPMENT_SETTINGS));
        else{
            Toast.makeText(activity,"Tap Build number seven times to enable Developer options, then enable USB debugging there.",Toast.LENGTH_LONG).show();
            open(activity,new Intent(Settings.ACTION_DEVICE_INFO_SETTINGS));
        }
    }
    private SetupLinks(){}
}
