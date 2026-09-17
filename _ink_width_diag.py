"""Diagnose the drawn-vs-measured glyph width of each toolbar caption.

Run when _make_docs_shots.py reports a width mismatch: it prints the ink extent
obtained at several deviation thresholds, so it is obvious whether a mismatch is
a real layout problem or just an anti-aliased edge falling under the threshold.
"""

import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image

import _make_docs_shots as M


def ink_width(img, rect, threshold, inset=4):
    x, y, w, h = rect
    crop = img.crop((x + inset, y + inset, x + w - inset, y + h - inset)).convert("L")
    px = list(crop.getdata())
    cw, ch = crop.size
    bg = sorted(px)[len(px) // 2]
    cols = [False] * cw
    for yy in range(ch):
        row = yy * cw
        for xx in range(cw):
            if abs(px[row + xx] - bg) > threshold:
                cols[xx] = True
    nz = [i for i, v in enumerate(cols) if v]
    return (nz[-1] - nz[0] + 1) if nz else 0


def main():
    mod = M.load_app_module()
    mod._enable_dpi_awareness()
    import tkinter.font as tkfont

    root = mod.TkinterDnD.Tk()
    root.withdraw()
    app = mod.ConverterGUI(root)
    hwnd = M.find_by_title(require_visible=False)
    if not hwnd:
        print("no window")
        return 1
    ex = M.user32.GetWindowLongW(hwnd, M.GWL_EXSTYLE)
    M.user32.SetWindowLongW(hwnd, M.GWL_EXSTYLE, ex | M.WS_EX_NOACTIVATE)
    root.geometry("+40+40")
    root.deiconify()
    M.pump(root, 11.0)

    style = mod.ttk.Style(root)
    font = tkfont.Font(root=root, font=style.lookup("TButton", "font"))
    origin = M.window_origin(hwnd)

    for lang in mod.LANGUAGES:
        if not M.switch_language(app, root, mod, lang):
            continue
        img = M.grab(hwnd)
        print("--- %s (button font %s)" % (lang, font.actual()))
        for attr, key in M.TOOLBAR:
            widget = getattr(app, attr)
            rect = M.widget_rect(origin, widget)
            caption = mod.STRINGS[lang][key]
            want = font.measure(caption)
            got = {t: ink_width(img, rect, t) for t in (40, 25, 15, 8)}
            print("  %-14s %-16r btn_w=%3d measured=%3d  ink@40/25/15/8 = %s"
                  % (key, caption, rect[2], want,
                     "/".join(str(got[t]) for t in (40, 25, 15, 8))))

    root.destroy()
    return 0


if __name__ == "__main__":
    sys.exit(main())
