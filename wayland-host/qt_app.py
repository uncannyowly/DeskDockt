"""Native Qt desktop/tray UI for Windows, macOS and X11; optional on Wayland."""
import argparse
from pathlib import Path
import subprocess
import sys
import threading
import json
import hashlib
import getpass

from PySide6.QtCore import QObject,QTimer,Signal,Qt,QLockFile,QStandardPaths
from PySide6.QtNetwork import QLocalServer,QLocalSocket
from PySide6.QtGui import QAction,QIcon
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QComboBox,QDoubleSpinBox,QCheckBox,QPushButton,QSystemTrayIcon,QMenu,
    QScrollArea,QPlainTextEdit,QInputDialog,QFileDialog,QMessageBox,QLineEdit)
from branding import NAME,ICON_PATH
from services import Worker,DeviceWatcher,load_settings,save_settings,send_file
from platforms import backend_name,subprocess_options

class Bridge(QObject):
    invoke=Signal(object,object)

class Window(QMainWindow):
    def __init__(self,serial=None):
        super().__init__();self.setWindowTitle(NAME);self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.resize(540,660);self.settings=load_settings();self.devices=[];self.requested=serial
        self.phone_clipboard='';self.quitting=False;self.busy=False
        self.bridge=Bridge();self.bridge.invoke.connect(lambda fn,args:fn(*args))
        self.dispatch=lambda fn,*args:self.bridge.invoke.emit(fn,args)
        self.worker=Worker(self.dispatch,self.worker_event);self.watcher=DeviceWatcher(self.dispatch,self.devices_changed)
        root=QWidget();layout=QVBoxLayout(root);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(root);self.setCentralWidget(scroll)
        icon=QLabel();icon.setPixmap(QIcon(str(ICON_PATH)).pixmap(72,72));icon.setAlignment(Qt.AlignmentFlag.AlignCenter);layout.addWidget(icon)
        title=QLabel('One mouse. Two screens.');title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet('font-size:23px;font-weight:600');layout.addWidget(title)
        self.status=QLabel('Select your phone, then start sharing.');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.device=QComboBox();layout.addWidget(QLabel('Phone'));layout.addWidget(self.device)
        self.edge=QComboBox();self.edge.addItems(['right','left','top','bottom']);self.edge.setCurrentText(self.settings['edge'])
        layout.addWidget(QLabel('Phone position'));layout.addWidget(self.edge)
        from layout_qt import LayoutEditor
        self.placement=LayoutEditor(self.settings,self.layout_changed);layout.addWidget(self.placement)
        self.edge.currentTextChanged.connect(lambda edge:self.placement.set_edge(edge) if self.placement.model.edge!=edge else None)
        self.speed=QDoubleSpinBox();self.speed.setRange(.1,4);self.speed.setSingleStep(.1);self.speed.setValue(self.settings['speed'])
        layout.addWidget(QLabel('Pointer speed'));layout.addWidget(self.speed)
        self.clip_sync=QCheckBox('Share clipboard');layout.addWidget(self.clip_sync)
        self.clip_sync.setChecked(self.settings['share_clipboard'])
        QApplication.clipboard().dataChanged.connect(self.sync_clipboard)
        self.clip_sync.toggled.connect(self.clipboard_toggled)
        self.repeat=QCheckBox('Repeat held keys');self.repeat.setChecked(self.settings['repeat']);layout.addWidget(self.repeat)
        self.pairing=QLineEdit(self.settings.get('pairing_code',''));self.pairing.setEchoMode(QLineEdit.EchoMode.Password)
        self.pairing.setPlaceholderText('Code in Android Settings → Wi-Fi')
        layout.addWidget(QLabel('Wi-Fi pairing code (not needed for ADB)'));layout.addWidget(self.pairing)
        self.wifi=QCheckBox('Use direct Wi-Fi instead of ADB');self.wifi.setChecked(self.settings['serial'].startswith('wifi://'));layout.addWidget(self.wifi)
        self.address=QLineEdit(self.settings.get('wifi_address',''));self.address.setPlaceholderText('192.168.1.20:19674');layout.addWidget(self.address)
        self.fingerprint=QLineEdit(self.settings.get('tls_fingerprint',''));self.fingerprint.setPlaceholderText('TLS SHA-256 fingerprint shown on phone');layout.addWidget(self.fingerprint)
        self.wifi.toggled.connect(self.controls);self.address.textChanged.connect(self.controls)
        tools=QHBoxLayout()
        for label,fn in (('Paste text',self.paste),('Send file',self.file)):
            button=QPushButton(label);button.clicked.connect(fn);tools.addWidget(button)
            if label=='Send file':self.file_button=button
        layout.addLayout(tools)
        row=QHBoxLayout();self.start=QPushButton('Start sharing');self.stop=QPushButton('Stop sharing')
        self.start.clicked.connect(self.start_clicked);self.stop.clicked.connect(self.worker.stop)
        row.addWidget(self.start);row.addWidget(self.stop);layout.addLayout(row)
        hint=QLabel('Move past the chosen edge to control Android.\nReturn through the phone edge, or press Ctrl + Alt + Shift + Esc.');hint.setWordWrap(True);layout.addWidget(hint)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(150);layout.addWidget(self.log)
        self.tray=QSystemTrayIcon(QIcon(str(ICON_PATH)),self);self.tray.setToolTip(NAME)
        menu=QMenu()
        show=QAction('Show '+NAME,self);show.triggered.connect(self.show_window);menu.addAction(show)
        self.tray_sharing=QAction('Start sharing',self)
        self.tray_sharing.triggered.connect(self.toggle_sharing);menu.addAction(self.tray_sharing)
        quit_action=QAction('Quit '+NAME,self);quit_action.triggered.connect(self.quit);menu.addAction(quit_action)
        self.tray.setContextMenu(menu);self.tray.activated.connect(lambda reason:self.show_window() if reason==QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show();self.device.currentIndexChanged.connect(self.controls)
        self.watcher.start();self.controls()
        if serial and serial.startswith('wifi://'):
            self.wifi.setChecked(True);self.address.setText(serial.removeprefix('wifi://'));self.requested=None
            QTimer.singleShot(0,self.start_clicked)

    def toggle_sharing(self):
        if self.worker.process is not None:self.worker.stop();self.controls()
        else:self.start_clicked()

    def show_window(self):self.showNormal();self.raise_();self.activateWindow()

    def closeEvent(self,event):
        event.ignore()
        if QSystemTrayIcon.isSystemTrayAvailable():self.hide()
        else:self.showMinimized()

    def controls(self,*_):
        running=self.worker.process is not None
        available=bool(self.address.text().strip()) if self.wifi.isChecked() else bool(self.devices and self.device.currentIndex()>=0 and self.devices[self.device.currentIndex()].state=='device')
        self.start.setEnabled(available and not running);self.stop.setEnabled(running)
        self.tray_sharing.setText('Stop sharing' if running else 'Start sharing')
        self.tray_sharing.setEnabled(self.stop.isEnabled() if running else self.start.isEnabled())
        self.tray.setToolTip(NAME+(' · Sharing' if running else ' · Disconnected'))
        self.file_button.setEnabled(not self.wifi.isChecked() and bool(self.devices))
        for control in (self.placement,self.device,self.edge,self.speed,self.repeat,self.pairing,self.wifi,self.address,self.fingerprint):control.setEnabled(not running)

    def devices_changed(self,devices,error=None):
        previous=self.devices[self.device.currentIndex()].serial if self.devices and self.device.currentIndex()>=0 else self.settings['serial']
        self.devices=devices;self.device.blockSignals(True);self.device.clear()
        self.device.addItems([device.label for device in devices])
        for index,device in enumerate(devices):
            if device.serial==(self.requested or previous):self.device.setCurrentIndex(index)
        self.device.blockSignals(False);self.controls()
        if error and not self.wifi.isChecked():self.status.setText(error)
        if self.requested and any(d.serial==self.requested and d.state=='device' for d in devices):
            self.requested=None;self.start_clicked()

    def start_clicked(self):
        index=self.device.currentIndex()
        if self.wifi.isChecked():
            serial='wifi://'+self.address.text().strip().removeprefix('wifi://')
        else:
            if index<0:return
            serial=self.devices[index].serial
        self.settings.update({'serial':serial,'edge':self.edge.currentText(),'speed':self.speed.value(),
                       'repeat':self.repeat.isChecked(),'pairing_code':self.pairing.text().strip(),
                       'wifi_address':self.address.text().strip(),'tls_fingerprint':self.fingerprint.text().strip()})
        save_settings(self.settings)
        try:self.worker.start(serial,self.settings['edge'],self.settings['speed'],self.settings['repeat'])
        except Exception as exc:self.status.setText(str(exc))
        self.controls()

    def worker_event(self,event):
        kind=event['type']
        if kind=='ready':
            self.worker.send('clipboard-sharing',enabled=self.clip_sync.isChecked())
            self.status.setText('Sharing is ready. Move past the '+self.settings['edge']+' edge.');self.sync_clipboard(force=True)
        elif kind=='active':
            self.status.setText('Controlling your phone.');self.sync_clipboard(force=True)
        elif kind=='connecting':self.status.setText('Connecting to Android…')
        elif kind=='permission':self.status.setText('Approve the desktop input-capture prompt.')
        elif kind=='clipboard':
            self.phone_clipboard=event['text']
            if self.clip_sync.isChecked() and QApplication.clipboard().text()!=self.phone_clipboard:
                QApplication.clipboard().setText(self.phone_clipboard)
        elif kind=='error':self.status.setText(event['message']);self.log.appendPlainText(event['message'])
        elif kind=='log':self.log.appendPlainText(event['message'])
        elif kind=='exited':
            self.status.setText('Sharing stopped.' if event['stopped'] else 'Connection ended. See details below.')
            if self.quitting:QApplication.instance().quit()
        self.controls()

    def layout_changed(self,edge,layout):
        self.settings.update(edge=edge,phone_layout=layout);save_settings(self.settings)
        if self.edge.currentText()!=edge:self.edge.setCurrentText(edge)

    def clipboard_toggled(self,enabled):
        self.settings['share_clipboard']=enabled;save_settings(self.settings)
        self.worker.send('clipboard-sharing',enabled=enabled)
        self.sync_clipboard(force=True)

    def sync_clipboard(self,force=False):
        text=QApplication.clipboard().text()
        if self.clip_sync.isChecked() and (force or text!=self.phone_clipboard):
            if self.worker.send('clipboard',text=text):self.phone_clipboard=text


    def paste(self):
        text,ok=QInputDialog.getMultiLineText(self,'Paste text','Text to enter in the phone’s focused field')
        if ok:self.worker.send('text',text=text)

    def file(self):
        if self.busy or self.wifi.isChecked() or not self.devices or self.device.currentIndex()<0:return
        path,_=QFileDialog.getOpenFileName(self,'Send a file')
        if not path:return
        serial=self.devices[self.device.currentIndex()].serial;self.busy=True
        def work():
            try:message='Saved to '+send_file(serial,path)
            except Exception as exc:message=str(exc)
            self.dispatch(done,message)
        def done(message):self.busy=False;self.status.setText(message)
        threading.Thread(target=work,daemon=True).start()

    def quit(self):
        if self.busy:self.status.setText('Wait for the file transfer to finish before quitting.');return
        self.quitting=True;self.watcher.close();self.tray.hide()
        if self.worker.process:
            self.worker.stop();QTimer.singleShot(10000,QApplication.instance().quit)
        else:QApplication.instance().quit()

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--connect');parser.add_argument('--smoke-test',action='store_true')
    args=parser.parse_args(argv)
    application=QApplication.instance() or QApplication([sys.argv[0]])
    application.setApplicationName(NAME);application.setQuitOnLastWindowClosed(False)
    user=hashlib.sha256(getpass.getuser().encode()).hexdigest()[:16]
    server_name='desk-dockt-desktop-'+user
    lock=QLockFile(str(Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))/('desk-dockt-'+user+'.lock')))
    if not lock.tryLock(0):
        socket=QLocalSocket();socket.connectToServer(server_name)
        if not socket.waitForConnected(3000):raise RuntimeError('Another desk dockt instance is starting; try opening it again shortly')
        socket.write((json.dumps({'connect':args.connect})+'\n').encode());socket.waitForBytesWritten(1000);socket.disconnectFromServer();return 0
    server=QLocalServer();server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(server_name):
        # Only the lock owner can remove a socket left by a crashed process.
        QLocalServer.removeServer(server_name)
        if not server.listen(server_name):raise RuntimeError('Could not create the desktop application socket')
    window=Window(args.connect);window.show()
    connections=[]
    def incoming():
        client=server.nextPendingConnection();connections.append(client)
        def message():
            if not client.canReadLine():return
            data=bytes(client.readLine(4096))
            try:
                serial=json.loads(data).get('connect')
                if isinstance(serial,str) and not window.worker.process:
                    if serial.startswith('wifi://'):
                        window.wifi.setChecked(True);window.address.setText(serial.removeprefix('wifi://'));window.start_clicked()
                    else:window.requested=serial;window.devices_changed(window.devices)
            except (ValueError,AttributeError):pass
            window.show_window();client.disconnectFromServer()
        client.readyRead.connect(message)
        client.disconnected.connect(lambda:connections.remove(client) if client in connections else None)
    server.newConnection.connect(incoming)
    if args.smoke_test:QTimer.singleShot(2000,window.quit)
    try:return application.exec()
    finally:window.watcher.close();window.worker.stop()

if __name__=='__main__':raise SystemExit(main())
