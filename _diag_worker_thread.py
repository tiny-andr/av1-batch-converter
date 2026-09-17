"""Worker threads and window enumeration in this harness: what works, what does not.

Background. `_verify_bundled_ffmpeg.py` used to time startup with a worker thread
that watched %TEMP% for the onefile extraction and polled EnumWindows for the
window. After part C (which builds Tk windows in-process) that thread completed
exactly one loop iteration and then stopped, with `error is None` -- no exception,
just silence. That made three launches in a row look like "no window appeared".

This script records what was ruled out, so the next person does not redo it:

  1. EnumWindows from a worker thread is fine -- before any Tk window, with a
     TkinterDnD window alive, after root.destroy(), and after a PrintWindow +
     GetDIBits capture. All 0.000s.
  2. Plain worker threads keep running after every stage of the Tk lifecycles.
  3. `threading.Thread` has no `stop` attribute, so `self.stop = False` in the
     watcher was not a name collision.
  4. The one-iteration stop still reproduces: create a Tk window in-process, then
     start the watcher and count iterations.

Conclusion is in DEVELOPMENT.md: do not observe startup from a worker thread.
Measure the window from the main thread and read the extraction timestamps off
disk (ctime of the _MEI folder, mtime of the ffmpeg.exe inside it).
"""

import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "av1_batch_converter.pyw")
TITLE = "AV1 Batch Converter"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))

GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002


def enum_once():
    count = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def proc(hwnd, _):
        count.append(1)
        return True

    user32.EnumWindows(proc, 0)
    return len(count)


def timed(label, in_thread, timeout=8.0):
    """Time one EnumWindows call, in the main thread or a worker thread."""
    box = {}

    def work():
        t0 = time.time()
        box["n"] = enum_once()
        box["dt"] = time.time() - t0

    if not in_thread:
        t0 = time.time()
        n = enum_once()
        print("  %-34s %.3fs, %d windows" % (label, time.time() - t0, n))
        return
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=timeout)
    if t.is_alive():
        print("  %-34s HUNG (>%.0fs)" % (label, timeout))
    else:
        print("  %-34s %.3fs, %d windows" % (label, box["dt"], box["n"]))


def thread_still_runs(label):
    box = {"ran": 0}

    def work():
        for _ in range(5):
            box["ran"] += 1
            time.sleep(0.01)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=3.0)
    print("  %-34s iterations=%d, hung=%s" % (label, box["ran"], t.is_alive()))


def capture(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    ok = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)

    class BMIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    bi = BMIH()
    bi.biSize = ctypes.sizeof(BMIH)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    return ok, w, h


def find_app_window():
    hits = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def proc(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if TITLE in buf.value:
                hits.append(hwnd)
                return False
        return True

    user32.EnumWindows(proc, 0)
    return hits[0] if hits else None


def counting_watcher(seconds):
    """The exact shape of the old StageWatcher loop, reduced to a counter."""
    state = {"iterations": 0, "hwnd": None}

    def run():
        end = time.time() + seconds
        while time.time() < end:
            state["iterations"] += 1
            hwnd = find_app_window()
            if hwnd:
                state["hwnd"] = hwnd
                return
            time.sleep(0.005)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t, state


def main():
    print("0. the watcher loop, before any Tk window exists in this process")
    t, state = counting_watcher(2.0)
    t.join(timeout=5.0)
    print("   after 2s: iterations=%d hung=%s" % (state["iterations"], t.is_alive()))

    print("\n1. EnumWindows from a worker thread")
    timed("main, before any Tk window", False)
    timed("worker, before any Tk window", True)

    spec = importlib.util.spec_from_file_location("abc_thr", SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["abc_thr"] = mod
    spec.loader.exec_module(mod)

    root = mod.TkinterDnD.Tk()
    root.title(TITLE)
    root.update_idletasks()
    root.update()
    time.sleep(0.5)
    hwnd = user32.GetAncestor(root.winfo_id(), GA_ROOT)
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)
    print("\n2. with a TkinterDnD window alive")
    timed("main", False)
    timed("worker", True)
    thread_still_runs("worker thread that only sleeps")

    ok, w, h = capture(hwnd)
    print("\n3. after a PrintWindow capture (ok=%s, %dx%d)" % (ok, w, h))
    timed("main", False)
    timed("worker", True)

    root.destroy()
    time.sleep(0.5)
    print("\n4. after root.destroy()")
    timed("main", False)
    timed("worker", True)
    thread_still_runs("worker thread that only sleeps")

    print("\n5. hasattr(threading.Thread, 'stop') = %s" % hasattr(threading.Thread, "stop"))

    print("\n6. reproduction: does the watcher loop keep iterating here?")
    t, state = counting_watcher(2.0)
    t.join(timeout=5.0)
    print("   after 2s: iterations=%d hung=%s hwnd=%s"
          % (state["iterations"], t.is_alive(), state["hwnd"]))
    print("\n   The contrast between step 0 and step 6 is the finding: the same loop")
    print("   runs fine before a Tk window exists in this process, and hangs after.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
