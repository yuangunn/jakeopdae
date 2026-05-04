# Diagnostic spec — same as keymacro.spec but with ``console=True`` and
# ``name='jakeopdae-debug'`` so a parallel build doesn't clobber the
# release exe. Use this when chasing import errors / silent crashes.

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).parent
ENTRY = str(ROOT / "keymacro" / "__main__.py")

_fonts_dir = ROOT / "keymacro" / "ui" / "assets" / "fonts"
datas = [
    (str(p), "keymacro/ui/assets/fonts")
    for p in _fonts_dir.glob("*.ttf")
]
_examples_dir = ROOT / "examples"
for _yaml in _examples_dir.glob("*.yaml"):
    datas.append((str(_yaml), "examples"))
datas += collect_data_files("PySide6", includes=["**/translations/*", "**/plugins/**"])

hiddenimports = (
    collect_submodules("keymacro")
    + ["pydantic", "pydantic_core"]
    + collect_submodules("pydantic")
)

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tests", "pytest", "_pytest", "tkinter", "matplotlib"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="jakeopdae-debug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False, upx=False, upx_exclude=[],
    runtime_tmpdir=None,
    console=True,            # show stderr/stdout for diagnosis
    disable_windowed_traceback=False,
    target_arch=None,
)
