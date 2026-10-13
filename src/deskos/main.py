from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from deskos.app import DeskOSApplication  # noqa: E402


def main() -> int:
    Gtk.init()
    if Gdk.Display.get_default() is None:
        print(
            "DeskOS requires an active graphical session (X11 or Wayland).",
            file=sys.stderr,
        )
        return 2
    return int(DeskOSApplication().run(sys.argv))


if __name__ == "__main__":
    raise SystemExit(main())
