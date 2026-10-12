"""Native (Tk) dialogs: browser picker, install prompt, instructions, status window."""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable, Sequence
from pathlib import Path
from tkinter import ttk
from typing import Literal

from usisain_launcher.browsers import Browser
from usisain_launcher.settings import APP_NAME

InstallChoice = Literal["add", "later", "never"]

BG = "#0b1220"
CARD = "#111a2e"
BORDER = "#1e2a46"
TEXT = "#e6edf7"
MUTED = "#93a3bd"
ACCENT = "#22d3ee"
ACCENT_HOVER = "#67e8f9"
ACCENT_TEXT = "#04202a"
GHOST_HOVER = "#1b2742"
OK = "#34d399"
WARN = "#fbbf24"
ERR = "#f87171"

if sys.platform == "darwin":
    FONT_FAMILY = "Helvetica Neue"
elif sys.platform == "win32":
    FONT_FAMILY = "Segoe UI"
else:
    FONT_FAMILY = "DejaVu Sans"

F_TITLE = (FONT_FAMILY, 15, "bold")
F_BODY = (FONT_FAMILY, 10)
F_SMALL = (FONT_FAMILY, 9)
F_BTN = (FONT_FAMILY, 10, "bold")

_images: dict[str, tk.PhotoImage] = {}


def init(root: tk.Tk, assets: Path) -> None:
    """Apply the window icon and ttk theme once."""
    root.configure(bg=BG)
    for size in (256, 128, 64, 32):
        path = assets / f"icon-{size}.png"
        if path.exists():
            try:
                _images[str(size)] = tk.PhotoImage(file=str(path))
            except tk.TclError:
                continue
    icons = [_images[k] for k in ("256", "128", "64", "32") if k in _images]
    if icons:
        root.iconphoto(True, *icons)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(
        "Usis.Horizontal.TProgressbar",
        troughcolor=CARD,
        background=ACCENT,
        bordercolor=CARD,
        lightcolor=ACCENT,
        darkcolor=ACCENT,
    )


