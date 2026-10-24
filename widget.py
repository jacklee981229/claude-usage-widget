"""Desktop widget showing estimated Claude plan usage: a 5-hour donut and a weekly bar.

Start it with `pythonw widget.py` so no console window opens. Right-click it to exit.
"""
import ctypes
import json
import math
import threading
import tkinter as tk
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

import usage_estimate as ue

POSITION_FILE = Path(__file__).resolve().parent / "data" / "position.json"
REFRESH_MS = 30_000
WIDTH, HEIGHT = 236, 300
BG, TEXT, MUTED, TRACK = "#171717", "#ededed", "#a3a3a3", "#2a2a2a"
# The ring and bar take one colour a day, round the rainbow from Monday's red to Sunday's violet.
RAINBOW = ("#ff453a", "#ff9f0a", "#ffd60a", "#30d158", "#0a84ff", "#5e5ce6", "#bf5af2")
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FR_PRIVATE = 0x10


def load_font():
    """Hanken Grotesk for this process only, so nothing is installed in Windows; Segoe UI if the files are missing."""
    add = ctypes.windll.gdi32.AddFontResourceExW
    add.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    loaded = [add(str(FONT_DIR / f"HankenGrotesk-{weight}.ttf"), FR_PRIVATE, None) for weight in ("Regular", "Bold")]
    return "Hanken Grotesk" if all(loaded) else "Segoe UI Variable Text"


FONT = load_font()
LABEL, SMALL, BIG, MONO = (FONT, 10), (FONT, 8), (FONT, 24, "bold"), ("Cascadia Mono", 8)
# The ring and the bar, in logical pixels.
RING_CY, RING_R, RING_W = 118, 58, 15
BAR_Y, BAR_H = 224, 10
PAD = 22
DESKTOP_CLASSES = ("Progman", "WorkerW")

user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
# Handles are 64-bit; without these declarations ctypes would cut them to 32 bits.
user32.FindWindowW.restype = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowExW.restype = wintypes.HWND
user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND] + [ctypes.c_int] * 4 + [wintypes.UINT]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
GWL_EXSTYLE, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = -20, 0x00000080, 0x08000000
HWND_TOPMOST, HWND_NOTOPMOST, GW_HWNDNEXT, GW_HWNDPREV = -1, -2, 2, 3
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
ERROR_ALREADY_EXISTS = 183
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND, DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE = 33, 2, 34, 0xFFFFFFFE


def desktop_window():
    """The top-level window showing the desktop icons."""
    progman = user32.FindWindowW("Progman", None)
    if user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None):
        return progman
    # Wallpaper apps can move the icons into a separate WorkerW window.
    found = []

    def check(hwnd, _):
        if user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
            found.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(check), 0)
    return found[0] if found else progman


def class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(hwnd, buffer, 64)
    return buffer.value


def resets_in(reset, now):
    if reset is None:
        return "not started"
    hours, minutes = divmod(max(0, math.ceil((reset - now).total_seconds() / 60)), 60)
    return f"resets in {hours}h {minutes}m" if hours else f"resets in {minutes}m"


def resets_at(reset, tz=None):
    return reset.astimezone(tz).strftime("resets %a %H:%M")


def source_text(measured_at, now, tz=None):
    """Where the numbers come from: an official reading plus the estimate since, or the estimate alone."""
    if measured_at is None:
        return f"estimate · {now.astimezone(tz):%H:%M}"
    return f"official {measured_at.astimezone(tz):%H:%M} + est."


def day_colour(day):
    return RAINBOW[day.weekday()]


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def rgb(colour):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def coverage(distance):
    """How much of a pixel a shape covers, from the pixel centre's distance to the shape's edge (negative inside)."""
    return min(1.0, max(0.0, 0.5 - distance))


def photo_rows(width, height, colour_at):
    """Pixels for PhotoImage.put: one {…} group of #rrggbb per row."""
    return " ".join("{" + " ".join("#%02x%02x%02x" % colour_at(x + 0.5, y + 0.5) for x in range(width)) + "}" for y in range(height))


