#!/usr/bin/env python3
"""Install launchers for this checkout, without sudo or package changes."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import shutil
import plistlib
import shlex
from branding import NAME, ICON_NAME, ICON_PATH

APP_ID='io.github.deskdock.PythonHost'

def desktop_quote(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'

def install(prefix=None):
    if sys.platform in ('win32','darwin'):return install_portable(prefix)
    local=Path(prefix) if prefix else Path.home()/'.local'
    data=Path(os.environ.get('XDG_DATA_HOME',local/'share')) if prefix is None else local/'share'
    command=local/'bin'/'desk-dockt'
    desktop=data/'applications'/(APP_ID+'.desktop')
    command.parent.mkdir(parents=True,exist_ok=True)
    desktop.parent.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).resolve().with_name('launch.py')
    # repr produces Python literals, never interpolated shell commands.
    command.write_text('#!/usr/bin/python\nimport os, sys\nos.execv('+repr(sys.executable)+', ['+repr(sys.executable)+', '+repr(str(source))+', *sys.argv[1:]])\n')
    command.chmod(0o755)
    compatibility=command.with_name('deskdock-python')
    compatibility.write_text(command.read_text());compatibility.chmod(0o755)
    icon=data/'icons/hicolor/256x256/apps'/(ICON_NAME+'.png')
    icon.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ICON_PATH.with_name('desk-dockt-256.png'),icon)
    desktop.write_text('[Desktop Entry]\nType=Application\nVersion=1.0\nName='+NAME+'\nComment=Share your mouse and keyboard with Android on Wayland\nExec='+desktop_quote(command)+'\nIcon='+ICON_NAME+'\nTerminal=false\nCategories=Utility;\nStartupNotify=true\nStartupWMClass='+APP_ID+'\n')
    if prefix is None:
        autostart=Path(os.environ.get('XDG_CONFIG_HOME',Path.home()/'.config'))/'autostart'/desktop.name
        if autostart.exists():autostart.write_text(desktop.read_text()+'X-GNOME-Autostart-enabled=true\n')
    extension=data/'gnome-shell/extensions/deskdock-cursor@local'
    shutil.copytree(Path(__file__).with_name('cursor-extension'),extension,dirs_exist_ok=True)
    if prefix is None:
        try:
            from gi.repository import Gio
            source=Gio.SettingsSchemaSource.get_default()
            if source and source.lookup('org.gnome.shell',True):
                settings=Gio.Settings.new('org.gnome.shell')
                enabled=list(settings.get_strv('enabled-extensions'))
                if 'deskdock-cursor@local' not in enabled:settings.set_strv('enabled-extensions',enabled+['deskdock-cursor@local'])
                disabled=list(settings.get_strv('disabled-extensions'))
                if 'deskdock-cursor@local' in disabled:settings.set_strv('disabled-extensions',[name for name in disabled if name!='deskdock-cursor@local'])
                Gio.Settings.sync()
        except ImportError:pass # X11 installs do not need GObject or GNOME.
    return command,desktop

def install_portable(prefix=None):
    source=Path(__file__).resolve().with_name('launch.py')
    if sys.platform=='darwin':
        app=(Path(prefix) if prefix else Path.home()/'Applications')/'desk dockt.app'
        executable=app/'Contents/MacOS/desk-dockt';executable.parent.mkdir(parents=True,exist_ok=True)
        resources=app/'Contents/Resources';resources.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ICON_PATH.with_suffix('.icns'),resources/'desk-dockt.icns')
        executable.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(source))+' "$@"\n');executable.chmod(0o755)
        with (app/'Contents/Info.plist').open('wb') as stream:
            plistlib.dump({'CFBundleName':NAME,'CFBundleDisplayName':NAME,'CFBundleExecutable':'desk-dockt',
                'CFBundleIdentifier':'io.github.deskdockt.host','CFBundlePackageType':'APPL',
                'CFBundleIconFile':'desk-dockt.icns','CFBundleVersion':'0.2.0'},stream)
        return executable,app
    location=Path(prefix) if prefix else Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'desk-dockt'
    location.mkdir(parents=True,exist_ok=True)
    interpreter=Path(sys.executable);windowed=interpreter.with_name('pythonw.exe')
    if windowed.exists():interpreter=windowed
    command=location/'desk-dockt.cmd'
    command.write_text('@echo off\r\n'+subprocess.list2cmdline([str(interpreter),str(source)]).replace('%','%%')+' %*\r\n')
    shortcut=location/'desk-dockt.lnk'
    if prefix is None:
        shortcut=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/desk dockt.lnk'
        shortcut.parent.mkdir(parents=True,exist_ok=True)
        def quote(value):return "'"+str(value).replace("'","''")+"'"
        script="$s=(New-Object -ComObject WScript.Shell).CreateShortcut("+quote(shortcut)+");$s.TargetPath="+quote(interpreter)+";$s.Arguments="+quote(subprocess.list2cmdline([str(source)]))+";$s.IconLocation="+quote(ICON_PATH.with_suffix('.ico'))+";$s.Save()"
        import base64
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()],check=True)
    return command,shortcut

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix',type=Path,help='Alternative installation prefix, useful for packaging/tests')
    args=parser.parse_args()
    for path in install(args.prefix):print(path)

if __name__=='__main__':main()
