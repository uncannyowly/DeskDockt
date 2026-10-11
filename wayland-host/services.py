"""Device discovery, saved settings, and an isolated capture worker."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
from platforms import subprocess_options
import signal
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parent
APP_ID = 'io.github.deskdock.PythonHost'

@dataclass(frozen=True)
class Device:
    serial: str
    state: str
    model: str

    @property
    def label(self):
        suffix = '' if self.state == 'device' else f' ({self.state})'
        return f'{self.model.replace("_", " ")} · {self.serial}{suffix}'


def parse_devices(output):
    devices = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0] == 'List' or line.startswith('*'):
            continue
        details = dict(part.split(':',1) for part in parts[2:] if ':' in part)
        devices.append(Device(parts[0],parts[1],details.get('model','Android')))
    return devices


def config_path():
    if sys.platform=='win32':return Path(os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))/'desk-dockt/settings.json'
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/desk-dockt/settings.json'
    return Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'deskdock-python'/'settings.json'


def load_settings(path=None):
    defaults = {'serial':'','edge':'right','speed':1.0,'repeat':True,'pairing_code':'','wifi_address':'','tls_fingerprint':''}
    try:
        data = json.loads((path or config_path()).read_text())
        if not isinstance(data,dict): return defaults
        if data.get('edge') in ('left','right','top','bottom'): defaults['edge']=data['edge']
        speed = data.get('speed')
        if isinstance(speed,(float,int)) and 0.1 <= speed <= 4: defaults['speed']=float(speed)
        if isinstance(data.get('serial'),str): defaults['serial']=data['serial']
        if isinstance(data.get('repeat'),bool): defaults['repeat']=data['repeat']
        for name in ('pairing_code','wifi_address','tls_fingerprint'):
            if isinstance(data.get(name),str):defaults[name]=data[name]
    except (OSError,ValueError): pass
    return defaults


def save_settings(data,path=None):
    path=path or config_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n')
    if os.name!='nt':temporary.chmod(0o600)
    temporary.replace(path)

class Worker:
    """Read events on a background thread; dispatch marshals them onto GTK's loop."""
    def __init__(self,dispatch,callback):
        self.dispatch,self.callback=dispatch,callback
        self.process=None
        self.lock=threading.Lock()
        self.stopping=False

    def start(self,serial,edge,speed,repeat=True):
        if self.process is not None: raise RuntimeError('A connection is already running')
        interpreter=sys.executable
        if sys.platform=='win32' and Path(interpreter).name.lower()=='pythonw.exe':
            interpreter=str(Path(interpreter).with_name('python.exe'))
        command=([interpreter,'--worker'] if getattr(sys,'frozen',False) else [interpreter,'-u',str(ROOT/'worker.py')])
        command+=['--desktop-worker','--serial',serial,
                 '--edge',edge,'--speed',str(speed)]
        if not repeat: command.append('--no-repeat')
        self.stopping=False
        environment=os.environ.copy()
        environment['DESK_DOCKT_PAIRING_CODE']=load_settings().get('pairing_code','')
        environment['DESK_DOCKT_TLS_FINGERPRINT']=load_settings().get('tls_fingerprint','')
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True,env=environment,**subprocess_options())
        process=self.process
        threading.Thread(target=self.read,args=(process,),daemon=True).start()

    def read(self,process):
        for line in process.stdout:
            line=line.rstrip()
            if line.startswith('@event '):
                try: event=json.loads(line[7:])
                except ValueError: event={'type':'log','message':line}
            else: event={'type':'log','message':line}
            self.dispatch(self.callback,event)
        code=process.wait()
        process.stdout.close()
        self.dispatch(self.finished,process,code)

    def finished(self,process,code):
        if self.process is not process: return False
        process.stdin.close()
        self.process=None
        self.callback({'type':'exited','code':code,'stopped':self.stopping})
        return False

    def send(self,command,**data):
        process=self.process
        if process is None or process.poll() is not None: return False
        try:
            with self.lock:
                process.stdin.write(json.dumps({'command':command,**data})+'\n')
                process.stdin.flush()
            return True
        except (BrokenPipeError,OSError): return False

    def stop(self):
        process=self.process
        if process is None: return
        self.stopping=True
        self.send('stop')
        # Signal also cancels an outstanding compositor consent request.
        if process.poll() is None and sys.platform!='win32':process.send_signal(signal.SIGTERM)
        def deadline():
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    if sys.platform=='win32':process.kill()
                    else:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
        threading.Thread(target=deadline,daemon=True).start()

class DeviceWatcher:
    """ADB's streaming device list, no repeated subprocess polling."""
    def __init__(self,dispatch,callback):
        self.dispatch,self.callback=dispatch,callback
        self.process=None
        self.closed=threading.Event()

    def start(self):
        def track():
            try:
                self.process=subprocess.Popen(['adb','track-devices','-l'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,**subprocess_options())
                def exact(n):
                    data=b''
                    while len(data)<n:
                        part=self.process.stdout.read(n-len(data))
                        if not part: raise EOFError('ADB device watcher stopped')
                        data+=part
                    return data
                while not self.closed.is_set():
                    size=int(exact(4),16)
                    if size>1024*1024: raise ValueError('Invalid ADB device-list size')
                    self.dispatch(self.callback,parse_devices(exact(size).decode()))
            except (OSError,EOFError,ValueError) as exc:
                if not self.closed.is_set(): self.dispatch(self.callback,[],str(exc))
            finally:
                if self.process:
                    if self.process.poll() is None: self.process.terminate()
                    self.process.wait()
                    self.process.stdout.close()
        threading.Thread(target=track,daemon=True).start()

    def close(self):
        self.closed.set()
        if self.process and self.process.poll() is None: self.process.terminate()


def send_file(serial,path):
    """Choose a distinct download name so sending never replaces an existing file."""
    import uuid
    source=Path(path).resolve()
    if not source.is_file(): raise ValueError('The selected file no longer exists')
    remote='/sdcard/Download/'+source.stem+'-'+uuid.uuid4().hex[:12]+source.suffix
    result=subprocess.run(['adb','-s',serial,'push',str(source),remote],capture_output=True,text=True,timeout=300)
    if result.returncode: raise RuntimeError(result.stderr or result.stdout)
    return remote
