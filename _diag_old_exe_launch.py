"""Why does the archived 1.0.0 build fail to open a window?

Launches the same binary under three names / locations and reports whether a
window with the app title appears.

WARNING: every trial leaves a real window on the desktop for up to 30 seconds.
Ask the user before running this. The archived binary predates the rename, so
its title is "AV1 NVENC Batch Converter" and the TITLE filter below never
matches it - which is exactly the bug this script was written to expose.

  1. the raw archive name        av1_batch_converter.exe.bak-20260917
  2. copied to a temp dir as     av1_old.exe        (plain .exe, odd folder)
  3. copied to a temp dir as     av1_batch_converter.exe
"""

import ctypes
import ctypes.wintypes as wt
import os
import shutil
import subprocess
import tempfile
import time

TITLE = "AV1 Batch Converter"
SRC = r"C:\Users\Administrator\Documents\shell\av1_batch_converter.exe.bak-20260917"

user32 = ctypes.windll.user32


def wait_for_window(timeout=30.0):
    hwnds = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if TITLE in buf.value:
                hwnds.append((hwnd, buf.value))
        return True

    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnds.clear()
        user32.EnumWindows(proc, 0)
        if hwnds:
            return hwnds[0]
        time.sleep(0.4)
    return None


def kill_tree(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def trial(name, path):
    t0 = time.time()
    try:
        proc = subprocess.Popen([path], cwd=os.path.dirname(path))
    except OSError as exc:
        print("%-28s launch failed: %s" % (name, exc))
        return
    found = wait_for_window(30.0)
    dt = time.time() - t0
    code = proc.poll()
    print("%-28s window=%-5s in %5.2fs   exit_code=%s"
          % (name, bool(found), dt, code))
    if found:
        print("%-28s title=%r" % ("", found[1]))
    kill_tree(proc.pid)


print("source exists:", os.path.isfile(SRC), os.path.getsize(SRC), "bytes")
scratch = os.path.join(tempfile.gettempdir(), "av1_old_probe")
os.makedirs(scratch, exist_ok=True)

trial("1. raw .bak- name", SRC)

copy_a = os.path.join(scratch, "av1_old.exe")
shutil.copy2(SRC, copy_a)
trial("2. copied, av1_old.exe", copy_a)

copy_b = os.path.join(scratch, "av1_batch_converter.exe")
shutil.copy2(SRC, copy_b)
trial("3. copied, original name", copy_b)
