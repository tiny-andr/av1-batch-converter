"""Diagnose why the packaged exe stops being on screen during the click sequence.

Checks, after every synthetic click: does the process still exist, does the window
handle still exist, and which window is actually in the foreground.
"""
import ctypes
import os
import subprocess
import time
from ctypes import wintypes

EXE = r"C:\Users\Administrator\Documents\shell\av1_batch_converter.exe"
TITLE = "AV1 NVENC Batch Converter"

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

user32 = ctypes.windll.user32


def text_of(hwnd):
    if not hwnd:
        return "<none>"
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value or "<untitled>"


def cls_of(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def rect_of(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right - r.left, r.bottom - r.top)


def foreground(hwnd):
    cur = user32.GetForegroundWindow()
    user32.AttachThreadInput(user32.GetWindowThreadProcessId(cur, None),
                             user32.GetWindowThreadProcessId(hwnd, None), True)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)


def click(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.08)
    user32.mouse_event(0x0004, 0, 0, 0, 0)


def report(tag, proc, hwnd):
    alive = proc.poll() is None
    exists = bool(user32.IsWindow(hwnd))
    fg = user32.GetForegroundWindow()
    print(f"[{tag}]")
    print(f"    process alive   : {alive} (exitcode={proc.poll()})")
    print(f"    our hwnd exists : {exists}")
    print(f"    our rect        : {rect_of(hwnd) if exists else '-'}")
    print(f"    foreground hwnd : {fg}  cls={cls_of(fg)!r}  title={text_of(fg)!r}")
    print(f"    our visible     : {bool(user32.IsWindowVisible(hwnd)) if exists else '-'}")
    return alive and exists


def main():
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    print(f"launched pid={proc.pid}")
    hwnd = 0
    for _ in range(100):
        hwnd = user32.FindWindowW(None, TITLE)
        if hwnd:
            break
        time.sleep(0.3)
    print(f"hwnd={hwnd}")
    foreground(hwnd)
    time.sleep(5.0)
    ok = report("after launch", proc, hwnd)

    x, y = 963, 146
    for step in range(1, 6):
        click(x, y)
        time.sleep(1.2)
        ok = report(f"after click {step} at ({x},{y})", proc, hwnd)
        if not ok:
            print("!! the app is gone from the screen - stopping here")
            break
        # park the pointer so no hover halo / tooltip is involved
        user32.SetCursorPos(554, 591)
        time.sleep(0.8)
        ok = report(f"  after parking, click {step}", proc, hwnd)
        if not ok:
            print("!! the app disappeared while the pointer was parked")
            break
        # put it back in front before the next click
        foreground(hwnd)
        time.sleep(0.4)

    try:
        proc.terminate()
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    print("done")


if __name__ == "__main__":
    main()
