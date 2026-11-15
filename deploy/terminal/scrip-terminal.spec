from pathlib import Path
import sys
from PyInstaller.utils.hooks import copy_metadata

root = Path(SPECPATH).resolve().parents[1]
metadata = []
for package in ('pydantic', 'pydantic_core', 'fastapi', 'starlette', 'uvicorn',
                'anyio', 'h11', 'click', 'idna', 'typing_extensions',
                'annotated-types', 'typing-inspection', 'annotated-doc'):
    metadata += copy_metadata(package)
analysis = Analysis(
    [str(root / 'deploy/terminal/entry.py')], pathex=[str(root / 'src')],
    binaries=[], datas=metadata + [(str(Path(sys.base_prefix) / 'LICENSE.txt'), 'licenses')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops.asyncio',
        'uvicorn.protocols.http.h11_impl', 'uvicorn.lifespan.on'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['PySide6', 'shiboken6', 'tkinter', 'pytest', 'mypy', 'ruff', 'PIL'],
    noarchive=False,
)
archive = PYZ(analysis.pure)
console = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='scrip',
              console=True, debug=False, strip=False, upx=False)
hook = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='scrip-cli',
           console=True, debug=False, strip=False, upx=False)
bundle = COLLECT(console, hook, analysis.binaries, analysis.datas,
                 strip=False, upx=False, name='ScripTerminal')
