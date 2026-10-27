# Third-party notices — native desktop migration

The application's own code has no new license grant in this change. Its copyright
and license remain separate from the third-party libraries below. Do not describe
the entire repository as LGPL merely because it imports PySide6.

## Qt for Python

The native shell uses PySide6-Essentials and PySide6-Addons 6.12.0 / Shiboken,
QtCore, QtGui, QtWidgets, QtNetwork and QtMultimedia. These components are available under LGPLv3/GPLv3 or a
commercial Qt agreement. This project uses the LGPL option for those modules;
it does not import QtWebEngine or GPL-only add-on modules for the shell.

Before distributing an installer, include the exact bundled libraries' license
texts and copyright notices; retain replaceable dynamically linked Qt DLLs;
provide corresponding library source, including applicable changes, or a compliant
written source offer; and preserve replacement/relinking and reverse-engineering
rights for debugging library modifications. Include required installation
information where applicable. Check the actual artifact's complete dependency
and module inventory; an installed SDK is not proof of a compliant bundle.

Task 223 is source-mode only. Task 227 must assemble and verify these materials
against its exact artifact before claiming packaging completion. No installer is
published by this notice and no public release is authorized.

References: [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations),
[Qt for Python licenses](https://doc.qt.io/qtforpython-6/licenses.html).

Task 226 adds only QtMultimedia from Addons for native device capture. Installing
Addons does not authorize collecting every module into the final artifact.
Qt documents [Multimedia's LGPL option](https://doc.qt.io/qt-6/qtmultimedia-index.html)
and [its FFmpeg attribution](https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html).
The installed SDK contains `avcodec-63.dll`, `avformat-63.dll` and `avutil-61.dll`;
this is an SDK inventory, not proof of which DLLs a future installer contains.
If FFmpeg is bundled, include its corresponding license/notices and matching
source/build information too. Verify the actual binary configuration and all
transitive notices; do not infer LGPL-only contents just from an import or filename.
The one-folder artifact should keep those shared libraries replaceable and the
application's terms must preserve applicable third-party modification/debugging
rights. No repository-wide license change is made by adding these dependencies.

Windows semantic desktop actions additionally depend on `pywinauto` and its
`comtypes`, `six` and `pywin32` dependencies. Task 227 must include their installed
versions and actual license texts in the artifact inventory as well.

Existing third-party components retain their own notices. The remaining legacy
dependency inventory and planned replacements are in
[Task 222](review/task-222-stabilization.md).
