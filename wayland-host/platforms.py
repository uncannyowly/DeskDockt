"""Select a real capture backend, never treat XWayland as an X11 session."""
import os
import sys

def backend_name(requested='auto',system=None,environ=None):
    system=system or sys.platform
    environ=os.environ if environ is None else environ
    if requested!='auto':
        valid={'win32':('windows',),'darwin':('macos',)}.get(system,('x11','wayland'))
        if requested not in valid:raise ValueError(f'{requested} is unavailable on {system}')
        if requested=='x11' and (environ.get('WAYLAND_DISPLAY') or environ.get('XDG_SESSION_TYPE')=='wayland'):
            raise ValueError('X11 capture cannot control a Wayland desktop through XWayland')
        return requested
    if system=='win32':return 'windows'
    if system=='darwin':return 'macos'
    if system.startswith('linux'):
        if environ.get('WAYLAND_DISPLAY') or environ.get('XDG_SESSION_TYPE')=='wayland':return 'wayland'
        if environ.get('DISPLAY'):return 'x11'
    raise RuntimeError('No supported graphical desktop session found')

def subprocess_options():
    return {'creationflags':subprocess_no_window()} if sys.platform=='win32' else {}

def subprocess_no_window():
    import subprocess
    return subprocess.CREATE_NO_WINDOW
