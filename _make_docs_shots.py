"""Render the README screenshots, one pair per UI language.

Each README is written for one language, so it has to show *that* language's UI:
English README -> English screenshots, and so on. This renders all three pairs
(zh / ja / en x dark / light) from the application itself.

Nothing here touches the user's mouse or the foreground:

* The language is changed by calling ``ConverterGUI._toggle_language()`` and the
  theme by ``_toggle_theme()``. Posted WM_LBUTTONDOWN messages are ignored by Tk
  for non-foreground windows, and real synthetic clicks need the foreground plus
  cursor movement.
* The window is mapped with ``WS_EX_NOACTIVATE`` so it never takes focus, and
  captured with ``PrintWindow``, which renders occluded windows.

Because a screenshot that silently shows the wrong language would be worse than
no screenshot, every render is tied back to real widget text before it is saved:
the button and label captions are read out of the live widgets and compared with
the target language's ``STRINGS`` entries.
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

# Widget attribute -> the STRINGS key whose text it must be showing.
CAPTIONS = (
    ("add_folder_btn", "add_folder"),
    ("add_files_btn", "add_files"),
    ("load_list_btn", "load_list"),
    ("remove_btn", "remove_selected"),
    ("clear_btn", "clear_list"),
    ("start_btn", "start_conversion"),
    ("stop_btn", "stop_conversion"),
    ("concurrent_label", "max_concurrent"),
    ("encoder_label", "encoder"),
)

# The subset whose rendered pixel width is measured back out of the screenshot.
TOOLBAR = (
    ("add_folder_btn", "add_folder"),
    ("add_files_btn", "add_files"),
    ("load_list_btn", "load_list"),
    ("remove_btn", "remove_selected"),
    ("clear_btn", "clear_list"),
)

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
    which reports a client-sized rect and has no caption. The window carrying the
    title bar is the one enumerated by title, so look it up there.
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


def client_crop(img):
    return img.crop((CLIENT_OFFSET[0], CLIENT_OFFSET[1],
                     CLIENT_OFFSET[0] + CLIENT_SIZE[0],
                     CLIENT_OFFSET[1] + CLIENT_SIZE[1]))


def mean_luma(img):
    px = list(img.convert("L").getdata())
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


def window_origin(hwnd):
    rect = wt.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top


def widget_rect(origin, widget):
    """Image-space rect of a widget, from Tk's own screen coordinates."""
    x = widget.winfo_rootx() - origin[0]
    y = widget.winfo_rooty() - origin[1]
    return x, y, widget.winfo_width(), widget.winfo_height()


