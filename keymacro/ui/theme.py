"""Design tokens — single source of truth, mirrors ``DESIGN.md`` 1:1.

Compact density: targets ~14px body / 12px label / sub-40px control
heights so the whole window fits on a 720p monitor at 100% scale and
stays comfortable at 150–200% DPI scaling.
"""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------

C: Final[dict[str, str]] = {
    "surface": "#13110E",
    "surface-dim": "#0F0E0B",
    "surface-bright": "#1F1C17",
    "surface-container-lowest": "#0A0908",
    "surface-container-low": "#16140F",
    "surface-container": "#1A1813",
    "surface-container-high": "#1F1D17",
    "surface-container-highest": "#26241D",
    "on-surface": "#F2EBDA",
    "on-surface-variant": "#A39B85",
    "outline": "#46423A",
    "outline-variant": "#2C2922",
    "primary": "#E8B26A",
    "on-primary": "#13110E",
    "primary-container": "#3E2F18",
    "on-primary-container": "#F2D7A8",
    "primary-fixed-dim": "#C99752",
    "secondary": "#5BA8E5",
    "secondary-container": "#0E2C46",
    "on-secondary-container": "#CDE3F7",
    "tertiary": "#86B889",
    "tertiary-container": "#1F3A22",
    "on-tertiary-container": "#D4E8D5",
    "quaternary": "#D9847C",
    "quaternary-container": "#4A211D",
    "on-quaternary-container": "#F2D2CD",
    "quinary": "#A98FD9",
    "quinary-container": "#322446",
    "on-quinary-container": "#E0D2F2",
    "senary": "#C9B96A",
    "senary-container": "#3A331A",
    "on-senary-container": "#F2E7B7",
    "error": "#D9847C",
    "ember": "#D44A30",
    "background": "#13110E",
    "on-background": "#F2EBDA",
}


STRIPE: Final[dict[str, str]] = {
    "image": C["secondary"],
    "time": C["tertiary"],
    "pixel": C["quaternary"],
    "web_element": C["quinary"],
    "web_url": C["quinary"],
    "hybrid_image": C["primary"],   # brass — the "bridges two worlds" stamp
    "ocr_text": C["senary"],        # khaki — the librarian stamp
    "schedule": C["tertiary"],      # sage — schedule is time-family
}


# ---------------------------------------------------------------------------
# Typography (compact density — every font is one tier smaller than v1)
# ---------------------------------------------------------------------------

FONT_DISPLAY: Final[str] = "Space Grotesk"
# Body / Korean — bundled via ``ui/fonts.py``. Falls through to system
# defaults if the bundled TTFs can't be loaded.
FONT_BODY: Final[str] = (
    "'Noto Sans KR', 'Pretendard Variable', Pretendard, "
    "'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
)
FONT_MONO: Final[str] = "JetBrains Mono, Consolas, monospace"


def font_face(role: str) -> tuple[str, int, int, str]:
    table = {
        "display-lg": (FONT_DISPLAY, 32, 600, "-0.02em"),
        "display-md": (FONT_DISPLAY, 22, 600, "-0.01em"),
        "display-sm": (FONT_DISPLAY, 18, 600, "-0.01em"),
        "headline-lg": (FONT_BODY, 16, 600, "0"),
        "headline-md": (FONT_BODY, 14, 600, "0"),
        "headline-sm": (FONT_BODY, 12, 600, "0"),
        "body-lg": (FONT_BODY, 13, 400, "0"),
        "body-md": (FONT_BODY, 12, 400, "0"),
        "body-sm": (FONT_BODY, 10, 400, "0"),
        "label-lg": (FONT_BODY, 12, 600, "0.02em"),
        "label-md": (FONT_BODY, 11, 600, "0.04em"),
        "label-sm": (FONT_BODY, 9, 700, "0.08em"),
        "data-lg": (FONT_MONO, 14, 500, "0"),
        "data-md": (FONT_MONO, 12, 500, "0"),
        "data-sm": (FONT_MONO, 10, 400, "0"),
    }
    if role not in table:
        raise KeyError(f"unknown typography role: {role!r}")
    return table[role]


