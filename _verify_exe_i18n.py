"""Verify the packaged exe: trilingual switching + encoder-info log.

Runs against the deployed copy the user actually double-clicks. The exe cannot be
introspected from outside, so:
  * the two icon buttons are located by scanning the header band for ink blobs,
    never by hard-coded coordinates;
  * the language switch is driven with real synthetic mouse clicks;
  * the app window is forced topmost, because the WorkBuddy window grabs the
    foreground as soon as a click lands anywhere else and then covers the app
    rectangle, so every screen grab would silently capture the wrong window.
"""
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab

EXE = r"C:\Users\Administrator\Documents\shell\av1_batch_converter.exe"
TITLE = "AV1 NVENC Batch Converter"
HERE = os.path.dirname(os.path.abspath(__file__))
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
RAMP = " .:-=+*#%@"
HWND_TOPMOST = -1
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010

# Without this the verifier sees DPI-virtualized coordinates while the app (which
# calls SetProcessDpiAwareness itself) reports real pixels, and every click lands
# in the wrong place on a scaled monitor.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

user32 = ctypes.windll.user32
failures = []


def fail(msg):
    failures.append(msg)
    print(f"  !! FAIL: {msg}")


def wait_for_hwnd(timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = user32.FindWindowW(None, TITLE)
        if hwnd:
            return hwnd
        time.sleep(0.3)
    return 0


def front(hwnd):
    """Force the app on top of everything and give it the keyboard focus.

    Returns the foreground window handle so the caller can confirm the click will
    land on the app rather than on whatever else happens to be in front.
    """
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    cur = user32.GetForegroundWindow()
    user32.AttachThreadInput(user32.GetWindowThreadProcessId(cur, None),
                             user32.GetWindowThreadProcessId(hwnd, None), True)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    return user32.GetForegroundWindow()


def window_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def client_origin(hwnd):
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y


def client_size(hwnd):
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def grab(hwnd, tag):
    x, y, w, h = window_rect(hwnd)
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    crop = ImageGrab.grab(all_screens=True).crop((x - vx, y - vy, x - vx + w, y - vy + h))
    crop.save(os.path.join(HERE, f"_shot_exe_i18n_{tag}.png"))
    print(f"  [{tag}] {w}x{h} -> _shot_exe_i18n_{tag}.png")
    return crop


def click(screen_x, screen_y):
    user32.SetCursorPos(int(screen_x), int(screen_y))
    time.sleep(0.25)
    user32.mouse_event(0x0002, 0, 0, 0, 0)  # LEFTDOWN
    time.sleep(0.09)
    user32.mouse_event(0x0004, 0, 0, 0, 0)  # LEFTUP


def ink_profile(img, y0, y1, x0, x1, thr=26):
    """Per-column count of pixels that differ from the band's median brightness."""
    px = img.convert("RGB").load()
    vals = sorted(sum(px[x, y]) // 3 for y in range(y0, y1) for x in range(x0, x1))
    bg = vals[len(vals) // 2]
    return [sum(1 for y in range(y0, y1) if abs(sum(px[x, y]) // 3 - bg) > thr)
            for x in range(x0, x1)], bg


def blob_groups(profile, x0, min_ink=2):
    groups, start = [], None
    for i, n in enumerate(profile):
        if n >= min_ink:
            if start is None:
                start = i
        elif start is not None:
            groups.append((start + x0, i - 1 + x0))
            start = None
    if start is not None:
        groups.append((start + x0, len(profile) - 1 + x0))
    return [g for g in groups if g[1] - g[0] >= 2]


def band_rows(img, y0, y1, x0, x1, min_ink=3):
    px = img.convert("RGB").load()
    vals = sorted(sum(px[x, y]) // 3 for y in range(y0, y1, 2) for x in range(x0, x1, 2))
    bg = vals[len(vals) // 2]
    rows, start = [], None
    for y in range(y0, y1):
        n = sum(1 for x in range(x0, x1, 2) if abs(sum(px[x, y]) // 3 - bg) > 26)
        if n >= min_ink:
            if start is None:
                start = y
        elif start is not None:
            if y - 1 - start >= 4:
                rows.append((start, y - 1))
            start = None
    return rows


def group_runs(rows, gap=8):
    """Collapse text rows into runs of consecutive lines (a paragraph of log output)."""
    runs = []
    for row in rows:
        if runs and row[0] - runs[-1][-1][1] <= gap:
            runs[-1].append(row)
        else:
            runs.append([row])
    return runs


def ink_signature(img, box, thr=26):
    """Per-column ink distribution of a text region, normalised to sum 1.

    A plain "fraction of changed pixels" is far too blunt for sparse text: swapping
    an entire language only repaints a few percent of a mostly empty row, so the
    signal drowns. The shape of the ink profile is what actually encodes the words.
    """
    crop = img.crop(box)
    px = crop.convert("RGB").load()
    w, h = crop.size
    vals = sorted(sum(px[x, y]) // 3 for y in range(0, h, 2) for x in range(0, w, 2))
    bg = vals[len(vals) // 2]
    cols = [sum(1 for y in range(h) if abs(sum(px[x, y]) // 3 - bg) > thr) for x in range(w)]
    total = sum(cols)
    return [c / total for c in cols] if total else [0.0] * w


def sig_distance(a, b):
    """L1/2 of two normalised ink profiles: 0 = identical, 1 = disjoint."""
    if len(a) != len(b):
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / 2.0


def ascii_view(img, box, cols=118, rows=22):
    crop = img.crop(box).convert("L").resize((cols, rows))
    px = crop.load()
    return "\n".join("".join(RAMP[min(9, px[x, y] * 10 // 256)] for x in range(cols))
                     for y in range(rows))


def diff_ratio(a, b, box=None):
    if box:
        a, b = a.crop(box), b.crop(box)
    pa, pb = a.convert("L").load(), b.convert("L").load()
    w, h = a.size
    changed = sum(1 for y in range(0, h, 2) for x in range(0, w, 2)
                  if abs(pa[x, y] - pb[x, y]) > 40)
    return changed / max(1, (w // 2) * (h // 2))


def main():
    proc = subprocess.Popen([EXE], cwd=os.path.dirname(EXE))
    print(f"launched pid={proc.pid}")
    try:
        hwnd = wait_for_hwnd()
        if not hwnd:
            print("FAIL: window never appeared")
            return 1
        if front(hwnd) != hwnd:
            fail("could not bring the app to the foreground")
        time.sleep(5.0)  # let the encoder probe finish before judging the log

        rl, rt, rw, rh = window_rect(hwnd)
        cl, ct = client_origin(hwnd)
        cw, ch = client_size(hwnd)
        ox, oy = cl - rl, ct - rt
        print(f"window rect=({rl},{rt},{rw}x{rh})  client {cw}x{ch} at offset ({ox},{oy})")

        title = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, title, 256)
        print(f"window title = {title.value!r}")
        if title.value != TITLE:
            fail(f"unexpected window title {title.value!r}")

        # ---- regions of interest ----------------------------------------
        band_y0, band_y1 = oy + 6, oy + 46
        row_box = (ox, oy + 52, ox + cw, oy + 92)      # the five action buttons

        before = grab(hwnd, "1_start")

        profile, bg = ink_profile(before, band_y0, band_y1, ox + 2, ox + cw, thr=26)
        groups = blob_groups(profile, ox + 2)
        print(f"\nheader band y {band_y0}..{band_y1}  bg={bg}  ink groups={groups}")
        if len(groups) < 2:
            fail(f"expected 2 icon buttons in the header, found {len(groups)} groups")
            return 1
        lang_box, theme_box = groups[-2], groups[-1]
        print(f"language icon x {lang_box}  theme icon x {theme_box}")
        if not lang_box[1] < theme_box[0]:
            fail("language icon is not left of the theme icon")

        def best_y(box):
            sub, _ = ink_profile(before, band_y0, band_y1, box[0], box[1] + 1)
            return band_y0 + sub.index(max(sub))

        lang_pt = (rl + (lang_box[0] + lang_box[1]) // 2, rt + best_y(lang_box))
        theme_pt = (rl + (theme_box[0] + theme_box[1]) // 2, rt + best_y(theme_box))
        park_pt = (rl + cw // 2, rt + int(ch * 0.75))
        print(f"click targets  language={lang_pt}  theme={theme_pt}  park={park_pt}")

        def snap_and_park(tag):
            """Park the pointer off the buttons, then capture. Avoids hover halo + tooltip."""
            user32.SetCursorPos(*park_pt)
            time.sleep(1.0)
            return grab(hwnd, tag)

        # ---- click the language button three times; the UI must cycle ----
        # It starts in the system language (Chinese here), so after three clicks the
        # visible text has to be back to exactly where it began.
        states = [("start", before)]
        for step in (1, 2, 3):
            if front(hwnd) != hwnd:
                fail(f"lost the foreground before click {step}")
            click(*lang_pt)
            time.sleep(0.45)
            states.append((f"click{step}", snap_and_park(f"lang_click{step}")))

        print("\n--- button row per state (this is what must change) ---")
        for tag, shot in states:
            print(f"  [{tag}]")
            print("\n".join("    " + l for l in ascii_view(shot, row_box, cols=118, rows=7).splitlines()))

        # ---- compare the whole top block, not just the buttons -----------
        # The log box holds the encoder arguments, which are the same in every
        # language, so it has to be excluded or it dilutes the signal.
        rows_all = band_rows(before, oy + 95, oy + ch - 18, ox + 4, ox + cw - 26)
        runs = group_runs(rows_all)
        runs.sort(key=len, reverse=True)
        print(f"\ntext runs below the buttons (row count per run): {[len(r) for r in runs]}")
        if not runs:
            fail("no text found below the button row")
            return 1
        log_run = runs[0]
        log_top = log_run[0][0] - 14
        log_box = (ox + 4, log_top, ox + cw - 26, log_run[-1][1] + 12)
        print(f"largest text run = {len(log_run)} lines, y {log_run[0][0]}..{log_run[-1][1]}")

        # Everything from just under the buttons down to the log box: the drag hint,
        # the status line and the progress bar live in there, and all of them are
        # translated.
        top_box = (ox, oy + 45, ox + cw, log_top - 6)
        print(f"top block = x {top_box[0]}..{top_box[2]}, y {top_box[1]}..{top_box[3]}")

        sig_row = {tag: ink_signature(shot, row_box) for tag, shot in states}
        sig_top = {tag: ink_signature(shot, top_box) for tag, shot in states}

        for i in range(len(states) - 1):
            a, b = states[i][0], states[i + 1][0]
            d_row = sig_distance(sig_row[a], sig_row[b])
            d_top = sig_distance(sig_top[a], sig_top[b])
            verdict = "different" if d_row > 0.25 else "TOO SIMILAR"
            print(f"  {a} -> {b}:  button row ink distance={d_row:.3f} ({verdict})"
                  f"   top block={d_top:.3f}")
            if d_row < 0.25:
                fail(f"button labels did not change between {a} and {b}")
            if d_top < 0.10:
                fail(f"the other labels did not change between {a} and {b}")

        d_cycle = sig_distance(sig_row["start"], sig_row["click3"])
        print(f"  start -> click3 (three languages later): ink distance={d_cycle:.3f} (must be 0)")
        if d_cycle > 0.02:
            fail("three clicks did not bring the UI back to the starting language")
        else:
            print("  ok: the third click cycled the language back to the starting one")

        # ---- the encoder-info block must be on screen -------------------
        print(f"\nlog text run: {len(log_run)} lines in y {log_run[0][0]}..{log_run[-1][1]}")
        for a, b in log_run:
            print(f"    row y {a}-{b}")
        if len(log_run) < 7:
            fail(f"expected at least 7 log lines (4 availability + 3 encoder info), "
                 f"got {len(log_run)}")
        print("  log area ascii (first line = accelerator, then 4 availability rows,"
              " then codec / quality / common args):")
        print("\n".join("    " + l for l in ascii_view(before, log_box, cols=118, rows=16).splitlines()))

        # ---- theme button still works ------------------------------------
        if front(hwnd) != hwnd:
            fail("lost the foreground before the theme click")
        click(*theme_pt)
        time.sleep(0.7)
        after_theme = snap_and_park("theme_toggled")
        td = diff_ratio(before, after_theme)
        print(f"\nwhole-window pixel change after toggling the theme = {td:.3f}")
        if td < 0.3:
            fail("toggling the theme did not noticeably change the window")
        print("  header after the theme toggle:")
        print("\n".join("    " + l for l in
                        ascii_view(after_theme, (cw - 170, 0, cw, 60), cols=70, rows=13).splitlines()))
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("terminated")


if __name__ == "__main__":
    rc = main()
    print("\n" + "=" * 66)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print("  -", f)
    else:
        print("RESULT: ALL CHECKS PASSED")
    sys.exit(rc or (1 if failures else 0))
