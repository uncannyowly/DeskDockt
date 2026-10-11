"""Windows/macOS native event filters through pynput; capture-only suppression."""
import sys

VK={44:120,8:67,9:61,13:66,27:111,32:62,33:92,34:93,35:123,36:122,37:21,38:19,39:22,40:20,
    45:124,46:112,160:59,161:60,162:113,163:114,164:57,165:58,91:117,92:118,20:115,
    186:74,187:70,188:55,189:69,190:56,191:76,192:68,219:71,220:73,221:72,222:75}
VK.update({65+i:29+i for i in range(26)});VK.update({48+i:7+i for i in range(10)})
VK.update({112+i:131+i for i in range(12)})
MAC={105:120,0:29,1:47,2:32,3:34,4:36,5:35,6:54,7:52,8:31,9:50,11:30,12:45,13:51,
     14:33,15:46,16:53,17:48,18:8,19:9,20:10,21:11,22:13,23:12,24:70,25:16,
     26:14,27:69,28:15,29:7,30:72,31:43,32:49,33:71,34:37,35:44,36:66,
     37:40,38:38,39:75,40:39,41:74,42:73,43:55,44:76,45:42,46:41,47:56,
     48:61,49:62,50:68,51:67,53:111,54:118,55:117,56:59,57:115,58:57,59:113,
     60:60,61:58,62:114,96:135,97:136,98:137,99:133,100:138,101:139,103:141,
     109:140,111:142,115:122,116:92,117:112,118:134,119:123,120:132,121:93,
     122:131,123:21,124:22,125:20,126:19}