R: Final[dict[str, int]] = {
    "sm": 4,
    "default": 6,
    "md": 8,
    "lg": 10,
    "xl": 14,
    "full": 9999,
}

SP: Final[dict[str, int]] = {
    "unit": 4,
    "page-margin": 14,
    "card-padding": 12,
    "card-gap": 8,
    "section-margin": 18,
    "transport-height": 64,
}


# ---------------------------------------------------------------------------
# QSS generator
# ---------------------------------------------------------------------------


def build_qss() -> str:
    return f"""
/* === application chrome ============================================== */

QMainWindow, QWidget {{
    background-color: {C['background']};
    color: {C['on-background']};
    font-family: "Noto Sans KR", "Pretendard Variable", "Apple SD Gothic Neo",
                 "Malgun Gothic", sans-serif;
    font-size: 12px;
}}

QStatusBar {{
    background-color: {C['surface-container-lowest']};
    color: {C['on-surface-variant']};
    border-top: 1px solid {C['outline-variant']};
    font-size: 10px;
    padding: 2px 10px;
}}

QToolTip {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    padding: 4px 8px;
    border-radius: {R['md']}px;
    font-size: 11px;
}}

/* === splitters ======================================================= */

QSplitter::handle {{ background-color: {C['outline-variant']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* === scroll areas ==================================================== */

QScrollArea, QScrollArea > QWidget > QWidget {{
    background-color: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {C['outline-variant']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C['outline']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

/* === labels ========================================================== */

QLabel[role="display-md"] {{
    font-family: "Space Grotesk", "Noto Sans KR", "Pretendard Variable", sans-serif;
    font-size: 22px; font-weight: 600;
    letter-spacing: -0.4px;
    color: {C['on-surface']};
}}
QLabel[role="display-sm"] {{
    font-family: "Space Grotesk", "Noto Sans KR", "Pretendard Variable", sans-serif;
    font-size: 18px; font-weight: 600;
    letter-spacing: -0.3px;
    color: {C['on-surface']};
}}
QLabel[role="headline-md"] {{ font-size: 14px; font-weight: 600; color: {C['on-surface']}; }}
QLabel[role="headline-sm"] {{ font-size: 12px; font-weight: 600; color: {C['on-surface']}; }}
QLabel[role="body-lg"] {{ font-size: 13px; color: {C['on-surface']}; }}
QLabel[role="body-md"] {{ font-size: 12px; color: {C['on-surface-variant']}; }}
QLabel[role="label-md"] {{
    font-size: 11px; font-weight: 600; letter-spacing: 0.4px;
    color: {C['on-surface-variant']};
}}
QLabel[role="label-sm"] {{
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
    color: {C['on-surface-variant']};
}}
QLabel[role="data-md"] {{
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 12px; font-weight: 500;
    color: {C['on-surface']};
}}
QLabel[role="data-sm"] {{
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 10px; color: {C['on-surface-variant']};
}}
QLabel[role="muted"] {{ color: {C['on-surface-variant']}; }}

/* === step card ======================================================= */

QFrame[role="step-card"] {{
    background-color: {C['surface-container']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['lg']}px;
}}
QFrame[role="step-card"]:hover {{
    background-color: {C['surface-container-high']};
    border: 1px solid {C['outline']};
}}
QFrame[role="step-card"][state="active"] {{
    background-color: {C['surface-container-high']};
    border: 1px solid {C['primary']};
}}
QFrame[role="step-card"][state="error"] {{
    border: 1px solid {C['quaternary']};
}}

/* === badges & meta tags ============================================== */

QLabel[badge="image"] {{
    background-color: {C['secondary-container']};
    color: {C['on-secondary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="time"] {{
    background-color: {C['tertiary-container']};
    color: {C['on-tertiary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="pixel"] {{
    background-color: {C['quaternary-container']};
    color: {C['on-quaternary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="web_element"], QLabel[badge="web_url"] {{
    background-color: {C['quinary-container']};
    color: {C['on-quinary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="hybrid_image"] {{
    background-color: {C['primary-container']};
    color: {C['on-primary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="ocr_text"] {{
    background-color: {C['senary-container']};
    color: {C['on-senary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[badge="schedule"] {{
    background-color: {C['tertiary-container']};
    color: {C['on-tertiary-container']};
    border-radius: {R['sm']}px;
    padding: 2px 6px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.8px;
}}
QLabel[role="meta-tag"] {{
    background-color: {C['surface-container-highest']};
    color: {C['on-surface-variant']};
    border-radius: {R['sm']}px;
    padding: 2px 7px;
    font-size: 9px; font-weight: 700; letter-spacing: 0.6px;
}}

/* === buttons ========================================================= */

QPushButton[role="primary"] {{
    background-color: {C['primary']};
    color: {C['on-primary']};
    border: none;
    border-radius: 16px;
    height: 32px;
    padding: 0 16px;
    font-size: 12px; font-weight: 700; letter-spacing: 0.2px;
}}
QPushButton[role="primary"]:hover {{ background-color: {C['primary-fixed-dim']}; }}
QPushButton[role="primary"]:pressed {{
    background-color: {C['primary-container']};
    color: {C['on-primary-container']};
}}
QPushButton[role="primary"]:disabled {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface-variant']};
}}

QPushButton[role="ghost"] {{
    background-color: transparent;
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    border-radius: 14px;
    height: 28px;
    padding: 0 12px;
    font-size: 12px; font-weight: 600;
}}
QPushButton[role="ghost"]:hover {{
    background-color: {C['surface-container-low']};
    border: 1px solid {C['outline']};
}}
QPushButton[role="ghost"]:disabled {{
    color: {C['on-surface-variant']};
}}

/* Chrome status pill — sage when CDP port is listening. */
QPushButton[role="ghost"][state="listening"] {{
    color: {C['tertiary']};
    border-color: {C['tertiary']};
}}

QPushButton[role="danger-ghost"] {{
    background-color: transparent;
    color: {C['error']};
    border: 1px solid {C['outline-variant']};
    border-radius: 12px;
    height: 24px;
    padding: 0 10px;
    font-size: 11px; font-weight: 600;
}}
QPushButton[role="danger-ghost"]:hover {{
    border: 1px solid {C['error']};
    background-color: rgba(217, 132, 124, 0.08);
}}

QPushButton[role="transport-play"] {{
    background-color: {C['primary']};
    color: {C['on-primary']};
    border: none;
    border-radius: 22px;
    min-height: 40px;
    min-width: 110px;
    font-size: 13px; font-weight: 700; letter-spacing: 0.2px;
}}
QPushButton[role="transport-play"]:hover {{
    background-color: {C['primary-fixed-dim']};
}}
QPushButton[role="transport-play"]:disabled {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface-variant']};
}}

QPushButton[role="transport-ghost"] {{
    background-color: transparent;
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    border-radius: 22px;
    min-height: 40px;
    min-width: 86px;
    font-size: 12px; font-weight: 600;
}}
QPushButton[role="transport-ghost"]:hover {{
    background-color: {C['surface-container-low']};
    border: 1px solid {C['outline']};
}}
QPushButton[role="transport-ghost"]:disabled {{
    color: {C['on-surface-variant']};
}}

QPushButton[role="icon-mini"] {{
    background-color: transparent;
    color: {C['on-surface-variant']};
    border: 1px solid transparent;
    border-radius: {R['md']}px;
    padding: 2px 6px;
    font-size: 10px;
}}
QPushButton[role="icon-mini"]:hover {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
}}

/* === type picker tile ================================================ */

QPushButton[role="type-tile"] {{
    background-color: {C['surface-container-low']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['lg']}px;
    padding: 14px;
    text-align: left;
    font-size: 12px;
}}
QPushButton[role="type-tile"]:hover {{
    background-color: {C['surface-container-high']};
    border: 1px solid {C['primary']};
}}

/* === inputs ========================================================== */

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: {C['surface-container-low']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['md']}px;
    padding: 5px 9px;
    selection-background-color: {C['primary']};
    selection-color: {C['on-primary']};
    font-size: 12px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {C['primary']};
}}
QLineEdit:disabled {{ color: {C['on-surface-variant']}; }}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 0; height: 0; border: none;
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox::down-arrow {{
    image: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 4px solid {C['on-surface-variant']};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    selection-background-color: {C['surface-container-highest']};
    selection-color: {C['primary']};
    outline: none;
    font-size: 12px;
}}

QCheckBox {{
    color: {C['on-surface']};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C['outline-variant']};
    border-radius: {R['sm']}px;
    background-color: {C['surface-container-low']};
}}
QCheckBox::indicator:checked {{
    background-color: {C['primary']};
    border: 1px solid {C['primary']};
}}

/* === group boxes ===================================================== */

QGroupBox {{
    background-color: {C['surface-container-low']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['md']}px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
    color: {C['on-surface-variant']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 10px;
}}

/* === transport bar (sticky bottom) =================================== */

QFrame[role="transport-bar"] {{
    background-color: {C['surface-container-lowest']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['lg']}px;
}}
QFrame[role="match-track"] {{
    background-color: {C['surface-container-highest']};
    border-radius: 2px;
    min-height: 4px;
    max-height: 4px;
}}
QFrame[role="match-fill"] {{
    background-color: {C['primary']};
    border-radius: 2px;
}}

/* === status pills ==================================================== */

QFrame[role="status-pill"] {{
    background-color: transparent;
    border: 1px solid {C['outline-variant']};
    border-radius: 11px;
    padding: 3px 9px;
}}
QFrame[role="status-pill"][state="running"] {{
    background-color: rgba(232, 178, 106, 0.10);
    border: 1px solid {C['primary']};
}}
QFrame[role="status-pill"][state="paused"] {{
    background-color: rgba(91, 168, 229, 0.10);
    border: 1px solid {C['secondary']};
}}

/* === empty state rules =============================================== */

QFrame[role="empty-rule"] {{
    background-color: transparent;
    border-top: 1px dashed {C['outline-variant']};
    max-height: 1px;
    min-height: 1px;
}}

/* === log panel ======================================================= */

QTextEdit[role="log"] {{
    background-color: {C['surface-container-lowest']};
    color: {C['on-surface-variant']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['md']}px;
    font-family: "JetBrains Mono", Consolas, monospace;
    font-size: 10px;
    padding: 8px;
}}

/* === menu / dialogs ================================================== */

QMenu {{
    background-color: {C['surface-container-high']};
    color: {C['on-surface']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['md']}px;
    padding: 4px;
}}
QMenu::item {{ padding: 4px 12px; border-radius: {R['sm']}px; font-size: 12px; }}
QMenu::item:selected {{
    background-color: {C['surface-container-highest']};
    color: {C['primary']};
}}

QDialog {{ background-color: {C['surface-container']}; }}

QMessageBox {{
    background-color: {C['surface-container']};
    color: {C['on-surface']};
}}
QMessageBox QLabel {{ color: {C['on-surface']}; font-size: 12px; }}

/* === form layout label cells ========================================= */

QFormLayout QLabel {{
    color: {C['on-surface-variant']};
    font-size: 11px;
    font-weight: 600;
}}

/* === toasts (top-right floating notifications) ======================= */

QWidget[role="toast"] {{
    background-color: {C['surface-container-high']};
    border: 1px solid {C['outline-variant']};
    border-radius: {R['md']}px;
}}
QWidget[role="toast"][kind="success"] {{
    border-left: 3px solid {C['tertiary']};
}}
QWidget[role="toast"][kind="info"] {{
    border-left: 3px solid {C['secondary']};
}}
QWidget[role="toast"][kind="warning"] {{
    border-left: 3px solid {C['primary']};
}}
QWidget[role="toast"][kind="error"] {{
    border-left: 3px solid {C['quaternary']};
}}
QWidget[role="toast"] QPushButton#toastClose {{
    color: {C['on-surface-variant']};
    background-color: transparent;
    border: none;
    font-size: 14px;
    font-weight: 700;
}}
QWidget[role="toast"] QPushButton#toastClose:hover {{
    color: {C['on-surface']};
    background-color: {C['surface-container-highest']};
    border-radius: {R['sm']}px;
}}
"""


def apply_theme(widget) -> None:
    widget.setStyleSheet(build_qss())
