from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QPainter,QColor,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QCheckBox,QDoubleSpinBox,QApplication
from layout_model import Model
import sys
from platforms import backend_name

class Preview(QWidget):
    def __init__(self,editor):
        super().__init__();self.editor=editor;self.setMinimumHeight(270)
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.RenderHint.Antialiasing)
        monitor,phone=self.editor.model.scene(self.width(),self.height())
        p.setPen(QColor('#667085'));p.setBrush(QColor('#253047'));p.drawRoundedRect(QRectF(*monitor),8,8)
        p.setPen(QColor('white'));p.drawText(QRectF(*monitor),Qt.AlignmentFlag.AlignCenter,'Monitor')
        p.setBrush(QColor('#557ac6'));p.drawRoundedRect(QRectF(*phone),7,7)
        p.drawText(QRectF(*phone),Qt.AlignmentFlag.AlignCenter,'Phone')
        x,y,w,h=monitor;px,py,pw,ph=phone;m=self.editor.model
        if not m.enabled:px,py,pw,ph=x,y,w,h
        p.setPen(QPen(QColor('#38d9a9'),5))
        if m.edge in ('left','right'):
            ex=x if m.edge=='left' else x+w;p.drawLine(int(ex),int(max(y,py)),int(ex),int(min(y+h,py+ph)))
        else:
            ey=y if m.edge=='top' else y+h;p.drawLine(int(max(x,px)),int(ey),int(min(x+w,px+pw)),int(ey))
    def mousePressEvent(self,event):
        self.editor.model.begin(event.position().x(),event.position().y(),self.width(),self.height())
    def mouseMoveEvent(self,event):
        self.editor.model.move(event.position().x(),event.position().y(),self.width(),self.height());self.editor.refresh()
    def mouseReleaseEvent(self,event):self.editor.model.drag=None

class LayoutEditor(QWidget):
    def __init__(self,settings,changed):
        super().__init__();monitors=[];names=[]
        for screen in QApplication.screens():
            g=screen.geometry();monitors.append((g.width(),g.height(),g.x(),g.y()));names.append(screen.name())
        name=backend_name()
        if name in ('windows','macos'):
            from screeninfo import get_monitors
            native=get_monitors();monitors=[(m.width,m.height,m.x,m.y) for m in native];names=[getattr(m,'name',None) or f'Monitor {i+1}' for i,m in enumerate(native)]
        elif name=='x11':
            from backend_x11 import Backend
            backend=Backend(lambda *_:None)
            try:monitors=backend.monitors();names=[f'Monitor {i+1}' for i in range(len(monitors))]
            finally:backend.close()
        self.model=Model(monitors,settings,changed);layout=QVBoxLayout(self)
        layout.addWidget(QLabel('Drag the phone beside a monitor. Green shows the crossing area.'))
        self.monitor=QComboBox();self.monitor.addItems(names);self.monitor.setCurrentIndex(self.model.index);layout.addWidget(self.monitor)
        self.preview=Preview(self);layout.addWidget(self.preview)
        row=QHBoxLayout();self.enabled=QCheckBox('Use positioned phone');self.enabled.setChecked(self.model.enabled);row.addWidget(self.enabled)
        row.addWidget(QLabel('Phone height / monitor height'))
        self.size=QDoubleSpinBox();self.size.setRange(.15,1.5);self.size.setSingleStep(.05);self.size.setValue(self.model.height);row.addWidget(self.size);layout.addLayout(row)
        self.monitor.currentIndexChanged.connect(self.select);self.enabled.toggled.connect(self.toggle);self.size.valueChanged.connect(self.resize_phone)
    def select(self,index):self.model.index=index;self.model.commit();self.refresh()
    def toggle(self,value):self.model.enabled=value;self.model.commit();self.refresh()
    def resize_phone(self,value):self.model.height=value;self.model.commit();self.refresh()
    def refresh(self):
        self.enabled.blockSignals(True);self.enabled.setChecked(self.model.enabled);self.enabled.blockSignals(False);self.preview.update()
    def set_edge(self,edge):self.model.edge=edge;self.model.commit();self.refresh()