class Backend:
    def __init__(self,emit):
        from pynput import mouse,keyboard
        self.mouse_module=mouse;self.emit=emit;self.captured=False;self.epoch=0
        self.controller=mouse.Controller();self.overlay=None;self.anchor=(0,0)
        self.listeners=[];self.modifiers=set()
        if sys.platform=='darwin':
            import Quartz
            from ApplicationServices import AXIsProcessTrusted
            self.quartz=Quartz
            if not AXIsProcessTrusted():
                raise RuntimeError('Allow desk dockt (or Python) in macOS Privacy & Security → Accessibility and Input Monitoring, then restart it.')
            options={'darwin_intercept':self.mac_mouse}
            keyoptions={'darwin_intercept':self.mac_keyboard}
        else:
            import ctypes
            self.ctypes=ctypes;self.user32=ctypes.windll.user32
            self.user32.SetProcessDPIAware()
            self.state=(ctypes.c_ubyte*256)()
            self.user32.GetKeyboardState(self.state)
            options={'win32_event_filter':self.win_mouse}
            keyoptions={'win32_event_filter':self.win_keyboard}
        self.mouse=mouse.Listener(**options);self.keyboard=keyboard.Listener(**keyoptions)

    def monitors(self):
        from screeninfo import get_monitors
        return [(m.width,m.height,m.x,m.y) for m in get_monitors()]

    def start(self):
        for listener in (self.mouse,self.keyboard):
            listener.start();listener.wait();self.listeners.append(listener)

    def poll(self):
        if any(not listener.is_alive() for listener in self.listeners):
            raise RuntimeError('Desktop input listener stopped; reconnect after checking system permissions')

    def capture(self):
        self.anchor=tuple(self.controller.position)
        if sys.platform=='darwin':
            q=self.quartz
            self.hidden_display=q.CGMainDisplayID()
            q.CGDisplayHideCursor(self.hidden_display)
        else:
            for i in range(256):self.state[i]=128 if self.user32.GetAsyncKeyState(i)&0x8000 else 0
            from PySide6.QtWidgets import QWidget
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QCursor
            self.overlay=QWidget(None,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowDoesNotAcceptFocus)
            self.overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.overlay.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            # Qt uses logical coordinates; map the native cursor to its Qt screen.
            from PySide6.QtGui import QGuiApplication
            for screen in QGuiApplication.screens():
                geo=screen.geometry();scale=screen.devicePixelRatio()
                x,y=self.anchor
                if geo.x()*scale<=x<(geo.x()+geo.width())*scale and geo.y()*scale<=y<(geo.y()+geo.height())*scale:
                    self.overlay.setGeometry(int(x/scale)-12,int(y/scale)-12,25,25);break
            self.overlay.show()
        self.epoch+=1;self.captured=True

    def release(self,point):
        self.captured=False;self.epoch+=1;self.modifiers.clear()
        if sys.platform=='darwin':self.quartz.CGDisplayShowCursor(self.hidden_display)
        elif self.overlay:
            self.overlay.close();self.overlay.deleteLater();self.overlay=None
            for i in range(256):self.state[i]&=1
        self.controller.position=(int(point[0]),int(point[1]))

    def close(self):
        if self.captured:self.release(self.anchor)
        for listener in self.listeners:listener.stop()
        for listener in self.listeners:listener.join(timeout=2)

    def win_mouse(self,message,data):
        if data.flags&1:return True # Do not suppress our own return warp.
        if not self.captured:
            if message==0x200:self.emit('position',(data.pt.x,data.pt.y))
            return True
        if message==0x200:self.emit('motion',(data.pt.x-self.anchor[0],data.pt.y-self.anchor[1]))
        elif message in (0x201,0x202,0x204,0x205,0x207,0x208):
            button={0x201:1,0x202:1,0x204:2,0x205:2,0x207:3,0x208:3}[message]
            self.emit('button',(button,message in (0x201,0x204,0x207)))
        elif message in (0x20a,0x20e):
            value=self.ctypes.c_short(data.mouseData>>16).value/120
            self.emit('scroll',(value,0) if message==0x20e else (0,value))
        self.mouse.suppress_event()

    def win_keyboard(self,message,data):
        if not self.captured:return True
        down=message in (0x100,0x104);vk=int(data.vkCode)
        self.state[vk]=(self.state[vk]&1)|(128 if down else 0)
        # Maintain generic modifier slots while desktop delivery is suppressed.
        for general,left,right in ((16,160,161),(17,162,163),(18,164,165)):
            self.state[general]=(self.state[left]|self.state[right])&128
        buffer=self.ctypes.create_unicode_buffer(8)
        count=self.user32.ToUnicode(vk,data.scanCode,self.state,buffer,8,4)
        text=buffer.value if count>0 else ''
        self.emit('key',(VK.get(vk,0),ord(text[0]) if text else 0,down))
        self.keyboard.suppress_event()

    def mac_mouse(self,kind,event):
        q=self.quartz
        if kind in (q.kCGEventTapDisabledByTimeout,q.kCGEventTapDisabledByUserInput):
            self.emit('failure',('macOS disabled input capture; reconnect to restore input monitoring',));return event
        point=q.CGEventGetLocation(event)
        if not self.captured:
            if kind==q.kCGEventMouseMoved:self.emit('position',(point.x,point.y))
            return event
        if kind in (q.kCGEventMouseMoved,q.kCGEventLeftMouseDragged,q.kCGEventRightMouseDragged,q.kCGEventOtherMouseDragged):
            self.emit('motion',(q.CGEventGetIntegerValueField(event,q.kCGMouseEventDeltaX),q.CGEventGetIntegerValueField(event,q.kCGMouseEventDeltaY)))
        elif kind in (q.kCGEventLeftMouseDown,q.kCGEventLeftMouseUp,q.kCGEventRightMouseDown,q.kCGEventRightMouseUp,q.kCGEventOtherMouseDown,q.kCGEventOtherMouseUp):
            button=1 if kind in (q.kCGEventLeftMouseDown,q.kCGEventLeftMouseUp) else 2 if kind in (q.kCGEventRightMouseDown,q.kCGEventRightMouseUp) else 3
            self.emit('button',(button,kind in (q.kCGEventLeftMouseDown,q.kCGEventRightMouseDown,q.kCGEventOtherMouseDown)))
        elif kind==q.kCGEventScrollWheel:
            self.emit('scroll',(q.CGEventGetIntegerValueField(event,q.kCGScrollWheelEventDeltaAxis2),q.CGEventGetIntegerValueField(event,q.kCGScrollWheelEventDeltaAxis1)))
        return None

    def mac_keyboard(self,kind,event):
        if not self.captured:return event
        q=self.quartz;native=q.CGEventGetIntegerValueField(event,q.kCGKeyboardEventKeycode)
        code=MAC.get(native,0)
        if kind==q.kCGEventFlagsChanged:
            down=code not in self.modifiers
            if down:self.modifiers.add(code)
            else:self.modifiers.discard(code)
        elif kind in (q.kCGEventKeyDown,q.kCGEventKeyUp):down=kind==q.kCGEventKeyDown
        else:return event
        _,text=q.CGEventKeyboardGetUnicodeString(event,8,None,None)
        self.emit('key',(code,ord(text[0]) if text else 0,down))
        return None
