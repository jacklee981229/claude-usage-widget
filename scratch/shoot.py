"""The widget in set states, with test data, for the README's screenshots and the showcase video's clips.

python scratch\\shoot.py .github\\readme [scale]   -> one PNG per state (scale 2 by default), rounded, with a soft
                                                  shadow on a clear ground
python scratch\\shoot.py hold <state>             -> just shows that state at the screen's scale, for the showcase's
                                                  capture_window.py

It takes no mutex and never reads transcripts, so it runs beside Jack's own widget without touching it.
"""
import ctypes
import math
import struct
import sys
import zlib
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tkinter as tk  # noqa: E402

HOLD = sys.argv[1] == "hold"
SCALE = None if HOLD else float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
if SCALE:
    real = tk.Misc.winfo_fpixels

    def fpixels(self, what):
        # Draw at SCALE instead of the screen's own, fonts too (their sizes are in points).
        self.tk.call("tk", "scaling", SCALE * 96 / 72)
        return SCALE * 96

    tk.Misc.winfo_fpixels = fpixels

import widget  # noqa: E402

LOCAL = datetime.now().astimezone().tzinfo


def at(day, hour, minute):
    return datetime(2026, 10, day, hour, minute, tzinfo=LOCAL)


SAT = at(31, 9, 0)  # the week resets Saturday 09:00
# name: (now, (5-hour %, 5-hour reset, week %, week reset, official reading time), (5-hour full at, week full at))
STATES = {
    "on-pace": (at(28, 14, 20), (34, at(28, 17, 20), 28, SAT, at(28, 14, 2)), (None, None)),
    "ahead": (at(28, 11, 5), (63, at(28, 14, 20), 41, SAT, at(28, 10, 58)), (None, None)),
    "nearly-full": (at(30, 19, 40), (91, at(30, 20, 28), 87, SAT, at(30, 19, 31)), (None, None)),
    "estimate": (at(27, 16, 10), (47, at(27, 18, 20), 64, SAT, None), (None, None)),
    "not-started": (at(26, 8, 50), (0, None, 12, SAT, at(26, 8, 31)), (None, None)),
    "running-out": (at(28, 14, 0), (68, at(28, 16, 44), 71, SAT, at(28, 13, 58)), (at(28, 14, 43), at(29, 13, 10))),
}


class Shot(widget.Widget):
    def saved_position(self):
        return 60, 60

    def refresh(self):
        pass

    def poll(self):
        pass

    def stay_on_desktop(self):
        pass

    def show(self, name):
        self.shown = STATES[name]
        self.draw()
        self.root.update()


def grab(hwnd):
    r = wintypes.RECT()
    widget.user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    gdi32.CreateCompatibleBitmap.restype = wintypes.HANDLE
    gdi32.CreateCompatibleDC.restype = wintypes.HANDLE
    user32.GetWindowDC.restype = wintypes.HANDLE
    wdc = user32.GetWindowDC(wintypes.HWND(hwnd))
    mdc = gdi32.CreateCompatibleDC(wintypes.HANDLE(wdc))
    bmp = gdi32.CreateCompatibleBitmap(wintypes.HANDLE(wdc), w, h)
    gdi32.SelectObject(wintypes.HANDLE(mdc), wintypes.HANDLE(bmp))
    user32.PrintWindow(wintypes.HWND(hwnd), wintypes.HANDLE(mdc), 2)
    header = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    info = ctypes.create_string_buffer(header, 44)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(wintypes.HANDLE(mdc), wintypes.HANDLE(bmp), 0, h, buf, info, 0)
    gdi32.DeleteObject(wintypes.HANDLE(bmp))
    gdi32.DeleteDC(wintypes.HANDLE(mdc))
    user32.ReleaseDC(wintypes.HWND(hwnd), wintypes.HANDLE(wdc))
    return w, h, buf.raw


def rounded_distance(x, y, w, h, r):
    """Signed distance from a pixel centre to a w x h rectangle with corner radius r (negative inside)."""
    qx = abs(x - w / 2) - (w / 2 - r)
    qy = abs(y - h / 2) - (h / 2 - r)
    return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r


def framed(w, h, bgra, scale):
    """The card with Windows 11's rounded corners, on a clear ground with a soft shadow below it."""
    m, radius, drop, spread = round(28 * scale), 8 * scale, 10 * scale, 26 * scale
    W, H = w + 2 * m, h + 2 * m
    rows = []
    for Y in range(H):
        row = bytearray([0])
        for X in range(W):
            x, y = X - m + 0.5, Y - m + 0.5
            shadow = rounded_distance(x, y - drop, w, h, radius)
            sa = 0.32 * (1 - min(1, max(0, shadow) / spread)) ** 2.4
            d = rounded_distance(x, y, w, h, radius)
            ca = min(1, max(0, 0.5 - d))
            if ca > 0:
                i = (min(h - 1, max(0, int(y))) * w + min(w - 1, max(0, int(x)))) * 4
                b, g, r = bgra[i], bgra[i + 1], bgra[i + 2]
            else:
                r = g = b = 0
            a = ca + sa * (1 - ca)
            if a > 0:  # card over its black shadow, un-premultiplied
                r, g, b = (round(c * ca / a) for c in (r, g, b))
            row += bytes((r, g, b, round(a * 255)))
        rows.append(bytes(row))
    return W, H, b"".join(rows)


def png(path, w, h, raw):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    shot = Shot()
    if HOLD:
        shot.show(sys.argv[2])
        shot.root.mainloop()
    else:
        for name in STATES:
            shot.show(name)
            shot.root.after(300)
            shot.root.update()
            w, h, bgra = grab(shot.hwnd)
            png(Path(sys.argv[1]) / f"{name}.png", *framed(w, h, bgra, SCALE))
            print(name, w, h)
        shot.root.destroy()