def _logo(size: int) -> tk.PhotoImage | None:
    """Return a cached logo scaled down from the 128px asset by an integer factor."""
    key = f"logo-{size}"
    if key in _images:
        return _images[key]
    base = _images.get("128")
    if base is None:
        return None
    factor = max(1, 128 // size)
    _images[key] = base.subsample(factor, factor)
    return _images[key]


class FlatButton(tk.Label):
    """A Label-based button so colours render identically on Windows and macOS."""

    def __init__(
        self,
        master: tk.Misc,
        text: str,
        command: Callable[[], None],
        kind: Literal["primary", "ghost", "link"] = "ghost",
    ) -> None:
        palette = {
            "primary": (ACCENT, ACCENT_TEXT, ACCENT_HOVER),
            "ghost": (CARD, TEXT, GHOST_HOVER),
            "link": (BG, MUTED, BG),
        }[kind]
        self._bg, fg, self._hover = palette
        super().__init__(
            master,
            text=text,
            bg=self._bg,
            fg=fg,
            font=F_BTN if kind != "link" else F_SMALL,
            padx=16 if kind != "link" else 4,
            pady=8 if kind != "link" else 4,
            cursor="hand2",
            takefocus=True,
            highlightthickness=1 if kind == "ghost" else 0,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        self._command = command
        self._kind = kind
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", lambda _e: self._command())
        self.bind("<Return>", lambda _e: self._command())
        self.bind("<space>", lambda _e: self._command())

    def _on_enter(self, _e: object) -> None:
        self.configure(bg=self._hover)
        if self._kind == "link":
            self.configure(fg=TEXT)

    def _on_leave(self, _e: object) -> None:
        self.configure(bg=self._bg)
        if self._kind == "link":
            self.configure(fg=MUTED)

    def set_enabled(self, enabled: bool) -> None:
        self.configure(fg=(ACCENT_TEXT if self._kind == "primary" else TEXT) if enabled else MUTED)
        self.bind("<Button-1>", (lambda _e: self._command()) if enabled else (lambda _e: None))


def _center(win: tk.Toplevel | tk.Tk) -> None:
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = (win.winfo_screenwidth() - w) // 2
    y = (win.winfo_screenheight() - h) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def _modal(root: tk.Tk, title: str) -> tk.Toplevel:
    win = tk.Toplevel(root, bg=BG)
    win.title(title)
    win.resizable(False, False)
    win.attributes("-topmost", True)
    win.after(400, lambda: win.attributes("-topmost", False))
    return win


def _show_modal(win: tk.Toplevel) -> None:
    _center(win)
    win.lift()
    win.focus_force()
    try:
        win.grab_set()
    except tk.TclError:
        pass
    win.wait_window()


def _header(parent: tk.Misc, title: str, subtitle: str = "") -> None:
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", padx=24, pady=(22, 8))
    logo = _logo(64)
    if logo is not None:
        tk.Label(row, image=logo, bg=BG).pack(side="left", padx=(0, 14))
    text = tk.Frame(row, bg=BG)
    text.pack(side="left", fill="x", expand=True)
    tk.Label(
        text, text=title, bg=BG, fg=TEXT, font=F_TITLE, anchor="w", justify="left", wraplength=380
    ).pack(fill="x")
    if subtitle:
        tk.Label(
            text,
            text=subtitle,
            bg=BG,
            fg=MUTED,
            font=F_BODY,
            anchor="w",
            justify="left",
            wraplength=380,
        ).pack(fill="x", pady=(4, 0))


def _button_row(parent: tk.Misc) -> tk.Frame:
    row = tk.Frame(parent, bg=BG)
    row.pack(fill="x", padx=24, pady=(14, 22))
    return row


# --------------------------------------------------------------------------- dialogs


def choose_browser(
    root: tk.Tk, browsers: Sequence[Browser], preselect: Browser | None, default: Browser | None
) -> Browser | None:
    win = _modal(root, f"{APP_NAME} - Choose a browser")
    _header(
        win,
        "Which browser should UsisAIn use?",
        "Several browsers are open. Pick the one to add the extension to.",
    )
    selected = tk.StringVar(value=(preselect or browsers[0]).key)
    result: dict[str, Browser | None] = {"value": None}
    rows: list[tuple[tk.Frame, tk.Label, Browser]] = []

    def refresh() -> None:
        for frame, dot, b in rows:
            active = selected.get() == b.key
            frame.configure(highlightbackground=ACCENT if active else BORDER)
            dot.configure(text="\u25cf" if active else "\u25cb", fg=ACCENT if active else MUTED)

    listbox = tk.Frame(win, bg=BG)
    listbox.pack(fill="x", padx=24, pady=(6, 0))
    for b in browsers:
        frame = tk.Frame(
            listbox, bg=CARD, highlightthickness=1, highlightbackground=BORDER, cursor="hand2"
        )
        frame.pack(fill="x", pady=4)
        dot = tk.Label(frame, bg=CARD, font=(FONT_FAMILY, 13), padx=12)
        dot.pack(side="left")
        name = tk.Label(frame, text=b.name, bg=CARD, fg=TEXT, font=F_BTN, pady=10, anchor="w")
        name.pack(side="left", fill="x", expand=True)
        widgets: list[tk.Misc] = [frame, dot, name]
        if default is not None and b.key == default.key:
            badge = tk.Label(frame, text="DEFAULT", bg=CARD, fg=ACCENT, font=F_SMALL, padx=12)
            badge.pack(side="right")
            widgets.append(badge)
        for w in widgets:
            w.bind("<Button-1>", lambda _e, k=b.key: (selected.set(k), refresh()))
            w.bind("<Double-Button-1>", lambda _e, k=b.key: (selected.set(k), confirm()))
        rows.append((frame, dot, b))

    def confirm() -> None:
        result["value"] = next((b for b in browsers if b.key == selected.get()), None)
        win.destroy()

    buttons = _button_row(win)
    FlatButton(buttons, "Continue", confirm, "primary").pack(side="right")
    FlatButton(buttons, "Cancel", win.destroy).pack(side="right", padx=(0, 8))
    win.bind("<Return>", lambda _e: confirm())
    win.bind("<Escape>", lambda _e: win.destroy())
    refresh()
    _show_modal(win)
    return result["value"]


def ask_install(root: tk.Tk, browser: Browser) -> InstallChoice:
    win = _modal(root, f"{APP_NAME} - Browser extension")
    _header(
        win,
        f"Add the {APP_NAME} extension to {browser.name}?",
        "Right-click any text, image, or video, or use the snipping tool, to check it "
        "for scams and misinformation without leaving the page.",
    )
    result: dict[str, InstallChoice] = {"value": "later"}

    def pick(choice: InstallChoice) -> None:
        result["value"] = choice
        win.destroy()

    buttons = _button_row(win)
    FlatButton(buttons, "Don't ask again", lambda: pick("never"), "link").pack(side="left")
    FlatButton(buttons, "Add", lambda: pick("add"), "primary").pack(side="right")
    FlatButton(buttons, "Not now", lambda: pick("later")).pack(side="right", padx=(0, 8))
    win.bind("<Return>", lambda _e: pick("add"))
    win.bind("<Escape>", lambda _e: pick("later"))
    win.protocol("WM_DELETE_WINDOW", lambda: pick("later"))
    _show_modal(win)
    return result["value"]


def show_instructions(
    root: tk.Tk,
    title: str,
    steps: Sequence[str],
    copy_text: str | None = None,
    note: str | None = None,
    on_retry: Callable[[], None] | None = None,
    check_installed: Callable[[], bool] | None = None,
) -> bool:
    win = _modal(root, f"{APP_NAME} - Install steps")
    _header(win, title)
    card = tk.Frame(win, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="x", padx=24, pady=(6, 0))
    for i, step in enumerate(steps, start=1):
        row = tk.Frame(card, bg=CARD)
        row.pack(fill="x", padx=14, pady=(10 if i == 1 else 4, 4))
        tk.Label(row, text=f"{i}", bg=ACCENT, fg=ACCENT_TEXT, font=F_SMALL, width=2).pack(
            side="left", anchor="n", pady=2
        )
        tk.Label(
            row,
            text=step,
            bg=CARD,
            fg=TEXT,
            font=F_BODY,
            justify="left",
            anchor="w",
            wraplength=400,
        ).pack(side="left", fill="x", padx=(10, 0))
    tk.Frame(card, bg=CARD, height=8).pack()

    note_label = tk.Label(
        win,
        text=note or "",
        bg=BG,
        fg=WARN,
        font=F_SMALL,
        justify="left",
        anchor="w",
        wraplength=440,
    )
    if note:
        note_label.pack(fill="x", padx=24, pady=(10, 0))

    buttons = _button_row(win)
    FlatButton(buttons, "Done", win.destroy, "primary").pack(side="right")
    if copy_text:
        status = tk.Label(buttons, text="", bg=BG, fg=OK, font=F_SMALL)

        def copy() -> None:
            copy_to_clipboard(root, copy_text)
            status.configure(text="Copied!")

        FlatButton(buttons, "Copy path", copy).pack(side="right", padx=(0, 8))
        status.pack(side="left")
    if on_retry is not None:
        FlatButton(buttons, "Open again", on_retry).pack(side="right", padx=(0, 8))

    detected = {"value": False}

    def poll_installed() -> None:
        if not win.winfo_exists():
            return
        try:
            if check_installed and check_installed():
                detected["value"] = True
                note_label.configure(
                    text="✓ Extension detected! Redirecting to Dashboard...",
                    fg=OK,
                    font=F_BTN,
                )
                note_label.pack(fill="x", padx=24, pady=(10, 0))
                win.after(1000, win.destroy)
                return
        except Exception:
            pass
        win.after(800, poll_installed)

    if check_installed is not None:
        win.after(800, poll_installed)

    win.bind("<Escape>", lambda _e: win.destroy())
    _show_modal(win)
    return detected["value"]


def show_error(root: tk.Tk, title: str, message: str) -> None:
    win = _modal(root, f"{APP_NAME} - Problem")
    _header(win, title, message)
    buttons = _button_row(win)
    FlatButton(buttons, "OK", win.destroy, "primary").pack(side="right")
    win.bind("<Return>", lambda _e: win.destroy())
    win.bind("<Escape>", lambda _e: win.destroy())
    _show_modal(win)


def prompt_change_port(
    root: tk.Tk, current_port: int, is_port_in_use: Callable[[int], bool] | None = None
) -> int | None:
    win = _modal(root, f"{APP_NAME} - Change Server Port")
    _header(
        win,
        "Change Server Port",
        "Enter a port number (1024 - 65535). UsisAIn will automatically restart on the new port.",
    )

    result: dict[str, int | None] = {"value": None}

    container = tk.Frame(win, bg=BG)
    container.pack(fill="x", padx=24, pady=(6, 0))

    lbl = tk.Label(
        container,
        text="Port number (1024 - 65535):",
        bg=BG,
        fg=TEXT,
        font=F_BTN,
        anchor="w",
    )
    lbl.pack(fill="x", pady=(0, 6))

    entry_frame = tk.Frame(
        container,
        bg=CARD,
        highlightthickness=1,
        highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    entry_frame.pack(fill="x")

    entry = tk.Entry(
        entry_frame,
        bg=CARD,
        fg=TEXT,
        insertbackground=TEXT,
        font=(FONT_FAMILY, 11, "bold"),
        relief="flat",
        bd=0,
    )
    entry.pack(fill="x", padx=10, pady=8)
    entry.insert(0, str(current_port))
    entry.focus_set()
    entry.select_range(0, tk.END)

    error_label = tk.Label(
        container,
        text="",
        bg=BG,
        fg=ERR,
        font=F_SMALL,
        anchor="w",
        justify="left",
        wraplength=380,
    )
    error_label.pack(fill="x", pady=(8, 0))

    def on_apply() -> None:
        raw_val = entry.get().strip()
        try:
            val = int(raw_val)
        except ValueError:
            error_label.configure(text="Please enter a valid numeric port number.")
            return

        if not (1024 <= val <= 65535):
            error_label.configure(text="Port must be between 1024 and 65535.")
            return

        if val == current_port:
            win.destroy()
            return

        if is_port_in_use is not None and is_port_in_use(val):
            error_label.configure(
                text=f"Port {val} is already in use by another application. Pick a different port."
            )
            return

        result["value"] = val
        win.destroy()

    buttons = _button_row(win)
    FlatButton(buttons, "Apply & Restart", on_apply, "primary").pack(side="right")
    FlatButton(buttons, "Cancel", win.destroy).pack(side="right", padx=(0, 8))

    win.bind("<Return>", lambda _e: on_apply())
    win.bind("<Escape>", lambda _e: win.destroy())

    _show_modal(win)
    return result["value"]


def copy_to_clipboard(root: tk.Tk, text: str) -> None:
    try:
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    except tk.TclError:
        pass


# --------------------------------------------------------------------------- status window


class StatusWindow:
    """Small always-available control window while the backend runs."""

    def __init__(
        self,
        root: tk.Tk,
        on_open_app: Callable[[], None],
        on_open_dashboard: Callable[[], None],
        on_add_extension: Callable[[], None],
        on_open_logs: Callable[[], None],
        on_quit: Callable[[], None],
        on_change_port: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self._on_change_port = on_change_port
        root.title(APP_NAME)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", on_quit)

        _header(root, APP_NAME, "Trust, fraud and misinformation checks, running on this computer.")

        card = tk.Frame(root, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=24, pady=(6, 0))
        line = tk.Frame(card, bg=CARD)
        line.pack(fill="x", padx=14, pady=(12, 6))
        self._dot = tk.Label(line, text="\u25cf", bg=CARD, fg=WARN, font=(FONT_FAMILY, 12))
        self._dot.pack(side="left")
        self._status = tk.Label(line, text="Starting...", bg=CARD, fg=TEXT, font=F_BTN, anchor="w")
        self._status.pack(side="left", padx=(8, 0))

        if on_change_port is not None:
            self.btn_port = FlatButton(line, "Change port...", on_change_port, "link")
            self.btn_port.pack(side="right")
        else:
            self.btn_port = None

        self._detail = tk.Label(
            card,
            text="",
            bg=CARD,
            fg=MUTED,
            font=F_SMALL,
            anchor="w",
            justify="left",
            wraplength=420,
        )
        self._detail.pack(fill="x", padx=14)
        self._bar = ttk.Progressbar(
            card, mode="indeterminate", length=420, style="Usis.Horizontal.TProgressbar"
        )
        self._bar.pack(fill="x", padx=14, pady=(8, 14))
        self._bar.start(12)

        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", padx=24, pady=(14, 0))
        self.btn_app = FlatButton(grid, "Open Web App", on_open_app, "primary")
        self.btn_app.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        self.btn_dash = FlatButton(grid, "Dashboard", on_open_dashboard)
        self.btn_dash.grid(row=0, column=1, sticky="ew", padx=(6, 0), pady=4)
        FlatButton(grid, "Add browser extension...", on_add_extension).grid(
            row=1, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        FlatButton(grid, "Open logs", on_open_logs).grid(
            row=1, column=1, sticky="ew", padx=(6, 0), pady=4
        )
        grid.columnconfigure(0, weight=1, uniform="c")
        grid.columnconfigure(1, weight=1, uniform="c")

        footer = tk.Frame(root, bg=BG)
        footer.pack(fill="x", padx=24, pady=(10, 18))
        tk.Label(
            footer, text="Closing this window stops UsisAIn.", bg=BG, fg=MUTED, font=F_SMALL
        ).pack(side="left")
        FlatButton(footer, "Quit", on_quit, "link").pack(side="right")

        self.set_state("starting", "Preparing the analysis engine...")
        _center(root)
        root.deiconify()

    def set_state(self, state: Literal["starting", "ready", "error"], detail: str = "") -> None:
        colour, label = {
            "starting": (WARN, "Starting..."),
            "ready": (OK, "Running"),
            "error": (ERR, "Not running"),
        }[state]
        self._dot.configure(fg=colour)
        self._status.configure(text=label)
        self._detail.configure(text=detail)
        enabled = state == "ready"
        self.btn_app.set_enabled(enabled)
        self.btn_dash.set_enabled(enabled)
        if self.btn_port is not None:
            self.btn_port.set_enabled(state != "starting")
        if state == "starting":
            self._bar.start(12)
        else:
            self._bar.stop()
            self._bar.configure(mode="determinate", value=100 if enabled else 0)
