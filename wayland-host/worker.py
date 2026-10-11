"""Cross-platform worker entry; Wayland stays on its compositor portal."""
import argparse
import importlib
import json
import queue
import signal
import sys
import threading

from platforms import backend_name
from protocol import Phone

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend',choices=('auto','wayland','x11','windows','macos'),default='auto')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--desktop-worker',action='store_true')
    parser.add_argument('--serial');parser.add_argument('--edge',choices=('left','right','top','bottom'),default='right')
    parser.add_argument('--speed',type=float,default=1);parser.add_argument('--no-repeat',action='store_true')
    args=parser.parse_args(argv)
    if not .1<=args.speed<=4:parser.error('Pointer speed must be between 0.1 and 4')
    backend=None;phone=None;engine=None
    def notify(**event):
        if args.desktop_worker:print('@event '+json.dumps(event),flush=True)
    try:
        name=backend_name(args.backend)
        if name=='wayland':
            from host import main as wayland_main
            original=sys.argv
            sys.argv=[original[0]]+(list(argv) if argv is not None else original[1:])
            if '--backend' in sys.argv:
                i=sys.argv.index('--backend');del sys.argv[i:i+2]
            try:return wayland_main()
            finally:sys.argv=original
        module=importlib.import_module('backend_x11' if name=='x11' else 'backend_hooks')
        events=queue.Queue(maxsize=8192)
        def emit(kind,data):
            try:events.put_nowait((kind,data,getattr(backend,'epoch',0)))
            except queue.Full:
                # Never leave a desktop captured when we cannot track its input.
                overflow.set()
        overflow=threading.Event()
        if args.check:
            backend=module.Backend(emit)
            backend.monitors();print(name+' capture backend available.');return 0
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QTimer
        application=QApplication.instance() or QApplication([])
        application.setQuitOnLastWindowClosed(False)
        backend=module.Backend(emit)
        phone=Phone(args.serial)
        phone.on_clipboard=lambda text:notify(type='clipboard',text=text)
        phone.on_disconnect=lambda:emit('failure',(str(phone.error),))
        notify(type='connecting');phone.launch();phone.connect();phone.wait_agent()
        from native_engine import Engine
        engine=Engine(phone,backend,args.edge,args.speed,notify,not args.no_repeat)
        if hasattr(backend,'start'):backend.start()
        failure=[]
        def stop(*_):application.quit()
        for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,stop)
        def tick():
            try:
                if overflow.is_set():raise RuntimeError('Input queue overflow; releasing desktop capture')
                backend.poll()
                for _ in range(512):
                    try:kind,data,epoch=events.get_nowait()
                    except queue.Empty:break
                    if kind not in ('command','failure') and epoch!=backend.epoch:continue
                    if kind=='failure':raise RuntimeError(data[0])
                    if kind=='command':
                        command=data
                        if command.get('command')=='stop':stop()
                        elif command.get('command')=='release':engine.release()
                        elif command.get('command')=='clipboard':phone.clipboard(command['text'])
                        elif command.get('command')=='text':phone.text(command['text'])
                    else:getattr(engine,kind)(*data)
                engine.tick()
            except Exception as exc:
                failure.append(str(exc));notify(type='error',message=str(exc));stop()
        timer=QTimer();timer.timeout.connect(tick);timer.start(10)
        if args.desktop_worker:
            def commands():
                for line in sys.stdin:
                    try:emit('command',json.loads(line))
                    except ValueError:pass
                emit('command',{'command':'stop'})
            threading.Thread(target=commands,daemon=True).start()
        notify(type='ready',edge=args.edge,width=phone.width,height=phone.height)
        application.exec()
        return 1 if failure else 0
    except Exception as exc:
        notify(type='error',message=str(exc));print(str(exc),file=sys.stderr);return 1
    finally:
        try:
            if engine:engine.release()
        finally:
            try:
                if backend:backend.close()
            finally:
                if phone:phone.close()

if __name__=='__main__':raise SystemExit(main())
