# Bundled software

Scrip application source is MIT licensed (LICENSE).

The Windows installer bundles CPython, PySide6 Essentials, Shiboken6, Qt, and Python
libraries used by the application. Each retains its own license. Distribution metadata
and available license texts are retained under `_internal/*.dist-info` in the installed
application; CPython's bundled license is retained by PyInstaller. The Qt/PySide shared
libraries are dynamically loaded and remain replaceable in `_internal/PySide6`.

- CPython: https://www.python.org/ ? Python Software Foundation license.
- PySide6/Shiboken6/Qt: https://www.qt.io/qt-for-python ? LGPLv3/GPL/commercial options
  as specified by each component. Source corresponding to the packaged version is
  available at https://download.qt.io/official_releases/QtForPython/ and
  https://download.qt.io/official_releases/qt/. Consult the included license texts.
- PyInstaller: https://pyinstaller.org/ ? GPL with the bootloader exception permitting
  bundled applications under their own licenses.
- Inno Setup: https://jrsoftware.org/ ? installer compiler; its installer engine retains
  the original author's copyright notices.

Other runtime libraries include FastAPI, Starlette, Pydantic, Uvicorn, h11, AnyIO, Click,
IDNA, and typing support packages. Their metadata and license notices accompany the bundle.
The installer contains no model weights or agent application binaries.

To inspect application source, use the versioned source distribution made by the release
workflow. A frozen installer does not change the licenses of the libraries it contains.
