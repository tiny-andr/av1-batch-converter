# AV1 Batch Converter

**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

A small Windows GUI for batch-converting videos to AV1. Drop in a folder, pick the
acceleration device you want, hit start. The encoder list is built by actually
probing your machine, so you never get a device that silently fails.

![AV1 Batch Converter, dark theme](docs/screenshot-dark-en.png)

## Why this exists

Dragging a few hundred files onto a `.bat` script fails: Windows caps a command line
at 8191 characters, so the tail of the list is silently dropped. This tool takes the
file list in-process instead, so the limit does not apply.

## Features

- **Batch queue** — add a folder, add files, drag and drop, or load a `list.txt`
- **Automatic accelerator detection** — NVIDIA / AMD / Intel / CPU, probed at startup
- **Multilingual UI** — Chinese, Japanese and English, follows your system language
- **Dark and light theme**, plus the matching Windows 11 title bar
- **HiDPI aware** — text and layout scale to whichever monitor the window is on
- **Parallel conversion** — 1 to 16 files at a time
- **No console windows** — ffmpeg runs hidden

## Requirements

- Windows 10 or 11
- [ffmpeg](https://ffmpeg.org/download.html) on your `PATH`
- A GPU whose encoder ffmpeg can drive, if you want hardware acceleration
  (AV1 encoding needs a recent card: RTX 40 series, RX 7000 series, Arc, or newer)

## Usage

There is no installer. Download `av1_batch_converter.exe` from
[Releases](../../releases) and run it.

Add files in whichever way suits you:

| Method | Notes |
| --- | --- |
| **Add Folder** | Scans the folder recursively for video files |
| **Add Files** | Normal multi-select file dialog |
| **Drag and drop** | Drop files or folders onto the list |
| **Load list.txt** | One path per line, `#` comments allowed |
| **Command line** | Pass files or folders as arguments, or drop them onto the exe |

Then set **Max concurrent** and the **Encoder**, and press **Start Conversion**.

### Output

Each file is written next to its source as `<name>.mp4` (AV1 in an MP4 container) and
**the original file is deleted**. Conversion goes through a temp file, so a failure
leaves your source untouched.

## Acceleration devices

The device list is not guessed from hardware names. At startup the program runs a
two-frame test encode with each candidate and keeps the ones that return success.
That matters because "has an Intel iGPU" does not mean "can encode AV1", and a
missing AMD runtime DLL looks exactly like no AMD card at all.

Unavailable devices stay in the dropdown but are greyed out and cannot be selected.
The first usable device in this order is picked by default:

| Priority | Device | Encoder | Parameters |
| --- | --- | --- | --- |
| 1 | NVIDIA GPU | `av1_nvenc` | `-preset p7 -rc vbr -cq 28 -b:v 0 -tune hq` |
| 2 | AMD GPU | `av1_amf` | `-quality quality -rc cqp -qp_i 28 -qp_p 28` |
| 3 | Intel iGPU | `av1_qsv` | `-preset 7 -global_quality 28` |
| 4 | CPU | `libsvtav1` | `-preset 6 -crf 30` |

Common to every device: `-g 240 -movflags +faststart -c:a aac -b:a 128k`

> The `28` in each row is **not** the same quality. The cq, qp_i/qp_p, global_quality
> and crf scales are not equivalent, so the numbers were chosen per encoder to land
> in a similar visual range.

CPU encoding with SVT-AV1 is one to two orders of magnitude slower than a GPU
encoder. It is the fallback, and the log says so when it is selected.

When the encoder changes, the log reprints the exact arguments in use:

```
  encoder    : av1_nvenc
  quality    : -preset p7 -rc vbr -cq 28 -b:v 0 -tune hq
  common     : -g 240 -movflags +faststart -c:a aac -b:a 128k
```

## Quality: this is a lossy re-encode

Every frame is decoded and encoded again. It is **not** a container swap or a rename,
quality always drops somewhat, and the original is deleted, so it cannot be undone.

Measured on clean 1080p footage, `-cq 28` scores VMAF 96 — visually indistinguishable
for most content. On a synthetic clip that is noisy across the whole frame the same
setting drops to VMAF 74. Source complexity matters far more than the cq number.

What survives and what does not, all measured:

| Item | Result |
| --- | --- |
| 10-bit depth | Kept (`yuv420p10le` is not flattened to 8-bit) |
| HDR10 metadata | Fully kept (bt2020nc + smpte2084 + mastering display + content light level) |
| **Multiple audio tracks** | **Only the first is kept, the rest are dropped silently** |
| **Subtitles** | **All dropped** |
| Audio | Forced to AAC 128k, so lossless or high-bitrate sources lose quality |

If any of those matter for your footage, convert with plain ffmpeg instead.

## Languages and theme

The header has two icon buttons. The language button sits to the left of the theme
button and shows the current language (`中` / `日` / `EN`); clicking cycles
Chinese → Japanese → English. The initial language follows your Windows UI language.

![AV1 Batch Converter, light theme](docs/screenshot-light-en.png)

Neither choice is persisted, so each launch starts from the defaults in the source.

## HiDPI

The UI is per-monitor DPI aware, and text plus layout follow the monitor the window
is on. Dragging the window from a 100% display to a 150% one rescales it instead of
leaving everything tiny.

## Build from source

`av1_batch_converter.pyw` is the whole program — Python and tkinter, no other runtime
dependency beyond `pywinstyles` (optional, for the themed title bar) and
`tkinterdnd2` (for drag and drop).

```bat
python -m pip install pyinstaller tkinterdnd2 pywinstyles
pyinstaller av1_batch_converter.spec --noconfirm --distpath dist --workpath build
```

`build.bat` does the same thing against a dedicated virtualenv and leaves
`dist\av1_batch_converter.exe`.

Note for Python 3.13: add `sys.modules["tkinter.tix"] = tkinter` before importing
tkinterdnd2, or the import fails on the removed `tkinter.tix` module.

## Development notes

Engineering notes — implementation details, pitfalls, verification scripts and the
measurement methodology — are in [DEVELOPMENT.md](DEVELOPMENT.md) (Chinese).

## License

[MIT](LICENSE)
