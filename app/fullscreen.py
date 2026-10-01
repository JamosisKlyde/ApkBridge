"""Session-only KDE fullscreen support. No persistent window rules or root access."""
import json
from pathlib import Path


def script_text(package, enabled):
    return '''
var targetPackage = PACKAGE;
var startFullscreen = ENABLED;
function matches(w) {
    if (!w || w.desktopWindow || w.dock) return false;
    var cls = String(w.resourceClass || "").toLowerCase();
    var name = String(w.resourceName || "").toLowerCase();
    return cls === targetPackage || name === targetPackage ||
        cls === "waydroid" || cls.indexOf("waydroid.") === 0 ||
        name === "waydroid" || name.indexOf("waydroid.") === 0 ||
        cls === "org.waydroid" || cls.indexOf("org.waydroid.") === 0 ||
        name === "org.waydroid" || name.indexOf("org.waydroid.") === 0;
}
function apply(w) { if (matches(w)) w.fullScreen = startFullscreen; }
workspace.windowList().forEach(apply);
// Apply once on creation; never force fullscreen again after the user exits it.
workspace.windowAdded.connect(function(w) { apply(w); });
registerShortcut("APKBridgeFullscreen", "APKBridge: Toggle Android fullscreen", "Ctrl+Alt+F11", function() {
    var w = workspace.activeWindow;
    if (matches(w)) w.fullScreen = !w.fullScreen;
});
'''.replace('PACKAGE', json.dumps(package.lower())).replace('ENABLED', 'true' if enabled else 'false')


def configure_fullscreen(package, enabled, *, required=False):
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtDBus import QDBusConnection, QDBusMessage
    from bridge_core import BridgeError
    app = QCoreApplication.instance() or QCoreApplication([])
    bus = QDBusConnection.sessionBus()
    def call(path, interface, method, *args):
        message = QDBusMessage.createMethodCall('org.kde.KWin', path, interface, method)
        message.setArguments(list(args))
        reply = bus.call(message)
        if reply.type() == QDBusMessage.MessageType.ErrorMessage:
            raise BridgeError('KDE fullscreen: ' + reply.errorMessage())
        return reply.arguments()
    try:
        service = bus.interface().isServiceRegistered('org.kde.KWin')
        available = service.isValid() and service.value()
        if not available:
            if enabled or required:
                raise BridgeError('Fullscreen currently requires KDE Plasma. Uncheck Launch fullscreen to launch normally.')
            return
        # Replace only our own session script. Normal launches also restore windows.
        call('/Scripting', 'org.kde.kwin.Scripting', 'unloadScript', 'apkbridge-fullscreen')
        path = Path.home() / '.local/share/apkbridge/fullscreen-session.js'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(script_text(package, enabled), encoding='utf-8')
        ids = call('/Scripting', 'org.kde.kwin.Scripting', 'loadScript', str(path), 'apkbridge-fullscreen')
        if not ids or int(ids[0]) < 0:
            raise BridgeError('KDE could not load the fullscreen helper.')
        call('/Scripting/Script' + str(ids[0]), 'org.kde.kwin.Script', 'run')
    finally:
        # Hold the Qt application reference through the synchronous D-Bus calls.
        _ = app
