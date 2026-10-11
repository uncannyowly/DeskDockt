#!/usr/bin/env python3
"""Build on the destination OS; PyInstaller does not cross-compile."""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parent
arguments=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--windowed' if sys.platform=='darwin' else '--console','--onedir',
    '--name','desk-dockt','--add-data',str(root/'assets')+':assets','--hidden-import','worker',
    '--hidden-import','native_engine','--hidden-import','protocol',
    '--add-data',str(root/'licenses')+':licenses','--add-data',str(root/'THIRD_PARTY.md')+':.']
if sys.platform in ('win32','darwin'):
    arguments+=['--hidden-import','backend_hooks','--collect-submodules','pynput','--collect-submodules','screeninfo']
else:arguments+=['--hidden-import','backend_x11']
if sys.platform=='win32':arguments+=['--icon',str(root/'assets/desk-dockt.ico')]
if sys.platform=='darwin':arguments+=['--icon',str(root/'assets/desk-dockt.icns'),'--osx-bundle-identifier','io.github.deskdockt.host']
subprocess.run(arguments+[str(root/'portable_launch.py')],cwd=root,check=True)
