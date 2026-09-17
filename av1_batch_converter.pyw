#!/usr/bin/env python3
import os
import re
import sys
import math
import ctypes
import shutil
import subprocess
import threading
import uuid

# Workaround: tkinterdnd2 tries to import tkinter.tix, which was removed in Python 3.13
import tkinter
sys.modules["tkinter.tix"] = tkinter

import tkinter as tk
import tkinter.font as tkfont
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

try:
    import pywinstyles
except ImportError:
    pywinstyles = None

# Per-monitor DPI awareness: keeps text crisp on mixed 100% / 150% displays.
ENABLE_PER_MONITOR_DPI = True

# Every size below is a 96-DPI design unit. sc() and font_px() translate them into
# the pixels of the monitor the window is actually on (see apply_dpi_scaling).
DPI_REFERENCE = 96.0
WINDOW_SIZE = (900, 650)
MIN_SIZE = (700, 450)
ICON_SIZE = 26
PAD = 10
GAP = 5
FONT_BODY = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI", 14)
FONT_ICON = ("Segoe UI", 10)
FONT_MONO = ("Cascadia Mono", 9)

# Tk reads the scaling factor once, from the primary monitor, and never revisits it.
# Keeping our own copy lets both the text and the hand-written pixel literals follow
# the monitor the window is on.
_dpi_scale = 1.0

# Starting theme: "dark" | "light". The button in the top-right corner toggles it at runtime.
# Backdrop styles: "dark" / "light" (solid client area) | "mica" / "acrylic" | "normal"
# Note: tkinter paints an opaque client area, so Mica/Acrylic only reach the titlebar.
DEFAULT_THEME = "dark"


# --------------------------------------------------------------------- localization

APP_TITLE = "AV1 Batch Converter"
APP_VERSION = "1.0.1"

LANGUAGES = ["zh", "ja", "en"]
LANG_LABELS = {"zh": "中", "ja": "日", "en": "EN"}

