"""Verify the trilingual UI and the encoder-info log lines.

Checks, in order:
  1. system_language() result on this machine
  2. language button sits to the LEFT of the theme button
  3. cycling zh -> ja -> en rewrites every visible label
  4. encoder-info block is printed at startup and reprinted on encoder switch
  5. narrow window: header row still fits
Screenshots plus ASCII brightness maps go to _shot_i18n_*.png / stdout.
"""
import ctypes
import importlib.machinery
import importlib.util
import os
import time

from PIL import ImageGrab

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "av1_batch_converter.pyw")
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
ASCII_RAMP = " .:-=+*#%@"

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
failures = []


def fail(msg):
    failures.append(msg)
    print(f"  !! FAIL: {msg}")


def ascii_map(img, cols=104, rows=30):
    small = img.convert("L").resize((cols, rows))
    px = small.load()
    lines = []
    for y in range(rows):
        lines.append("".join(ASCII_RAMP[min(9, px[x, y] * 10 // 256)] for x in range(cols)))
    return "\n".join(lines)


def header_map(img, cols=70, rows=12):
    """Zoom into the top-right corner where the two icon buttons live."""
    w, h = img.size
    crop = img.crop((max(0, w - 190), 0, w, 46))
    small = crop.convert("L").resize((cols, rows))
    px = small.load()
    lines = []
    for y in range(rows):
        lines.append("".join(ASCII_RAMP[min(9, px[x, y] * 10 // 256)] for x in range(cols)))
    return "\n".join(lines)


def shot(tag):
    root.update()
    time.sleep(0.6)
    root.update()
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    full = ImageGrab.grab(all_screens=True)
    x, y = root.winfo_rootx(), root.winfo_rooty()
    w, h = root.winfo_width(), root.winfo_height()
    crop = full.crop((x - vx, y - vy, x - vx + w, y - vy + h))
    crop.save(os.path.join(HERE, f"_shot_i18n_{tag}.png"))
    print(f"\n[{tag}] window {w}x{h} -> _shot_i18n_{tag}.png")
    return crop


def visible_strings():
    return {
        "add_folder": app.add_folder_btn.cget("text"),
        "add_files": app.add_files_btn.cget("text"),
        "load_list": app.load_list_btn.cget("text"),
        "remove": app.remove_btn.cget("text"),
        "clear": app.clear_btn.cget("text"),
        "start": app.start_btn.cget("text"),
        "stop": app.stop_btn.cget("text"),
        "concurrent": app.concurrent_label.cget("text"),
        "encoder": app.encoder_label.cget("text"),
        "tip_drag": app.tip_label.cget("text"),
        "log_frame": app.log_frame.cget("text"),
        "status": app.status_var.get(),
    }


def log_text():
    return app.log_box.get("1.0", "end")


print("=" * 72)
print(f"system_language() = {mod.system_language()!r}")
print(f"app.language (at startup) = {app.language!r}")
if app.language != mod.system_language():
    fail("initial language does not follow the system language")
print("=" * 72)

# ---- layout: language button must be left of the theme button -------------
lang_x = app.lang_btn.winfo_rootx()
theme_x = app.theme_btn.winfo_rootx()
print(f"language button rootx={lang_x}  theme button rootx={theme_x}")
if lang_x >= theme_x:
    fail("language button is not left of the theme button")
else:
    print("  ok: language button is left of the theme button")

root.geometry("900x650+120+70")
root.update()

# ---- cycle through all three languages -----------------------------------
results = {}
for _ in range(len(mod.LANGUAGES) + 1):
    lang = app.language
    crop = shot(f"lang_{lang}")
    strings = visible_strings()
    results[lang] = strings
    print(f"\n--- language = {lang} ({mod.LANG_NAMES[lang]}) ---")
    for key, value in strings.items():
        print(f"  {key:<11} = {value!r}")
    print(f"  language icon label = {mod.LANG_LABELS[lang]!r}")
    print("  header (right 150px, zoomed):")
    print("\n".join("    " + line for line in header_map(crop).splitlines()))
    # every string must differ per language
    app._toggle_language()
    root.update()

# each language must render distinct text; the "stop" button is genuinely the same
# word in Chinese and Japanese, so it is exempt.
keys = [k for k in results["en"] if k != "stop"]
for key in keys:
    values = [results[lang][key] for lang in mod.LANGUAGES]
    if len(set(values)) != len(values):
        fail(f"string {key!r} is not unique per language: {values}")
print(f"\nper-language uniqueness on {len(keys)} strings: "
      f"{'ok' if not failures else 'see failures above'}")
print(f"  (exempt: stop = {[results[lang]['stop'] for lang in mod.LANGUAGES]}"
      f" - 停止 is valid in both ja and zh)")

# back to zh for the remaining checks
while app.language != "zh":
    app._toggle_language()
    root.update()

# ---- encoder-info block in the log --------------------------------------
print("\n" + "=" * 72)
print("encoder info block (zh):")
text = log_text()
print("\n".join("  | " + line for line in text.splitlines()))
for probe in ("av1_nvenc", "av1_amf", "av1_qsv", "libsvtav1"):
    print(f"  codec string {probe!r} present: {probe in text}")
if app._active_backend_key and mod.BACKENDS_BY_KEY.get(app._active_backend_key):
    args = " ".join(mod.BACKENDS_BY_KEY[app._active_backend_key]["args"])
    print(f"  active backend = {app._active_backend_key!r}")
    print(f"  its args       = {args!r}")
    if args not in text:
        fail("active backend args are missing from the log")
common = " ".join(mod.COMMON_ARGS)
print(f"  common args in log: {common in text}")
if common not in text:
    fail("common args are missing from the log")
for key in ("log_encoder_codec", "log_quality_args", "log_common_args"):
    marker = app._t(key).split("{")[0].rstrip().rstrip(":")
    if marker not in text:
        fail(f"startup log is missing the {key} line")
    else:
        print(f"  startup log has {key}: {marker!r}")

# ---- does switching the accelerator reprint the info? --------------------
print("\n" + "=" * 72)
usable = [b for b in mod.ENCODER_BACKENDS if app.encoder_availability.get(b["key"])]
print(f"usable backends: {[b['key'] for b in usable]}")
if len(usable) >= 2:
    before = log_text()
    target = next(b for b in usable if b["key"] != app._active_backend_key)
    print(f"switching accelerator -> {target['label']}")
    app.encoder_var.set(target["label"])
    app._on_encoder_selected()
    root.update()
    after = log_text()
    delta = after[len(before):]
    print("log lines appended by the switch:")
    print("\n".join("  + " + line for line in delta.splitlines() if line.strip()))
    # The labels are translated, so look them up through _t rather than matching English.
    for key, label in (("log_encoder_codec", "codec"), ("log_quality_args", "quality args"),
                       ("log_common_args", "common args")):
        marker = app._t(key).split("{")[0].rstrip().rstrip(":")
        if marker not in delta:
            fail(f"switching the accelerator did not reprint the {label} line "
                 f"(marker {marker!r})")
        else:
            print(f"  ok: {label} line reprinted (marker {marker!r})")
    target_args = " ".join(mod.BACKENDS_BY_KEY[target["key"]]["args"])
    if target_args not in delta:
        fail("the reprinted quality args do not match the new backend")
    else:
        print(f"  ok: reprinted args match the new backend ({target_args})")
    shot("encoder_switched")
else:
    print("  only one usable backend on this machine - skipping the switch test")
    fail("cannot test the accelerator switch with a single usable backend")

# ---- narrow window -------------------------------------------------------
root.geometry("700x450+120+70")
root.update()
crop = shot("narrow")
header_right = app.theme_btn.winfo_rootx() + app.theme_btn.winfo_width()
print(f"\nnarrow window: theme button right edge at rootx={header_right}, "
      f"window right edge={root.winfo_rootx() + root.winfo_width()}")
if header_right > root.winfo_rootx() + root.winfo_width():
    fail("header buttons overflow the narrow window")
print("  ascii:")
print("\n".join("    " + line for line in ascii_map(crop).splitlines()))

root.destroy()

print("\n" + "=" * 72)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print(f"  - {f}")
else:
    print("RESULT: ALL CHECKS PASSED")
