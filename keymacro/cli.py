"""Command-line entrypoint for keymacro.

Subcommands:

* ``run`` — execute a macro inline; useful for scripts and CI.
* ``watch`` — bind global hotkeys (F9/F10/F11) and run on demand.
* ``gui`` — launch the PySide6 editor.
* ``validate`` — type-check a macro YAML without running it.
* ``export`` / ``import`` — pack/unpack a ``.kma`` archive.

DPI awareness is set on Windows before any capture/click happens so
screen coordinates match between OpenCV and the OS.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Optional

from .core.control import RunControl
from .core.logger import setup_logging
from .core.runner import RunResult, Runner
from .storage.yaml_repo import load_macro
from .storage.zip_archive import export_macro, import_macro

log = logging.getLogger(__name__)


def _setup_dpi_awareness() -> None:
    """Make the process per-monitor DPI aware on Windows. No-op elsewhere."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="keymacro")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help="if set, write per-run log files under this directory",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="run a macro")
    run_p.add_argument("macro", help="path to macro YAML")
    run_p.add_argument(
        "--debug-capture-dir",
        type=Path,
        default=None,
        help="when a step fails, dump the captured region here as a PNG",
    )
    run_p.add_argument(
        "--browser-mode",
        choices=["attach", "launch"],
        default=None,
        help="override macro's web_session.mode for this run",
    )
    run_p.add_argument(
        "--cdp-endpoint",
        default=None,
        help="override CDP endpoint (default: http://localhost:9222)",
    )

    watch_p = sub.add_parser(
        "watch",
        help="bind global hotkeys and run on demand (F9 start / F10 stop / F11 pause)",
    )
    watch_p.add_argument("macro")
    watch_p.add_argument("--debug-capture-dir", type=Path, default=None)
    watch_p.add_argument("--browser-mode", choices=["attach", "launch"], default=None)
    watch_p.add_argument("--cdp-endpoint", default=None)

    gui_p = sub.add_parser("gui", help="launch the PySide6 editor")
    gui_p.add_argument("macro", nargs="?", help="optional macro to preload")
    gui_p.add_argument("--debug-capture-dir", type=Path, default=None)

    chrome_p = sub.add_parser(
        "chrome-launch",
        help="launch Chrome with --remote-debugging-port for attach-mode macros",
    )
    chrome_p.add_argument(
        "--port", type=int, default=9222,
        help="remote debugging port (default: 9222)",
    )
    chrome_p.add_argument(
        "--user-data-dir",
        default=None,
        help="custom Chrome profile dir (default: a keymacro-managed profile)",
    )

    val_p = sub.add_parser("validate", help="validate a macro YAML")
    val_p.add_argument("macro")

    exp_p = sub.add_parser("export", help="pack a macro and its templates into .kma")
    exp_p.add_argument("macro")
    exp_p.add_argument("archive")

    imp_p = sub.add_parser("import", help="unpack a .kma archive")
    imp_p.add_argument("archive")
    imp_p.add_argument("dest")

    return p


def _format_run_summary(result: RunResult) -> str:
    lines = [f"macro: {result.macro_name}"]
    for sr in result.step_results:
        flag = "OK" if sr.success else "FAIL"
        extra = f" err={sr.error}" if sr.error else ""
        lines.append(
            f"  [{flag}] {sr.step_id} attempts={sr.attempts} "
            f"iters={sr.iterations_completed} duration={sr.duration_s:.2f}s{extra}"
        )
    if result.completed:
        lines.append("status: completed")
    else:
        lines.append(f"status: aborted at {result.aborted_at}")
    return "\n".join(lines)


def _run_macro(
    macro_path: Path,
    *,
    control: Optional[RunControl] = None,
    debug_capture_dir: Optional[Path] = None,
    browser_mode: Optional[str] = None,
    cdp_endpoint: Optional[str] = None,
) -> RunResult:
    macro = load_macro(macro_path)
    if browser_mode or cdp_endpoint:
        from .models.web import WebSessionConfig
        cfg = macro.web_session or WebSessionConfig()
        if browser_mode:
            cfg = cfg.model_copy(update={"mode": browser_mode})
        if cdp_endpoint:
            cfg = cfg.model_copy(update={"cdp_endpoint": cdp_endpoint})
        macro = macro.model_copy(update={"web_session": cfg})
    runner = Runner(
        macro,
        macro_dir=macro_path.parent,
        control=control,
        debug_capture_dir=debug_capture_dir,
    )
    return runner.run()


