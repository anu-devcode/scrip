# PyInstaller is run from the repository root. Only application modules/data are frozen.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

metadata = []
for name in ['uvicorn', 'PySide6_Essentials', 'shiboken6', 'fastapi', 'starlette',
             'pydantic', 'pydantic_core', 'h11', 'anyio', 'click', 'idna',
             'typing_extensions', 'annotated-types', 'typing-inspection', 'annotated-doc']:
    metadata += copy_metadata(name)

root = Path(SPECPATH).resolve().parents[1]
a = Analysis(
    [str(root / 'deploy/desktop/entry.py')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=collect_data_files('scrip_core') + metadata + [
        (str(Path(sys.base_prefix) / 'LICENSE.txt'), 'licenses')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.asyncio',
                   'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan.on'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'mypy', 'ruff', 'PIL', 'PySide6.QtNetwork'],
    noarchive=False,
)
pyz = PYZ(a.pure)
icon = str(root / 'assets/brand/icons/scrip-icon-256.png')
desktop = EXE(pyz, a.scripts, [], exclude_binaries=True, name='Scrip',
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=False, icon=icon)
cli = EXE(pyz, a.scripts, [], exclude_binaries=True, name='scrip-cli',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=True, icon=icon)
bundle = COLLECT(desktop, cli, a.binaries, a.datas, strip=False, upx=False, name='Scrip')
