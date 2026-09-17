"""Dead end, kept for the record: clicking the theme button via PostMessage.

Tk ignores posted WM_LBUTTONDOWN/WM_LBUTTONUP for a window that is not
foreground, so the theme never actually toggles and the two captures come out
identical. Use _make_docs_shots.py instead, which calls the method directly.

This script therefore writes to scratch names and must never be pointed at
docs/ -- running it would overwrite the real README screenshots with a pair of
identical dark images.
"""

import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "av1_batch_converter.exe")
SCRATCH = HERE

WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
MK_LBUTTON = 0x0001
PW_RENDERFULLCONTENT = 0x00000002
HEADER_ROWS = (8, 42)

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def find_window(timeout=40.0):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def enum_proc(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                if "AV1 Batch Converter" in buf.value:
                    found.append(hwnd)
        return True

    deadline = time.time() + timeout
    while time.time() < deadline:
        found.clear()
        user32.EnumWindows(enum_proc, 0)
        if found:
            return found[0]
        time.sleep(0.5)
    return None


def grab(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount = 1, 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")


def client_origin_offset(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x - rect.left, pt.y - rect.top


def ink_columns(img, y0, y1, bg_delta=40):
    grey = img.convert("L")
    px = grey.load()
    cols = [0] * grey.size[0]
    for y in range(y0, min(y1, grey.size[1])):
        for x in range(grey.size[0]):
            if abs(px[x, y] - 32) > bg_delta:
                cols[x] += 1
    return cols


def clusters(cols, min_gap=6):
    groups, run = [], []
    for x, c in enumerate(cols):
        if c > 0:
            run.append(x)
        elif run:
            groups.append((run[0], run[-1]))
            run = []
    if run:
        groups.append((run[0], run[-1]))
    merged = []
    for g in groups:
        if merged and g[0] - merged[-1][1] <= min_gap:
            merged[-1] = (merged[-1][0], g[1])
        else:
            merged.append(g)
    return merged


def signature(img):
    grey = img.convert("L")
    w, h = grey.size
    px = grey.load()
    cols = [0] * w
    for y in range(h):
        for x in range(w):
            if abs(px[x, y] - 32) > 40:
                cols[x] += 1
    total = float(sum(cols)) or 1.0
    return [c / total for c in cols]


def distance(a, b):
    if len(a) != len(b):
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


def post_click(hwnd, x, y):
    lparam = (y << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lparam)
    time.sleep(0.05)
    user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lparam)


def save_client(img, hwnd, path):
    cart_x, cart_y = client_origin_offset(hwnd)
    cw, ch = img.size[0] - cart_x, img.size[1] - cart_y
    img.crop((cart_x, cart_y, cart_x + cw, cart_y + ch)).save(path)
    return cw, ch


def main():
    subprocess.run(["taskkill", "/F", "/T", "/IM", "av1_batch_converter.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)

    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    hwnd = find_window()
    check("window appeared", hwnd is not None)
    if not hwnd:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return report()

    time.sleep(9.0)          # let the encoder probe finish
    dark_full = grab(hwnd)
    dark_full.save(os.path.join(HERE, "_shot_docs_dark_full.png"))

    ox, oy = client_origin_offset(hwnd)
    cols = ink_columns(dark_full, oy + HEADER_ROWS[0], oy + HEADER_ROWS[1])
    groups = [g for g in clusters(cols) if g[1] > dark_full.size[0] * 0.6]
    check("two icon buttons found in the header", len(groups) >= 2,
          "clusters: %s" % groups)
    if len(groups) < 2:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return report()

    theme_cx = (groups[-1][0] + groups[-1][1]) // 2
    theme_cy = oy + (HEADER_ROWS[0] + HEADER_ROWS[1]) // 2
    print("      theme button at client (%d, %d)" % (theme_cx - ox, theme_cy - oy))

    dark_sig = signature(dark_full)
    post_click(hwnd, theme_cx - ox, theme_cy - oy)
    time.sleep(1.4)
    light_full = grab(hwnd)
    light_full.save(os.path.join(HERE, "_shot_docs_light_full.png"))
    light_sig = signature(light_full)
    check("posted click switched the theme", distance(dark_sig, light_sig) > 0.10,
          "ink distance %.3f" % distance(dark_sig, light_sig))

    light_ink = sum(1 for y in range(light_full.size[1])
                    for x in range(0, light_full.size[0], 4)
                    if light_full.convert("L").load()[x, y] > 200)
    check("light theme is bright", light_ink > 5000, "%d bright samples" % light_ink)

    w1, h1 = save_client(dark_full, hwnd, os.path.join(SCRATCH, "_shot_themes_dark_client.png"))
    w2, h2 = save_client(light_full, hwnd, os.path.join(SCRATCH, "_shot_themes_light_client.png"))
    check("both shots same size", (w1, h1) == (w2, h2), "%sx%s vs %sx%s" % (w1, h1, w2, h2))

    # restore dark so the app is left in its default state, then close
    post_click(hwnd, theme_cx - ox, theme_cy - oy)
    time.sleep(0.8)
    user32.PostMessageW(hwnd, 0x0010, 0, 0)     # WM_CLOSE
    time.sleep(1.5)
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return report()


def report():
    print()
    print("FAILURES: " + ", ".join(failures) if failures else "ALL CHECKS PASSED")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
