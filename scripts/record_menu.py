"""Render the Vision Terminal Kosmos main menu to an SVG for documentation.

Run with:
    uv run --no-project --with rich --with pyfiglet python scripts/record_menu.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from rich.align import Align
from rich.console import Console
from rich.text import Text

from vtermkosmos import cli_ui


_STYLES = {
    "cursor": "reverse bold",
    "virtual": f"italic magenta",
    "dir": "bold cyan",
    "file": "",
}


def main() -> None:
    console = Console(
        record=True,
        width=100,
        force_terminal=True,
        color_system="truecolor",
        highlight=False,
    )

    # Banner: pyfiglet art + subtitle, centered (matches the prompt_toolkit browser).
    console.print(Align.center(Text(cli_ui.BANNER_ART, style=f"bold {cli_ui.BRAND_COLOR}")))
    console.print(Align.center(Text(cli_ui.BANNER_SUBTITLE, style="italic white")))

    console.rule(style=cli_ui.ACCENT_COLOR)
    console.print(Text(" /home/heltonmaia/Videos/Kooha", style=f"bold {cli_ui.BRAND_COLOR}"))
    console.rule(style=cli_ui.ACCENT_COLOR)

    entries: list[tuple[str, str]] = [
        ("virtual", "[use this folder]"),
        ("virtual", ".. (parent)"),
        ("file", "2AF11_OF_low_1min_tracked.webm"),
        ("file", "analises.mp4"),
        ("file", "analises.webm"),
        ("file", "bot_test.webm"),
        ("file", "Kooha-2025-02-27-10-29-51.webm"),
        ("cursor", "Kooha-2025-02-27-10-30-24.webm"),
        ("file", "Kooha-2025-02-27-10-31-32.webm"),
        ("file", "Kooha-2025-02-27-10-31-42.webm"),
        ("file", "Kooha-2025-04-27-18-29-04.webm"),
        ("dir", "reference/"),
    ]
    for kind, name in entries:
        prefix = "▶ " if kind == "cursor" else "  "
        console.print(Text(prefix + name, style=_STYLES[kind]))

    console.rule(style=cli_ui.ACCENT_COLOR)
    console.print(
        Text(
            " ↑/↓ move   ↵ open/select   ← parent   →/space descend   / type path   q quit",
            style="dim",
        )
    )

    out = ROOT / "assets" / "menu.svg"
    out.parent.mkdir(exist_ok=True)
    console.save_svg(str(out), title="Vision Terminal Kosmos")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
