"""Real D-Bus regression: a second launch must activate the existing GTK window."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

@unittest.skipUnless(os.environ.get('DESK_DOCKT_TEST_X11')=='1','requires isolated graphical display')
class RelaunchTests(unittest.TestCase):
    def test_second_launch_activates_existing_instance(self):
        root=str(Path(__file__).resolve().parent)
        # The outer timeout also bounds readiness and shutdown of the fixture.
        driver=r'''
import os,subprocess,sys,tempfile,time
from pathlib import Path
root=sys.argv[1]
fixture=r"""
import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from app import App,GLib
class Probe(App):
    def check_support(self):return 'Isolated startup regression test'
    def on_activate(self,*args):
        super().on_activate(*args)
        path=Path(sys.argv[2]);count=int(path.read_text())+1 if path.exists() else 1
        path.write_text(str(count))
        assert self.window.get_visible()
        GLib.timeout_add(100 if count==2 else 8000,lambda:self.quit() or False)
application=Probe()
application.run(['desk-dockt-startup-test'])
"""
with tempfile.TemporaryDirectory() as directory:
    ready=Path(directory)/'activations'
    process=subprocess.Popen([sys.executable,'-c',fixture,root,str(ready)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            if ready.exists():break
            if process.poll() is not None:raise AssertionError('Primary GTK instance exited before readiness')
            time.sleep(.1)
        assert ready.exists(),'Primary GTK instance did not become ready'
        result=subprocess.run([sys.executable,str(Path(root)/'app.py')],capture_output=True,text=True,timeout=5)
        assert result.returncode==0,(result.returncode,result.stderr)
        process.wait(timeout=5)
        assert ready.read_text()=='2','Second launch did not activate the existing window'
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=5)
'''
        environment=dict(os.environ,GTK_A11Y='none')
        result=subprocess.run(['dbus-run-session','--',sys.executable,'-c',driver,root],
                              env=environment,capture_output=True,text=True,timeout=22)
        self.assertEqual(result.returncode,0,result.stderr)
