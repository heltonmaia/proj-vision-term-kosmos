"""Interactive menu loop for VisionTerminal.

Running the CLI with no subcommand enters this loop: show the Rich menu,
prompt for a choice, collect the arguments interactively, dispatch to
`processor`, then ask whether to keep going. Exits only when the user
picks "q" or declines to return to the menu.
"""

from __future__ import annotations

import glob
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

from rich.prompt import Confirm, Prompt

from . import cli_ui, processor
from .processor import ProcessorError

try:
    import readline  # type: ignore[import-not-found]
    _HAS_READLINE = True
except ImportError:  # pragma: no cover - Windows without pyreadline
    _HAS_READLINE = False


# ---------------------------------------------------------------------------
# TAB completion for filesystem paths (readline)
# ---------------------------------------------------------------------------
def _path_completer(text: str, state: int) -> str | None:
    """readline completer that expands filesystem paths like a shell."""
    expanded = os.path.expanduser(text) if text else ""
    matches = sorted(glob.glob(expanded + "*"))
    # Append "/" to directories so the user can keep tabbing deeper.
    results = [m + "/" if os.path.isdir(m) else m for m in matches]

    # Preserve the leading "~" the user typed, if any.
    if text.startswith("~"):
        home = os.path.expanduser("~")
        results = [
            ("~" + r[len(home):]) if r.startswith(home) else r
            for r in results
        ]
    try:
        return results[state]
    except IndexError:
        return None


@contextmanager
def _path_completion() -> Iterator[None]:
    """Temporarily enable TAB path completion for the current prompt."""
    if not _HAS_READLINE:
        yield
        return
    old_completer = readline.get_completer()
    old_delims = readline.get_completer_delims()
    readline.set_completer(_path_completer)
    # Keep "/", ".", "-", "_" etc. as part of the word being completed.
    readline.set_completer_delims(" \t\n;")
    # macOS ships libedit (BSD) under the `readline` name; the bind syntax differs.
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    try:
        yield
    finally:
        readline.set_completer(old_completer)
        readline.set_completer_delims(old_delims)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------
def _ask_path(label: str, must_exist: bool = True) -> Path:
    """Prompt for a filesystem path with TAB completion; re-ask on failure."""
    while True:
        with _path_completion():
            raw = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]{label}[/]")
        raw = raw.strip().strip('"').strip("'")
        if not raw:
            cli_ui.error("Path cannot be empty.")
            continue
        path = Path(raw).expanduser()
        if must_exist and not path.exists():
            cli_ui.error(f"Path not found: {path}")
            continue
        return path


def _ask_out_path(label: str, default: Path) -> Path:
    """Prompt for an output path (may not exist yet) with TAB completion."""
    with _path_completion():
        raw = Prompt.ask(
            f"[bold {cli_ui.BRAND_COLOR}]{label}[/]", default=str(default)
        )
    return Path(raw.strip().strip('"').strip("'")).expanduser()


def _ask_int(label: str, default: int) -> int:
    while True:
        raw = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]{label}[/]", default=str(default))
        try:
            return int(raw)
        except ValueError:
            cli_ui.error("Please enter an integer.")


# ---------------------------------------------------------------------------
# Per-command flows
# ---------------------------------------------------------------------------
def _flow_cut() -> None:
    src = _ask_path("Input video")
    start = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]Start time[/] (HH:MM:SS, MM:SS, or seconds)")
    end = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]End time[/]")
    default_out = src.with_name(f"{src.stem}_cut{src.suffix}")
    dst = _ask_out_path("Output file", default_out)
    with cli_ui.make_progress() as progress:
        task = progress.add_task(f"Cutting {src.name}", total=1)
        processor.cut_video(src, dst, start=start, end=end)
        progress.advance(task)
    cli_ui.success(f"Trim saved to: [bold]{dst}[/]")


