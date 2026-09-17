"""Screenshot the window at full and minimum size and check the action row for overflow."""
import ctypes
import importlib.machinery
import importlib.util
import os
import time

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
root.deiconify()
root.update_idletasks()
root.update()
root.attributes("-topmost", True)
root.update()

user32 = ctypes.windll.user32


def shot(tag):
    root.update()
    time.sleep(0.7)
    root.update()
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    full = ImageGrab.grab(all_screens=True)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    crop = full.crop((x - vx, y - vy, x - vx + w, y - vy + h))
    crop.save(os.path.join(HERE, f"_shot_{tag}.png"))
    print(f"\n[{tag}] window {w}x{h} -> _shot_{tag}.png")
    return crop


def check_row(tag):
    combo = app.encoder_combo
    row = combo.master
    print(f"  action row width={row.winfo_width()}")
    for child in row.winfo_children():
        right = child.winfo_x() + child.winfo_width()
        text = ""
        try:
            text = child.cget("text")
        except Exception:
            text = ""
        flag = "OVERFLOW" if right > row.winfo_width() else "ok"
        print(f"    {child.winfo_class():<12} x={child.winfo_x():4d} w={child.winfo_width():4d} "
              f"right={right:4d} {flag:<9} {text}")
    print(f"  combo visible: {combo.winfo_ismapped()}  value={app.encoder_var.get()!r}")


root.geometry("900x650+120+70")
shot("enc_wide")
check_row("wide")

root.geometry("700x450+120+70")
shot("enc_narrow")
check_row("narrow")

root.geometry("900x650+120+70")
app._toggle_theme()
shot("enc_light")
check_row("light")

print(f"\nlight theme colors: text={app.theme['text']} text_dim={app.theme['text_dim']}")
app.encoder_combo.event_generate("<Button-1>")
root.update()
time.sleep(0.4)
root.update()
path = app._dropdown_listbox_path()
print("  dropdown after theme switch:")
for i in range(int(root.tk.call(path, "size"))):
    print(f"    [{i}] {root.tk.call(path, 'get', str(i)):<22} fg={root.tk.call(path, 'itemcget', str(i), '-foreground')!r}")

root.destroy()