def text_ink_width(img, rect, inset=4):
    """Width in pixels of the glyphs drawn inside ``rect``.

    Inset past the button border so only the caption contributes ink.
    """
    x, y, w, h = rect
    crop = img.crop((x + inset, y + inset, x + w - inset, y + h - inset)).convert("L")
    px = list(crop.getdata())
    cw, ch = crop.size
    sample = sorted(px)
    bg = sample[len(sample) // 2]
    cols = [False] * cw
    for yy in range(ch):
        row = yy * cw
        for xx in range(cw):
            if abs(px[row + xx] - bg) > 40:
                cols[xx] = True
    nz = [i for i, v in enumerate(cols) if v]
    return (nz[-1] - nz[0] + 1) if nz else 0


def switch_language(app, root, mod, target):
    """Cycle the language button until the UI is in ``target``."""
    for _ in range(len(mod.LANGUAGES) + 1):
        if app.language == target:
            pump(root, 0.5)
            return True
        app._toggle_language()
        pump(root, 0.5)
    return False


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

    ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE)

    root.geometry("+40+40")
    root.deiconify()
    # The startup encoder probe takes a few seconds and appends its result to the
    # log box; wait it out so every shot has the same settled content.
    pump(root, 11.0)

    ox, oy, ow, oh = client_offset(hwnd)
    client = (ow - 2 * ox, oh - ox - oy)
    check("client-area offset is %s" % (CLIENT_OFFSET,), (ox, oy) == CLIENT_OFFSET,
          "offset (%d, %d)" % (ox, oy))
    check("client area is %dx%d" % CLIENT_SIZE, client == CLIENT_SIZE,
          "client %dx%d" % client)
    check("window is not foreground", user32.GetForegroundWindow() != hwnd)

    print("      initial language from the system: %s" % app.language)
    initial_lang = app.language

    # ttk.Button draws with the font configured on the TButton style, so measure
    # the captions with that exact font to get the expected glyph widths.
    import tkinter.font as tkfont
    style = mod.ttk.Style(root)
    btn_font = tkfont.Font(root=root, font=style.lookup("TButton", "font"))

    shots = {}
    for lang in mod.LANGUAGES:
        check("UI switched to %s" % lang, switch_language(app, root, mod, lang),
              "app.language = %s" % app.language)

        # The conclusive check: the captions on screen really are this language's.
        mismatches = []
        for attr, key in CAPTIONS:
            shown = str(getattr(app, attr).cget("text"))
            want = mod.STRINGS[lang][key]
            if shown != want:
                mismatches.append("%s: %r != %r" % (attr, shown, want))
        check("%s: visible captions match STRINGS[%s]" % (lang, lang), not mismatches,
              "; ".join(mismatches[:3]))

        dark = grab(hwnd)
        check("%s: dark render is dark" % lang, mean_luma(dark) < 90,
              "mean luma %.1f" % mean_luma(dark))

        # The pixels must agree with those captions: the glyphs actually drawn
        # inside each toolbar button should be as wide as Tk measures that string.
        #
        # Font.measure() sums advance widths, which include each glyph's side
        # bearings, while the ink extent counts only painted pixels -- and CJK
        # glyphs leave more side bearing than Latin ones. So the drawn width is
        # allowed to fall a little short, proportionally. A caption from the
        # wrong language is off by 30% or more, so this still catches it.
        origin = window_origin(hwnd)
        width_errors = []
        for attr, key in TOOLBAR:
            widget = getattr(app, attr)
            drawn = text_ink_width(dark, widget_rect(origin, widget))
            expected = btn_font.measure(mod.STRINGS[lang][key])
            tolerance = max(2, round(0.06 * expected))
            if abs(drawn - expected) > tolerance:
                width_errors.append("%s drawn %d vs measured %d (tol %d)"
                                    % (key, drawn, expected, tolerance))
        check("%s: drawn glyph widths match the captions" % lang, not width_errors,
              "; ".join(width_errors[:3]))

        app._toggle_theme()
        pump(root, 1.2)
        light = grab(hwnd)
        check("%s: light render is light" % lang, mean_luma(light) > 170,
              "mean luma %.1f" % mean_luma(light))

        app._toggle_theme()
        pump(root, 1.2)
        back = grab(hwnd)
        d = distance(signature(client_crop(back)), signature(client_crop(dark)))
        check("%s: theme round-trips back to dark" % lang, d < 0.05,
              "ink distance %.3f" % d)

        client_crop(dark).save(os.path.join(DOCS, "screenshot-dark-%s.png" % lang))
        client_crop(light).save(os.path.join(DOCS, "screenshot-light-%s.png" % lang))
        shots[lang] = (dark, light)
        dark.save(os.path.join(HERE, "_shot_docs_dark_%s_full.png" % lang))
        light.save(os.path.join(HERE, "_shot_docs_light_%s_full.png" % lang))

    # The three languages all render the same layout, so a caption swap is the
    # only reason their captures should differ -- but they must differ.
    distinct = len({mod.STRINGS[l]["add_folder"] for l in mod.LANGUAGES})
    check("the three languages have distinct captions", distinct == 3,
          "%d distinct add_folder strings" % distinct)

    sigs = {l: signature(client_crop(shots[l][0])) for l in mod.LANGUAGES}
    for i, a in enumerate(mod.LANGUAGES):
        for b in mod.LANGUAGES[i + 1:]:
            d = distance(sigs[a], sigs[b])
            check("%s and %s renders differ" % (a, b), d > 0.10,
                  "ink distance %.3f" % d)

    # The packaged exe starts in the system language, so it is a fair reference
    # for that one language only. Read it before the loop changes anything.
    ref_lang = initial_lang
    if os.path.isfile(EXE_CAPTURE) and ref_lang in shots:
        exe = client_crop(Image.open(EXE_CAPTURE).convert("RGB"))
        d = distance(signature(exe), signature(client_crop(shots[ref_lang][0])))
        check("source and exe render the %s dark theme identically" % ref_lang,
              d < 0.05, "ink distance %.3f" % d)

    for lang in mod.LANGUAGES:
        for theme in ("dark", "light"):
            name = "screenshot-%s-%s.png" % (theme, lang)
            img = Image.open(os.path.join(DOCS, name))
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
