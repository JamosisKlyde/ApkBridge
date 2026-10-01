import sys
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import fullscreen
import bridge_core as core

class FullscreenTests(unittest.TestCase):
    def test_kwin_targeting_toggle_and_restore(self):
        for enabled in (True, False):
            script = fullscreen.script_text('com.example.app', enabled)
            harness = '''
const vm = require('vm'); const assert = require('assert');
let android = {resourceClass:'org.waydroid.com.example.app',fullScreen:false};
let unrelated = {resourceClass:'konsole',fullScreen:false};
let added, toggle;
let context = {workspace:{windowList:()=>[android,unrelated],activeWindow:android,
windowAdded:{connect:f=>added=f}},registerShortcut:(a,b,c,f)=>toggle=f};
vm.runInNewContext(SCRIPT,context);
assert.equal(android.fullScreen,ENABLED); assert.equal(unrelated.fullScreen,false);
toggle(); assert.equal(android.fullScreen,!ENABLED);
context.workspace.activeWindow=unrelated; toggle(); assert.equal(unrelated.fullScreen,false);
let newer={resourceClass:'waydroid',fullScreen:!ENABLED};added(newer);assert.equal(newer.fullScreen,ENABLED);
'''.replace('SCRIPT',json.dumps(script)).replace('ENABLED','true' if enabled else 'false')
            subprocess.run(['node','-e',harness],check=True)

    def test_display_button_preserves_compatibility(self):
        record = {'profile': 'Phone Portrait', 'fake_touch': True, 'fake_wifi': False, 'invert_colors': True}
        with patch.object(core, 'load_state', return_value={'apps': {'com.example.app': record}}), patch.object(core, 'launch_package') as launch:
            core.set_fullscreen('com.example.app', True)
            launch.assert_called_once_with('com.example.app', 'Phone Portrait', fullscreen=True, fake_touch=True, fake_wifi=False, invert_colors=True)

    def test_android_display_mode_and_restore(self):
        for enabled in (True, False):
            props = {}
            def set_prop(name, value):
                props[name] = value
                return True
            with patch.object(core, 'ensure_session'), patch.object(core, 'set_prop', side_effect=set_prop), patch.object(core, '_csv_prop', return_value=False), patch.object(core.time, 'sleep'), patch.object(core, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
                core.apply_profile('com.example.app', 'Desktop Balanced', fullscreen=enabled)
                self.assertEqual(props['persist.waydroid.multi_windows'], not enabled)
                self.assertEqual(props['persist.waydroid.width'], '' if enabled else 1280)
                self.assertEqual(props['persist.waydroid.height'], '' if enabled else 800)
                run.assert_called_once_with(['waydroid','session','stop'], timeout=40)

    def test_restart_failure_is_reported(self):
        with patch.object(core, 'ensure_session'), patch.object(core, 'set_prop', return_value=True), patch.object(core, '_csv_prop', return_value=False), patch.object(core, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'stop failed')):
            with self.assertRaises(core.BridgeError):
                core.apply_profile('com.example.app', 'Desktop Balanced', fullscreen=True)

    def test_saved_fullscreen_used_by_shortcut(self):
        state={'apps':{'com.example.app':{'fullscreen':True}}}
        with patch.object(core,'load_state',return_value=state), patch.object(core,'save_state'), patch.object(core,'apply_profile',return_value={}), patch.object(core,'run',return_value=subprocess.CompletedProcess([],0,'','')), patch.object(fullscreen,'configure_fullscreen') as configure:
            core.launch_package('com.example.app')
            configure.assert_called_once_with('com.example.app',True)
            core.launch_package('com.example.app',fullscreen=False)
            self.assertFalse(state['apps']['com.example.app']['fullscreen'])

if __name__ == '__main__': unittest.main()