STRINGS = {
    "en": {
        "add_folder": "Add Folder",
        "add_files": "Add Files",
        "load_list": "Load list.txt",
        "remove_selected": "Remove Selected",
        "clear_list": "Clear List",
        "start_conversion": "Start Conversion",
        "stop_conversion": "Stop",
        "max_concurrent": "Max concurrent:",
        "encoder": "Encoder:",
        "log_title": "Log",
        "tip_drag": "Tip: Drag and drop files or folders here to add them",
        "tip_theme": "Switch theme",
        "tip_language": "Switch language",
        "tip_encoder": "Pick an acceleration device; grey means unavailable",
        "ready": "Ready",
        "not_running": "Not running",
        "stopping": "Stopping...",
        "stopped_by_user": "Stopped by user",
        "done": "Done",
        "processing": "Processing {done}/{total}",
        "status_added_folder": "Added {n} videos from folder",
        "status_added_files": "Added {n} files (total {total})",
        "status_added_drop": "Added {n} items from drop (total {total})",
        "status_loaded_files": "Loaded {n} files from {path}",
        "status_removed": "Removed {n} items (total {total})",
        "status_list_cleared": "List cleared",
        "status_loaded_cmdline": "Loaded {n} files from command line",
        "status_cannot_add": "Cannot add files while conversion is running",
        "log_no_encoder": "No usable encoder found - none of the listed encoders could start.",
        "log_ffmpeg_bundled": "ffmpeg: bundled with the program",
        "log_ffmpeg_beside": "ffmpeg: beside the program ({path})",
        "log_ffmpeg_path": "ffmpeg: from PATH ({path})",
        "log_ffmpeg_missing_src": "ffmpeg: not found, neither bundled nor on PATH",
        "log_ffmpeg_version": "ffmpeg version: {ver}",
        "log_acceleration": "Acceleration: {label}",
        "log_available": "available",
        "log_unavailable": "unavailable",
        "log_encoder_codec": "  encoder    : {codec}",
        "log_quality_args": "  quality    : {args}",
        "log_common_args": "  common     : {args}",
        "log_encoder_switched": "Encoder switched to {label}",
        "log_start": "Start conversion: {total} files, max {n} concurrent, encoder {label}",
        "log_cpu_slow": "Note: CPU encoding (SVT-AV1) is far slower than a GPU encoder.",
        "log_queued": "Queued: {path}",
        "log_stop_requested": "Stop requested, skipping remaining submissions",
        "log_added_folder": "Added folder: {path} ({n} videos)",
        "log_added_files": "Added {n} files via file dialog",
        "log_dropped_folder": "Dropped folder: {path} ({n} videos)",
        "log_drop_complete": "Drop complete: {n} items added",
        "log_loaded_list": "Loaded list file: {path} ({n} entries)",
        "log_removed": "Removed {n} selected items",
        "log_initial_folder": "Initial folder argument: {path}",
        "log_done": "Done: {path}",
        "log_failed": "Failed: {path}",
        "log_ffmpeg_missing": "Could not run ffmpeg. Failed: {path}",
        "log_replace_failed": "Failed to replace original file {path}: {err}",
        "log_exception": "Exception: {path}\n{err}",
        "mb_no_files_title": "No files",
        "mb_no_files_msg": "Please add some video files first.",
        "mb_busy_title": "Busy",
        "mb_busy_msg": "Conversion already running.",
        "mb_no_encoder_title": "No encoder",
        "mb_no_encoder_msg": "No usable encoder was detected. Either ffmpeg is missing, or it cannot start any AV1 encoder on this machine.",
        "mb_stopped_title": "Stopped",
        "mb_stopped_msg": "Batch conversion stopped by user.",
        "mb_done_title": "Done",
        "mb_done_msg": "Batch conversion finished.",
        "mb_info_title": "Info",
        "mb_select_msg": "Please select one or more items to remove.",
        "mb_error_title": "Error",
        "mb_load_failed": "Failed to load list:\n{err}",
        "fd_select_folder": "Select folder containing videos",
        "fd_select_videos": "Select video files",
        "fd_video_files": "Video files",
        "fd_all_files": "All files",
        "fd_text_files": "Text files",
        "fd_select_list": "Select list.txt",
    },
    "zh": {
        "add_folder": "添加文件夹",
        "add_files": "添加文件",
        "load_list": "载入 list.txt",
        "remove_selected": "移除选中",
        "clear_list": "清空列表",
        "start_conversion": "开始转换",
        "stop_conversion": "停止",
        "max_concurrent": "最大并发:",
        "encoder": "编码器:",
        "log_title": "日志",
        "tip_drag": "提示：把文件或文件夹拖到这里添加",
        "tip_theme": "切换主题",
        "tip_language": "切换语言",
        "tip_encoder": "选择加速编码设备，灰色表示不可用",
        "ready": "就绪",
        "not_running": "未运行",
        "stopping": "正在停止...",
        "stopped_by_user": "已被用户停止",
        "done": "完成",
        "processing": "处理中 {done}/{total}",
        "status_added_folder": "已从文件夹添加 {n} 个视频",
        "status_added_files": "已添加 {n} 个文件（共 {total}）",
        "status_added_drop": "已从拖放添加 {n} 项（共 {total}）",
        "status_loaded_files": "已从 {path} 载入 {n} 个文件",
        "status_removed": "已移除 {n} 项（共 {total}）",
        "status_list_cleared": "列表已清空",
        "status_loaded_cmdline": "已从命令行载入 {n} 个文件",
        "status_cannot_add": "转换中无法添加文件",
        "log_no_encoder": "未找到可用的编码器 —— 列表里的编码器都无法启动。",
        "log_ffmpeg_bundled": "ffmpeg：随程序自带",
        "log_ffmpeg_beside": "ffmpeg：与程序同目录（{path}）",
        "log_ffmpeg_path": "ffmpeg：来自 PATH（{path}）",
        "log_ffmpeg_missing_src": "ffmpeg：未找到，自带和 PATH 里都没有",
        "log_ffmpeg_version": "ffmpeg 版本：{ver}",
        "log_acceleration": "加速设备: {label}",
        "log_available": "可用",
        "log_unavailable": "不可用",
        "log_encoder_codec": "  编码器    : {codec}",
        "log_quality_args": "  质量参数  : {args}",
        "log_common_args": "  公共参数  : {args}",
        "log_encoder_switched": "已切换编码器为 {label}",
        "log_start": "开始转换：{total} 个文件，最大并发 {n}，编码器 {label}",
        "log_cpu_slow": "注意：CPU 编码（SVT-AV1）比 GPU 慢得多，请耐心等待。",
        "log_queued": "已排队: {path}",
        "log_stop_requested": "已请求停止，跳过剩余任务",
        "log_added_folder": "已添加文件夹: {path}（{n} 个视频）",
        "log_added_files": "已通过文件对话框添加 {n} 个文件",
        "log_dropped_folder": "拖入文件夹: {path}（{n} 个视频）",
        "log_drop_complete": "拖放完成：新增 {n} 项",
        "log_loaded_list": "已载入列表文件: {path}（{n} 条）",
        "log_removed": "已移除 {n} 个选中项",
        "log_initial_folder": "命令行文件夹参数: {path}",
        "log_done": "完成: {path}",
        "log_failed": "失败: {path}",
        "log_ffmpeg_missing": "无法运行 ffmpeg。失败: {path}",
        "log_replace_failed": "替换原文件失败 {path}: {err}",
        "log_exception": "异常: {path}\n{err}",
        "mb_no_files_title": "没有文件",
        "mb_no_files_msg": "请先添加要转换的视频文件。",
        "mb_busy_title": "忙碌中",
        "mb_busy_msg": "转换已在运行。",
        "mb_no_encoder_title": "没有可用的编码器",
        "mb_no_encoder_msg": "未检测到可用的编码器。可能是找不到 ffmpeg，或者这台机器上没有任何 AV1 编码器能启动。",
        "mb_stopped_title": "已停止",
        "mb_stopped_msg": "批量转换已被用户停止。",
        "mb_done_title": "完成",
        "mb_done_msg": "批量转换已完成。",
        "mb_info_title": "提示",
        "mb_select_msg": "请先选中要移除的项目。",
        "mb_error_title": "错误",
        "mb_load_failed": "载入列表失败:\n{err}",
        "fd_select_folder": "选择包含视频的文件夹",
        "fd_select_videos": "选择视频文件",
        "fd_video_files": "视频文件",
        "fd_all_files": "所有文件",
        "fd_text_files": "文本文件",
        "fd_select_list": "选择 list.txt",
    },
    "ja": {
        "add_folder": "フォルダを追加",
        "add_files": "ファイルを追加",
        "load_list": "list.txt を読み込む",
        "remove_selected": "選択を削除",
        "clear_list": "リストをクリア",
        "start_conversion": "変換開始",
        "stop_conversion": "停止",
        "max_concurrent": "最大同時実行数:",
        "encoder": "エンコーダー:",
        "log_title": "ログ",
        "tip_drag": "ヒント: ファイルやフォルダをここにドラッグして追加",
        "tip_theme": "テーマを切り替え",
        "tip_language": "言語を切り替え",
        "tip_encoder": "加速デバイスを選択（グレーは使用不可）",
        "ready": "準備完了",
        "not_running": "実行中ではありません",
        "stopping": "停止しています...",
        "stopped_by_user": "ユーザーにより停止",
        "done": "完了",
        "processing": "処理中 {done}/{total}",
        "status_added_folder": "フォルダから {n} 件の動画を追加しました",
        "status_added_files": "{n} 件追加しました（合計 {total}）",
        "status_added_drop": "ドロップから {n} 件追加しました（合計 {total}）",
        "status_loaded_files": "{path} から {n} 件読み込みました",
        "status_removed": "{n} 件削除しました（合計 {total}）",
        "status_list_cleared": "リストをクリアしました",
        "status_loaded_cmdline": "コマンドラインから {n} 件読み込みました",
        "status_cannot_add": "変換中はファイルを追加できません",
        "log_no_encoder": "使用可能なエンコーダーが見つかりません - 一覧のエンコーダーはどれも起動できませんでした。",
        "log_ffmpeg_bundled": "ffmpeg: 同梱",
        "log_ffmpeg_beside": "ffmpeg: プログラムと同じ場所（{path}）",
        "log_ffmpeg_path": "ffmpeg: PATH から（{path}）",
        "log_ffmpeg_missing_src": "ffmpeg: 見つかりません（同梱・PATH ともになし）",
        "log_ffmpeg_version": "ffmpeg バージョン: {ver}",
        "log_acceleration": "加速デバイス: {label}",
        "log_available": "使用可能",
        "log_unavailable": "使用不可",
        "log_encoder_codec": "  エンコーダー  : {codec}",
        "log_quality_args": "  品質パラメータ: {args}",
        "log_common_args": "  共通パラメータ: {args}",
        "log_encoder_switched": "エンコーダーを {label} に切り替えました",
        "log_start": "変換開始: {total} ファイル、最大同時実行 {n}、エンコーダー {label}",
        "log_cpu_slow": "注意: CPU エンコード（SVT-AV1）は GPU よりはるかに遅いです。",
        "log_queued": "キューに追加: {path}",
        "log_stop_requested": "停止が要求されました。残りのタスクをスキップします",
        "log_added_folder": "フォルダを追加: {path}（{n} 件の動画）",
        "log_added_files": "ファイルダイアログから {n} 件追加しました",
        "log_dropped_folder": "ドロップされたフォルダ: {path}（{n} 件の動画）",
        "log_drop_complete": "ドロップ完了: {n} 件追加",
        "log_loaded_list": "リストファイルを読み込みました: {path}（{n} 件）",
        "log_removed": "選択した {n} 件を削除しました",
        "log_initial_folder": "コマンドラインのフォルダ引数: {path}",
        "log_done": "完了: {path}",
        "log_failed": "失敗: {path}",
        "log_ffmpeg_missing": "ffmpeg を実行できませんでした。失敗: {path}",
        "log_replace_failed": "元のファイルの置換に失敗しました {path}: {err}",
        "log_exception": "例外: {path}\n{err}",
        "mb_no_files_title": "ファイルがありません",
        "mb_no_files_msg": "先に変換する動画ファイルを追加してください。",
        "mb_busy_title": "実行中",
        "mb_busy_msg": "変換はすでに実行中です。",
        "mb_no_encoder_title": "使用可能なエンコーダーがありません",
        "mb_no_encoder_msg": "使用可能なエンコーダーが検出されませんでした。ffmpeg が見つからないか、この環境で AV1 エンコーダーを起動できない可能性があります。",
        "mb_stopped_title": "停止しました",
        "mb_stopped_msg": "バッチ変換はユーザーにより停止されました。",
        "mb_done_title": "完了",
        "mb_done_msg": "バッチ変換が完了しました。",
        "mb_info_title": "情報",
        "mb_select_msg": "削除する項目を選択してください。",
        "mb_error_title": "エラー",
        "mb_load_failed": "リストの読み込みに失敗しました:\n{err}",
        "fd_select_folder": "動画を含むフォルダを選択",
        "fd_select_videos": "動画ファイルを選択",
        "fd_video_files": "動画ファイル",
        "fd_all_files": "すべてのファイル",
        "fd_text_files": "テキストファイル",
        "fd_select_list": "list.txt を選択",
    },
}


