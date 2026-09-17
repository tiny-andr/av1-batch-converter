"""Check that switching theme or language writes nothing to the log.

Deliberately desktop-friendly: the window is withdrawn before the widgets are built,
so nothing appears on screen, no window is forced topmost, and the cursor is never
moved. The theme and language must still actually change, otherwise the check would
pass simply because the buttons did nothing.
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


def log_text():
    return app.log_box.get("1.0", "end")


print("=" * 70)
print(f"startup language = {app.language}   theme = {app.theme_mode}")
print("--- log after startup ---")
for line in log_text().splitlines():
    print(f"  | {line}")
print("=" * 70)

baseline = log_text()
baseline_lines = len(baseline.splitlines())
print(f"baseline: {baseline_lines} log lines")

# ---- theme: toggle twice, the log must not grow ---------------------------
themes = [app.theme_mode]
for i in (1, 2):
    app._toggle_theme()
    root.update()
    themes.append(app.theme_mode)
    print(f"theme toggle {i} -> {app.theme_mode}")
if themes[1] == themes[0] or themes[2] != themes[0]:
    failures.append(f"the theme did not actually toggle: {themes}")

after_theme = log_text()
print(f"after theme toggles: {len(after_theme.splitlines())} log lines")
if after_theme != baseline:
    failures.append("toggling the theme changed the log")
    print("  new lines:")
    for line in after_theme[len(baseline):].splitlines():
        print(f"    + {line}")

# ---- language: cycle all three, the log must not grow ---------------------
langs = [app.language]
for i in (1, 2, 3):
    app._toggle_language()
    root.update()
    langs.append(app.language)
    print(f"language click {i} -> {app.language}")
if len(set(langs[:3])) != 3:
    failures.append(f"the language did not actually cycle: {langs}")
if langs[3] != langs[0]:
    failures.append(f"three clicks did not return to the start language: {langs}")

after_lang = log_text()
print(f"after language switches: {len(after_lang.splitlines())} log lines")
if after_lang != baseline:
    failures.append("switching the language changed the log")
    print("  new lines:")
    for line in after_lang[len(baseline):].splitlines():
        print(f"    + {line}")

# ---- the strings really are gone from the tables -------------------------
for key in ("log_theme_switched", "log_language_switched", "theme_dark", "theme_light"):
    for lang, table in mod.STRINGS.items():
        if key in table:
            failures.append(f"dead string {key!r} is still in the {lang} table")
if hasattr(mod, "LANG_NAMES"):
    failures.append("LANG_NAMES is still defined but nothing uses it")

# ---- the encoder info block must still be there ---------------------------
# Only the active backend's codec is printed, and NVIDIA wins the probe here.
active = mod.BACKENDS_BY_KEY[app._active_backend_key]
for needle in (active["codec"], " ".join(active["args"]), " ".join(mod.COMMON_ARGS)):
    if needle not in baseline:
        failures.append(f"the encoder info block lost {needle!r}")

# ---- status bar must still follow the language ----------------------------
app._toggle_language()
root.update()
print(f"\nfinal language = {app.language}   status = {app.status_var.get()!r}")
if app.language == "en" and app.status_var.get() != "Ready":
    failures.append("the status bar did not follow the language")
if app.language == "ja" and app.status_var.get() != "準備完了":
    failures.append("the status bar did not follow the language")

root.destroy()

print("\n" + "=" * 70)
if failures:
    print(f"RESULT: {len(failures)} FAILURE(S)")
    for f in failures:
        print("  -", f)
else:
    print("RESULT: ALL CHECKS PASSED")
    print(f"  theme/language switching leaves the log untouched ({baseline_lines} lines)")
sys.exit(1 if failures else 0)
