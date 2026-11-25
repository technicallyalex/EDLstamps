# Licensing, dependencies and provenance

## EDLstamps v1.1.0 Windows build

The Windows x64 ZIP uses CPython 3.14.6, PySide6 Essentials and Shiboken 6.12.0, Qt 6.12.0, PyInstaller 6.21.0, and PyInstaller hooks-contrib 2026.6. Third-party components retain their own terms. The archive includes the app license and separate runtime notices.

- Qt, PySide6 and Shiboken are used under LGPL-3.0. The Qt DLLs and bindings are distributed as separate files in `_internal`. Compatible modified versions can be substituted. The project's license does not restrict reverse engineering for debugging modifications to these libraries.
- Corresponding library sources are available from the upstream [Qt 6.12.0 source archive](https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz) and the [PySide6/Shiboken 6.12.0 source archive](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.12.0-src/pyside-setup-everywhere-src-6.12.0.tar.xz). This project did not patch those libraries. Component attribution is published in the [Qt license and attribution documentation](https://doc.qt.io/qt-6/licensing.html).
- [CPython 3.14.6 source](https://www.python.org/downloads/release/python-3146/), [PyInstaller 6.21.0 source](https://github.com/pyinstaller/pyinstaller/tree/v6.21.0), and [hooks-contrib 2026.6 source](https://github.com/pyinstaller/pyinstaller-hooks-contrib/tree/v2026.6) are also available upstream.
- The logo and EDLstamps wordmark were generated with OpenAI image generation. Product names describe the supported workflow.

## Historical audit of v1.0.1

Reviewed against main at `768643c81d957f833893385d31b350b4695490ba` on 2026-10-31. The MIT license was selected by the maintainer during this audit.

## Scope of the MIT license

The root [LICENSE](../LICENSE) applies to the project's own source and documentation to the extent the licensors hold applicable rights. Retain its copyright and permission notice, including the original repository URL, with copies or substantial portions. Its warranty/liability disclaimer applies as written. This is the standard MIT license, with no added requirement to publish modifications or link back from a user interface.

Bundled runtimes, libraries, build-tool components and other third-party material retain their own licenses. The project license and AI disclosure do not establish ownership or clear third-party rights.

## Dependencies and attribution

| Component | Verified evidence | Applicable terms and remaining work |
| --- | --- | --- |
| Python standard library and Tkinter | Source imports standard-library modules, including tkinter and ctypes; no third-party Python runtime package is declared. The inspected executable contains `python314.dll`. | Python has the [PSF license and incorporated component notices](https://docs.python.org/3/license.html). Retain the exact distribution's license and notices with future portable releases. |
| Tcl/Tk | Build script references Python314's Tcl/Tk 8.6 directories. The executable contains `tcl86t.dll`, `tk86t.dll` and `_tk_data\\license.terms`. | Preserve the Tcl/Tk copyright and permission notices. The archive contains Tk notices; this is not a complete audit of all runtime notice requirements. |
| PyInstaller | [build_portable_exe.bat](../build_portable_exe.bat) installs/upgrades PyInstaller and creates a one-file app. Static archive inspection confirms a PyInstaller package and a `runtime_tkinter` entry. | PyInstaller's [license and bootloader exception](https://pyinstaller.org/en/stable/license.html) distinguish the bootloader from application code; runtime hooks can have Apache-2.0 terms. The exact release build's PyInstaller version, custom hook sources and applicable file-level notices are unverified. |
| Other native runtime libraries | Static inspection found `libssl-3.dll`, `libcrypto-3.dll`, `libffi-8.dll`, `zlib1.dll` and `VCRUNTIME140.dll`. | Their own licenses and redistribution conditions apply. Obtain the exact build's Python/native-library distribution notices and a version inventory; filenames alone do not prove complete license coverage. |
| DaVinci Resolve and YouTube | The app parses an exported EDL and produces chapter text; source imports no Resolve SDK or YouTube client package. | Names identify the workflow. No rights to those products, services, trademarks, input EDLs or underlying media are granted by this project. |

There are no separate image/font asset files in the tracked source tree. The executable's embedded runtime includes additional third-party data, so the source-tree inventory is not a complete executable asset inventory. Users remain responsible for permissions for their marker text and media.

## Binary and build provenance

The repository executable at the reviewed commit and the v1.0.1 release executable are byte-identical: SHA-256 `c6bbb59f14044ad079881534e8bbcd6bc237c5c787558995078d0bc8ff72ca01`. They were inspected without execution. Identity establishes which artifact was reviewed; it does not establish reproducibility, authorship or complete notice coverage.

The checked-in build script refers to absent `runtime_tkinter.py` and `hooks/` inputs, uses an unpinned PyInstaller upgrade, and records no complete build manifest. Restore the actual helper sources and record the Python, Tcl/Tk, PyInstaller and native-library versions plus their notices before representing the release as reproducible or fully documented for redistribution. No missing custom helper was reconstructed or assigned a license during this audit.

The repository did not previously contain a LICENSE or third-party notice file. This documentation and new MIT grant do not insert notices into previously published executables or establish historical permissions for their third-party contents. Future distributions should include LICENSE and the applicable third-party texts as sidecar files or accessible bundled notices.