def ring_rows(size, radius, half_width, fraction, colour):
    """A full track ring with an arc over it from 12 o'clock clockwise, round-capped, smoothed at the edges.

    Tk's canvas draws arcs with jagged edges and square ends, so the ring is painted pixel by pixel instead.
    """
    bg, track, accent = rgb(BG), rgb(TRACK), rgb(colour)
    centre, sweep = size / 2, 2 * math.pi * min(max(fraction, 0), 1)
    caps = [(centre + radius * math.sin(a), centre - radius * math.cos(a)) for a in (0, sweep)]

    def colour_at(x, y):
        dx, dy = x - centre, y - centre
        band = abs(math.hypot(dx, dy) - radius) - half_width
        colour = mix(bg, track, coverage(band))
        if sweep <= 0:
            return colour
        if sweep >= 2 * math.pi or math.atan2(dx, -dy) % (2 * math.pi) <= sweep:
            arc = band
        else:
            arc = min(math.hypot(x - cx, y - cy) for cx, cy in caps) - half_width
        return mix(colour, accent, coverage(arc))

    return photo_rows(size, size, colour_at)


def bar_rows(width, height, fraction, colour):
    """A round-ended track with a round-ended fill from the left, smoothed at the edges."""
    bg, track, accent = rgb(BG), rgb(TRACK), rgb(colour)
    r = height / 2
    end = max(r, r + (width - height) * min(max(fraction, 0), 1))

    def capsule(x, y, right):
        return math.hypot(x - min(max(x, r), right), y - r) - r

    def colour_at(x, y):
        colour = mix(bg, track, coverage(capsule(x, y, width - r)))
        return mix(colour, accent, coverage(capsule(x, y, end))) if fraction > 0 else colour

    return photo_rows(width, height, colour_at)


def cursor():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


