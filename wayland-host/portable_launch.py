#!/usr/bin/env python3
"""Source and PyInstaller entry for the portable Qt edition."""
import sys
if '--worker' in sys.argv:
    from worker import main
    args=sys.argv[1:];args.remove('--worker');raise SystemExit(main(args))
else:
    if sys.platform=='win32' and getattr(sys,'frozen',False):
        # Keep real worker pipes; hide only a console this GUI launched itself.
        import ctypes
        ctypes.windll.kernel32.GetConsoleWindow.restype=ctypes.c_void_p
        ctypes.windll.user32.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
        processes=(ctypes.c_ulong*2)()
        if ctypes.windll.kernel32.GetConsoleProcessList(processes,2)==1:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(),0)
    from qt_app import main
    raise SystemExit(main(sys.argv[1:]))
