"""Launch the packaged exe, capture the window, and confirm the Encoder picker is there."""
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


def grab(hwnd, tag):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    x, y = rect.left, rect.top
    w, h = rect.right - rect.left, rect.bottom - rect.top
    full = ImageGrab.grab(all_screens=True)
    crop = full.crop((x - vx, y - vy, x - vx + w, y - vy + h))
    out = os.path.join(HERE, f"_shot_exe_{tag}.png")
    crop.save(out)
    print(f"[{tag}] {w}x{h} -> {os.path.basename(out)}")
    return crop, (x, y, w, h)


def main():
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    print(f"launched pid={proc.pid}")
    try:
        hwnd = wait_for_hwnd()
        if not hwnd:
            print("FAIL: window never appeared")
            return 1
        foreground(hwnd)
        time.sleep(2.5)

        crop, (wx, wy, ww, wh) = grab(hwnd, "enc")
        px = crop.convert("RGB").load()

        print("\n=== text bands across the window (left third / right two thirds) ===")
        for x0, x1, label in ((20, 340, "left"), (340, min(760, crop.width), "right")):
            bands = []
            sy = 0
            while sy < crop.height:
                count = sum(1 for sx in range(x0, x1)
                            if sum(px[sx, sy]) // 3 > 170)
                if count > 6:
                    start = sy
                    peak = count
                    while sy + 1 < crop.height:
                        nxt = sum(1 for sx in range(x0, x1)
                                  if sum(px[sx, sy + 1]) // 3 > 170)
                        if nxt <= 6:
                            break
                        sy += 1
                        peak = max(peak, nxt)
                    bands.append((start, sy, peak))
                sy += 1
            print(f"  -- {label} --")
            for a, b, peak in bands:
                print(f"     y {a:3d}-{b:3d}  bright={peak}")

        print("\n=== ascii view of the action row (x 400..700) ===")
        ramp = " .:-=+*#%@"
        for sy in range(640, min(690, crop.height), 2):
            line = "".join(
                ramp[min(9, max(0, ((sum(px[sx, sy]) // 3) - 20) // 8))]
                for sx in range(400, min(700, crop.width), 2))
            print(f"  y={sy:3d} |{line}")

        print(f"\nwindow rect=({wx},{wy},{ww}x{wh})")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("terminated")


if __name__ == "__main__":
    sys.exit(main())
