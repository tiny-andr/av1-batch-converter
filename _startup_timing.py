"""Startup-cost diagnostic: where do the seconds go, old build vs new?

The combined verifier reported 31.96s for the old 13 MB exe and 4.4s for the new
48 MB one, which is backwards from the naive expectation. This isolates the
stages so the real numbers can be compared fairly:

  * extraction of the onefile archive (a thread watches %TEMP% for _MEI*)
  * the serial encoder probe, timed on its own
  * the window becoming visible

Both exes are measured with the *same* PATH, otherwise the comparison is
meaningless -- the old build needs ffmpeg from PATH, the new one does not.
"""

import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PYW = os.path.join(HERE, "av1_batch_converter.pyw")
OLD_EXE = os.path.join(r"C:\Users\Administrator\Documents\shell", "av1_batch_converter.exe")
NEW_EXE = os.path.join(HERE, "dist", "av1_batch_converter.exe")
PATH_FFMPEG_DIR = r"C:\Users\Administrator\bin"
TITLE = "AV1 Batch Converter"

user32 = ctypes.windll.user32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000

print("TEMP =", os.environ.get("TEMP"))


def titles_matching(part):
    found = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def proc(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if part in buf.value:
                found.append((hwnd, buf.value, bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(proc, 0)
    return found


print("\nwindows titled like the app *before* this test:", titles_matching(TITLE))


class Watcher(threading.Thread):
    """Watch %TEMP% for a new _MEI dir, and the desktop for the app window."""

    def __init__(self, t0):
        super().__init__(daemon=True)
        self.t0 = t0
        self.before = {d for d in os.listdir(tempfile.gettempdir()) if d.startswith("_MEI")}
        self.t_dir = None
        self.t_ffmpeg = None
        self.t_created = None
        self.t_visible = None
        self.dir_name = None
        self.stop = False

    def run(self):
        tmp = tempfile.gettempdir()
        while not self.stop:
            now = time.time() - self.t0
            if self.t_dir is None:
                for d in os.listdir(tmp):
                    if d.startswith("_MEI") and d not in self.before:
                        self.t_dir = now
                        self.dir_name = d
                        break
            if self.t_dir and self.t_ffmpeg is None:
                if os.path.isfile(os.path.join(tmp, self.dir_name, "ffmpeg", "ffmpeg.exe")):
                    self.t_ffmpeg = now
            if self.t_created is None:
                hits = titles_matching(TITLE)
                if hits:
                    self.t_created = now
                    hwnd = hits[0][0]
                    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)
            if self.t_created and self.t_visible is None:
                hits = titles_matching(TITLE)
                if hits and hits[0][2]:
                    self.t_visible = now
            time.sleep(0.005)


def measure(exe, label, strip=False, settle=6.0):
    env = dict(os.environ)
    if strip:
        keep = [p for p in env.get("PATH", "").split(os.pathsep)
                if os.path.normcase(p.rstrip("\\")) != os.path.normcase(PATH_FFMPEG_DIR)]
        env["PATH"] = os.pathsep.join(keep)

    t0 = time.time()
    w = Watcher(t0)
    w.start()
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe), env=env)
    deadline = time.time() + 120
    while time.time() < deadline and w.t_visible is None:
        time.sleep(0.02)
    time.sleep(settle)
    w.stop = True
    fg = user32.GetForegroundWindow()
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    fmt = lambda v: ("%.2fs" % v) if v is not None else "n/a"
    print("\n%-42s" % label)
    print("    archive dir created   %s" % fmt(w.t_dir))
    print("    ffmpeg.exe extracted  %s" % fmt(w.t_ffmpeg))
    print("    window created        %s" % fmt(w.t_created))
    print("    window visible        %s" % fmt(w.t_visible))
    print("    stole foreground      %s" % (fg == (titles_matching(TITLE)[0][0]
                                                 if titles_matching(TITLE) else 0)))
    return w


print("\n--- window-to-visible cost, same PATH for both ---")
measure(OLD_EXE, "1.0.0  13.2 MB, PATH ffmpeg present")
measure(NEW_EXE, "1.0.1  48.5 MB, bundled, PATH also present")
measure(NEW_EXE, "1.0.1  again (warm)")

print("\n--- new build with no ffmpeg on PATH at all ---")
measure(NEW_EXE, "1.0.1  48.5 MB, bundled only", strip=True)

print("\n--- the serial encoder probe, timed on its own ---")
spec = importlib.util.spec_from_file_location("abc_t", PYW)
mod = importlib.util.module_from_spec(spec)
sys.modules["abc_t"] = mod
spec.loader.exec_module(mod)
print("FFMPEG_CMD =", mod.FFMPEG_CMD)
t0 = time.time()
avail = mod.detect_backends()
print("detect_backends() took %.2fs -> %s" % (time.time() - t0, avail))
print("\nper-backend:")
for b in mod.ENCODER_BACKENDS:
    t0 = time.time()
    ok = mod.probe_backend(b)
    print("    %-24s %-6s %.2fs" % (b["label"], ok, time.time() - t0))

print("\nwindows titled like the app *after* this test:", titles_matching(TITLE))
