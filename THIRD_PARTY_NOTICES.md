# Third-party notices

APKBridge is an independent front-end. It is not an official Waydroid, Qt,
Riverbank, Android, or LineageOS product. Those projects retain their names,
copyrights, and licensing terms.

The published `.run` installer contains APKBridge source and packaging scripts.
It does not bundle an Android image, Python, PyQt6, Qt, Waydroid, APKs, or ARM
translation binaries. Dependencies may be obtained separately during setup.

| Component | Use in APKBridge | Licensing and upstream |
| --- | --- | --- |
| Python 3 | Runs the launcher and backend | PSF license and included third-party notices; [Python license](https://docs.python.org/3/license.html) |
| PyQt6 | Qt GUI and D-Bus bindings; system package or pip install | GPLv3 or a separately purchased Riverbank commercial license; this project uses the GPL edition. [Riverbank licensing](https://www.riverbankcomputing.com/software/pyqt/intro) |
| Qt 6 | Underlying GUI libraries installed with PyQt6 or by the distribution | Module-specific LGPLv3/GPL/commercial terms and additional notices. [Qt licensing](https://doc.qt.io/qt-6/licensing.html) |
| Waydroid | External CLI and Android container | GPLv3 for the upstream project, with separately licensed components/images. [Waydroid LICENSE](https://github.com/waydroid/waydroid/blob/main/LICENSE) |
| Waydroid Extras Script | Optional ARM support, downloaded only when requested | GPLv3 script; its downloaded payloads have their own terms. [casualsnek/waydroid_script](https://github.com/casualsnek/waydroid_script), [LICENSE](https://github.com/casualsnek/waydroid_script/blob/main/LICENSE) |
| KDE Plasma / KWin | Session-only fullscreen integration over D-Bus | External desktop software, not included. [KWin source](https://invent.kde.org/plasma/kwin) |
| Node.js | Executes simulated KWin JavaScript tests only | MIT and bundled dependency notices; [Node license](https://github.com/nodejs/node/blob/main/LICENSE). Not needed to run APKBridge. |

## Optional ARM support

The ARM helper fetches the community script and records the exact fetched Git
revision. It is not pinned to a reviewed revision, and the upstream script can
download additional components. Its GPL license does not automatically apply
to those payloads. In particular, do not assume libndk/libhoudini translation
binaries are open source or freely redistributable.

APKBridge does not grant rights to Android apps, commercial services, media,
firmware, or translation components. Their own terms continue to apply.

For the versions actually installed on your machine, consult the distribution
package notices or Python package metadata. This inventory is not a promise
that upstream versions or their transitive dependencies remain unchanged.
