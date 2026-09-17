"""Check that the UI actually scales with the monitor DPI.

Deliberately desktop-friendly: the window is withdrawn before the widgets are built,
so nothing appears on screen and the cursor is never moved. The scale is driven by
calling apply_dpi_scaling() with explicit DPI values, which is the same path the
monitor-change poll takes.

This machine has 96 DPI (2560x1440) and 144 DPI (3840x2160) displays, so 96 and 144
are the two values that matter in practice. 192 is included as a sanity check.
"""
import importlib.machinery
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "av1_batch_converter.pyw")

loader = importlib.machinery.SourceFileLoader("av1conv", SRC)
spec = importlib.util.spec_from_loader("av1conv", loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

mod._enable_dpi_awareness()
root = mod.TkinterDnD.Tk()
root.withdraw()  # keep it off the desktop for the whole run
app = mod.ConverterGUI(root)
root.update()

failures = []


def failing(msg):
    failures.append(msg)
    print(f"  !! FAIL: {msg}")


def measure(tag):
    """Measure real rendered geometry - font actual()['size'] is not reliable here."""
    import tkinter.font as tkfont
    root.update_idletasks()
    body = tkfont.nametofont("TkDefaultFont")
    row = {
        "scale": mod.dpi_scale(),
        "tk_scaling": round(float(root.tk.call("tk", "scaling")), 4),
        "geometry": root.geometry().split("+")[0],
        "body_linespace": body.metrics("linespace"),
        "body_text_w": body.measure("MMMMMMMMMM"),
        "title_h": app.title_label.winfo_reqheight(),
        "log_h": app.log_box.winfo_reqheight(),
        "icon_px": int(app.theme_btn.cget("width")),
        "english_btn_w": app.add_folder_btn.winfo_reqwidth(),
        "window_req_h": app.frame.winfo_reqheight(),
    }
    print(f"\n[{tag}]")
    for k, v in row.items():
        print(f"    {k:<15} = {v}")
    return row


base = measure("start (96 DPI design size)")

# A withdrawn Tk toplevel silently ignores geometry() size changes, so the requested
# size has to be captured on the way in rather than read back.
geometry_calls = []
_real_geometry = root.geometry


def spy_geometry(spec=None):
    if spec:
        geometry_calls.append(spec)
    return _real_geometry(spec) if spec else _real_geometry()


root.geometry = spy_geometry

print("\n" + "=" * 70)
print("simulate dragging the window onto the 150% 4K display")
print("=" * 70)
mod.apply_dpi_scaling(root, 144)
app._rescale_ui(1.0)
hi = measure("after rescale to 144 DPI")

# Integer font metrics mean the ratios land near, not exactly on, the DPI factor
# (a 12px line box becomes 25px, not 18px), so a band is the honest assertion.
ratio = 144 / 96.0
for key, label in (("body_linespace", "body line height"), ("body_text_w", "body text width"),
                   ("title_h", "title height"), ("icon_px", "icon button"),
                   ("english_btn_w", "button width"), ("window_req_h", "layout height")):
    got = hi[key] / base[key]
    print(f"  {label:<16} {base[key]} -> {hi[key]}  (ratio {got:.3f}, expected {ratio:.3f})")
    if not (1.35 <= got <= 1.70):
        failing(f"{label} did not scale by ~{ratio:.2f}: {base[key]} -> {hi[key]}")

bw, bh = map(int, base["geometry"].split("x"))
print(f"  baseline window size = {bw}x{bh}")
print(f"  geometry requests    = {geometry_calls}")
want = f"{int(round(bw * ratio))}x{int(round(bh * ratio))}"
if not geometry_calls:
    failing("the rescale never asked for a new window size")
elif geometry_calls[-1] != want:
    failing(f"expected a window size of {want}, got {geometry_calls[-1]}")
else:
    print(f"  ok: asked for {want} - a withdrawn Tk window ignores geometry() size "
          f"changes, so the request itself is what can be checked")

print("\n" + "=" * 70)
print("simulate dragging it back to the 100% display")
print("=" * 70)
mod.apply_dpi_scaling(root, 96)
app._rescale_ui(144 / 96.0)
back = measure("after rescale back to 96 DPI")
for key in ("body_linespace", "body_text_w", "title_h", "log_h", "icon_px",
            "english_btn_w", "window_req_h"):
    if back[key] != base[key]:
        failing(f"{key} did not return to {base[key]}: {back[key]}")
if back["geometry"] != base["geometry"]:
    failing(f"window size did not return to {base['geometry']}: {back['geometry']}")
if mod.dpi_scale() != 1.0:
    failing(f"scale did not return to 1.0: {mod.dpi_scale()}")

print("\n" + "=" * 70)
print("state must survive the rebuild")
print("=" * 70)
app.file_list = ["D:/a.mp4", "D:/b.mkv"]
for p in app.file_list:
    app.listbox.insert("end", p)
app.concurrent_var.set(3)
app._log("sentinel log line")
mod.apply_dpi_scaling(root, 144)
app._rescale_ui(1.0)
root.update_idletasks()
print(f"  file list   = {list(app.listbox.get(0, 'end'))}")
print(f"  concurrent  = {app.concurrent_var.get()}")
print(f"  log kept    = {'sentinel log line' in app.log_box.get('1.0', 'end')}")
print(f"  encoder     = {app.encoder_var.get()!r}")
print(f"  status      = {app.status_var.get()!r}")
print(f"  language    = {app.language!r}")
if list(app.listbox.get(0, "end")) != app.file_list:
    failing("the file list did not survive the rebuild")
if app.concurrent_var.get() != 3:
    failing("the concurrency value did not survive the rebuild")
if "sentinel log line" not in app.log_box.get("1.0", "end"):
    failing("the log did not survive the rebuild")
if not app.encoder_var.get():
    failing("the encoder selection did not survive the rebuild")
if app._active_backend_key is None:
    failing("the active backend key was lost in the rebuild")

# ---- the window title is the new name ------------------------------------
print(f"\nwindow title = {root.title()!r}")
if root.title() != "AV1 Batch Converter":
    failing(f"unexpected title {root.title()!r}")
if "NVENC" in root.title():
    failing("the title still mentions NVENC while AMD/Intel/CPU are supported")

root.destroy()

print("\n" + "=" * 70)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
else:
    print("RESULT: ALL CHECKS PASSED")
sys.exit(1 if failures else 0)
