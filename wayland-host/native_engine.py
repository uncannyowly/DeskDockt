"""Platform independent edge switching; hooks never perform socket I/O."""
import time

class Engine:
    def __init__(self,phone,backend,edge='right',speed=1,notify=None,repeat=True,layout=None):
        self.phone,self.backend,self.edge,self.speed=phone,backend,edge,speed
        self.notify=notify or (lambda **event:None)
        from clipboard_state import ClipboardState
        self.clipboard=ClipboardState()
        self.repeat=repeat;self.active=False;self.keys={};self.buttons=set()
        self.x=self.y=0;self.repeat_key=None;self.next_repeat=0
        zones=backend.monitors()
        if not zones:raise RuntimeError('No desktop monitors found')
        from placement import geometry
        self.zone,self.line,self.trigger_start,self.trigger_span=geometry(zones,edge,layout)

    def position(self,x,y):
        if self.active:return
        w,h,zx,zy=self.zone
        if not (zx<=x<zx+w and zy<=y<zy+h):return
        at_edge={'right':x>=zx+w-1 and zy<=y<zy+h,'left':x<=zx and zy<=y<zy+h,
                 'bottom':y>=zy+h-1 and zx<=x<zx+w,'top':y<=zy and zx<=x<zx+w}[self.edge]
        along=y if self.edge in ('right','left') else x
        lo=self.line[1] if self.edge in ('right','left') else self.line[0]
        hi=self.line[3] if self.edge in ('right','left') else self.line[2]
        if not at_edge or not lo<=along<=hi:return
        self.active=True
        try:
            self.backend.capture()
            self.x=2 if self.edge=='right' else self.phone.width-3 if self.edge=='left' else max(0,min(self.phone.width-1,(x-self.trigger_start)/self.trigger_span*self.phone.width))
            self.y=2 if self.edge=='bottom' else self.phone.height-3 if self.edge=='top' else max(0,min(self.phone.height-1,(y-self.trigger_start)/self.trigger_span*self.phone.height))
            self.clipboard.sync(self.phone)
            self.phone.enter(True);self.phone.move(self.x,self.y)
            self.notify(type='active')
        except Exception:
            self.release();raise

    def motion(self,dx,dy):
        if not self.active:return
        x,y=self.x+dx*self.speed,self.y+dy*self.speed
        if {'right':x<0,'left':x>=self.phone.width,'bottom':y<0,'top':y>=self.phone.height}[self.edge]:
            self.release();return
        self.x=max(0,min(self.phone.width-1,x));self.y=max(0,min(self.phone.height-1,y))
        self.phone.move(self.x,self.y)

    def button(self,button,down):
        if not self.active:return
        if button==2:self.phone.key(4,0,down)
        else:self.phone.button(button,down,self.x,self.y)
        if down:self.buttons.add(button)
        else:self.buttons.discard(button)

    def scroll(self,dx,dy):
        if self.active:self.phone.scroll(self.x,self.y,int(-dx),int(-dy))

    def key(self,code,char,down):
        if not self.active:return
        if char<32 or 127<=char<=159 or 0xfff0<=char<=0xffff:char=0
        if down and code in self.keys:return # Native autorepeat is replaced below.
        if down:
            if code==111 and any(k in self.keys for k in (113,114)) and any(k in self.keys for k in (57,58)) and any(k in self.keys for k in (59,60)):
                self.release();return
            if char>65535:self.phone.text(chr(char));return
            self.keys[code]=char
        else:char=self.keys.pop(code,char)
        if code or char:self.phone.key(code,char,down)
        if down and code not in (57,58,59,60,113,114,115,117,118,120):
            self.repeat_key=code;self.next_repeat=time.monotonic()+.5
        elif not down and self.repeat_key==code:self.repeat_key=None

    def tick(self):
        code=self.repeat_key
        if self.repeat and self.active and code in self.keys and time.monotonic()>=self.next_repeat:
            char=self.keys[code];self.phone.key(code,char,False);self.phone.key(code,char,True)
            self.next_repeat=time.monotonic()+.04

    def release(self):
        if not self.active:return
        self.active=False
        w,h,zx,zy=self.zone
        point=(zx+w-3 if self.edge=='right' else zx+2 if self.edge=='left' else max(zx,min(zx+w-1,self.trigger_start+self.x/self.phone.width*self.trigger_span)),
               zy+h-3 if self.edge=='bottom' else zy+2 if self.edge=='top' else max(zy,min(zy+h-1,self.trigger_start+self.y/self.phone.height*self.trigger_span)))
        try:self.backend.release(point)
        finally:
            try:
                for code,char in self.keys.items():self.phone.key(code,char,False)
                for button in self.buttons:
                    if button==2:self.phone.key(4,0,False)
                    else:self.phone.button(button,False,self.x,self.y)
                self.phone.enter(False)
            finally:
                self.keys.clear();self.buttons.clear();self.repeat_key=None
                self.notify(type='ready',edge=self.edge,width=self.phone.width,height=self.phone.height)
