"""Render the README screenshots from the application itself.

The theme is switched by calling ``ConverterGUI._toggle_theme()`` directly
instead of clicking. Posted WM_LBUTTONDOWN messages are ignored by Tk unless the
window is foreground, and real synthetic clicks need the foreground plus cursor
movement, which hijacks the user's mouse. Calling the method exercises the same
theme rebuild without touching either.

The window is mapped with WS_EX_NOACTIVATE so it never steals focus, and it is
captured with PrintWindow, which renders occluded windows. The capture is then
compared against a capture of the packaged exe to prove both render identically.
"""

import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import sys
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "av1_batch_converter.pyw")
DOCS = os.path.join(HERE, "docs")
EXE_CAPTURE = os.path.join(HERE, "_shot_release_capture.png")
CLIENT_OFFSET = (8, 31)
CLIENT_SIZE = (900, 650)

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def load_app_module():
    spec = importlib.util.spec_from_file_location("av1bc", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["av1bc"] = mod
    spec.loader.exec_module(mod)
    return mod


def find_by_title(require_visible=True, timeout=20.0):
    """Return the framed OS window for the app.

    root.winfo_id() gives Tk's inner window; GetParent on it is Tk's wrapper,
    which reports a client-sized rect and has no caption. The window that
    carries the title bar is the one enumerated by title, so look it up there.
    """
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def enum_proc(hwnd, _):
        if require_visible and not user32.IsWindowVisible(hwnd):
            return True
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
        time.sleep(0.3)
    return None


def client_offset(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return (pt.x - rect.left, pt.y - rect.top,
            rect.right - rect.left, rect.bottom - rect.top)


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


def mean_luma(img):
    grey = img.convert("L")
    px = list(grey.getdata())
    return sum(px[::13]) / float(len(px[::13]))


def signature(img):
    grey = img.convert("L")
    w, h = grey.size
    px = list(grey.getdata())
    sample = sorted(px[::7])
    bg = sample[len(sample) // 2]
    cols = [0] * w
    for y in range(h):
        row = y * w
        for x in range(w):
            if abs(px[row + x] - bg) > 40:
                cols[x] += 1
    total = float(sum(cols)) or 1.0
    return [c / total for c in cols]


def distance(a, b):
    if len(a) != len(b):
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


def pump(root, seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def main():
    os.makedirs(DOCS, exist_ok=True)
    mod = load_app_module()
    mod._enable_dpi_awareness()

    root = mod.TkinterDnD.Tk()
    root.withdraw()
    app = mod.ConverterGUI(root)

    hwnd = find_by_title(require_visible=False)
    check("found the framed window", hwnd is not None)
    if not hwnd:
        root.destroy()
        return report()

    # Appear without taking focus from whatever the user is doing.
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)

    root.geometry("+40+40")
    root.deiconify()
    # The startup encoder probe takes a few seconds and appends its result to
    # the log box; wait it out so the shot matches the exe.
    pump(root, 11.0)

    ex, ey, ew, eh = client_offset(hwnd)
    client = (ew - 2 * ex, eh - ex - ey)      # 8px side borders, 31px caption, 8px bottom
    check("client-area offset matches the reference shots", (ex, ey) == CLIENT_OFFSET,
          "offset (%d, %d)" % (ex, ey))
    check("client area is %dx%d" % CLIENT_SIZE, client == CLIENT_SIZE,
          "client %dx%d" % client)
    check("window is not foreground", user32.GetForegroundWindow() != hwnd)

    dark = grab(hwnd)
    dark.save(os.path.join(HERE, "_shot_docs_dark_full.png"))

    app._toggle_theme()
    pump(root, 1.5)
    light = grab(hwnd)
    light.save(os.path.join(HERE, "_shot_docs_light_full.png"))

    app._toggle_theme()
    pump(root, 1.0)
    back_to_dark = grab(hwnd)

    check("dark render is dark", mean_luma(dark) < 90, "mean luma %.1f" % mean_luma(dark))
    check("light render is light", mean_luma(light) > 170, "mean luma %.1f" % mean_luma(light))
    check("toggle round-trips back to dark",
          abs(mean_luma(back_to_dark) - mean_luma(dark)) < 3.0,
          "%.1f vs %.1f" % (mean_luma(back_to_dark), mean_luma(dark)))

    if os.path.isfile(EXE_CAPTURE):
        exe = Image.open(EXE_CAPTURE).convert("RGB")
        exe = exe.crop((CLIENT_OFFSET[0], CLIENT_OFFSET[1],
                        CLIENT_OFFSET[0] + CLIENT_SIZE[0], CLIENT_OFFSET[1] + CLIENT_SIZE[1]))
        src_dark = dark.crop((CLIENT_OFFSET[0], CLIENT_OFFSET[1],
                              CLIENT_OFFSET[0] + CLIENT_SIZE[0], CLIENT_OFFSET[1] + CLIENT_SIZE[1]))
        d = distance(signature(src_dark), signature(exe))
        check("source and exe render the dark theme identically", d < 0.05,
              "ink distance %.3f" % d)

    dark.crop((CLIENT_OFFSET[0], CLIENT_OFFSET[1],
               CLIENT_OFFSET[0] + CLIENT_SIZE[0], CLIENT_OFFSET[1] + CLIENT_SIZE[1])
              ).save(os.path.join(DOCS, "screenshot-dark.png"))
    light.crop((CLIENT_OFFSET[0], CLIENT_OFFSET[1],
                CLIENT_OFFSET[0] + CLIENT_SIZE[0], CLIENT_OFFSET[1] + CLIENT_SIZE[1])
               ).save(os.path.join(DOCS, "screenshot-light.png"))

    for name in ("screenshot-dark.png", "screenshot-light.png"):
        path = os.path.join(DOCS, name)
        img = Image.open(path)
        check("docs/%s is %dx%d" % (name, CLIENT_SIZE[0], CLIENT_SIZE[1]),
              img.size == CLIENT_SIZE, str(img.size))

    try:
        app._stop()
    except Exception:
        pass
    root.destroy()
    return report()


def report():
    print()
    print("FAILURES: " + ", ".join(failures) if failures else "ALL CHECKS PASSED")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
