"""New authenticated companion protocol plus legacy DeskDock transport."""
import shlex
import socket
import struct
import subprocess
import threading
import json
import os
import hmac
import hashlib
from platforms import subprocess_options

PACKAGE = 'com.floriandraschbacher.deskdock.pro'
NEW_PACKAGE='io.github.deskdockt.android'

class Phone:
    def __init__(self, serial=None):
        self.wifi=serial if serial and serial.startswith('wifi://') else None
        self.fingerprint=os.environ.get('DESK_DOCKT_TLS_FINGERPRINT','')
        self.adb = ['adb'] + (['-s', serial] if serial else [])
        self.sock = None
        self.port = None
        self.agent = None
        self.agent_ready = threading.Event()
        self.lock = threading.Lock()
        self.width = self.height = 0
        self.error = None
        self.on_disconnect = lambda: None
        self.on_clipboard = lambda text: None
        self.stop = threading.Event()
        self.reader = None
        self.protocol_version=1
        self.package=PACKAGE
        self.previous_ime=None
        self.pairing_code=os.environ.get('DESK_DOCKT_PAIRING_CODE','')

    def command(self, *args):
        return subprocess.check_output(self.adb + list(args), text=True, timeout=15,**subprocess_options()).strip()

    def launch(self):
        if self.wifi:self.package=NEW_PACKAGE;return
        try:
            if self.command('shell','pm','path',NEW_PACKAGE).startswith('package:'):self.package=NEW_PACKAGE
        except subprocess.SubprocessError:pass
        activity=NEW_PACKAGE+'/.MainActivity' if self.package==NEW_PACKAGE else PACKAGE+'/com.floriandraschbacher.deskdock.ui.MainActivity'
        self.command('shell','am','start','-n',activity)

    def json_event(self,kind,**values):
        self.send(json.dumps({'type':kind,**values},ensure_ascii=False).encode('utf-8'))

    def read(self):
        def exact(n):
            result = bytearray()
            while len(result) < n:
                chunk = self.sock.recv(n - len(result))
                if not chunk:
                    raise ConnectionError('Phone disconnected')
                result.extend(chunk)
            return bytes(result)
        size, = struct.unpack('>I', exact(4))
        if not 0 < size <= (1024*1024 if self.protocol_version==2 else 5*1024*1024):
            raise ValueError('Invalid phone frame size')
        return exact(size)

    def send(self, data):
        if len(data) > (1024 * 1024 if self.protocol_version==2 else 5 * 1024 * 1024):
            raise ValueError("Text is too large to send")
        with self.lock:
            self.sock.sendall(struct.pack('>I', len(data)) + data)

    def event(self, data):
        self.send(struct.pack('>I', 2) + data)

    def enter(self, entered):
        if self.protocol_version==2:return self.json_event('enter',entered=bool(entered))
        self.event(bytes((0, bool(entered))))

    def move(self, x, y):
        if self.protocol_version==2:return self.json_event('move',x=x,y=y)
        self.event(struct.pack('>Biii', 3, int(x), int(y), 0))

    def button(self, button, down, x, y):
        if self.protocol_version==2:return self.json_event('button',button=button,down=bool(down),x=x,y=y)
        self.event(struct.pack('>BiBii', 4, button, bool(down), int(x), int(y)))

    def scroll(self, x, y, dx, dy):
        if self.protocol_version==2:return self.json_event('scroll',x=x,y=y,dx=dx,dy=dy)
        self.event(struct.pack('>Biiii', 5, int(x), int(y), int(dx), int(dy)))

    def key(self, code, character, down):
        if self.protocol_version==2:return self.json_event('key',code=code,character=character,down=bool(down))
        self.event(struct.pack('>BiHB', 2, code, character if character <= 65535 else 0, bool(down)))

    def clipboard(self, text):
        if self.protocol_version==2:return self.json_event('clipboard',text=text)
        self.event(b"\x01" + text.encode("utf-8"))

    def text(self, text):
        if self.protocol_version==2:return self.json_event('text',text=text)
        data = text.encode('utf-8')
        self.event(bytes((7,)) + struct.pack('>I', len(data)) + data + b'\x01')

    def connect(self):
        if self.wifi:
            try:
                from wifi_transport import connect
                self.sock=connect(self.wifi,self.fingerprint)
                self.connect_new(json.loads(self.read()));return
            except Exception:self.close();raise
        try:
            self.port = self.command('forward', 'tcp:0', 'tcp:'+str(19673 if self.package==NEW_PACKAGE else 19672))
            # The launched Android activity may still be starting its sharing service.
            import time
            deadline=time.monotonic()+4
            while True:
                try:
                    self.sock=socket.create_connection(('127.0.0.1',int(self.port)),timeout=8)
                    break
                except ConnectionRefusedError:
                    if self.package!=NEW_PACKAGE or time.monotonic()>=deadline:raise
                    time.sleep(.1)
            greeting=self.read()
            if greeting.startswith(b'{'):
                self.connect_new(json.loads(greeting));return
            if greeting != b'HELLO':
                raise ValueError('Unexpected phone greeting')
            self.send(b'Server 18')
            version, package, device = self.read(), self.read(), self.read()
            if package.decode() != PACKAGE:
                raise ValueError('Unexpected Android package')
            self.config(self.read())
            print(f'{version.decode()}: {package.decode()}, {self.width}x{self.height}', flush=True)
            # Same shell permission used by the original DeskDock server.
            self.command('shell', 'pm', 'grant', PACKAGE, 'android.permission.WRITE_SECURE_SETTINGS')
            self.sock.settimeout(None)
            self.reader = threading.Thread(target=self.receive, daemon=True)
            self.reader.start()
        except Exception:
            self.close()
            raise

    def connect_new(self,greeting):
        if greeting.get('protocol')!='desk-dockt' or greeting.get('version')!=2:raise ValueError('Unsupported companion protocol')
        if not greeting.get('accessible'):raise RuntimeError('Enable desk dockt input control in Android Accessibility settings')
        pairing_required=greeting.get('authentication','pairing')!='adb'
        if self.wifi and not pairing_required:raise ValueError('Wi-Fi requires pairing authentication')
        if pairing_required and not self.pairing_code:raise RuntimeError('Enter the Wi-Fi pairing code from Android Settings')
        self.protocol_version=2
        self.width=int(greeting['width']);self.height=int(greeting['height'])
        if not 0<self.width<=32768 or not 0<self.height<=32768:raise ValueError('Invalid phone display size')
        proof=hmac.new(self.pairing_code.encode(),greeting['nonce'].encode(),hashlib.sha256).hexdigest() if pairing_required else ''
        self.json_event('authenticate',proof=proof)
        reply=json.loads(self.read())
        if reply.get('type')!='ready':raise RuntimeError(reply.get('message','Phone pairing failed'))
        ime=NEW_PACKAGE+'/.DockIme'
        if self.wifi:
            if not greeting.get('keyboard_selected'):raise RuntimeError('Enable and select desk dockt keyboard in Android settings for direct Wi-Fi')
        else:
            self.previous_ime=self.command('shell','settings','get','secure','default_input_method')
            self.command('shell','ime','enable',ime);self.command('shell','ime','set',ime)
        self.agent_ready.set();self.sock.settimeout(None)
        self.reader=threading.Thread(target=self.receive_new,daemon=True);self.reader.start()
        print(f'desk dockt protocol 2: {self.width}x{self.height}',flush=True)

    def receive_new(self):
        try:
            while not self.stop.is_set():
                message=json.loads(self.read())
                if message.get('type')=='clipboard':self.on_clipboard(message.get('text',''))
                elif message.get('type')=='config':
                    width,height=int(message['width']),int(message['height'])
                    if not 0<width<=32768 or not 0<height<=32768:raise ValueError('Invalid phone display size')
                    self.width,self.height=width,height
        except Exception as exc:
            if not self.stop.is_set():self.error=exc;self.on_disconnect()

    def wait_agent(self, timeout=8):
        if not self.agent_ready.wait(timeout):
            raise RuntimeError('The phone input service did not start. Check DeskDock permissions and tap CONNECT.')
        if self.error:
            raise self.error

    def monitor_agent(self, process):
        try:
            for line in process.stdout:
                if line.strip() == 'Started' and self.agent is process: self.agent_ready.set()
            code=process.wait()
            if not self.stop.is_set() and self.agent is process:
                self.error=RuntimeError(f'Phone input service exited ({code}). Check DeskDock permissions.')
                self.agent_ready.set()
                self.on_disconnect()
        finally:
            process.stdout.close()

    def config(self, data):
        if len(data) < 20 or struct.unpack('>I', data[:4])[0] != 3:
            raise ValueError('Invalid display configuration')
        _, self.width, self.height, self.dpi, self.speed, *_ = struct.unpack('>' + 'I' * (len(data)//4), data)
        if not 0 < self.width < 32768 or not 0 < self.height < 32768:
            raise ValueError('Invalid phone dimensions')

    def receive(self):
        try:
            while not self.stop.is_set():
                data = self.read()
                kind, = struct.unpack('>I', data[:4])
                if kind == 3:
                    self.config(data)
                elif kind == 2 and len(data) >= 5 and data[4] == 1:
                    self.on_clipboard(data[5:].decode("utf-8"))
                elif kind == 1 and len(data) >= 12:
                    subtype, length = struct.unpack('>II', data[4:12])
                    if subtype == 1:
                        path = data[12:12+length].decode()
                        if not path.startswith('/data/app/') or not path.endswith('.apk') or '\x00' in path:
                            raise ValueError('Invalid system-agent APK path')
                        previous,self.agent=self.agent,None
                        if previous and previous.poll() is None:
                            previous.terminate()
                            previous.wait(timeout=5)
                        command = f'export CLASSPATH={shlex.quote(path)}; app_process /system/bin com.floriandraschbacher.deskdock.systemservice.Service'
                        self.agent_ready.clear()
                        self.agent = subprocess.Popen(self.adb + ['shell', command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,text=True)
                        threading.Thread(target=self.monitor_agent,args=(self.agent,),daemon=True).start()
        except Exception as exc:
            if not self.stop.is_set():
                self.error = exc
                self.agent_ready.set()
                self.on_disconnect()

    def close(self):
        self.stop.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.sock.close()
        if self.reader and self.reader is not threading.current_thread():
            self.reader.join(timeout=2)
        if self.agent and self.agent.poll() is None:
            self.agent.terminate()
            try:
                self.agent.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.agent.kill()
                self.agent.wait()
        if self.port:
            port,self.port=self.port,None
            try:
                self.command("forward", "--remove", "tcp:" + port)
            except (OSError,subprocess.SubprocessError):
                pass
        if self.previous_ime and self.previous_ime!='null' and not self.previous_ime.startswith(NEW_PACKAGE+'/'):
            previous,self.previous_ime=self.previous_ime,None
            try:
                current=self.command('shell','settings','get','secure','default_input_method')
                if current.startswith(NEW_PACKAGE+'/'):self.command('shell','ime','set',previous)
            except (OSError,subprocess.SubprocessError):pass
