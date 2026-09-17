"""Launch the packaged exe, capture it through the DWM compositor, click the theme toggle, compare.

Pillow note: passing bbox together with all_screens=True resolves coordinates against the
primary monitor, not the virtual screen, which silently crops the wrong region on multi-monitor
setups. Always grab the full virtual screen and crop manually using SM_XVIRTUALSCREEN.
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

EXE = r"C:\Users\Administrator\Documents\shell\av1_batch_converter.exe"
TITLE = "AV1 NVENC Batch Converter"
HERE = os.path.dirname(os.path.abspath(__file__))
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77

user32 = ctypes.windll.user32


def wait_for_hwnd(timeout=25.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = user32.FindWindowW(None, TITLE)
        if hwnd:
            return hwnd
        time.sleep(0.3)
    return 0


def foreground(hwnd):
    cur = user32.GetForegroundWindow()
    user32.AttachThreadInput(user32.GetWindowThreadProcessId(cur, None),
                             user32.GetWindowThreadProcessId(hwnd, None), True)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)


def grab_window(hwnd, tag):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    vx, vy = user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    full = ImageGrab.grab(all_screens=True)
    crop = full.crop((x - vx, y - vy, x - vx + w, y - vy + h))
    out = os.path.join(HERE, f"_shot_exe_{tag}.png")
    crop.save(out)

    rgb = crop.convert("RGB")
    px = rgb.load()
    tot = light = n = 0
    for sy in range(0, h, 2):
        for sx in range(0, w, 2):
            r, g, b = px[sx, sy]
            v = (r + g + b) // 3
            tot += v
            n += 1
            if v > 200:
                light += 1
    print(f"\n[{tag}] {w}x{h} avg={tot/n:.1f} light%={100*light/n:.2f} -> {os.path.basename(out)}")
    print(f"  titlebar(450,15)   #%02x%02x%02x" % px[450, 15])
    print(f"  client bg(30,300)  #%02x%02x%02x" % px[30, 300])
    print(f"  listbox(300,200)   #%02x%02x%02x" % px[300, 200])
    return crop, tot / n


def find_toggle(crop):
    """Locate the theme button glyph: a small bright cluster in the top-right client area."""
    px = crop.convert("RGB").load()
    w, h = crop.size
    hits = []
    for sy in range(38, min(90, h)):
        for sx in range(max(0, w - 70), w - 8):
            r, g, b = px[sx, sy]
            if (r + g + b) // 3 > 100:
                hits.append((sx, sy))
    if not hits:
        return None
    xs = [p[0] for p in hits]
    ys = [p[1] for p in hits]
    return min(xs), min(ys), max(xs), max(ys)


def main():
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    print(f"launched pid={proc.pid}")
    try:
        hwnd = wait_for_hwnd()
        if not hwnd:
            print("FAIL: window never appeared")
            return 1
        foreground(hwnd)
        time.sleep(2.0)

        crop_dark, avg_dark = grab_window(hwnd, "dark")
        box = find_toggle(crop_dark)
        if box is None:
            print("\nFAIL: could not locate the toggle button in the dark capture")
            return 3
        bx, by, bx2, by2 = box
        cx, cy = (bx + bx2) // 2, (by + by2) // 2
        print(f"\ntoggle button found at window coords ({bx},{by})-({bx2},{by2}) center=({cx},{cy})")

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        sx, sy = rect.left + cx, rect.top + cy
        user32.SetCursorPos(sx, sy)
        time.sleep(0.2)
        user32.mouse_event(0x0002, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(0x0004, 0, 0, 0, 0)
        print(f"clicked at screen ({sx},{sy})")
        time.sleep(1.5)

        crop_light, avg_light = grab_window(hwnd, "light")

        print("\n=== verdict ===")
        print(f"dark avg={avg_dark:.1f}  light avg={avg_light:.1f}  delta={avg_light-avg_dark:+.1f}")
        ok = avg_dark < 80 and avg_light > 170
        print("PASS: theme toggle works in the packaged exe" if ok
              else "FAIL: toggle did not repaint the exe window")
        return 0 if ok else 2
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\nexe process terminated")


if __name__ == "__main__":
    sys.exit(main())
