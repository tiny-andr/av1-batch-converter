"""Verify the 1.0.1 build: ffmpeg bundled inside the exe, and the resolution order.

Five parts, cheapest first:

  A  static     -- archive contents, embedded ffmpeg size, PE version resource
  B  logic      -- resolve_ffmpeg() precedence, exercised headless
  C  text       -- read the log back out of a live (never shown) Tk window
  D  timing     -- unpack + startup cost of the onefile build, old vs new
  E  pixels     -- capture the packaged exe and read its log off the bitmap

Part E is the one that matters. Everything else could pass while the shipped exe
still ran some other ffmpeg.

Nothing here takes the foreground or moves the cursor. Windows are given
WS_EX_NOACTIVATE before they are first mapped, and captures go through
PrintWindow(PW_RENDERFULLCONTENT), which renders occluded windows from DWM.
"""

import ast
import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PYW = os.path.join(HERE, "av1_batch_converter.pyw")
VENDOR = os.path.join(HERE, "vendor", "ffmpeg", "ffmpeg.exe")
EXE = os.path.join(HERE, "dist", "av1_batch_converter.exe")
PATH_FFMPEG = r"C:\Users\Administrator\bin\ffmpeg.exe"
PATH_FFMPEG_DIR = r"C:\Users\Administrator\bin"
TITLE = "AV1 Batch Converter"

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))    # PER_MONITOR_AWARE_V2

GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
PW_RENDERFULLCONTENT = 0x00000002

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def note(text):
    print("      " + text)


# --------------------------------------------------------------------------
# win32 helpers
# --------------------------------------------------------------------------

def find_by_title(title_part):
    hwnds = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def proc(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if title_part in buf.value:
                hwnds.append(hwnd)
        return True

    user32.EnumWindows(proc, 0)
    return hwnds[0] if hwnds else None


def make_non_activating(hwnd):
    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)
    return bool(ex & WS_EX_NOACTIVATE)


def wait_for_window(timeout=120.0, poll=0.02):
    """Wait for the app's framed window, grabbing it before it is first mapped.

    Polling fast and accepting invisible windows catches the Tk toplevel while
    the app is still probing encoders -- before it is ever shown -- which is the
    only moment WS_EX_NOACTIVATE can be set early enough to keep it from taking
    the foreground.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = find_by_title(TITLE)
        if hwnd:
            pre_mapped = not user32.IsWindowVisible(hwnd)
            already = make_non_activating(hwnd)
            return hwnd, pre_mapped, already
        time.sleep(poll)
    return None, False, False


def wait_visible(hwnd, timeout=120.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if user32.IsWindowVisible(hwnd):
            return True
        time.sleep(0.02)
    return False


def window_rect(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def grab_window(hwnd, timeout=40.0):
    """PrintWindow capture, retried: a window mid-map yields a blank bitmap."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        _, _, w, h = window_rect(hwnd)
        if w > 100 and h > 100:
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
            img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
            if len(set(img.getdata())) > 20:
                return ok, img
            last = img
        time.sleep(0.3)
    return False, last


def kill_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)


def stripped_env():
    """Environment with the ffmpeg on PATH removed, so only the bundled copy can answer."""
    env = dict(os.environ)
    keep = [p for p in env.get("PATH", "").split(os.pathsep)
            if os.path.normcase(p.rstrip("\\")) != os.path.normcase(PATH_FFMPEG_DIR)]
    env["PATH"] = os.pathsep.join(keep)
    return env


# --------------------------------------------------------------------------
# reading a log region off a bitmap
# --------------------------------------------------------------------------

