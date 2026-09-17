"""Dev-only: render the converter GUI, capture dark + light + tooltip, and sample colors."""
import ctypes
import importlib.machinery
import importlib.util
import os
import sys
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "av1_batch_converter.pyw")
MODE = sys.argv[1] if len(sys.argv) > 1 else "dark"

loader = importlib.machinery.SourceFileLoader("av1conv", SRC)
spec = importlib.util.spec_from_loader("av1conv", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

_orig_theme = mod.apply_window_theme
mod.apply_window_theme = lambda root, mode=MODE: _orig_theme(root, MODE)

mod._enable_dpi_awareness()
root = mod.TkinterDnD.Tk()
app = mod.ConverterGUI(root)
mod.apply_window_theme = _orig_theme  # only force the initial mode at construction

SAMPLES = [
    r"D:\Camera\2026-08-12\DSC_02941.mov",
    r"F:\录屏\obs\tutorial_part3.mkv",
    r"D:\Camera\2026-08-12\DSC_02942.mov",
    r"F:\Downloads\some really long filename that should be readable here.webm",
    r"E:\archive\old_clip.avi",
    r"D:\Camera\2026-08-12\DSC_02943.mov",
]
for p in SAMPLES:
    app.file_list.append(p)
    app.listbox.insert("end", p)
app.listbox.selection_set(1)
app._log("Start conversion: 6 files, max 2 concurrent")
app._log("Done: " + SAMPLES[0].replace(".mov", ".mp4"))
app.progress.config(maximum=6, value=2)
app.status_var.set("Processing 2/6")

root.geometry("+140+90")
root.deiconify()
root.update_idletasks()
root.update()
root.lift()
root.attributes("-topmost", True)
root.update()


def capture(tag, extra_note=""):
    root.update()
    time.sleep(0.9)
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    rect = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
    x, y = rect.left, rect.top
    w, h = rect.right - rect.left, rect.bottom - rect.top
    from PIL import ImageGrab

    img = ImageGrab.grab(bbox=(x - 10, y - 10, x + w + 20, y + h + 30), all_screens=True)
    out = os.path.join(HERE, f"_shot_{tag}.png")
    img.save(out)
    print(f"\n=== {tag} {extra_note} -> {out} {img.size}")

    rgb = img.convert("RGB")
    px = rgb.load()
    tot = light = n = 0
    for sy in range(0, rgb.height, 3):
        for sx in range(0, rgb.width, 3):
            r, g, b = px[sx, sy]
            v = (r + g + b) // 3
            tot += v
            n += 1
            if v > 200:
                light += 1
    print(f"  avg brightness {tot/n:.1f}   light%% {100*light/n:.2f}")
    print("  titlebar #%02x%02x%02x" % px[460, 25])

    def walk(w):
        yield w
        for c in w.winfo_children():
            yield from walk(c)

    def probe(name, wd):
        rx = wd.winfo_rootx() - (x - 10)
        ry = wd.winfo_rooty() - (y - 10)
        ww, hh = wd.winfo_width(), wd.winfo_height()
        if ww < 2 or hh < 2:
            return
        cx, cy = rx + ww // 2, ry + hh // 2
        if not (0 <= cx < rgb.width and 0 <= cy < rgb.height):
            return
        print("  %-22s rect=(%d,%d,%dx%d) #%02x%02x%02x" % (name, rx, ry, ww, hh, *px[cx, cy]))

    for wd in walk(root):
        cls = wd.winfo_class()
        if cls in ("Frame", "TFrame", "Labelframe", "TLabelframe", "Toplevel"):
            continue
        probe(f"{cls}:{str(wd)[-6:]}", wd)


capture(f"{MODE}_initial")

app.theme_btn.event_generate("<Enter>")
root.update()
time.sleep(0.75)
root.update()
tip = app.theme_tooltip.tip
print(f"\ntooltip visible: {tip is not None}")
if tip is not None:
    tip.update_idletasks()
    from PIL import ImageGrab

    tr, tg = tip.winfo_rootx(), tip.winfo_rooty()
    tw, th = tip.winfo_width(), tip.winfo_height()
    shot = ImageGrab.grab(bbox=(tr, tg, tr + tw, tg + th), all_screens=True)
    shot.save(os.path.join(HERE, "_shot_tooltip.png"))
    pxs = shot.convert("RGB").load()
    print("  tooltip size %dx%d  inner=#%02x%02x%02x  center=#%02x%02x%02x"
          % (tw, th, *pxs[3, 3], *pxs[tw // 2, th // 2]))
app.theme_btn.event_generate("<Leave>")
root.update()
time.sleep(0.2)

app._toggle_theme()
print(f"\nafter toggle: theme_mode={app.theme_mode}")
capture(f"{MODE}_toggled", "(after clicking the toggle)")

root.destroy()
