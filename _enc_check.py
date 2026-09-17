"""Verify the encoder picker: detection, default choice, greyed-out entries, click blocking."""
import ctypes
import importlib.machinery
import importlib.util
import os
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "av1_batch_converter.pyw")
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77

loader = importlib.machinery.SourceFileLoader("av1conv", SRC)
spec = importlib.util.spec_from_loader("av1conv", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

mod._enable_dpi_awareness()
root = mod.TkinterDnD.Tk()
app = mod.ConverterGUI(root)
root.geometry("+120+80")
root.deiconify()
root.update_idletasks()
root.update()
root.attributes("-topmost", True)
root.update()

user32 = ctypes.windll.user32

print("=== detection ===")
for backend in mod.ENCODER_BACKENDS:
    print(f"  {backend['label']:<22} {app.encoder_availability[backend['key']]}")
print(f"  selected by default : {app.encoder_var.get()}")
print(f"  active backend key  : {app._active_backend_key}")


def open_dropdown():
    root.tk.call("ttk::combobox::Post", app.encoder_combo._w)
    root.update()
    time.sleep(0.35)
    root.update()


def lb(*args):
    return root.tk.call(app._dropdown_listbox_path(), *[str(a) for a in args])


def tkc(*args):
    return root.tk.call(*[str(a) for a in args])


def screenshot(path):
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    full = ImageGrab.grab(all_screens=True)
    x, y = int(tkc("winfo", "rootx", app._dropdown_listbox_path())), \
        int(tkc("winfo", "rooty", app._dropdown_listbox_path()))
    w, h = int(tkc("winfo", "width", app._dropdown_listbox_path())), \
        int(tkc("winfo", "height", app._dropdown_listbox_path()))
    crop = full.crop((x - vx - 4, y - vy - 4, x - vx + w + 4, y - vy + h + 4))
    crop.save(path)
    return crop, (w, h)


open_dropdown()
count = int(lb("size"))
print(f"\n=== dropdown (size={count}) ===")
for i in range(count):
    print(f"  [{i}] {lb('get', i):<22} fg={lb('itemcget', i, '-foreground')!r}")

print("\n=== can itemconfigure reach this listbox at all? ===")
path = app._dropdown_listbox_path()
try:
    root.tk.call(path, "itemconfigure", "0", "-foreground", "#ff0000")
    print(f"  after direct itemconfigure: fg={root.tk.call(path, 'itemcget', '0', '-foreground')!r}")
except Exception as exc:
    print(f"  direct itemconfigure failed: {exc}")

app._grey_unavailable_items()
print("  after _grey_unavailable_items():")
for i in range(count):
    print(f"    [{i}] fg={lb('itemcget', i, '-foreground')!r}")
app._probe_encoders() if False else None

crop, (lw, lh) = screenshot(os.path.join(HERE, "_shot_dropdown.png"))
px = crop.convert("RGB").load()

rows_per_item = (lh - 8) / max(1, count)
print(f"\n=== brightest text pixel per row (grey entries are dimmer) [{lw}x{lh}] ===")
for i in range(count):
    yy = min(max(int(4 + rows_per_item * (i + 0.5)), 0), crop.height - 1)
    brightest = 0
    for xx in range(4, crop.width - 2):
        r, g, b = px[xx, yy]
        brightest = max(brightest, (r + g + b) // 3)
    usable = app.encoder_availability[mod.ENCODER_BACKENDS[i]["key"]]
    print(f"  [{i}] {lb('get', i):<22} brightest={brightest:3d}  expected={'bright' if usable else 'dim'}")

print("\n=== click blocking ===")


def click_item(index, label):
    open_dropdown()
    box = lb("bbox", index)
    if not box:
        print(f"  {label}: no bbox for index {index}")
        return
    bx, by, bw, bh = [int(v) for v in box]
    before = app.encoder_var.get()
    path = app._dropdown_listbox_path()
    event = lambda kind: tkc("event", "generate", path, kind, "-x", bx + 3, "-y", by + bh // 2)
    event("<ButtonPress-1>")
    root.update()
    event("<ButtonRelease-1>")
    root.update()
    time.sleep(0.25)
    root.update()
    after = app.encoder_var.get()
    changed = "CHANGED" if before != after else "blocked"
    print(f"  click [{index}] {label:<22} {before!r} -> {after!r}  [{changed}]")
    app._on_encoder_selected()


click_item(2, "Intel iGPU (QSV)")
click_item(1, "AMD GPU (AMF)")
click_item(3, "CPU (SVT-AV1)")
click_item(0, "NVIDIA GPU (NVENC)")
print(f"  final selection: {app.encoder_var.get()}")

print("\n=== ffmpeg args per backend ===")
for backend in mod.ENCODER_BACKENDS:
    print(f"  {backend['key']:<7} {' '.join(mod.build_ffmpeg_args(backend['key']))}")

root.destroy()