def system_language():
    """Windows UI language mapped to a supported language, English otherwise."""
    try:
        langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
    except Exception:
        return "en"
    primary = langid & 0x03FF
    if primary == 0x04:
        return "zh"
    if primary == 0x11:
        return "ja"
    return "en"


# Acceleration backends, in preference order - the first available one is picked at
# startup. Availability is probed by actually running the encoder once, because
# "has an Intel iGPU" does not mean "can encode AV1" (only Arc / Meteor Lake+ can),
# and a missing AMD runtime DLL looks exactly like "no AMD card".
ENCODER_BACKENDS = [
    {
        "key": "nvidia",
        "label": "NVIDIA GPU (NVENC)",
        "codec": "av1_nvenc",
        "args": ["-preset", "p7", "-rc", "vbr", "-cq", "28", "-b:v", "0", "-tune", "hq"],
    },
    {
        "key": "amd",
        "label": "AMD GPU (AMF)",
        "codec": "av1_amf",
        "args": ["-quality", "quality", "-rc", "cqp", "-qp_i", "28", "-qp_p", "28"],
    },
    {
        "key": "intel",
        "label": "Intel iGPU (QSV)",
        "codec": "av1_qsv",
        "args": ["-preset", "7", "-global_quality", "28"],
    },
    {
        "key": "cpu",
        "label": "CPU (SVT-AV1)",
        "codec": "libsvtav1",
        "args": ["-preset", "6", "-crf", "30"],
    },
    {
        # Second CPU option. The ffmpeg build shipped inside this exe is gyan.dev's
        # "essentials" variant, which carries every hardware AV1 encoder but not
        # libsvtav1; it does carry libaom-av1. Listing both means the bundled build
        # still has a working CPU path, while anyone running against a full ffmpeg
        # keeps getting SVT-AV1 because it is probed first.
        "key": "cpu_aom",
        "label": "CPU (libaom AV1)",
        "codec": "libaom-av1",
        "args": ["-cpu-used", "6", "-crf", "30"],
    },
]

BACKENDS_BY_KEY = {backend["key"]: backend for backend in ENCODER_BACKENDS}

# Appended after the per-backend encoder arguments.
COMMON_ARGS = ["-g", "240", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k"]

# Two synthetic frames are enough to tell whether a hardware encoder can initialize.
# Measured well under half a second per backend on this machine.
PROBE_INPUT = ["-f", "lavfi", "-i", "testsrc2=s=256x256:r=30", "-frames:v", "2"]
PROBE_TIMEOUT = 20


# --------------------------------------------------------------------- ffmpeg

def _program_dir():
    """Folder the program lives in.

    A onefile build unpacks itself into a temp folder, so anything that should
    sit next to the program has to be resolved from the exe's own directory.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _ffmpeg_candidates():
    program = _program_dir()
    # 1. Dropped in beside the program by the user: an explicit override.
    yield os.path.join(program, "ffmpeg", "ffmpeg.exe"), "beside"
    # 2. Packed into the exe and unpacked to the temp folder for this run.
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        yield os.path.join(bundle, "ffmpeg", "ffmpeg.exe"), "bundled"
    # 3. The source tree layout, so running the .pyw directly uses the same build.
    yield os.path.join(program, "vendor", "ffmpeg", "ffmpeg.exe"), "vendor"


def resolve_ffmpeg():
    """Return (command, source).

    source is "beside", "bundled", "vendor", "path" or "missing". Bundled copies
    win over PATH deliberately: a stale or broken ffmpeg on PATH would otherwise
    shadow a known-good one that ships with the program.
    """
    for path, source in _ffmpeg_candidates():
        if os.path.isfile(path):
            return path, source
    found = shutil.which("ffmpeg")
    if found:
        return found, "path"
    return "ffmpeg", "missing"


FFMPEG_CMD, FFMPEG_SOURCE = resolve_ffmpeg()


def ffmpeg_version():
    """First line of `ffmpeg -version`, or "" when it cannot be run."""
    try:
        result = subprocess.run(
            [FFMPEG_CMD, "-hide_banner", "-version"],
            capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.splitlines()[0].strip() if result.stdout else ""


def probe_backend(backend):
    """True if the encoder really initializes here (device present and codec supported)."""
    cmd = [
        FFMPEG_CMD, "-hide_banner", "-loglevel", "error",
        *PROBE_INPUT,
        "-c:v", backend["codec"], *backend["args"],
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def detect_backends():
    """Probe every backend and return {key: usable}."""
    return {backend["key"]: probe_backend(backend) for backend in ENCODER_BACKENDS}


def build_ffmpeg_args(backend_key):
    """Full encoder argument list for the given backend."""
    backend = BACKENDS_BY_KEY.get(backend_key) or BACKENDS_BY_KEY["nvidia"]
    return ["-c:v", backend["codec"], *backend["args"], *COMMON_ARGS]

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".mts", ".m2ts"}

# Windows 11 dark palette, tuned to sit on top of the Mica base layer.
DARK = {
    "bg": "#202020",
    "surface": "#2b2b2b",
    "surface_hi": "#333333",
    "sunken": "#1a1a1a",
    "border": "#3d3d3d",
    "text": "#f3f3f3",
    "text_dim": "#a6a6a6",
    "accent_fallback": "#0078d4",
    "pressed": "#3f3f3f",
    "active_border": "#4a4a4a",
    "disabled_bg": "#252525",
    "disabled_fg": "#6b6b6b",
}

# Windows 11 light palette.
LIGHT = {
    "bg": "#f3f3f3",
    "surface": "#ffffff",
    "surface_hi": "#ebebeb",
    "sunken": "#ffffff",
    "border": "#d1d1d1",
    "text": "#1b1b1b",
    "text_dim": "#616161",
    "accent_fallback": "#0078d4",
    "pressed": "#d6d6d6",
    "active_border": "#b8b8b8",
    "disabled_bg": "#e6e6e6",
    "disabled_fg": "#a0a0a0",
}

PALETTES = {"dark": DARK, "light": LIGHT}


def _accent_color():
    """Read the system accent color, fall back to Fluent blue."""
    if pywinstyles is None:
        return DARK["accent_fallback"]
    try:
        color = pywinstyles.get_accent_color()
        if re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            return color
    except Exception:
        pass
    return DARK["accent_fallback"]


def _enable_dpi_awareness():
    if not ENABLE_PER_MONITOR_DPI or os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def dpi_scale():
    """Current monitor scale, 1.0 being the 96-DPI reference."""
    return _dpi_scale


def sc(px):
    """A 96-DPI design pixel expressed in the current monitor's pixels."""
    return int(round(px * _dpi_scale))


def font_px(spec, weight=None):
    """
    A (family, points) design font as an explicitly pixel-sized font tuple.

    Tk converts a point size to pixels when the font is first created and then
    caches the result, so changing 'tk scaling' afterwards does nothing to fonts
    that already exist. Sizing in pixels (Tk reads a negative size as pixels) keeps
    the conversion in our hands, which is what makes a rescale re-appliable.
    """
    family, points = spec[0], spec[1]
    size = -max(6, int(round(points * DPI_REFERENCE / 72.0 * _dpi_scale)))
    return (family, size, weight) if weight else (family, size)


def _window_dpi(root=None):
    """DPI of the monitor the window is on, or of the system default."""
    if os.name != "nt":
        return DPI_REFERENCE
    user32 = ctypes.windll.user32
    if root is not None:
        try:
            parent = user32.GetParent(root.winfo_id())
        except Exception:
            parent = 0
        for hwnd in (parent, root.winfo_id()):
            if not hwnd:
                continue
            try:
                dpi = user32.GetDpiForWindow(hwnd)
            except Exception:
                dpi = 0
            if dpi:
                return float(dpi)
    try:
        return float(user32.GetDpiForSystem())
    except Exception:
        return DPI_REFERENCE


def apply_dpi_scaling(root=None, dpi=None):
    """
    Point the text scaling and every sc() literal at the window's monitor.

    Tk resolves its scaling factor once, from the primary monitor, so on a mixed
    100% / 150% desktop the window keeps 100% metrics even after it is dragged onto
    the 4K screen - which is exactly what made the text look tiny there. The factor
    is cached in _dpi_scale so sc() and font_px() follow the same monitor.
    """
    global _dpi_scale
    dpi = float(dpi) if dpi else _window_dpi(root)
    _dpi_scale = dpi / DPI_REFERENCE
    if root is not None:
        try:
            root.tk.call("tk", "scaling", dpi / 72.0)
        except Exception:
            pass
    return dpi


def apply_window_theme(root, mode=DEFAULT_THEME):
    """Apply the Windows 11 dark or light look. Returns the resolved palette."""
    mode = mode if mode in PALETTES else DEFAULT_THEME
    theme = dict(PALETTES[mode])
    theme["mode"] = mode
    theme["accent"] = _accent_color()
    theme["select_fg"] = "#ffffff" if mode == "dark" else "#ffffff"

    if pywinstyles is not None:
        for style in (mode, "dark" if mode == "dark" else "light"):
            try:
                pywinstyles.apply_style(root, style)
                break
            except Exception:
                continue

    root.configure(bg=theme["bg"])

    for name in ("TkDefaultFont", "TkTextFont"):
        try:
            tkfont.nametofont(name).configure(family=FONT_BODY[0], size=font_px(FONT_BODY)[1])
        except Exception:
            pass
    try:
        tkfont.nametofont("TkFixedFont").configure(family=FONT_MONO[0],
                                                   size=font_px(FONT_MONO)[1])
    except Exception:
        pass

    st = ttk.Style()
    try:
        st.theme_use("clam")
    except Exception:
        pass

    st.configure(
        ".",
        background=theme["bg"],
        foreground=theme["text"],
        fieldbackground=theme["surface"],
        troughcolor=theme["surface"],
        bordercolor=theme["border"],
        lightcolor=theme["surface"],
        darkcolor=theme["surface"],
        selectbackground=theme["accent"],
        selectforeground="#ffffff",
        font=font_px(FONT_BODY),
    )
    st.configure("TFrame", background=theme["bg"])
    st.configure("TLabel", background=theme["bg"], foreground=theme["text"])
    st.configure("TLabelframe", background=theme["bg"], bordercolor=theme["border"],
                 relief="solid", borderwidth=1)
    st.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["text"])

    st.configure("TButton", background=theme["surface"], foreground=theme["text"],
                 bordercolor=theme["border"], lightcolor=theme["surface"],
                 darkcolor=theme["surface"], padding=(sc(10), sc(5)), relief="flat",
                 focuscolor=theme["bg"])
    st.map("TButton",
           background=[("disabled", theme["disabled_bg"]), ("pressed", theme["pressed"]),
                       ("active", theme["surface_hi"])],
           bordercolor=[("focus", theme["accent"]), ("active", theme["active_border"])],
           foreground=[("disabled", theme["disabled_fg"])])

    st.configure("TProgressbar", background=theme["accent"], troughcolor=theme["surface"],
                 bordercolor=theme["surface"], lightcolor=theme["accent"],
                 darkcolor=theme["accent"], thickness=sc(6))
    st.configure("TSpinbox", fieldbackground=theme["surface"], background=theme["surface"],
                 foreground=theme["text"], arrowcolor=theme["text"],
                 bordercolor=theme["border"], relief="flat", padding=(sc(4), sc(3)))
    st.map("TSpinbox",
           bordercolor=[("focus", theme["accent"])],
           arrowcolor=[("disabled", theme["disabled_fg"])])
    # A readonly Combobox paints its text on the field background, so both have to be
    # themed - clam's default is a white field, which makes light text invisible.
    st.configure("TCombobox", fieldbackground=theme["surface"], background=theme["surface"],
                 foreground=theme["text"], arrowcolor=theme["text"],
                 bordercolor=theme["border"], lightcolor=theme["surface"],
                 darkcolor=theme["surface"], relief="flat", padding=(sc(4), sc(3)))
    st.map("TCombobox",
           fieldbackground=[("readonly", theme["surface"]), ("disabled", theme["bg"])],
           foreground=[("readonly", theme["text"]), ("disabled", theme["text_dim"])],
           background=[("readonly", theme["surface"]), ("active", theme["surface_hi"])],
           arrowcolor=[("disabled", theme["text_dim"])],
           bordercolor=[("focus", theme["accent"])])

    st.configure("TScrollbar", background=theme["surface"], troughcolor=theme["bg"],
                 bordercolor=theme["bg"], arrowcolor=theme["text"], relief="flat",
                 lightcolor=theme["surface"], darkcolor=theme["surface"])
    st.map("TScrollbar",
           background=[("pressed", theme["pressed"]), ("active", theme["surface_hi"])])

    root.option_add("*Menu.background", theme["surface"])
    root.option_add("*Menu.foreground", theme["text"])
    root.option_add("*Menu.activeBackground", theme["surface_hi"])
    root.option_add("*Menu.activeForeground", theme["text"])
    root.option_add("*Text.background", theme["sunken"])
    root.option_add("*Text.foreground", theme["text"])
    root.option_add("*Text.insertBackground", theme["text"])
    root.option_add("*Text.selectBackground", theme["accent"])
    root.option_add("*Text.selectForeground", "#ffffff")
    root.option_add("*Listbox.background", theme["sunken"])
    root.option_add("*Listbox.foreground", theme["text"])
    root.option_add("*Listbox.selectBackground", theme["accent"])
    root.option_add("*Listbox.selectForeground", "#ffffff")

    return theme