def _flow_convert() -> None:
    src = _ask_path("Input file")
    default_out = src.with_suffix(".webp") if src.suffix.lower() in processor.IMAGE_EXTS else src.with_suffix(".mp4")
    dst = _ask_out_path("Output file (extension picks the format)", default_out)
    quality = _ask_int("Quality (1-100, images only)", default=92)
    with cli_ui.make_progress() as progress:
        task = progress.add_task(f"Converting {src.name} → {dst.suffix}", total=1)
        processor.convert_any(src, dst, quality=quality)
        progress.advance(task)
    cli_ui.success(f"Saved to: [bold]{dst}[/]")


def _flow_wa_fix() -> None:
    src = _ask_path("Input video")
    default_out = src.with_name(f"{src.stem}_wa.mp4")
    dst = _ask_out_path("Output file", default_out)
    max_h = _ask_int("Max height (px)", default=720)
    bitrate = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]Video bitrate[/]", default="1500k")
    with cli_ui.make_progress() as progress:
        task = progress.add_task(f"WhatsApp-fix {src.name}", total=1)
        processor.wa_fix(src, dst, max_height=max_h, video_bitrate=bitrate)
        progress.advance(task)
    cli_ui.success(f"WhatsApp-ready: [bold]{dst}[/]")


def _flow_batch() -> None:
    folder = _ask_path("Folder to process")
    op = Prompt.ask(
        f"[bold {cli_ui.BRAND_COLOR}]Operation[/]",
        choices=["convert", "resize"],
        default="convert",
    )
    target_ext: str | None = None
    max_side: int | None = None
    if op == "convert":
        ext = Prompt.ask(f"[bold {cli_ui.BRAND_COLOR}]Target extension[/] (e.g. .webp, .mp4)")
        target_ext = ext if ext.startswith(".") else f".{ext}"
    else:
        max_side = _ask_int("Longest side (px)", default=1280)
    out_folder = _ask_out_path("Output folder", folder / "_out")

    files = processor.list_media(
        folder,
        kinds=("image",) if op == "resize" else ("image", "video"),
    )
    if not files:
        cli_ui.error(f"No media files found in: {folder}")
        return
    cli_ui.info(f"{len(files)} file(s) → {out_folder}")
    with cli_ui.make_progress() as progress:
        task = progress.add_task(f"Batch {op}", total=len(files))

        def _tick(_: Path) -> None:
            progress.advance(task)

        processor.batch_apply(
            folder,
            out_folder,
            operation=op,
            target_ext=target_ext,
            max_side=max_side,
            progress_cb=_tick,
        )
    cli_ui.success(f"Batch complete in: [bold]{out_folder}[/]")


def _flow_info() -> None:
    src = _ask_path("Video to inspect")
    m = processor.probe_video(src)
    cli_ui.console.print(
        cli_ui.media_info_panel(m.width, m.height, m.fps, m.duration_seconds, m.path)
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
_ACTIONS: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("cut", _flow_cut),
    "2": ("convert", _flow_convert),
    "3": ("wa-fix", _flow_wa_fix),
    "4": ("batch", _flow_batch),
    "5": ("info", _flow_info),
}


def loop() -> None:
    """Render the menu in a loop until the user decides to quit."""
    first = True
    while True:
        if first:
            first = False
        else:
            cli_ui.console.rule(style=cli_ui.ACCENT_COLOR)
        cli_ui.render_menu()
        choice = Prompt.ask(
            f"\n[bold {cli_ui.ACCENT_COLOR}]Choose an option[/] "
            "[dim](1=cut, 2=convert, 3=wa-fix, 4=batch, 5=info, q=quit)[/]",
            choices=["1", "2", "3", "4", "5", "q"],
            default="q",
            show_choices=False,
        )
        if choice == "q":
            cli_ui.console.print(f"[bold {cli_ui.BRAND_COLOR}]Goodbye![/]")
            return

        _name, fn = _ACTIONS[choice]
        try:
            fn()
        except ProcessorError as err:
            cli_ui.error(str(err))
        except KeyboardInterrupt:
            cli_ui.console.print("\n[yellow]Cancelled.[/]")

        if not Confirm.ask(
            f"\n[bold {cli_ui.BRAND_COLOR}]Back to menu?[/]", default=True
        ):
            cli_ui.console.print(f"[bold {cli_ui.BRAND_COLOR}]Goodbye![/]")
            return
