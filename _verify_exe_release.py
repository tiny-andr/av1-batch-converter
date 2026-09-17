"""Post-rebuild sanity check for the packaged exe.

Launches the exe, waits for its window, and captures the client area with
PrintWindow(PW_RENDERFULLCONTENT). PrintWindow works on occluded windows, so
this never needs to steal the foreground or move the mouse.

Compares the capture against the client area of a previously verified
screenshot using the ink-signature metric, then reports the embedded version
resource read straight out of the PE file.
"""

import ctypes
import ctypes.wintypes as wt
import os
import struct
import subprocess
import sys
import time

from PIL import Image, ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))
EXE = os.path.join(HERE, "dist", "av1_batch_converter.exe")
REFERENCE = os.path.join(HERE, "_shot_exe_i18n_1_start.png")
CROP_OFFSET = (8, 31)          # client-area offset inside the reference screenshot
CROP_SIZE = (900, 650)         # client area at 100% scaling

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))   # PER_MONITOR_AWARE_V2

PW_RENDERFULLCONTENT = 0x00000002

failures = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  -> " + detail) if detail else ""))
    if not ok:
        failures.append(name)


def wait_for_window(timeout=40.0):
    """Find the app window by title.

    The exe is a PyInstaller onefile bundle: Popen gives us the bootstrap
    parent, and the real Tk window belongs to its child process, so matching on
    the parent PID finds nothing. Match on the window title instead.
    """
    hwnds = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            if "AV1 Batch Converter" in buf.value:
                hwnds.append(hwnd)
        return True

    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnds.clear()
        user32.EnumWindows(enum_proc, 0)
        if hwnds:
            return hwnds[0]
        time.sleep(0.5)
    return None


def grab_window(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetWindowDC(hwnd)
    memdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(memdc, bmp)
    ok = user32.PrintWindow(hwnd, memdc, PW_RENDERFULLCONTENT)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD),
                    ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]

    bi = BITMAPINFOHEADER()
    bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.biWidth, bi.biHeight = w, -h
    bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(memdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(memdc)
    user32.ReleaseDC(hwnd, hdc)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    return ok, img


def client_crop(img, hwnd):
    """Crop the client area out of a full-window capture.

    PrintWindow returns the whole window including the non-client frame, while
    the reference shots were cropped to the client area. Map client (0,0) to
    screen space and subtract the window origin so both sides line up.
    """
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    origin = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    left = origin.x - rect.left
    top = origin.y - rect.top
    cw, ch = img.size[0] - left, img.size[1] - top
    return img.crop((left, top, left + min(cw, CROP_SIZE[0]), top + min(ch, CROP_SIZE[1])))


def ink_signature(img):
    """Per-column count of pixels deviating from the background median.

    Sparse UI text changes only a few percent of raw pixels, so a plain
    pixel-difference ratio is blind to it. The column profile is not.
    """
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


def pe_product_version(path):
    """Read the four version words out of VS_FIXEDFILEINFO."""
    with open(path, "rb") as fh:
        data = fh.read()
    needle = struct.pack("<II", 0xFEEF04BD, 0x00010000)
    off = data.find(needle)
    if off < 0:
        return None
    fv_ms, fv_ls, pv_ms, pv_ls = struct.unpack_from("<IIII", data, off + 8)
    return ((fv_ms >> 16) & 0xFFFF, fv_ms & 0xFFFF,
            (fv_ls >> 16) & 0xFFFF, fv_ls & 0xFFFF)


def main():
    check("packaged exe exists", os.path.isfile(EXE), EXE)

    words = pe_product_version(EXE)
    check("PE version resource present", words is not None, str(words))
    if words:
        ver = "%d.%d.%d.%d" % (words[0], words[1], words[2], words[3])
        check("PE file version is 1.0.1", ver.startswith("1.0.1"), ver)

    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    hwnd = wait_for_window()
    check("window appeared", hwnd is not None)
    if hwnd is None:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return report()

    # Let the startup encoder probe finish so the log has its final content.
    time.sleep(9.0)
    check("process still alive after startup", proc.poll() is None)

    ok, img = grab_window(hwnd)
    check("PrintWindow succeeded", bool(ok))
    img.save(os.path.join(HERE, "_shot_release_capture.png"))
    check("capture is not blank", len(set(img.getdata())) > 20,
          "%d distinct colours" % len(set(img.getdata())))

    if os.path.isfile(REFERENCE):
        ref = Image.open(REFERENCE).convert("RGB")
        ref = ref.crop((CROP_OFFSET[0], CROP_OFFSET[1],
                        CROP_OFFSET[0] + CROP_SIZE[0], CROP_OFFSET[1] + CROP_SIZE[1]))
        ref.save(os.path.join(HERE, "_shot_release_reference.png"))
        cap = client_crop(img, hwnd)
        cap.save(os.path.join(HERE, "_shot_release_capture_client.png"))
        check("client area size matches the reference", cap.size == ref.size,
              "%s vs %s" % (cap.size, ref.size))
        dist = signature_distance(ink_signature(cap), ink_signature(ref))
        check("client area matches the verified build", dist < 0.12,
              "ink distance %.3f" % dist)

    # A rebuilt onefile exe spawns a child; terminate the whole tree.
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    check("process tree cleaned up", proc.poll() is not None)
    return report()


def report():
    print()
    if failures:
        print("FAILURES: " + ", ".join(failures))
    else:
        print("ALL CHECKS PASSED")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
