# PyInstaller spec — produces ``dist/jakeopdae.exe`` (single-file, windowed).
#
# Build:
#   .\.venv\Scripts\Activate.ps1
#   pip install pyinstaller
#   pyinstaller packaging/keymacro.spec --clean --noconfirm
#
# Output:
#   dist\jakeopdae.exe   (single file, ~150–250 MB depending on extras installed)
#
# What's bundled:
#   - Python interpreter + standard library
#   - keymacro package (every submodule via ``collect_submodules``)
#   - Noto Sans KR 4 weights from keymacro/ui/assets/fonts/
#   - PySide6 + Qt plugins (auto-discovered by PyInstaller's hook)
#   - opencv-python-headless, numpy, mss, pynput, Pillow, PyYAML, pydantic
#
# What's NOT bundled (user installs separately if they need it):
#   - Tesseract binary (for OCR)
#   - Playwright browsers (``playwright install chromium`` after first run)

# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

ROOT = Path(SPECPATH).parent
ENTRY = str(ROOT / "keymacro" / "__main__.py")

# --- bundled data files -----------------------------------------------------

# Noto Sans KR — 4 weights live under keymacro/ui/assets/fonts/. PyInstaller
# unpacks them at runtime to ``sys._MEIPASS`` and ``Path(__file__).parent``
# inside ``keymacro.ui.fonts`` resolves there, so registration just works.
_fonts_dir = ROOT / "keymacro" / "ui" / "assets" / "fonts"
datas = [
    (str(p), "keymacro/ui/assets/fonts")
    for p in _fonts_dir.glob("*.ttf")
]

# PySide6 needs its translations / styles / image plugins shipped along.
datas += collect_data_files("PySide6", includes=["**/translations/*", "**/plugins/**"])

# --- hidden imports ---------------------------------------------------------

# Pydantic v2 uses dynamic imports for discriminated unions; PyInstaller's
# static analysis sometimes misses model files referenced only via the
# ``Field(discriminator=...)`` machinery. Pull in everything under our package
# explicitly so a missed import doesn't crash the .exe at runtime.
hiddenimports = (
    collect_submodules("keymacro")
    + ["pydantic", "pydantic_core"]
    + collect_submodules("pydantic")
)

# --- analysis ---------------------------------------------------------------

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        # We never ship test machinery in the runtime .exe.
        "tests",
        "pytest",
        "_pytest",
        # Saves ~30 MB and we don't use either.
        "tkinter",
        "matplotlib",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# --- single-file executable -------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="jakeopdae",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,         # UPX often confuses Defender; keep raw
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,     # GUI app — no console window pop-up
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,         # add a .ico path here when we have an icon
)


# --- optional code signing --------------------------------------------------
#
# When ``KEYMACRO_PFX_PATH`` is set in the environment, sign the freshly
# built exe with ``signtool``. The hook is a no-op without the env var so
# normal dev builds aren't affected. See ``docs/CODE_SIGNING.md`` for the
# full procedure (PFX format, GitHub Actions Secret encoding, EV vs OV).

import os as _os
import subprocess as _subprocess

_pfx = _os.environ.get("KEYMACRO_PFX_PATH")
if _pfx:
    _target = str(ROOT / "dist" / "jakeopdae.exe")
    _password = _os.environ.get("KEYMACRO_PFX_PASSWORD", "")
    _ts_url = _os.environ.get(
        "KEYMACRO_TS_URL", "http://timestamp.sectigo.com",
    )
    _cmd = [
        "signtool", "sign",
        "/f", _pfx,
        "/p", _password,
        "/tr", _ts_url,
        "/td", "sha256",
        "/fd", "sha256",
        _target,
    ]
    print("[codesign] signing", _target, "with", _pfx)
    try:
        _subprocess.run(_cmd, check=True)
        print("[codesign] success")
    except (_subprocess.CalledProcessError, FileNotFoundError) as _e:
        print(f"[codesign] FAILED: {_e}")
        # Don't fail the whole build — operators can re-sign offline.
