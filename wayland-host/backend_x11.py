"""X11 grabs apply only during phone control, with a transparent grab cursor."""
from keymap import KEYS

class Backend:
    def __init__(self,emit):
        from Xlib import X,display
        self.X=X;self.display=display.Display();self.root=self.display.screen().root
        self.emit=emit;self.captured=False;self.center=None;self.epoch=0;self.last=None
        pixmap=self.root.create_pixmap(1,1,1)
        gc=pixmap.create_gc(foreground=0);pixmap.fill_rectangle(gc,0,0,1,1)
        self.cursor=pixmap.create_cursor(pixmap,(0,0,0),(0,0,0),0,0)
        gc.free();pixmap.free()

    def monitors(self):
        try:
            reply=self.root.xrandr_get_monitors(True)
            return [(m.width,m.height,m.x,m.y) for m in reply.monitors]
        except Exception:
            screen=self.display.screen();return [(screen.width_in_pixels,screen.height_in_pixels,0,0)]

    def capture(self):
        X=self.X
        result=self.root.grab_pointer(False,X.PointerMotionMask|X.ButtonPressMask|X.ButtonReleaseMask,
                                     X.GrabModeAsync,X.GrabModeAsync,0,self.cursor,X.CurrentTime)
        if result!=X.GrabSuccess:raise RuntimeError('Another application already owns the X11 pointer grab')
        result=self.root.grab_keyboard(False,X.GrabModeAsync,X.GrabModeAsync,X.CurrentTime)
        if result!=X.GrabSuccess:
            self.display.ungrab_pointer(X.CurrentTime);self.display.sync()
            raise RuntimeError('Another application already owns the X11 keyboard grab')
        screen=self.display.screen();self.center=(screen.width_in_pixels//2,screen.height_in_pixels//2)
        self.epoch+=1;self.captured=True;self.last=self.center;self.root.warp_pointer(*self.center);self.display.sync()

    def poll(self):
        X=self.X
        if not self.captured:
            point=self.root.query_pointer();self.emit('position',(point.root_x,point.root_y))
        # Drain in bounded batches so a busy mouse cannot starve stop commands.
        events=[self.display.next_event() for _ in range(min(self.display.pending_events(),256))]
        index=0;warp=False
        while index<len(events):
            event=events[index];index+=1
            if not self.captured:continue
            if event.type==X.MotionNotify:
                point=(event.root_x,event.root_y)
                if point==self.center:self.last=self.center
                else:
                    self.emit('motion',(point[0]-self.last[0],point[1]-self.last[1]))
                    self.last=point;warp=True
            elif event.type in (X.ButtonPress,X.ButtonRelease):
                down=event.type==X.ButtonPress
                if event.detail in (4,5,6,7):
                    if down:self.emit('scroll',({6:1,7:-1}.get(event.detail,0),{4:1,5:-1}.get(event.detail,0)))
                else:self.emit('button',({1:1,3:2,2:3}.get(event.detail,1),down))
            elif event.type in (X.KeyPress,X.KeyRelease):
                if event.type==X.KeyRelease and index<len(events):
                    following=events[index]
                    if following.type==X.KeyPress and following.detail==event.detail and following.time==event.time:
                        index+=1;continue # X11's synthetic repeat release/press pair.
                keysym=self.display.keycode_to_keysym(event.detail,1 if event.state&X.ShiftMask else 0)
                if event.state&X.LockMask and 97<=keysym<=122:keysym-=32
                char=keysym&0xffffff if keysym&0xff000000==0x01000000 else keysym if 32<=keysym<0xff00 else 0
                self.emit('key',(KEYS.get(event.detail-8,0),char,event.type==X.KeyPress))
        if warp:self.root.warp_pointer(*self.center);self.display.sync()

    def release(self,point):
        self.captured=False;self.epoch+=1
        self.display.ungrab_keyboard(self.X.CurrentTime);self.display.ungrab_pointer(self.X.CurrentTime)
        self.root.warp_pointer(int(point[0]),int(point[1]));self.display.sync()

    def close(self):
        try:
            if self.captured:self.release(self.center)
            self.cursor.free()
        finally:self.display.close()
