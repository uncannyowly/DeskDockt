#!/usr/bin/env python3
"""Default to the desktop app; --cli and --check expose the capture engine."""
from pathlib import Path
import os
import sys

root=Path(__file__).resolve().parent
args=sys.argv[1:]
if '--worker' in args:
    args.remove('--worker')
    from worker import main
    raise SystemExit(main(args))
if '--cli' in args:
    args.remove('--cli');target='worker.py'
elif '--check' in args:target='worker.py'
else:
    from platforms import backend_name
    target='app.py' if backend_name()=='wayland' and '--qt' not in args else 'qt_app.py'
    if '--qt' in args:args.remove('--qt')
if getattr(sys,'frozen',False):
    from qt_app import main
    raise SystemExit(main(args))
os.execv(sys.executable,[sys.executable,str(root/target),*args])
