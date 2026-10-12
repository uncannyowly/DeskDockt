"""Shared layout editor state; no toolkit or desktop access."""
from placement import phone_rect,dragged

class Model:
    def __init__(self,monitors,settings,changed):
        self.monitors=monitors;self.changed=changed;self.edge=settings['edge']
        layout=settings.get('phone_layout');self.enabled=bool(layout)
        self.index=next((i for i,z in enumerate(monitors) if layout and list(z)==layout['monitor']),0)
        self.offset=layout['offset'] if layout else .175
        zone=monitors[self.index]
        self.height=(layout['size'] if self.edge in ('left','right') else layout['size']*zone[0]/zone[1]/.46) if layout else .65
        self.size=0;self.drag=None

    def scene(self,width,height):
        zone=self.monitors[self.index];aspect=zone[0]/zone[1]
        mh=min(height*.42,width*.48/aspect);mw=mh*aspect
        x=(width-mw)/2;y=(height-mh)/2
        self.size=self.height if self.edge in ('left','right') else self.height*mh*.46/mw
        px,py,pw,ph=phone_rect(self.edge,self.offset,self.size,mw,mh)
        return (x,y,mw,mh),(x+px,y+py,pw,ph)

    def begin(self,x,y,width,height):
        monitor,phone=self.scene(width,height);px,py,pw,ph=phone
        if px<=x<=px+pw and py<=y<=py+ph:self.drag=(x,y,px+pw/2,py+ph/2);return True
        return False

    def move(self,x,y,width,height):
        if not self.drag:return
        (mx,my,mw,mh),_=self.scene(width,height)
        sx,sy,cx,cy=self.drag
        self.edge,self.offset,self.size=dragged(cx+x-sx-mx,cy+y-sy-my,mw,mh,self.height*mh)
        self.enabled=True;self.commit()

    def commit(self):
        zone=self.monitors[self.index]
        size=self.height if self.edge in ('left','right') else self.height*zone[1]*.46/zone[0]
        # Keep a visible overlap when size changes or the monitor is switched.
        self.offset=max(-size+.001,min(.999,self.offset))
        self.changed(self.edge,dict(monitor=list(zone),offset=self.offset,size=size) if self.enabled else None)