class Widget:
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except OSError:
            pass
        previous = user32.GetForegroundWindow()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.scale = self.root.winfo_fpixels("1i") / 96
        self.canvas = tk.Canvas(self.root, width=self.px(WIDTH), height=self.px(HEIGHT), bg=BG, highlightthickness=0)
        self.canvas.pack()
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Exit", command=self.root.destroy)
        self.canvas.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        self.canvas.bind("<Button-1>", self.start_drag)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.save_position)
        self.root.geometry("+%d+%d" % self.saved_position())
        self.root.update()
        self.hwnd = int(self.root.wm_frame(), 16)
        # A tool window stays out of Alt+Tab; no-activate stops a click from lifting it over other windows.
        ex_style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, ex_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        # Windows 11 rounds the card's corners, smoothly, and drops the grey frame it adds to them; older Windows keeps
        # a plain square card.
        try:
            for attribute, value in ((DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND), (DWMWA_BORDER_COLOR, DWMWA_COLOR_NONE)):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(wintypes.HWND(self.hwnd), attribute, ctypes.byref(ctypes.c_uint(value)), 4)
        except (OSError, AttributeError):
            pass
        # Appearing made the widget the active window; hand focus back to where it was.
        if previous:
            user32.SetForegroundWindow(previous)
        self.raised = False
        self.reader = ue.TranscriptReader()
        self.result = self.shown = None  # result is written by the worker thread
        self.worker = None
        self.draw()
        self.refresh()
        self.poll()
        self.stay_on_desktop()

    def px(self, value):
        return round(value * self.scale)

    def saved_position(self):
        try:
            saved = json.loads(POSITION_FILE.read_text(encoding="utf-8"))
            return saved["x"], saved["y"]
        except (OSError, ValueError, KeyError):
            return self.root.winfo_screenwidth() - self.px(WIDTH) - self.px(40), self.px(40)

    def start_drag(self, _):
        self.drag_from = (*cursor(), self.root.winfo_x(), self.root.winfo_y())

    def drag(self, _):
        x0, y0, left, top = self.drag_from
        x, y = cursor()
        self.root.geometry(f"+{left + x - x0}+{top + y - y0}")

    def save_position(self, _):
        rect = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        POSITION_FILE.parent.mkdir(exist_ok=True)
        POSITION_FILE.write_text(json.dumps({"x": rect.left, "y": rect.top}), encoding="utf-8")

    def stay_on_desktop(self):
        """Sit just above the desktop, under every app window; come to the top while the desktop is active (Win+D)."""
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        if class_name(user32.GetForegroundWindow()) in DESKTOP_CLASSES:
            if not self.raised:
                user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
                self.raised = True
        else:
            if self.raised:
                user32.SetWindowPos(self.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                self.raised = False
            desktop = desktop_window()
            if self.app_window_between(desktop):
                user32.SetWindowPos(self.hwnd, user32.GetWindow(desktop, GW_HWNDPREV), 0, 0, 0, 0, flags)
        self.root.after(500, self.stay_on_desktop)

    def app_window_between(self, desktop):
        """Whether a visible app window sits between the widget and the desktop.

        Tool windows, such as the to-do widget, don't count; otherwise two desktop
        widgets keep swapping places.
        """
        hwnd = user32.GetWindow(self.hwnd, GW_HWNDNEXT)
        while hwnd and hwnd != desktop:
            if user32.IsWindowVisible(hwnd) and not user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            hwnd = user32.GetWindow(hwnd, GW_HWNDNEXT)
        return False

    def refresh(self):
        if self.worker is None or not self.worker.is_alive():
            self.worker = threading.Thread(target=self.compute, daemon=True)
            self.worker.start()
        self.root.after(REFRESH_MS, self.refresh)

    def compute(self):
        self.reader.refresh()
        now = datetime.now(timezone.utc)
        self.result = (now, ue.combine(self.reader.costs.values(), self.reader.activity, now, ue.read_official()))

    def poll(self):
        if self.result is not self.shown:
            self.shown = self.result
            self.draw()
        self.root.after(500, self.poll)

    def draw(self):
        c, p = self.canvas, self.px
        c.delete("all")
        if self.shown is None:
            c.create_text(p(WIDTH / 2), p(HEIGHT / 2), text="Reading Claude Code transcripts...", fill=MUTED, font=SMALL)
            return
        now, (five, five_reset, week, week_reset, measured_at) = self.shown
        left, right, mid = p(PAD), p(WIDTH - PAD), p(WIDTH / 2)
        # Redrawn at least every 30 s, so the colour turns soon after midnight.
        colour = day_colour(datetime.now().date())
        c.create_text(left, p(30), text="5-hour window", anchor="w", fill=MUTED, font=LABEL)
        c.create_text(right, p(30), text=resets_in(five_reset, now), anchor="e", fill=MUTED, font=SMALL)
        # Painted in real pixels, so the ring is as sharp at 150% scaling as at 100%.
        size = p(2 * (RING_R + RING_W / 2) + 4)
        ring = tk.PhotoImage(width=size, height=size)
        ring.put(ring_rows(size, p(RING_R), p(RING_W) / 2, five / 100, colour))
        c.create_image(mid, p(RING_CY), image=ring)
        c.create_text(mid, p(RING_CY), text=f"{five:.0f}%", fill=TEXT, font=BIG)
        c.create_text(left, p(BAR_Y - 18), text="This week", anchor="w", fill=MUTED, font=LABEL)
        c.create_text(right, p(BAR_Y - 18), text=f"{week:.0f}%", anchor="e", fill=TEXT, font=LABEL + ("bold",))
        bar = tk.PhotoImage(width=right - left, height=p(BAR_H))
        bar.put(bar_rows(right - left, p(BAR_H), week / 100, colour))
        c.create_image(left, p(BAR_Y), image=bar, anchor="nw")
        c.create_text(left, p(BAR_Y + BAR_H + 16), text=resets_at(week_reset), anchor="w", fill=MUTED, font=SMALL)
        c.create_text(left, p(HEIGHT - 24), text=source_text(measured_at, now), anchor="w", fill=MUTED, font=MONO)
        # The canvas holds only a reference Tk can't see; without this the pictures vanish.
        self.pictures = (ring, bar)


if __name__ == "__main__":
    # One widget at a time: starting a second copy just exits.
    mutex = kernel32.CreateMutexW(None, False, "ClaudeUsageWidget")
    if ctypes.get_last_error() != ERROR_ALREADY_EXISTS:
        Widget().root.mainloop()
