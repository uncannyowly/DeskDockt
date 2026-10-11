package io.github.deskdockt.android;

import android.inputmethodservice.InputMethodService;
import android.os.SystemClock;
import android.view.*;
import android.view.inputmethod.*;
import android.widget.Button;
import org.json.JSONObject;

/** Standard Android input connection; no hidden API or root input injector. */
public final class DockIme extends InputMethodService {
    public static volatile DockIme instance;
    private int meta;
    private android.content.ClipboardManager clipboard;
    private final android.content.ClipboardManager.OnPrimaryClipChangedListener clipboardChanged=this::shareClipboard;
    private void shareClipboard(){
        if(!getSharedPreferences("pairing",MODE_PRIVATE).getBoolean("share_clipboard",false))return;
        android.content.ClipData clip=clipboard.getPrimaryClip();
        if(clip!=null && clip.getItemCount()>0 && clip.getItemAt(0).getText()!=null)ServerService.clipboard(clip.getItemAt(0).getText().toString());
    }
    @Override public void onCreate(){super.onCreate();instance=this;clipboard=getSystemService(android.content.ClipboardManager.class);clipboard.addPrimaryClipChangedListener(clipboardChanged);}
    @Override public void onDestroy(){clipboard.removePrimaryClipChangedListener(clipboardChanged);instance=null;super.onDestroy();}
    @Override public View onCreateInputView(){Button button=new Button(this);button.setText("desk dockt keyboard · tap to switch keyboard");button.setOnClickListener(view->getSystemService(InputMethodManager.class).showInputMethodPicker());return button;}
    public void release(){meta=0;}
    public void handle(JSONObject message) {
        InputConnection connection=getCurrentInputConnection();if(connection==null)return;
        String kind=message.optString("type");
        if("text".equals(kind)){connection.commitText(message.optString("text"),1);return;}
        if(!"key".equals(kind))return;
        int code=message.optInt("code"),character=message.optInt("character");boolean down=message.optBoolean("down");
        int flag=(code==59||code==60)?KeyEvent.META_SHIFT_ON:(code==113||code==114)?KeyEvent.META_CTRL_ON:(code==57||code==58)?KeyEvent.META_ALT_ON:(code==117||code==118)?KeyEvent.META_META_ON:0;
        if(flag!=0){if(down)meta|=flag;else meta&=~flag;}
        if(down && (meta&(KeyEvent.META_CTRL_ON|KeyEvent.META_META_ON))!=0) {
            int action=code==KeyEvent.KEYCODE_A?android.R.id.selectAll:code==KeyEvent.KEYCODE_C?android.R.id.copy:code==KeyEvent.KEYCODE_X?android.R.id.cut:code==KeyEvent.KEYCODE_V?android.R.id.paste:0;
            if(action!=0){connection.performContextMenuAction(action);return;}
        }
        if(character>=32 && character<=0x10ffff && (meta&(KeyEvent.META_CTRL_ON|KeyEvent.META_ALT_ON|KeyEvent.META_META_ON))==0) {
            if(down)connection.commitText(new String(Character.toChars(character)),1);return;
        }
        if(down && code==KeyEvent.KEYCODE_ENTER){EditorInfo info=getCurrentInputEditorInfo();int action=info==null?0:info.imeOptions&EditorInfo.IME_MASK_ACTION;
            if(action!=EditorInfo.IME_ACTION_NONE && action!=EditorInfo.IME_ACTION_UNSPECIFIED){connection.performEditorAction(action);return;}}
        long now=SystemClock.uptimeMillis();connection.sendKeyEvent(new KeyEvent(now,now,down?KeyEvent.ACTION_DOWN:KeyEvent.ACTION_UP,code,0,meta));
    }
}