def text_lines(img, min_ink=3, gap=2):
    """Group ink rows into text lines -> [(y0, y1, x0, x1)], top to bottom."""
    grey = img.convert("L")
    w, h = grey.size
    px = list(grey.getdata())
    sample = sorted(px[::5])
    bg = sample[len(sample) // 2]
    rows = [sum(1 for x in range(w) if abs(px[y * w + x] - bg) > 55) for y in range(h)]

    lines = []
    y = 0
    while y < h:
        if rows[y] <= min_ink:
            y += 1
            continue
        y0 = y
        blank = 0
        end = y
        while end < h and blank <= gap:
            if rows[end] > min_ink:
                blank = 0
                end += 1
            else:
                blank += 1
                end += 1
        y1 = max(y0 + 1, end - blank)
        xs = [x for yy in range(y0, y1) for x in range(w)
              if abs(px[yy * w + x] - bg) > 55]
        if xs:
            lines.append((y0, y1, min(xs), max(xs) + 1))
        y = end
    return lines


def ink_signature(img):
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


def signature_distance(a, b):
    if len(a) != len(b):
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


# --------------------------------------------------------------------------
# A -- static
# --------------------------------------------------------------------------

def archive_entries(exe):
    """Parse `pyi-archive_viewer -l` output into {member name: (stored, unpacked)}.

    The viewer prints the member name as a Python repr, so backslashes arrive
    doubled and the quotes need unescaping -- literal_eval, not strip("'").
    """
    pyi = os.path.join(os.path.dirname(sys.executable), "pyi-archive_viewer.exe")
    out = subprocess.run([pyi, "-l", exe], capture_output=True, text=True)
    entries = {}
    for line in out.stdout.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 6 and parts[-1].startswith("'"):
            try:
                stored, unpacked = int(parts[1]), int(parts[2])
                name = ast.literal_eval(parts[-1])
            except (ValueError, SyntaxError):
                continue
            entries[name] = (stored, unpacked)
    return entries


def part_a():
    print("\n=== A. static checks ===")
    check("packaged exe exists", os.path.isfile(EXE), EXE)
    if not os.path.isfile(EXE):
        return
    entries = archive_entries(EXE)
    for name in ("ffmpeg\\ffmpeg.exe", "ffmpeg\\LICENSE", "ffmpeg\\README-ffmpeg.txt"):
        present = name in entries
        check("embedded: %s" % name, present,
              ("%d of %d bytes stored" % entries[name]) if present else "absent")
    if "ffmpeg\\ffmpeg.exe" in entries:
        check("embedded ffmpeg is the vendor copy",
              entries["ffmpeg\\ffmpeg.exe"][1] == os.path.getsize(VENDOR),
              "%d vs %d" % (entries["ffmpeg\\ffmpeg.exe"][1], os.path.getsize(VENDOR)))
    with open(EXE, "rb") as fh:
        data = fh.read()
    off = data.find(struct.pack("<II", 0xFEEF04BD, 0x00010000))
    check("PE version resource present", off >= 0)
    if off >= 0:
        fv_ms, fv_ls = struct.unpack_from("<II", data, off + 8)
        ver = "%d.%d.%d.%d" % ((fv_ms >> 16) & 0xFFFF, fv_ms & 0xFFFF,
                               (fv_ls >> 16) & 0xFFFF, fv_ls & 0xFFFF)
        check("PE version is 1.0.1", ver.startswith("1.0.1"), ver)


# --------------------------------------------------------------------------
# B -- resolution order, headless
# --------------------------------------------------------------------------

def load_module():
    spec = importlib.util.spec_from_file_location("abc_v", PYW)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["abc_v"] = mod
    spec.loader.exec_module(mod)
    return mod


def part_b(mod):
    print("\n=== B. ffmpeg resolution order (headless) ===")
    tmp = tempfile.mkdtemp(prefix="ffmpeg-order-")
    program_dir = os.path.join(tmp, "program")
    os.makedirs(program_dir)
    decoy = os.path.join(tmp, "decoy", "ffmpeg.exe")
    os.makedirs(os.path.dirname(decoy))
    with open(decoy, "wb") as fh:
        fh.write(b"MZ" + b"\0" * 64)

    real_program_dir = mod._program_dir
    real_which = mod.shutil.which
    had_meipass = hasattr(sys, "_MEIPASS")
    old_meipass = getattr(sys, "_MEIPASS", None)

    def r():
        path, source = mod.resolve_ffmpeg()
        return source, path

    try:
        mod._program_dir = lambda: program_dir

        mod.shutil.which = lambda name: None
        check("nothing anywhere -> missing", r() == ("missing", "ffmpeg"), str(r()))

        mod.shutil.which = lambda name: decoy
        check("PATH only -> path", r() == ("path", decoy), str(r()))

        bundle = os.path.join(tmp, "meipass")
        os.makedirs(os.path.join(bundle, "ffmpeg"))
        shutil.copyfile(decoy, os.path.join(bundle, "ffmpeg", "ffmpeg.exe"))
        sys._MEIPASS = bundle
        bundled = os.path.join(bundle, "ffmpeg", "ffmpeg.exe")
        check("bundled beats PATH", r() == ("bundled", bundled), str(r()))

        os.makedirs(os.path.join(program_dir, "ffmpeg"))
        beside = os.path.join(program_dir, "ffmpeg", "ffmpeg.exe")
        shutil.copyfile(decoy, beside)
        check("beside beats bundled", r() == ("beside", beside), str(r()))
    finally:
        mod._program_dir = real_program_dir
        mod.shutil.which = real_which
        if had_meipass:
            sys._MEIPASS = old_meipass
        elif hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS
        shutil.rmtree(tmp, ignore_errors=True)


# --------------------------------------------------------------------------
# C -- read the log out of a live in-process window that is never shown
# --------------------------------------------------------------------------

def run_source_capture():
    """Build the GUI in-process and return (log text, log rect, capture, client size).

    In-process, winfo_id() IS the Tk toplevel and it is frameless: GetWindowRect
    reports the client size and PrintWindow renders exactly the client area. So
    widget geometry maps 1:1 onto the capture, and the log rect needs no
    colour-hunting. (Out of process the same window is framed, and the capture
    gains a caption and border -- see part_e for the offset.)
    """
    mod = load_module()
    root = mod.TkinterDnD.Tk()
    root.title(TITLE)
    framed = user32.GetAncestor(root.winfo_id(), GA_ROOT)
    if framed:
        make_non_activating(framed)
    app = mod.ConverterGUI(root)
    client_w, client_h = root.winfo_width(), root.winfo_height()
    root.update_idletasks()
    root.update()
    time.sleep(1.5)

    text = app.log_box.get("1.0", "end-1c")
    lb = app.log_box
    log_rect = (lb.winfo_rootx() - root.winfo_rootx(),
                lb.winfo_rooty() - root.winfo_rooty(),
                lb.winfo_width(), lb.winfo_height())
    stole = user32.GetForegroundWindow() == framed
    img = None
    if framed:
        ok, img = grab_window(framed)
    root.destroy()
    return text, log_rect, img, (client_w, client_h), stole


def part_c():
    print("\n=== C. log text read back from a live window ===")
    text, log_rect, img, client, stole = run_source_capture()
    lines = text.split("\n")
    print("  --- source run, vendor/ffmpeg present (the shipped configuration) ---")
    for i, line in enumerate(lines[:11], 1):
        print("   %2d |%s|" % (i, line))
    print("  client area %s, log rect inside it %s" % (client, log_rect))
    check("capture succeeded", img is not None)
    check("in-process window did not steal the foreground", not stole)
    check("log row 1 reports a bundled ffmpeg",
          bool(lines) and ("自" in lines[0] or "bundled" in lines[0] or "同梱" in lines[0]),
          lines[0] if lines else "")
    check("libaom is available as the CPU fallback",
          any("libaom" in l and ("可用" in l or "available" in l or "使用可能" in l)
              for l in lines),
          next((l for l in lines if "libaom" in l), "not found"))
    check("SVT-AV1 is reported unavailable by this build",
          any("SVT-AV1" in l and ("不可用" in l or "unavailable" in l or "使用不可" in l)
              for l in lines),
          next((l for l in lines if "SVT-AV1" in l), "not found"))

    vendor_dir = os.path.join(HERE, "vendor", "ffmpeg")
    parked = os.path.join(HERE, "vendor", "_ffmpeg_parked")
    shutil.move(vendor_dir, parked)
    try:
        text2, _, _, _, _ = run_source_capture()
        control = text2.split("\n")
        print("  --- control: vendor hidden, the PATH ffmpeg takes over ---")
        for i, line in enumerate(control[:2], 1):
            print("   %2d |%s|" % (i, line))
        check("control falls through to PATH",
              len(control) >= 2 and "PATH" in (control[0] + control[1]),
              control[0] if control else "")
        check("row 1 differs between bundled and PATH",
              bool(control) and control[0] != lines[0],
              "%r vs %r" % (lines[0] if lines else "", control[0] if control else ""))
        check("version line differs too (essentials vs full)",
              len(control) > 1 and len(lines) > 1 and control[1] != lines[1],
              "%r vs %r" % (lines[1] if len(lines) > 1 else "",
                            control[1] if len(control) > 1 else ""))
    finally:
        shutil.move(parked, vendor_dir)
    return log_rect, img, lines, client


# --------------------------------------------------------------------------
# D -- startup cost
# --------------------------------------------------------------------------

class StageWatcher(threading.Thread):
    """Unused: kept only as a record of a harness trap.

    A watcher thread that polls %TEMP% and EnumWindows inside its loop completed
    exactly one iteration and then stopped, with no exception raised, whenever it
    was started *after* the in-process Tk runs of part C. The same thread body
    works fine when started before any Tk window exists, and EnumWindows itself
    was separately measured to be safe from a worker thread both with a
    TkinterDnD window alive and after a PrintWindow capture. Rather than chase
    it further, measure_startup now observes every stage from the main thread and
    reads the extraction timestamps off disk -- which is exact anyway.
    """

    def __init__(self, t0):
        super().__init__(daemon=True)
        self.t0 = t0
        self.tmp = os.environ.get("TEMP", tempfile.gettempdir())
        self.before = {d for d in os.listdir(self.tmp) if d.startswith("_MEI")}
        self.t_dir = self.t_ffmpeg = self.t_created = self.t_visible = None
        self.dir_name = None
        self.hwnd = None
        self.stop = False
        self.iterations = 0
        self.error = None

    def run(self):
        try:
            while not self.stop:
                self.iterations += 1
                now = time.time() - self.t0
                if self.t_dir is None:
                    for d in os.listdir(self.tmp):
                        if d.startswith("_MEI") and d not in self.before:
                            self.t_dir, self.dir_name = now, d
                            break
                if self.dir_name and self.t_ffmpeg is None:
                    if os.path.isfile(os.path.join(self.tmp, self.dir_name,
                                                   "ffmpeg", "ffmpeg.exe")):
                        self.t_ffmpeg = now
                if self.hwnd is None:
                    hwnd = find_by_title(TITLE)
                    if hwnd:
                        self.hwnd = hwnd
                        self.t_created = now
                        make_non_activating(hwnd)
                elif self.t_visible is None and user32.IsWindowVisible(self.hwnd):
                    self.t_visible = now
                time.sleep(0.005)
        except Exception as exc:                      # noqa: BLE001 - report it, do not swallow
            self.error = repr(exc)


def extraction_times(tmp, before, t0):
    """When the onefile archive was unpacked, read off the files it wrote.

    Timestamps on disk are more reliable than watching the directory: nothing has
    to poll, and the answers survive whatever else the harness is doing.
    """
    fresh = [d for d in os.listdir(tmp) if d.startswith("_MEI") and d not in before]
    if not fresh:
        return None, None
    newest = max((os.path.join(tmp, d) for d in fresh), key=os.path.getctime)
    try:
        t_dir = os.path.getctime(newest) - t0
    except OSError:
        return None, None
    ffmpeg = os.path.join(newest, "ffmpeg", "ffmpeg.exe")
    t_ffmpeg = None
    if os.path.isfile(ffmpeg):
        try:
            t_ffmpeg = os.path.getmtime(ffmpeg) - t0
        except OSError:
            pass
    return t_dir, t_ffmpeg


def measure_startup(exe, label, timeout=120.0):
    """Time a launch end to end. Everything is observed from the main thread."""
    tmp = os.environ.get("TEMP", tempfile.gettempdir())
    before = {d for d in os.listdir(tmp) if d.startswith("_MEI")}

    t0 = time.time()
    proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
    hwnd, pre_mapped, already = wait_for_window(timeout=timeout)
    t_visible = time.time() - t0
    if hwnd is None:
        kill_tree(proc.pid)
        return {"label": label, "found": False}

    time.sleep(3.0)                      # the encoder probe must finish first
    alive = proc.poll() is None
    t_dir, t_ffmpeg = extraction_times(tmp, before, t0) if alive else (None, None)
    stole = user32.GetForegroundWindow() == hwnd
    kill_tree(proc.pid)
    return {"label": label, "found": True, "alive_at_capture": alive,
            "dir": t_dir, "ffmpeg": t_ffmpeg, "visible": t_visible,
            "pre_mapped": pre_mapped, "already_had": already,
            "stole_foreground": stole}


def part_d():
    print("\n=== D. startup cost of the packaged build (unpack + encoder probe) ===")
    results = []
    # Only the current build is launched here. The archived 13.2 MB pre-release
    # binary is deliberately left out: it still carries the old window title
    # ("AV1 NVENC Batch Converter"), so a title match never fires for it, and
    # launching it flashed a window on the desktop for the whole of every trial.
    # Its timing baseline is recorded in DEVELOPMENT.md instead.
    for label in ("1.0.1  48.5 MB, bundled, cold",
                  "1.0.1  48.5 MB, bundled, warm"):
        r = measure_startup(EXE, label)
        results.append(r)
        if r["found"]:
            fmt = lambda v: ("%.2fs" % v) if v is not None else "n/a"
            note("%-34s _MEI dir at %s, ffmpeg extracted at %s, window visible at %s"
                 % (label, fmt(r["dir"]), fmt(r["ffmpeg"]), fmt(r["visible"])))
        else:
            note("%-34s no window appeared" % label)
    for r in results:
        check("launched: %s" % r["label"], r["found"])
        if r["found"]:
            check("did not steal the foreground: %s" % r["label"],
                  not r["stole_foreground"])
            check("startup stayed under 30s: %s" % r["label"],
                  r.get("visible") is not None and r["visible"] < 30)
    return results


# --------------------------------------------------------------------------
# E -- read the packaged exe's log off the bitmap
# --------------------------------------------------------------------------

def capture_exe(exe, cwd, settle=8.0):
    proc = subprocess.Popen([exe], cwd=cwd, env=stripped_env())
    hwnd, pre_mapped, already = wait_for_window(timeout=120.0)
    if hwnd is None:
        kill_tree(proc.pid)
        return None
    wait_visible(hwnd)
    time.sleep(settle)
    ok, img = grab_window(hwnd)
    fg = user32.GetForegroundWindow()
    kill_tree(proc.pid)
    return {"ok": ok, "img": img, "pre_mapped": pre_mapped, "already_had": already,
            "stole_foreground": fg == hwnd}


def part_e(ref_img, ref_lines, log_rect, client):
    """Compare the packaged exe's log against the same log rendered from source.

    The source capture is the client area only; the exe capture includes the
    caption and borders. Both windows are the same size, so the log box sits at
    the same place inside the client area of each, offset by the frame.
    """
    print("\n=== E. the packaged exe's own log, read from pixels ===")
    res = capture_exe(EXE, os.path.dirname(EXE))
    check("exe window captured", res is not None and res["ok"])
    if not res or not res["ok"]:
        return
    check("exe never took the foreground", not res["stole_foreground"],
          "WS_EX_NOACTIVATE already set: %s, caught before first map: %s"
          % (res["already_had"], res["pre_mapped"]))

    img = res["img"]
    # Keep the source-vs-exe cross-check in _make_docs_shots.py fed with a current
    # capture; a stale one would fail there for the wrong reason.
    img.save(os.path.join(HERE, "_shot_release_capture.png"))
    check("reference capture is the client area alone", ref_img.size == client,
          "%s vs client %s" % (ref_img.size, client))
    fx = (img.size[0] - client[0]) // 2
    fy = (img.size[1] - client[1]) - fx
    check("exe capture is the client area plus a symmetric frame",
          (img.size[0] - fx * 2, img.size[1] - fx - fy) == client,
          "capture %s, frame left/top (%d, %d), client %s"
          % (img.size, fx, fy, client))
    note("frame offset used for the exe capture = (%d, %d)" % (fx, fy))
    if img.size[0] - fx * 2 != client[0]:
        return

    lx, ly, lw, lh = log_rect
    ref_log = ref_img.crop((lx, ly, lx + lw, ly + lh))
    exe_log = img.crop((fx + lx, fy + ly, fx + lx + lw, fy + ly + lh))
    ref_log.save(os.path.join(HERE, "_shot_bundled_ref_log.png"))
    exe_log.save(os.path.join(HERE, "_shot_bundled_exe_log.png"))
    ref_geom = text_lines(ref_log)
    exe_geom = text_lines(exe_log)

    print("  log region %dx%d: source %d text lines, exe %d text lines"
          % (lw, lh, len(ref_geom), len(exe_geom)))
    check("exe log has the same text-line count as the source run",
          len(exe_geom) == len(ref_geom) and len(ref_geom) > 5,
          "%d vs %d" % (len(exe_geom), len(ref_geom)))
    if len(exe_geom) != len(ref_geom):
        return

    print("  %-5s %-8s %-8s  %s" % ("row", "src px", "exe px", "source text"))
    deltas = []
    for i, (a, b) in enumerate(zip(ref_geom, exe_geom), 1):
        rw, ew = a[3] - a[2], b[3] - b[2]
        deltas.append(abs(rw - ew))
        print("  %-5d %-8d %-8d  %s" % (i, rw, ew, ref_lines[i - 1].strip()[:36]))
    worst = max((a[3] - a[2]) for a in ref_geom)
    check("every log row renders at the same width in the exe as from source",
          max(deltas) <= max(3, int(0.06 * worst)),
          "max delta %d px against a widest row of %d px" % (max(deltas), worst))

    dist = signature_distance(ink_signature(exe_log), ink_signature(ref_log))
    check("exe log region matches the bundled source reference", dist < 0.12,
          "ink distance %.3f" % dist)

    # --- control: give the exe a user-supplied ffmpeg beside it -----------
    sandbox = tempfile.mkdtemp(prefix="av1-beside-")
    os.makedirs(os.path.join(sandbox, "ffmpeg"))
    shutil.copyfile(EXE, os.path.join(sandbox, "av1_batch_converter.exe"))
    shutil.copyfile(PATH_FFMPEG, os.path.join(sandbox, "ffmpeg", "ffmpeg.exe"))
    try:
        res2 = capture_exe(os.path.join(sandbox, "av1_batch_converter.exe"), sandbox)
        check("control run with an ffmpeg folder beside the exe captured",
              res2 is not None and res2["ok"])
        if res2 and res2["ok"]:
            log2 = res2["img"].crop((fx + lx, fy + ly, fx + lx + lw, fy + ly + lh))
            log2.save(os.path.join(HERE, "_shot_bundled_beside_log.png"))
            geom2 = text_lines(log2)
            d2 = signature_distance(ink_signature(log2), ink_signature(ref_log))
            print("  control log rows: %d, ink distance vs bundled %.3f"
                  % (len(geom2), d2))
            if geom2 and ref_geom:
                w_ref = ref_geom[0][3] - ref_geom[0][2]
                w_bes = geom2[0][3] - geom2[0][2]
                print("  row 1 ink width: bundled %d px -> beside %d px" % (w_ref, w_bes))
                print("  expected beside row 1 text: %s"
                      % "ffmpeg: beside the program (%s)"
                        % os.path.join(sandbox, "ffmpeg", "ffmpeg.exe"))
                check("an ffmpeg folder beside the exe visibly changes the log",
                      w_bes > w_ref * 1.5, "%d vs %d" % (w_bes, w_ref))
            check("beside-override log differs from the bundled log", d2 > 0.12,
                  "ink distance %.3f" % d2)
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def main():
    mod = load_module()
    print("APP_VERSION = %s   FFMPEG_SOURCE = %s   FFMPEG_CMD = %s"
          % (mod.APP_VERSION, mod.FFMPEG_SOURCE, mod.FFMPEG_CMD))

    part_a()
    part_b(mod)
    log_rect, ref_img, ref_lines, client = part_c()
    part_d()
    if log_rect and ref_img is not None:
        part_e(ref_img, ref_lines, log_rect, client)

    print()
    if failures:
        print("FAILURES (%d): %s" % (len(failures), "; ".join(failures)))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
