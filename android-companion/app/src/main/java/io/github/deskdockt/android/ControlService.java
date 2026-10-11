package io.github.deskdockt.android;

import android.accessibilityservice.*;
import android.content.*;
import android.graphics.*;
import android.os.Handler;
import android.view.*;
import android.view.accessibility.AccessibilityEvent;
import org.json.JSONObject;

/** Public accessibility gestures and a non-interactive cursor overlay. */
public final class ControlService extends AccessibilityService {
    public static volatile ControlService instance;
    private WindowManager windows;private Cursor cursor;private WindowManager.LayoutParams params;
    private float x,y,lastX,lastY;private boolean entered,dragging,gestureBusy,finishDrag;
    private GestureDescription.StrokeDescription stroke;private final Handler handler=new Handler();
    @Override public void onServiceConnected(){instance=this;windows=getSystemService(WindowManager.class);ServerService.dimensions();}
    @Override public void onAccessibilityEvent(AccessibilityEvent event){ServerService.dimensions();}
    @Override public void onInterrupt(){leave();}
    @Override public void onDestroy(){leave();instance=null;super.onDestroy();}
    public void handle(JSONObject message) {
        String kind=message.optString("type");
        if("enter".equals(kind)){if(message.optBoolean("entered"))enter();else leave();return;}
        if("clipboard".equals(kind)){getSystemService(ClipboardManager.class).setPrimaryClip(ClipData.newPlainText("desk dockt",message.optString("text")));return;}
        if("text".equals(kind)){if(DockIme.instance!=null)DockIme.instance.handle(message);return;}
        if("key".equals(kind)) {
            int code=message.optInt("code");
            if(code==120){if(message.optBoolean("down") && android.os.Build.VERSION.SDK_INT>=28)performGlobalAction(GLOBAL_ACTION_TAKE_SCREENSHOT);return;}
            if(message.optBoolean("down") && (code==4||code==111)){performGlobalAction(GLOBAL_ACTION_BACK);return;}
            if(message.optBoolean("down") && code==3){performGlobalAction(GLOBAL_ACTION_HOME);return;}
            if(DockIme.instance!=null)DockIme.instance.handle(message);return;
        }
        if(!entered)return;
        if("move".equals(kind)){x=(float)message.optDouble("x");y=(float)message.optDouble("y");position();if(dragging)drag();}
        else if("button".equals(kind) && message.optInt("button")==1){
            x=(float)message.optDouble("x");y=(float)message.optDouble("y");position();
            if(message.optBoolean("down")){dragging=true;finishDrag=false;drag();}
            else{dragging=false;finishDrag=true;drag();}
        } else if("scroll".equals(kind)) {
            float dx=(float)message.optDouble("dx")*80,dy=(float)message.optDouble("dy")*80;
            Path path=new Path();path.moveTo(x,y);path.lineTo(Math.max(1,x-dx),Math.max(1,y-dy));
            dispatchGesture(new GestureDescription.Builder().addStroke(new GestureDescription.StrokeDescription(path,0,180)).build(),null,null);
        }
    }
    private void enter(){if(entered)return;entered=true;cursor=new Cursor(this);
        params=new WindowManager.LayoutParams(48,48,WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON|WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE|WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE|WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,PixelFormat.TRANSLUCENT);
        params.gravity=Gravity.TOP|Gravity.LEFT;windows.addView(cursor,params);position();}
    private void position(){if(cursor!=null){params.x=(int)x;params.y=(int)y;windows.updateViewLayout(cursor,params);}}
    private void drag() {
        if(gestureBusy || (!dragging&&!finishDrag))return;
        Path path=new Path();path.moveTo(stroke==null?x:lastX,stroke==null?y:lastY);path.lineTo(x,y);
        boolean continuing=dragging;GestureDescription.StrokeDescription next=stroke==null?
            new GestureDescription.StrokeDescription(path,0,16,continuing):stroke.continueStroke(path,0,16,continuing);
        lastX=x;lastY=y;gestureBusy=true;stroke=continuing?next:null;finishDrag=false;
        boolean accepted=dispatchGesture(new GestureDescription.Builder().addStroke(next).build(),new GestureResultCallback(){
            @Override public void onCompleted(GestureDescription description){gestureBusy=false;if(finishDrag || entered && dragging&&(x!=lastX||y!=lastY))drag();}
            @Override public void onCancelled(GestureDescription description){gestureBusy=false;stroke=null;dragging=false;finishDrag=false;}
        },handler);
        if(!accepted){gestureBusy=false;stroke=null;dragging=false;finishDrag=false;}
    }
    public void leave(){dragging=false;if(stroke!=null){finishDrag=true;drag();}entered=false;
        if(cursor!=null){try{windows.removeView(cursor);}catch(IllegalArgumentException ignored){}cursor=null;}
        if(DockIme.instance!=null)DockIme.instance.release();}
    private static final class Cursor extends View {
        private final Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        Cursor(Context context){super(context);}
        @Override public void onDraw(Canvas canvas){Path arrow=new Path();arrow.moveTo(2,2);arrow.lineTo(2,36);arrow.lineTo(12,27);arrow.lineTo(21,43);arrow.lineTo(27,40);arrow.lineTo(18,24);arrow.lineTo(33,24);arrow.close();paint.setColor(Color.rgb(30,210,245));paint.setStyle(Paint.Style.FILL);canvas.drawPath(arrow,paint);paint.setColor(Color.BLACK);paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(2);canvas.drawPath(arrow,paint);}
    }
}