def _cmd_run(args: argparse.Namespace) -> int:
    _setup_dpi_awareness()
    macro_path = Path(args.macro)
    if not macro_path.exists():
        print(f"macro file not found: {macro_path}", file=sys.stderr)
        return 2
    try:
        result = _run_macro(
            macro_path,
            debug_capture_dir=args.debug_capture_dir,
            browser_mode=getattr(args, "browser_mode", None),
            cdp_endpoint=getattr(args, "cdp_endpoint", None),
        )
    except Exception as e:
        print(f"실행 실패:\n{e}", file=sys.stderr)
        return 1
    print(_format_run_summary(result))
    return 0 if result.completed else 1


def _cmd_watch(args: argparse.Namespace) -> int:
    _setup_dpi_awareness()
    macro_path = Path(args.macro)
    if not macro_path.exists():
        print(f"macro file not found: {macro_path}", file=sys.stderr)
        return 2

    from .hotkey.manager import HotkeyManager

    control = RunControl()
    runner_done = threading.Event()
    quit_flag = threading.Event()

    def _start():
        if not runner_done.is_set():
            print("(already running — press F10 to stop first)")
            return
        control.reset()
        runner_done.clear()
        threading.Thread(target=_run_one, daemon=True).start()

    def _run_one():
        try:
            result = _run_macro(
                macro_path,
                control=control,
                debug_capture_dir=args.debug_capture_dir,
                browser_mode=getattr(args, "browser_mode", None),
                cdp_endpoint=getattr(args, "cdp_endpoint", None),
            )
            print(_format_run_summary(result))
        except Exception as e:
            print(f"실행 실패:\n{e}", file=sys.stderr)
        finally:
            runner_done.set()

    def _stop():
        if runner_done.is_set():
            quit_flag.set()
            return
        control.stop()

    def _pause():
        paused = control.toggle_pause()
        print("(paused)" if paused else "(resumed)")

    runner_done.set()  # nothing running yet
    hk = HotkeyManager(on_start=_start, on_stop=_stop, on_pause=_pause)
    hk.start()
    print(
        "watching: F9 start  /  F10 stop (or quit if idle)  /  F11 pause-resume\n"
        f"macro: {macro_path}"
    )
    try:
        while not quit_flag.is_set():
            quit_flag.wait(0.5)
    finally:
        control.stop()
        hk.stop()
    return 0


def _cmd_gui(args: argparse.Namespace) -> int:
    _setup_dpi_awareness()
    from .ui.app import run_gui

    initial = Path(args.macro) if getattr(args, "macro", None) else None
    return run_gui(initial_macro=initial, debug_capture_dir=args.debug_capture_dir)


def _cmd_validate(args: argparse.Namespace) -> int:
    macro_path = Path(args.macro)
    if not macro_path.exists():
        print(f"macro file not found: {macro_path}", file=sys.stderr)
        return 2
    load_macro(macro_path)
    print(f"OK: {macro_path} is a valid macro")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    macro_path = Path(args.macro)
    macro = load_macro(macro_path)
    out = export_macro(macro, macro_path.parent, args.archive)
    print(f"exported -> {out}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    macro, yaml_path = import_macro(args.archive, args.dest)
    print(f"imported {macro.name} -> {yaml_path}")
    return 0


def _cmd_chrome_launch(args: argparse.Namespace) -> int:
    """Launch Chrome with --remote-debugging-port for attach-mode macros."""
    from .core.chrome_launcher import ensure_chrome_running

    udd = Path(args.user_data_dir) if args.user_data_dir else None
    ok, msg = ensure_chrome_running(port=args.port, user_data_dir=udd)
    print(msg)
    return 0 if ok else 2


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    setup_logging(
        verbose=args.verbose,
        log_dir=args.log_dir,
    )

    handlers = {
        "run": _cmd_run,
        "watch": _cmd_watch,
        "gui": _cmd_gui,
        "validate": _cmd_validate,
        "export": _cmd_export,
        "import": _cmd_import,
        "chrome-launch": _cmd_chrome_launch,
    }
    handler = handlers.get(args.cmd)
    if handler is None:
        parser.print_help()
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