class Tooltip:
    """Themed tooltip that appears after a short hover delay."""

    def __init__(self, widget, text, theme_getter, delay=450):
        self.widget = widget
        self.text = text
        self.theme_getter = theme_getter
        self.delay = delay
        self.tip = None
        self._job = None
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _show(self):
        if self.tip is not None:
            return
        theme = self.theme_getter()
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        try:
            self.tip.wm_attributes("-topmost", True)
        except Exception:
            pass
        # text may be a callable so the tooltip follows the current language.
        text = self.text() if callable(self.text) else self.text
        tk.Label(
            self.tip,
            text=text,
            background=theme["surface"],
            foreground=theme["text"],
            font=font_px(FONT_BODY),
            padx=sc(8),
            pady=sc(4),
            relief="solid",
            borderwidth=1,
            highlightbackground=theme["border"],
            highlightthickness=1,
        ).pack()
        self.tip.update_idletasks()
        wx, wy = self.widget.winfo_rootx(), self.widget.winfo_rooty()
        ww, wh = self.widget.winfo_width(), self.widget.winfo_height()
        tw, th = self.tip.winfo_width(), self.tip.winfo_height()
        x = max(0, wx + (ww - tw) // 2)
        self.tip.wm_geometry(f"+{x}+{wy + wh + sc(4)}")

    def _hide(self):
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None


class ConverterGUI:
    def __init__(self, root, initial_paths=None):
        self.root = root
        self.root.title(APP_TITLE)

        # Tk only ever measures the primary monitor, so the scale is resolved here
        # and then re-checked once the window is mapped (it may open elsewhere).
        self._applied_scale = 0.0
        self._applied_dpi = apply_dpi_scaling(self.root)
        self._applied_scale = dpi_scale()
        self.root.geometry(f"{sc(WINDOW_SIZE[0])}x{sc(WINDOW_SIZE[1])}")
        self.root.minsize(sc(MIN_SIZE[0]), sc(MIN_SIZE[1]))

        self.file_list = []
        self.stop_event = threading.Event()
        self.worker = None
        self._busy = False

        # Widget-independent state, so a rebuild after a DPI change keeps it.
        self.concurrent_var = tk.IntVar(value=1)
        self.encoder_availability = {}
        self._last_valid_encoder = None
        self._active_backend_key = None

        # Follow the Windows UI language on startup; the header button cycles it.
        self.language = system_language()
        self._status_key = "ready"
        self._status_args = {}

        self.theme_mode = DEFAULT_THEME
        self.theme = apply_window_theme(self.root, self.theme_mode)
        self._build_ui()
        self._probe_encoders()

        if initial_paths:
            self._handle_initial_paths(initial_paths)

        self.root.after(400, self._poll_monitor_dpi)

    def _build_ui(self):
        self.frame = ttk.Frame(self.root, padding=sc(PAD))
        self.frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(self.frame)
        header.pack(fill=tk.X, pady=(0, sc(10)))
        self.title_label = ttk.Label(header, text=APP_TITLE, font=font_px(FONT_TITLE, "bold"))
        self.title_label.pack(side=tk.LEFT)
        self._build_theme_toggle(header)
        self._build_language_toggle(header)

        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=sc(GAP))

        self.add_folder_btn = ttk.Button(btn_frame, text=self._t("add_folder"), command=self._add_folder)
        self.add_folder_btn.pack(side=tk.LEFT, padx=sc(GAP))
        self.add_files_btn = ttk.Button(btn_frame, text=self._t("add_files"), command=self._add_files)
        self.add_files_btn.pack(side=tk.LEFT, padx=sc(GAP))
        self.load_list_btn = ttk.Button(btn_frame, text=self._t("load_list"), command=self._load_list)
        self.load_list_btn.pack(side=tk.LEFT, padx=sc(GAP))
        self.remove_btn = ttk.Button(btn_frame, text=self._t("remove_selected"), command=self._remove_selected)
        self.remove_btn.pack(side=tk.LEFT, padx=sc(GAP))
        self.clear_btn = ttk.Button(btn_frame, text=self._t("clear_list"), command=self._clear_list)
        self.clear_btn.pack(side=tk.LEFT, padx=sc(GAP))

        self.listbox = tk.Listbox(
            self.frame,
            selectmode=tk.EXTENDED,
            bg=self.theme["sunken"],
            fg=self.theme["text"],
            selectbackground=self.theme["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=self.theme["border"],
            highlightcolor=self.theme["accent"],
            relief="flat",
            borderwidth=0,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True, pady=sc(GAP))

        scrollbar = ttk.Scrollbar(self.listbox)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        self.tip_label = ttk.Label(
            self.frame,
            text=self._t("tip_drag"),
            foreground=self.theme["text_dim"],
        )
        self.tip_label.pack()

        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind('<<Drop>>', self._on_drop)

        self.status_var = tk.StringVar(value=self._t("ready"))
        self.status_label = ttk.Label(self.frame, textvariable=self.status_var,
                                      font=font_px(FONT_BODY))
        self.status_label.pack(anchor=tk.W, pady=sc(2))

        self.progress = ttk.Progressbar(self.frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=sc(GAP))

        log_frame = ttk.LabelFrame(self.frame, text=self._t("log_title"))
        log_frame.pack(fill=tk.BOTH, expand=True, pady=sc(GAP))
        self.log_frame = log_frame

        # ScrolledText bundles a classic tk.Scrollbar, which Windows renders natively
        # and therefore ignores the dark theme. Use a ttk.Scrollbar instead.
        log_inner = ttk.Frame(log_frame)
        log_inner.pack(fill=tk.BOTH, expand=True)
        self.log_box = tk.Text(log_inner, state=tk.DISABLED, height=12)
        self.log_vbar = ttk.Scrollbar(log_inner, orient=tk.VERTICAL, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=self.log_vbar.set)
        self.log_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_box.configure(
            bg=self.theme["sunken"],
            fg=self.theme["text"],
            insertbackground=self.theme["text"],
            selectbackground=self.theme["accent"],
            selectforeground="#ffffff",
            highlightthickness=1,
            highlightbackground=self.theme["border"],
            highlightcolor=self.theme["accent"],
            relief="flat",
            borderwidth=0,
            font=font_px(FONT_MONO),
        )

        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, pady=sc(GAP))

        self.start_btn = ttk.Button(action_frame, text=self._t("start_conversion"), command=self._start)
        self.start_btn.pack(side=tk.LEFT, padx=sc(GAP))
        self.stop_btn = ttk.Button(action_frame, text=self._t("stop_conversion"), command=self._stop)
        self.stop_btn.pack(side=tk.LEFT, padx=sc(GAP))

        self.concurrent_label = ttk.Label(action_frame, text=self._t("max_concurrent"))
        self.concurrent_label.pack(side=tk.LEFT, padx=(sc(25), sc(GAP)))
        ttk.Spinbox(action_frame, from_=1, to=16, textvariable=self.concurrent_var, width=5).pack(side=tk.LEFT)

        self.encoder_label = ttk.Label(action_frame, text=self._t("encoder"))
        self.encoder_label.pack(side=tk.LEFT, padx=(sc(25), sc(GAP)))
        self.encoder_var = tk.StringVar()
        self.encoder_combo = ttk.Combobox(
            action_frame, textvariable=self.encoder_var, state="readonly", width=21,
            values=[b["label"] for b in ENCODER_BACKENDS],
        )
        self.encoder_combo.pack(side=tk.LEFT)
        self.encoder_combo.bind("<<ComboboxSelected>>", self._on_encoder_selected)
        # The dropdown is re-populated every time it opens, which drops per-item colors,
        # so re-apply them right before it is shown.
        self.encoder_combo.bind("<Button-1>", lambda e: self.root.after_idle(self._grey_unavailable_items), add="+")
        self.encoder_combo.bind("<Key-Down>", lambda e: self.root.after_idle(self._grey_unavailable_items), add="+")
        self.encoder_tooltip = Tooltip(self.encoder_combo, lambda: self._t("tip_encoder"), lambda: self.theme)

    def _build_theme_toggle(self, parent):
        """Small icon button in the top-right corner that flips dark / light."""
        size = sc(ICON_SIZE)
        self.theme_btn = tk.Canvas(parent, width=size, height=size,
                                   highlightthickness=0, bd=0, cursor="hand2")
        self.theme_btn.pack(side=tk.RIGHT)
        self.theme_btn.bind("<Button-1>", lambda e: self._toggle_theme())
        self.theme_btn.bind("<Enter>", lambda e: self._draw_theme_icon(hover=True))
        self.theme_btn.bind("<Leave>", lambda e: self._draw_theme_icon(hover=False))
        self.theme_tooltip = Tooltip(self.theme_btn, lambda: self._t("tip_theme"), lambda: self.theme)
        self._draw_theme_icon()

    def _build_language_toggle(self, parent):
        """Icon button left of the theme button that cycles zh -> ja -> en."""
        size = sc(ICON_SIZE)
        self.lang_btn = tk.Canvas(parent, width=size, height=size,
                                  highlightthickness=0, bd=0, cursor="hand2")
        # Packed after the theme button, so it lands to its left.
        self.lang_btn.pack(side=tk.RIGHT)
        self.lang_btn.bind("<Button-1>", lambda e: self._toggle_language())
        self.lang_btn.bind("<Enter>", lambda e: self._draw_language_icon(hover=True))
        self.lang_btn.bind("<Leave>", lambda e: self._draw_language_icon(hover=False))
        self.lang_tooltip = Tooltip(self.lang_btn, lambda: self._t("tip_language"), lambda: self.theme)
        self._draw_language_icon()

    def _draw_language_icon(self, hover=False):
        canvas = self.lang_btn
        canvas.delete("all")
        theme = self.theme
        bg = theme["surface_hi"] if hover else theme["bg"]
        canvas.configure(bg=bg)
        size = sc(ICON_SIZE)
        centre = size / 2.0
        if hover:
            canvas.create_oval(1, 1, size - 1, size - 1,
                               fill=theme["surface_hi"], outline=theme["border"])
        canvas.create_text(centre, centre, text=LANG_LABELS.get(self.language, "EN"),
                           fill=theme["text"], font=font_px(FONT_ICON))

    def _toggle_language(self):
        index = LANGUAGES.index(self.language) if self.language in LANGUAGES else 0
        self.language = LANGUAGES[(index + 1) % len(LANGUAGES)]
        self._apply_language()
        self._draw_language_icon(hover=True)

    def _t(self, key, **kwargs):
        """Look up a UI string in the active language, falling back to English."""
        table = STRINGS.get(self.language) or STRINGS["en"]
        text = table.get(key)
        if text is None:
            text = STRINGS["en"].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def _set_status(self, key, **kwargs):
        """Set the status bar from a translation key so it survives language switches."""
        self._status_key = key
        self._status_args = kwargs
        self.status_var.set(self._t(key, **kwargs))

    def _refresh_status(self):
        if self._status_key:
            self.status_var.set(self._t(self._status_key, **self._status_args))

    def _apply_language(self):
        """Re-render every visible string after a language change."""
        self.root.title(APP_TITLE)
        self.add_folder_btn.config(text=self._t("add_folder"))
        self.add_files_btn.config(text=self._t("add_files"))
        self.load_list_btn.config(text=self._t("load_list"))
        self.remove_btn.config(text=self._t("remove_selected"))
        self.clear_btn.config(text=self._t("clear_list"))
        self.start_btn.config(text=self._t("start_conversion"))
        self.stop_btn.config(text=self._t("stop_conversion"))
        self.concurrent_label.config(text=self._t("max_concurrent"))
        self.encoder_label.config(text=self._t("encoder"))
        self.tip_label.config(text=self._t("tip_drag"))
        self.log_frame.config(text=self._t("log_title"))
        self._refresh_status()

    def _draw_theme_icon(self, hover=False):
        canvas = self.theme_btn
        canvas.delete("all")
        theme = self.theme
        bg = theme["surface_hi"] if hover else theme["bg"]
        canvas.configure(bg=bg)
        size = sc(ICON_SIZE)
        if hover:
            canvas.create_oval(1, 1, size - 1, size - 1,
                               fill=theme["surface_hi"], outline=theme["border"])
        fg = theme["text"]
        # Every offset below is a fraction of the icon's half-width, so the glyph
        # keeps its proportions at any DPI. Ratios come from the original 26px art.
        c = size / 2.0
        if theme["mode"] == "dark":
            # Sun: currently dark, click to go light.
            r = c * 0.31
            canvas.create_oval(c - r, c - r, c + r, c + r, fill=fg, outline="")
            for i in range(8):
                angle = math.radians(i * 45)
                canvas.create_line(c + c * 0.50 * math.cos(angle), c + c * 0.50 * math.sin(angle),
                                   c + c * 0.73 * math.cos(angle), c + c * 0.73 * math.sin(angle),
                                   fill=fg, width=max(1.0, c * 0.108))
        else:
            # Moon: currently light, click to go dark.
            r = c * 0.42
            canvas.create_oval(c - r, c - r, c + r, c + r, fill=fg, outline="")
            canvas.create_oval(c - c * 0.115, c - c * 0.654,
                               c + c * 0.731, c + c * 0.192, fill=bg, outline="")

    def _poll_monitor_dpi(self):
        """
        Follow the window when it is dragged to a monitor with another scale.

        Windows reports the new DPI through GetDpiForWindow straight away, but Tk
        neither notices nor rescales, so this is polled rather than event driven.
        """
        if not self._alive():
            return
        try:
            dpi = _window_dpi(self.root)
            if abs(dpi - self._applied_dpi) >= 1.0:
                previous = self._applied_scale
                self._applied_dpi = dpi
                apply_dpi_scaling(self.root, dpi)
                self._rescale_ui(previous)
        except Exception:
            pass
        self.root.after(700, self._poll_monitor_dpi)

    def _alive(self):
        try:
            return bool(self.root.winfo_exists())
        except Exception:
            return False

    def _rescale_ui(self, previous_scale=None):
        """
        Rebuild the window at the new scale, keeping what the user had going.

        A rebuild rather than a touch-up, because Tk bakes point sizes and pack
        paddings into widgets when they are created - only fresh widgets come out
        right. Skipped while a batch is running so the log wiring stays intact.
        """
        if self._busy:
            return
        self.root.update_idletasks()
        old_w, old_h = self.root.winfo_width(), self.root.winfo_height()
        if old_w <= 1 or old_h <= 1:
            # Nothing laid out yet (window not mapped): fall back to the design size.
            old_w, old_h = sc(WINDOW_SIZE[0]), sc(WINDOW_SIZE[1])
        else:
            ratio = (_dpi_scale / previous_scale) if previous_scale else 1.0
            old_w, old_h = int(old_w * ratio), int(old_h * ratio)
        saved = list(self.file_list)
        log = self.log_box.get("1.0", "end-1c")
        concurrent = self.concurrent_var.get()
        selected = self._selected_backend_key()

        self.frame.destroy()
        # The ttk style carries the button font and paddings, and the named fonts feed
        # every widget that does not set its own - both have to be rebuilt at the new
        # scale before the widgets are created, or they come out at the old size.
        self.theme = apply_window_theme(self.root, self.theme_mode)
        self._build_ui()

        self.concurrent_var.set(concurrent)
        for path in saved:
            self.listbox.insert(tk.END, path)
        if log:
            self.log_box.configure(state=tk.NORMAL)
            self.log_box.insert("1.0", log)
            self.log_box.see("end")
            self.log_box.configure(state=tk.DISABLED)
        if selected:
            backend = BACKENDS_BY_KEY[selected]
            self.encoder_var.set(backend["label"])
            self._last_valid_encoder = backend["label"]
            self._active_backend_key = selected
        elif self._last_valid_encoder:
            self.encoder_var.set(self._last_valid_encoder)

        # Keep whatever size the user had, expressed in the new monitor's pixels.
        self.root.minsize(sc(MIN_SIZE[0]), sc(MIN_SIZE[1]))
        self.root.geometry(f"{max(sc(MIN_SIZE[0]), old_w)}"
                           f"x{max(sc(MIN_SIZE[1]), old_h)}")
        self._style_native_widgets()
        self._refresh_status()
        self._grey_unavailable_items()
        self._bind_dropdown_events()
        self._draw_theme_icon()
        self._draw_language_icon()

    def _probe_encoders(self):
        """Detect usable encoders, pick the best one, and grey out the rest."""
        self._log_ffmpeg_source()
        self.encoder_availability = detect_backends()
        available = [b for b in ENCODER_BACKENDS if self.encoder_availability[b["key"]]]

        if not available:
            self.encoder_var.set("")
            self._log(self._t("log_no_encoder"))
            return

        chosen = available[0]
        self.encoder_var.set(chosen["label"])
        self._last_valid_encoder = chosen["label"]
        self._active_backend_key = chosen["key"]
        self._bind_dropdown_events()
        self._grey_unavailable_items()

        self._log(self._t("log_acceleration", label=chosen["label"]))
        for backend in ENCODER_BACKENDS:
            key = "log_available" if self.encoder_availability[backend["key"]] else "log_unavailable"
            self._log(f"  {backend['label']:<22} {self._t(key)}")
        self._log_encoder_info()

    def _log_ffmpeg_source(self):
        """Report which ffmpeg is in use and at what version.

        The bundled copy lives in the temp folder a onefile build unpacks to, so
        its path is noise; the version is what makes a bug report actionable.
        A copy the user placed themselves, or one found on PATH, is worth naming.
        """
        if FFMPEG_SOURCE == "missing":
            self._log(self._t("log_ffmpeg_missing_src"))
            return
        if FFMPEG_SOURCE in ("bundled", "vendor"):
            self._log(self._t("log_ffmpeg_bundled"))
        elif FFMPEG_SOURCE == "beside":
            self._log(self._t("log_ffmpeg_beside", path=FFMPEG_CMD))
        else:
            self._log(self._t("log_ffmpeg_path", path=FFMPEG_CMD))
        version = ffmpeg_version()
        if version:
            self._log(self._t("log_ffmpeg_version", ver=version))

    def _log_encoder_info(self):
        """Print the encoder and its exact arguments, including the quality settings."""
        backend = BACKENDS_BY_KEY.get(self._active_backend_key)
        if not backend:
            return
        self._log(self._t("log_encoder_codec", codec=backend["codec"]))
        self._log(self._t("log_quality_args", args=" ".join(backend["args"])))
        self._log(self._t("log_common_args", args=" ".join(COMMON_ARGS)))

    def _dropdown_listbox_path(self):
        """Widget path of the Listbox ttk.Combobox uses inside its popdown window.

        That Listbox is built by Tcl, not by tkinter, so it is not registered in the
        Python widget tree and nametowidget() cannot find it. Everything below talks
        to it through tk.call with the path instead.
        """
        popdown = self.root.tk.call("ttk::combobox::PopdownWindow", self.encoder_combo)
        return f"{popdown}.f.l"

    def _grey_unavailable_items(self):
        """Paint the dropdown list and colour unusable backends grey."""
        if not getattr(self, "encoder_availability", None):
            return
        try:
            path = self._dropdown_listbox_path()
        except Exception:
            return
        # The popdown Listbox is built by Tcl and is not reachable through ttk styles,
        # so it has to be painted directly. ttk re-applies its own options whenever the
        # dropdown opens, which is why this also runs from the <Map> handler.
        theme = self.theme
        try:
            self.root.tk.call(
                path, "configure",
                "-background", theme["sunken"],
                "-foreground", theme["text"],
                "-selectbackground", theme["accent"],
                "-selectforeground", theme["select_fg"],
                "-borderwidth", "0",
                "-highlightthickness", "1",
                "-highlightbackground", theme["border"],
                "-highlightcolor", theme["accent"],
            )
        except Exception:
            pass
        for index, backend in enumerate(ENCODER_BACKENDS):
            usable = self.encoder_availability.get(backend["key"], False)
            color = self.theme["text"] if usable else self.theme["text_dim"]
            try:
                self.root.tk.call(path, "itemconfigure", index, "-foreground", color)
            except Exception:
                # Items only exist after the dropdown has been opened once; the
                # <Map> handler installed by _bind_dropdown_events will retry then.
                return

    def _bind_dropdown_events(self):
        """Install dropdown handlers once - they must survive a failed recolor."""
        try:
            path = self._dropdown_listbox_path()
            # "bind" is a top-level Tcl command, not a widget subcommand, so the widget
            # path is its first argument.
            callback = self.root.register(self._on_dropdown_click)
            # ttk commits the pick on ButtonRelease-1 (see ttk::combobox::Release), so
            # that is the event that has to be vetoed - blocking Button-1 alone lets
            # the release go through and still selects the row.
            self.root.tk.call("bind", path, "<ButtonRelease-1>", f"{callback} %W %y")
            # ttk rebuilds the list items when the dropdown opens, which drops the
            # per-item colors, so recolor on <Map> too. Covers keyboard opening.
            recolor = self.root.register(lambda: self.root.after_idle(self._grey_unavailable_items))
            self.root.tk.call("bind", path, "<Map>", recolor)
        except Exception:
            pass

    def _on_dropdown_click(self, widget_path, y):
        """Refuse a click on a greyed-out entry; 'break' cancels ttk's own handling."""
        try:
            index = int(self.root.tk.call(widget_path, "nearest", y))
        except Exception:
            return ""
        if 0 <= index < len(ENCODER_BACKENDS):
            if not self.encoder_availability.get(ENCODER_BACKENDS[index]["key"]):
                self.root.bell()
                return "break"
        return ""

    def _on_encoder_selected(self, event=None):
        """Keep the selection on a usable backend even if it was set by keyboard."""
        label = self.encoder_var.get()
        backend = next((b for b in ENCODER_BACKENDS if b["label"] == label), None)
        if backend and self.encoder_availability.get(backend["key"]):
            self._last_valid_encoder = label
            if self._active_backend_key != backend["key"]:
                self._active_backend_key = backend["key"]
                self._log(self._t("log_encoder_switched", label=label))
                self._log_encoder_info()
            return
        if self._last_valid_encoder:
            self.encoder_var.set(self._last_valid_encoder)
            self.root.bell()

    def _selected_backend_key(self):
        label = self.encoder_var.get()
        for backend in ENCODER_BACKENDS:
            if backend["label"] == label and self.encoder_availability.get(backend["key"]):
                return backend["key"]
        return None

    def _toggle_theme(self):
        self.theme_mode = "light" if self.theme_mode == "dark" else "dark"
        self.theme = apply_window_theme(self.root, self.theme_mode)
        self._style_native_widgets()
        self._draw_theme_icon(hover=True)

    def _style_native_widgets(self):
        """Re-apply colors to classic tk widgets, which the ttk theme cannot reach."""
        theme = self.theme
        self.listbox.configure(
            bg=theme["sunken"], fg=theme["text"],
            selectbackground=theme["accent"], selectforeground=theme["select_fg"],
            highlightbackground=theme["border"], highlightcolor=theme["accent"],
        )
        self.log_box.configure(
            bg=theme["sunken"], fg=theme["text"], insertbackground=theme["text"],
            selectbackground=theme["accent"], selectforeground=theme["select_fg"],
            highlightbackground=theme["border"], highlightcolor=theme["accent"],
        )
        self.tip_label.configure(foreground=theme["text_dim"])
        # Greyed-out dropdown entries are painted with theme colors, so refresh them too.
        self._grey_unavailable_items()

    def _set_ui_busy(self, busy):
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.add_folder_btn.config(state=state)
        self.add_files_btn.config(state=state)
        self.load_list_btn.config(state=state)
        self.remove_btn.config(state=state)
        self.clear_btn.config(state=state)

    def _log(self, msg):
        self.log_box.config(state=tk.NORMAL)
        self.log_box.insert(tk.END, msg + "\n")
        self.log_box.see(tk.END)
        self.log_box.config(state=tk.DISABLED)

    def _add_folder(self):
        folder = filedialog.askdirectory(title=self._t("fd_select_folder"))
        if not folder:
            return
        added = 0
        for root_dir, _, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in VIDEO_EXTS:
                    path = os.path.join(root_dir, f)
                    if path not in self.file_list:
                        self.file_list.append(path)
                        self.listbox.insert(tk.END, path)
                        added += 1
        self._set_status("status_added_folder", n=added)
        self._log(self._t("log_added_folder", path=folder, n=added))

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title=self._t("fd_select_videos"),
            filetypes=[
                (self._t("fd_video_files"),
                 "*.mp4 *.mov *.mkv *.avi *.wmv *.flv *.webm *.m4v *.mts *.m2ts"),
                (self._t("fd_all_files"), "*.*"),
            ]
        )
        if not files:
            return
        added = 0
        for path in files:
            if path not in self.file_list:
                self.file_list.append(path)
                self.listbox.insert(tk.END, path)
                added += 1
        self._set_status("status_added_files", n=added, total=len(self.file_list))
        self._log(self._t("log_added_files", n=added))

    def _on_drop(self, event):
        if self._busy:
            self._set_status("status_cannot_add")
            return
        paths = self.root.tk.splitlist(event.data)
        if not paths:
            return

        total_added = 0
        for path in paths:
            path = path.strip('"')
            if os.path.isdir(path):
                added = 0
                for root_dir, _, files in os.walk(path):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in VIDEO_EXTS:
                            file_path = os.path.join(root_dir, f)
                            if file_path not in self.file_list:
                                self.file_list.append(file_path)
                                self.listbox.insert(tk.END, file_path)
                                added += 1
                self._log(self._t("log_dropped_folder", path=path, n=added))
                total_added += added
            elif os.path.isfile(path):
                if path.lower().endswith(".txt"):
                    count_before = len(self.file_list)
                    self._load_list_file(path)
                    total_added += len(self.file_list) - count_before
                    continue
                ext = os.path.splitext(path)[1].lower()
                if ext in VIDEO_EXTS and path not in self.file_list:
                    self.file_list.append(path)
                    self.listbox.insert(tk.END, path)
                    total_added += 1

        self._set_status("status_added_drop", n=total_added, total=len(self.file_list))
        self._log(self._t("log_drop_complete", n=total_added))

    def _load_list(self):
        path = filedialog.askopenfilename(
            title=self._t("fd_select_list"),
            filetypes=[(self._t("fd_text_files"), "*.txt"), (self._t("fd_all_files"), "*.*")]
        )
        if not path:
            return
        self._load_list_file(path)

    def _load_list_file(self, path):
        added = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if not os.path.isabs(line):
                        base = os.path.dirname(path)
                        line = os.path.join(base, line)
                    if os.path.isfile(line) and line not in self.file_list:
                        self.file_list.append(line)
                        self.listbox.insert(tk.END, line)
                        added += 1
            self._set_status("status_loaded_files", n=added, path=path)
            self._log(self._t("log_loaded_list", path=path, n=added))
        except Exception as e:
            messagebox.showerror(self._t("mb_error_title"),
                                 self._t("mb_load_failed", err=e))

    def _remove_selected(self):
        selected = list(self.listbox.curselection())
        if not selected:
            messagebox.showinfo(self._t("mb_info_title"), self._t("mb_select_msg"))
            return
        # Remove from back to front so indices stay valid
        removed = 0
        for idx in reversed(selected):
            path = self.file_list[idx]
            self.file_list.pop(idx)
            self.listbox.delete(idx)
            removed += 1
        self._set_status("status_removed", n=removed, total=len(self.file_list))
        self._log(self._t("log_removed", n=removed))

    def _clear_list(self):
        self.file_list.clear()
        self.listbox.delete(0, tk.END)
        self._set_status("status_list_cleared")

    def _handle_initial_paths(self, paths):
        for p in paths:
            p = p.strip('"')
            if os.path.isdir(p):
                self._log(self._t("log_initial_folder", path=p))
                for root_dir, _, files in os.walk(p):
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in VIDEO_EXTS:
                            path = os.path.join(root_dir, f)
                            if path not in self.file_list:
                                self.file_list.append(path)
                                self.listbox.insert(tk.END, path)
            elif os.path.isfile(p):
                if p.lower().endswith(".txt"):
                    self._load_list_file(p)
                elif os.path.splitext(p)[1].lower() in VIDEO_EXTS and p not in self.file_list:
                    self.file_list.append(p)
                    self.listbox.insert(tk.END, p)
        self._set_status("status_loaded_cmdline", n=len(self.file_list))

    def _start(self):
        if not self.file_list:
            messagebox.showwarning(self._t("mb_no_files_title"), self._t("mb_no_files_msg"))
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(self._t("mb_busy_title"), self._t("mb_busy_msg"))
            return

        backend_key = self._selected_backend_key()
        if backend_key is None:
            messagebox.showwarning(self._t("mb_no_encoder_title"), self._t("mb_no_encoder_msg"))
            return
        # Snapshot for the worker thread - reading a Tk variable off the UI thread is not safe.
        self._active_backend_key = backend_key

        self.stop_event.clear()
        self._set_ui_busy(True)
        self.worker = threading.Thread(target=self._convert_all, daemon=True)
        self.worker.start()

    def _stop(self):
        if not self.worker or not self.worker.is_alive():
            self._set_status("not_running")
            return
        self.stop_event.set()
        self._set_status("stopping")

    def _convert_all(self):
        total = len(self.file_list)
        self.progress.config(maximum=total, value=0)
        completed = 0
        self.stop_event.clear()

        max_workers = max(1, self.concurrent_var.get())
        backend = BACKENDS_BY_KEY.get(self._active_backend_key)
        label = backend["label"] if backend else "?"
        self.root.after(0, lambda: self._log(
            self._t("log_start", total=total, n=max_workers, label=label)))
        if backend and backend["codec"] == "libsvtav1":
            self.root.after(0, lambda: self._log(self._t("log_cpu_slow")))

        def update_status(done):
            self.root.after(0, lambda v=done: self.progress.config(value=v))
            self.root.after(0, lambda d=done: self._set_status("processing", done=d, total=total))

        def process_future(future, path):
            nonlocal completed
            completed += 1
            try:
                success, msg = future.result()
            except Exception as e:
                msg = self._t("log_exception", path=path, err=e)
            self.root.after(0, lambda m=msg: self._log(m))
            update_status(completed)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for file_path in self.file_list:
                if self.stop_event.is_set():
                    self.root.after(0, lambda: self._log(self._t("log_stop_requested")))
                    break
                self.root.after(0, lambda p=file_path: self._log(self._t("log_queued", path=p)))
                future = executor.submit(self._convert_one, file_path)
                futures[future] = file_path

            for future in as_completed(futures):
                if self.stop_event.is_set():
                    continue
                process_future(future, futures[future])

        def finish():
            self._set_ui_busy(False)
            if self.stop_event.is_set():
                self._set_status("stopped_by_user")
                messagebox.showinfo(self._t("mb_stopped_title"), self._t("mb_stopped_msg"))
            else:
                self._set_status("done")
                messagebox.showinfo(self._t("mb_done_title"), self._t("mb_done_msg"))
        self.root.after(0, finish)

    def _convert_one(self, file_path):
        file_dir = os.path.dirname(file_path)
        filename = os.path.splitext(os.path.basename(file_path))[0]
        tmp_name = f"{filename}_tmp_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(file_dir, f"{filename}.mp4")
        tmp_path = os.path.join(file_dir, tmp_name)

        cmd = [
            FFMPEG_CMD,
            "-loglevel", "error",
            "-stats",
            "-i", file_path,
            *build_ffmpeg_args(self._active_backend_key),
            "-y", tmp_path,
        ]

        try:
            creationflags = subprocess.CREATE_NO_WINDOW
            subprocess.run(
                cmd, check=True, capture_output=True, text=True,
                creationflags=creationflags
            )
        except subprocess.CalledProcessError as e:
            self._safe_remove(tmp_path)
            return False, self._t("log_failed", path=file_path) + f"\n{e.stderr or e}"
        except FileNotFoundError:
            return False, self._t("log_ffmpeg_missing", path=file_path)

        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(tmp_path, output_path)
        except OSError as e:
            self._safe_remove(tmp_path)
            return False, self._t("log_replace_failed", path=file_path, err=e)

        return True, self._t("log_done", path=output_path)

    def _safe_remove(self, path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


def main():
    _enable_dpi_awareness()
    initial = sys.argv[1:] if len(sys.argv) > 1 else None
    root = TkinterDnD.Tk()
    app = ConverterGUI(root, initial_paths=initial)
    root.mainloop()


if __name__ == "__main__":
    main()
