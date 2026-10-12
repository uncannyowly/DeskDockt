from gi.repository import Gtk,Gdk
from layout_model import Model

class LayoutEditor(Gtk.Box):
    def __init__(self,settings,changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL,spacing=8)
        items=Gdk.Display.get_default().get_monitors();monitors=[];names=[]
        for i in range(items.get_n_items()):
            m=items.get_item(i);g=m.get_geometry();monitors.append((g.width,g.height,g.x,g.y));names.append(m.get_connector() or f'Monitor {i+1}')
        self.model=Model(monitors,settings,changed)
        self.append(Gtk.Label(label='Drag the phone beside a monitor. Green shows the crossing area.',wrap=True))
        self.monitor=Gtk.DropDown.new_from_strings(names);self.monitor.set_selected(self.model.index);self.append(self.monitor)
        self.preview=Gtk.DrawingArea(content_height=270);self.preview.set_draw_func(self.draw);self.append(self.preview)
        drag=Gtk.GestureDrag();drag.connect('drag-begin',self.begin);drag.connect('drag-update',self.move);drag.connect('drag-end',self.end);self.preview.add_controller(drag)
        row=Gtk.Box(spacing=8);self.enabled=Gtk.CheckButton(label='Use positioned phone');self.enabled.set_active(self.model.enabled);row.append(self.enabled)
        row.append(Gtk.Label(label='Phone height / monitor height',wrap=True));self.size=Gtk.SpinButton.new_with_range(.15,1.5,.05);self.size.set_digits(2);self.size.set_value(self.model.height);row.append(self.size);self.append(row)
        self.monitor.connect('notify::selected',self.select);self.enabled.connect('toggled',self.toggle);self.size.connect('value-changed',self.resize_phone)
    def draw(self,widget,cr,width,height):
        monitor,phone=self.model.scene(width,height)
        for rect,color,label in ((monitor,(.14,.19,.28),'Monitor'),(phone,(.33,.48,.78),'Phone')):
            cr.set_source_rgb(*color);cr.rectangle(*rect);cr.fill();cr.set_source_rgb(1,1,1);cr.move_to(rect[0]+8,rect[1]+22);cr.show_text(label)
        x,y,w,h=monitor;px,py,pw,ph=phone
        if not self.model.enabled:px,py,pw,ph=x,y,w,h
        cr.set_source_rgb(.22,.85,.66);cr.set_line_width(5)
        if self.model.edge in ('left','right'):
            ex=x if self.model.edge=='left' else x+w;cr.move_to(ex,max(y,py));cr.line_to(ex,min(y+h,py+ph))
        else:
            ey=y if self.model.edge=='top' else y+h;cr.move_to(max(x,px),ey);cr.line_to(min(x+w,px+pw),ey)
        cr.stroke()
    def begin(self,gesture,x,y):self.model.begin(x,y,self.preview.get_width(),self.preview.get_height())
    def move(self,gesture,dx,dy):
        if self.model.drag:
            x,y,*_=self.model.drag;self.model.move(x+dx,y+dy,self.preview.get_width(),self.preview.get_height());self.refresh()
    def end(self,*_):self.model.drag=None
    def select(self,*_):self.model.index=self.monitor.get_selected();self.model.commit();self.refresh()
    def toggle(self,*_):self.model.enabled=self.enabled.get_active();self.model.commit();self.refresh()
    def resize_phone(self,*_):self.model.height=self.size.get_value();self.model.commit();self.refresh()
    def refresh(self):
        if self.enabled.get_active()!=self.model.enabled:self.enabled.set_active(self.model.enabled)
        self.preview.queue_draw()
    def set_edge(self,edge):self.model.edge=edge;self.model.commit();self.refresh()
