"""Check that no language makes a widget overflow its row, and that the
Japanese labels (usually the widest) still fit at the minimum window size."""
import importlib.machinery
import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "av1_batch_converter.pyw")

loader = importlib.machinery.SourceFileLoader("av1conv", SRC)
spec = importlib.util.spec_from_loader("av1conv", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

mod._enable_dpi_awareness()
root = mod.TkinterDnD.Tk()
app = mod.ConverterGUI(root)
root.deiconify()
# Keep the window mapped - a withdrawn Tk toplevel ignores geometry() changes, so the
# narrow-window test would measure nothing. A fully transparent window is the way to
# stay out of the user's way and still get real layout numbers.
root.attributes("-alpha", 0.0)
root.update_idletasks()
root.update()

problems = []


def audit(tag):
    print(f"\n[{tag}] window {root.winfo_width()}x{root.winfo_height()}")
    for row in (app.add_folder_btn.master,):
        for child in row.winfo_children():
            right = child.winfo_x() + child.winfo_width()
            req = child.winfo_reqwidth()
            text = child.cget("text") if "text" in child.keys() else ""
            over = right > row.winfo_width()
            clipped = child.winfo_width() < req
            flag = "OVERFLOW" if over else ("CLIPPED" if clipped else "ok")
            if over or clipped:
                problems.append(f"{tag}: {child.winfo_class()} {text!r} {flag}")
            print(f"    {flag:<9} x={child.winfo_x():4d} w={child.winfo_width():4d} "
                  f"req={req:4d} right={right:4d} {text!r}")


sizes = {"default": "900x650+120+70", "min": "700x450+120+70", "tiny": "620x400+120+70"}
for size_name, geom in sizes.items():
    for lang in mod.LANGUAGES:
        while app.language != lang:
            app._toggle_language()
            root.update()
        root.geometry(geom)
        root.update_idletasks()
        root.update()
        audit(f"{lang} / {size_name}")
        print(f"      status={app.status_var.get()!r} encoder={app.encoder_var.get()!r}")

root.destroy()

print("\n" + "=" * 60)
if problems:
    print(f"{len(problems)} problem(s):")
    for p in problems:
        print("  -", p)
else:
    print("no overflow or clipping in any language / size")
