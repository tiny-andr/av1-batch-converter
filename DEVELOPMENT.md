# 开发笔记（作者自用，中文）

> 这是作者本机的工程笔记：实现细节、踩过的坑、验证脚本、打包流程。
> 面向使用者的说明见 [README.md](README.md) / [README.zh-CN.md](README.zh-CN.md) / [README.ja.md](README.ja.md)。
> 文中出现的绝对路径都是作者机器上的位置。

---

用来解决 Windows 拖拽文件到 bat 脚本时的命令行长限制问题。

## 为什么直接拖 200 个文件到 bat 上会失败

拖拽文件到 `.bat` 或 `.exe` 上时，Windows 会把所有文件路径拼成一条命令行，例如：

```
"av1 nvenc.bat" "C:\path\to\file1.mp4" "C:\path\to\file2.mp4" ...
```

Windows 命令行总长度限制是 **8191 字符**。200 个文件只要平均路径超过约 40 字符就会爆表。

**这个限制跟用什么语言写程序无关。** 直接拖拽文件到 exe 上，exe 收到的仍然是命令行参数，仍然受 8191 字符限制。

## 规避方法

这个程序改为用以下方式获取文件列表，绕开命令行限制：

- **拖一个文件夹**：程序自动遍历文件夹内所有视频
- **用「Add Files」按钮选择文件**：Windows 文件对话框可多选，不受命令行限制
- **拖一个 `list.txt`**：把文件路径写进 txt，程序读取

## 使用方法

### 1. 直接运行

双击 `av1_batch_converter.exe`：

- 点 **Add Folder** 选一个文件夹
- 或点 **Add Files** 多选文件
- 或直接把文件/文件夹**拖到列表区域**
- 点 **Start Conversion** 开始转换
- 可设置 **Max concurrent** 并行数量（默认 1）

### 并行转换

界面右下角的 **Max concurrent** 控制同时运行几个 ffmpeg：

- 填 `1`：串行，跟原来 bat 一样，一个转完再转下一个
- 填 `3` 或 `5`：同时跑 3/5 个 ffmpeg，适合磁盘和 GPU 吃得住的情况
- 不建议超过 CPU 核心数或显存能承受的范围

### 隐藏 ffmpeg 黑窗

点击 **Start Conversion** 后，ffmpeg 不会再弹出黑色命令行窗口，所有进度只显示在软件界面里。

### 2. 拖文件夹到 exe 上

直接把一个**文件夹**拖到 `av1_batch_converter.exe` 上，程序启动后会自动加载文件夹里的视频。

> 注意：拖的是**文件夹**，不是单个文件。拖单个文件仍然受命令行限制。

### 3. 用 list.txt

新建一个 `list.txt`，每行写一个视频完整路径：

```
D:\videos\a.mp4
D:\videos\b.mp4
E:\media\c.mkv
```

把 `list.txt` 拖到 exe 上，程序会读取列表。

## 加速设备选择

界面右下角的 **Encoder** 下拉框可以选择用哪个设备编码。程序启动时会**逐个试跑编码器**来判断可用性，而不是只看装了哪块显卡。

### 为什么必须试跑

"有 Intel 核显" ≠ "能用 QSV 编 AV1"：

- Intel 核显里**只有 Arc 独显和 Meteor Lake 及更新的核显**才支持 AV1 编码。
  本机的 UHD 770（i7-12700）就只支持 AV1 **解码**，试跑报 `Error creating a MFX session: -9`。
- AMD 侧如果没装驱动运行时（`amfrt64.dll` 缺失），表现和"没有 AMD 显卡"一模一样。
- NVIDIA 需要 GTX 40 系及更新的 NVENC 才支持 AV1 编码。

### 设备优先级

启动时按以下顺序取第一个可用的作为默认值：

```
NVIDIA GPU (NVENC) → AMD GPU (AMF) → Intel iGPU (QSV) → CPU (SVT-AV1)
```

不可用的设备在下拉框里**显示为灰色且点不动**（点击会响铃提示，不会改变选择）。

### 各设备的编码参数

| 设备 | 编码器 | 参数 |
| --- | --- | --- |
| NVIDIA | `av1_nvenc` | `-preset p7 -rc vbr -cq 28 -b:v 0 -tune hq` |
| AMD | `av1_amf` | `-quality quality -rc cqp -qp_i 28 -qp_p 28` |
| Intel | `av1_qsv` | `-preset 7 -global_quality 28` |
| CPU | `libsvtav1` | `-preset 6 -crf 30` |

公共参数（所有设备一致）：`-g 240 -movflags +faststart -c:a aac -b:a 128k`

> 注意 cq / global_quality / crf 三者的刻度**互不等价**，同样的 `28` 在不同编码器上画质不同。
> NVENC 保持原参数未动（`-cq 28`）；SVT-AV1 用 `-crf 30` 是为了贴近 NVENC 的观感。

**CPU 编码（SVT-AV1）比 GPU 慢一到两个数量级**，只在没有可用 GPU 编码器时作为保底，选中时日志里会提示。

### 在本机实测的结果

| 设备 | 状态 | 原因 |
| --- | --- | --- |
| NVIDIA GPU (NVENC) | ✅ 可用 | RTX 4070 Ti SUPER |
| AMD GPU (AMF) | ❌ 不可用 | 无 AMD 显卡（`amfrt64.dll` 缺失） |
| Intel iGPU (QSV) | ❌ 不可用 | UHD 770 不支持 AV1 编码（`MFX session: -9`） |
| CPU (SVT-AV1) | ✅ 可用 | SVT-AV1 v4.2.0 |

> AMD 和 Intel 两条分支**无法在本机实测**（没有对应硬件），参数按 ffmpeg 官方选项书写。
> 如果你换到那两种机器上发现报错，把 ffmpeg 的错误原文发出来即可调整。

## 画质：不是无损，是完整的有损重编码

`-c:v av1_nvenc` 会把每一帧重新编码一遍，**不是换容器、不是改后缀**。画质必然下降，程序还会删掉原文件，所以**不可逆**。

### cq 28 到底是什么水平（实测）

`-cq` 的量表是 **0~63**（0 = 交给编码器自动），28 正好在正中间 —— 单看刻度是"中等"。
但刻度不等于画质，实测（ffmpeg 9.0 + RTX 4070 Ti SUPER，1080p 真实拍摄素材 5 秒，源为 4.6 Mbps H.264）：

| `-cq` | 体积（源 2.87 MB） | PSNR | SSIM | VMAF | 评价 |
| --- | --- | --- | --- | --- | --- |
| 16 | 25.6 MB（源 892%） | 49.07 | 0.9947 | **97.71** | 过度，体积反而比源大 9 倍 |
| 20 | 17.6 MB（613%） | 47.82 | 0.9933 | 97.39 | 极高品质 |
| 24 | 11.7 MB（409%） | 46.42 | 0.9912 | 96.91 | 高品质 |
| **28** | **7.9 MB（274%）** | **44.87** | **0.9880** | **96.18** | **肉眼基本看不出损失**（当前设置） |
| 32 | 5.2 MB（182%） | 43.07 | 0.9828 | 95.09 | 很好，继续省体积 |
| 36 | 3.5 MB（122%） | 41.17 | 0.9745 | 93.59 | 优秀线边缘，仔细看能发现 |
| 44 | 1.5 MB（53%） | 37.40 | 0.9445 | 88.44 | 明显有损 |

VMAF 参考：93+ 优秀（肉眼难以分辨），80+ 良好，<80 能看出问题。

结论：**干净素材下 cq 28 已经算高品质**（VMAF 96），往上加到 20 只能换回 1.5 分 VMAF，体积却翻一倍多，不划算。

### ⚠️ 但片源复杂度的影响远超 cq 数字

同一台机器、同样 cq 28，换成**高噪声素材**（全画面随机噪点，模拟夜景/高 ISO）：

| 片源 | VMAF |
| --- | --- |
| 干净的真实拍摄素材 | **96.18** |
| 全画面噪声的合成片源 | **74.0** |

差了 22 分。原因是随机噪声不可压缩，编码器只能抹掉它，而"抹掉噪声"本身就是画质损失。

所以：**夜景、高 ISO、老 DV 录像这类噪点多的片子，cq 28 会明显掉到"看出涂抹"的水平**，建议这类素材降到 20~24。

> 测试方法备注：用 `lavfi` 合成片源加 `noise` 滤镜测编码器会得出**过于悲观**的结论 —— 随机噪声会把 PSNR 锁死在噪声功率对应的下限，cq 16 和 cq 44 测出来只差 0.16 dB（体积却差 12 倍），完全失真。测画质必须用真实素材。

### 什么会保留、什么会丢（均已实测）

| 项目 | 结果 |
| --- | --- |
| 10bit 位深 | ✅ 保留（`yuv420p10le` 未被降到 8bit） |
| HDR10 | ✅ 完整保留：bt2020nc + smpte2084 + mastering display + content light level 全部写入 |
| **多条音轨** | ⚠️ **只留第一条**，第二条静默丢弃（实测 2 条音轨 → 输出只剩 1 条） |
| **字幕** | ⚠️ **全部丢弃**（实测 srt 字幕流消失） |
| 音频 | 强制转 AAC 128k，源为无损/高码率时会二次降质 |

丢失音轨和字幕的根因：命令里没有 `-map`，ffmpeg 默认对每种流类型只选一路最好的，且 mp4 不收图形字幕。

### 想少损失一点

`FFMPEG_ARGS`（源码第 35 行）可以调：

- 画质优先：`-cq` 从 `28` 降到 `20`~`24`（数值越小质量越高，体积越大）
- 音效优先：`-b:a` 从 `128k` 提到 `192k`/`256k`
- 要保留全部音轨：加 `-map 0:v -map 0:a`
- 要保留文本字幕：加 `-map 0:s? -c:s mov_text`（图形字幕 PGS/DVDSUB 无法进 mp4，只能丢弃）

## 依赖

- 需要 ffmpeg 在系统 PATH 中
- 想用硬件加速需要一块 ffmpeg 能驱动的显卡：NVIDIA（`av1_nvenc`）、AMD（`av1_amf`）、
  Intel（`av1_qsv`）任一即可；都没有则回退到 CPU（`libsvtav1`）。AV1 编码本身要求较新的卡
- 界面外观依赖 `pywinstyles`（可选，缺失时自动降级为系统默认外观）
- 拖放依赖 `tkinterdnd2`

## 源码

`av1_batch_converter.pyw` 是 Python 源码，使用 tkinter 做界面。版本号在文件顶部的 `APP_VERSION`，
打包时由 `version_info.txt` 写进 exe 的版本资源（右键属性可见）。

## 外观

Windows 11 风格外观，通过 `pywinstyles` 调用 DWM 实现，不是控件自绘：

- 标题栏跟随明暗主题（`DWMWA_USE_IMMERSIVE_DARK_MODE`）
- ttk 使用 `clam` 主题并整体重新配色
- 强调色自动读取系统 accent color，读不到时回退到 Fluent 蓝 `#0078d4`
- 开启 per-monitor DPI 感知，避免在 150% 缩放的副屏上发虚

**主题切换按钮**在窗口右上角，26×26 的图标：

- 暗色时显示太阳（点了变亮），亮色时显示月亮（点了变暗）
- 鼠标悬浮显示「切换主题」提示，延迟 450ms 出现
- 切换会连同标题栏、ttk 控件、列表框、日志框一起换色
- 图标是 Canvas 现画的，没有图片依赖，打包不受影响

**主题不会持久化**，每次启动用文件顶部的 `DEFAULT_THEME`。

### HiDPI 缩放（4K 屏上文字一律很小的问题）

原来的做法只在启动时调一次 `tk scaling`，结果把窗口拖到 150% 的 4K 副屏上文字依然很小。原因有两条，缺一不可：

1. **Tk 只在进程启动时按主显示器读一次 DPI**，之后就算窗口换到别的显示器也不会重读。本机主屏是 2K@100%，副屏是 4K@150%，所以 Tk 一直按 100% 排版。
2. **`tk scaling` 改不动已经建好的字体**。Tk 在字体创建那一刻就把"点"换算成"像素"缓存下来了，之后改 scaling 只影响新建的字体。所以光调 scaling 没用，点数字号的字体必须重建。

`GetDpiForWindow(hwnd)` 是唯一会随窗口所在显示器实时变化的接口（100% 屏返回 96、150% 屏返回 144、竖屏返回 96），Tk 不认它，所以自己轮询。

改法：

- 顶部定义一组**以 96 DPI 为基准的设计尺寸**：`WINDOW_SIZE`、`MIN_SIZE`、`ICON_SIZE`、`PAD`、`GAP` 和字号表 `FONT_BODY` / `FONT_TITLE` / `FONT_ICON` / `FONT_MONO`。
- 所有尺寸走 `sc(px)`（乘缩放比后取整），所有字体走 `font_px(spec)`：
  ```python
  def font_px(spec, weight=None):
      family, points = spec[0], spec[1]
      size = -max(6, int(round(points * DPI_REFERENCE / 72.0 * _dpi_scale)))
      return (family, size, weight) if weight else (family, size)
  ```
  **负数字号 = 像素字号**，这是关键：只有像素字号会被重新应用，点数字号不认新的 scaling。
- `_poll_monitor_dpi` 每 700ms 比一次 `GetDpiForWindow`，差值 ≥ 1 就重排。
- 重排走 `_rescale_ui()`：销毁 `self.frame` → **重新 `apply_window_theme()`（必须，见下）** → `_build_ui()` → 恢复状态。

三个坑：

- **`_rescale_ui` 里必须先重新 `apply_window_theme()`**。不重新应用的话，ttk 的 style 还是旧的一套，字体和 padding 全都停在原来的尺寸 —— 只重建控件是没用的，ttk 控件的样式来自 style，不是来自控件本身。
- **`withdraw()` 过的窗口不认 `geometry()` 尺寸变更**。窗口没映射时改 geometry，读回来还是老值。验证时只能用「拦截 `geometry` 调用、断言请求的尺寸」这种办法（见 `_dpi_check.py`）。
- 拖到另一个显示器时窗口尺寸也要跟着放大：按新旧缩放比换算当前尺寸，并同步 `minsize`。

### 语言切换（中 / 日 / 英）

**语言切换按钮**紧挨着主题按钮的左边，同样是 26×26 的 Canvas 图标，显示当前语言：

| 当前语言 | 图标文字 |
| --- | --- |
| 中文 | 中 |
| 日本語 | 日 |
| English | EN |

- **启动时跟随系统语言**：读 `GetUserDefaultUILanguage()`，取低 10 位主语言 ID，`0x04` → 中文、`0x11` → 日文、其余一律英文
- 点击按 `中文 → 日文 → 英文 → 中文` 循环，鼠标悬浮显示「切换语言」提示
- 切换会立即重写**标题、全部按钮、标签、拖放提示、日志框标题、状态栏**
- **切换主题和语言都不写日志**（日志只记和转码有关的事），所以日志里那几行编码参数不会被反复切换刷掉
- **状态栏文字跟着语言走**：状态不是存字符串，而是存翻译键 + 参数（`_set_status(key, **kwargs)`），切语言时按新语言重新渲染一遍，所以「处理中 3/10」会变成「Processing 3/10」而不是留着上一种语言
- **主题/语言两个 tooltip 的文字都是可调用的**（`lambda: self._t(...)`），不是启动时固定的字符串 —— 否则切完语言提示文字还是旧的

三语的字符串集中在文件顶部的 `STRINGS` 字典里，键名一一对应，缺键自动回退英文：

```python
STRINGS = {"en": {...}, "zh": {...}, "ja": {...}}
LANGUAGES = ["zh", "ja", "en"]          # 点击循环顺序
LANG_LABELS = {"zh": "中", "ja": "日", "en": "EN"}   # 按钮图标
```

新增一个界面字符串时，**三个语言字典都要加**，用 `self._t("key", arg=...)` 取值。

> 日文和中文的「停止」都是 `停止`，所以三语唯一性检测里这一项要豁免 —— 那是正常的，
> 不是漏翻。

### 日志里的编码参数

程序启动探测完设备后，会把当前的编码器与质量参数打进日志：

```
加速设备: NVIDIA GPU (NVENC)
  NVIDIA GPU (NVENC)     可用
  AMD GPU (AMF)          不可用
  Intel iGPU (QSV)       不可用
  CPU (SVT-AV1)          可用
  编码器    : av1_nvenc
  质量参数  : -preset p7 -rc vbr -cq 28 -b:v 0 -tune hq
  公共参数  : -g 240 -movflags +faststart -c:a aac -b:a 128k
```

**切换加速器会重新打印这三行**（`_on_encoder_selected` → `_log_encoder_info`），所以日志里
能直接看出每个任务实际用的是哪套参数：

```
已切换编码器为 CPU (SVT-AV1)
  编码器    : libsvtav1
  质量参数  : -preset 6 -crf 30
  公共参数  : -g 240 -movflags +faststart -c:a aac -b:a 128k
```

三行标签也是翻译过的（`编码器` / `エンコーダー` / `encoder`），参数本身是 ffmpeg 选项，不翻译，
所以**换语言不会让已写进日志的内容变样**，只有新写的行用新语言。

可调开关都在文件顶部：

| 常量 | 作用 |
| --- | --- |
| `DEFAULT_THEME` | 启动时的主题，`dark` / `light` |
| `ENABLE_PER_MONITOR_DPI` | 关掉则退回系统默认 DPI 行为 |
| `DARK` / `LIGHT` | 两套配色，键名一一对应 |

亮色下 `surface` 是纯白 `#ffffff`、`bg` 是 `#f3f3f3`（Win11 Mica 亮色底），
按钮的按下/禁用/悬停色也在同一字典里（`pressed` / `disabled_bg` / `active_border`），
改配色只需要动这两个字典。

已知限制：日志框不能用 `scrolledtext.ScrolledText`，它自带的是原生 `tk.Scrollbar`，
Windows 用系统主题绘制、不理会 Tk 配色，深色下会露出一条白条。现已改为 `tk.Text` + `ttk.Scrollbar`。

第二个深色主题的坑：**`ttk.Combobox` 必须单独配色**。它是 readonly 状态，文字画在
`fieldbackground` 上，而 clam 主题的默认 field 是白色 —— 配上浅色文字就是"白底白字"，
看起来像一个空白方块。除了 `st.configure("TCombobox")` / `st.map("TCombobox")`，
下拉列表本身（Tcl 内部创建的 Listbox）还得用 `tk.call` 直接设置背景色，因为 ttk 样式管不到它。

## 重新打包

源码与打包配置归档在：`E:\workbuddy\shell\av1_converter\`

- 双击 `build.bat` 一键重新生成 `dist/av1_batch_converter.exe`
- 依赖专用 venv：`C:\Users\Administrator\.workbuddy\binaries\python\envs\av1_converter_sys`
  （需安装 `pyinstaller`、`tkinterdnd2`、`pywinstyles`，tkdnd 资源由 spec 的 datas 打包进去）
- 产物生成后手动替换 `C:\Users\Administrator\Documents\shell\av1_batch_converter.exe`

自检脚本（都不真正转换视频）：

| 脚本 | 验证对象 | 产物 |
| --- | --- | --- |
| `_screenshot_check.py` | 源码版外观：逐个控件采样颜色 + 模拟悬浮验证 tooltip + 点击主题按钮再采样 | `_shot_dark_initial.png` / `_shot_tooltip.png` / `_shot_dark_toggled.png` |
| `_verify_exe.py` | 打包版外观：真实启动进程 → 截图 → 找主题按钮并真点击 → 对比切换前后 | `_shot_exe_dark.png` / `_shot_exe_light.png` |
| `_enc_check.py` | 设备检测与下拉框：探测结果、默认选择、置灰颜色、**模拟真实点击验证灰色项点不动** | `_shot_dropdown.png` |
| `_enc_shots.py` | 布局：宽窗口 / 最小窗口 / 亮色三种状态截图 + 控件是否溢出 | `_shot_enc_wide.png` / `_shot_enc_narrow.png` / `_shot_enc_light.png` |
| `_verify_exe_enc.py` | 打包版里的 Encoder 控件：启动 exe → 扫描界面文字分布 → 右上角打 ASCII 图确认渲染正常 | `_shot_exe_enc.png` |
| `_i18n_check.py` | 源码版三语：三语下逐个控件取文字、三语唯一性、语言按钮在主题按钮左侧、编码参数是否写进日志、切换加速器是否重打 | `_shot_i18n_lang_zh.png` / `_lang_ja.png` / `_lang_en.png` / `_encoder_switched.png` / `_narrow.png` |
| `_i18n_layout.py` | 三语 × 三档窗口尺寸（900 / 700 / 620 宽）下控件是否溢出或被裁 | 无（纯文本报告） |
| `_verify_exe_i18n.py` | 打包版三语：启动 exe → 扫描头部找两个图标按钮 → 真实点击三次 → 用**墨迹签名**判断界面确实换过语言且第三次点回原语言 | `_shot_exe_i18n_1_start.png` / `_lang_click1~3.png` / `_theme_toggled.png` |
| `_exe_focus_diag.py` | 诊断脚本：每次点击后查进程是否存活、窗口句柄、前台窗口是谁（用来定位"截图抓错窗口"） | 无（纯文本报告） |
| `_quiet_toggle_check.py` | **不占屏幕**的验证：窗口 `withdraw()` 后直接调方法切主题/语言 ×N，断言日志一行没长、按钮确实生效、死字符串已清空 | 无（纯文本报告） |
| `_dpi_check.py` | DPI 缩放：窗口 `withdraw()` 后依次按 96 / 144 / 96 驱动 `apply_dpi_scaling`，断言正文字体、标题字体、图标、按钮 padding、窗口尺寸都跟着变，且状态（文件列表/并发/日志/编码器选择）在重建后保留 | 无（纯文本报告） |
| `_verify_exe_release.py` | 发布前验收：读 PE 里的版本资源、启动 exe、**PrintWindow** 抓客户区、与上一版已验收截图做墨迹签名比对 | `_shot_release_capture.png` |
| `_make_docs_shots.py` | 生成 README 用的截图：源码进程内直接调 `_toggle_theme()` 切亮/暗，PrintWindow 抓图，并与 exe 的抓图做比对确保两边渲染一致 | `docs/screenshot-dark.png` / `docs/screenshot-light.png` |
| `_shot_exe_themes.py` | 尝试用投递窗口消息（`PostMessage`）点主题按钮抓 exe 的亮色截图。**结论：Tk 会忽略非前台窗口的投递鼠标消息**，此路不通，保留作为记录 | 无 |

改动配色后跑 `_screenshot_check.py`，改完打包再跑 `_verify_exe.py`、`_verify_exe_enc.py` 和 `_verify_exe_i18n.py`。
只是改文案/日志这类**不动布局**的改动，跑 `_quiet_toggle_check.py` 就够了，不必惊动屏幕。
发布前跑 `_verify_exe_release.py`，要重出 README 截图跑 `_make_docs_shots.py`。

### 截图但不打扰用户：PrintWindow + WS_EX_NOACTIVATE

要验证界面又不想打断用户，两个关键点：

- **抓图用 `PrintWindow(hwnd, hdc, 2)`（`PW_RENDERFULLCONTENT`）**，它能渲染被遮挡的窗口，所以既不需要把窗口翻到前台，也不需要 `ImageGrab` 抓屏幕。窗口本身照样会出现在屏幕上，但**不抢焦点**。
- **建窗口后立刻给外层窗口加 `WS_EX_NOACTIVATE`**，窗口出现时就不会把用户正在用的程序挤到后台。

```python
hwnd = find_by_title(require_visible=False)      # 见下
ex = user32.GetWindowLongW(hwnd, -20)            # GWL_EXSTYLE
user32.SetWindowLongW(hwnd, -20, ex | 0x08000000)   # WS_EX_NOACTIVATE
```

两个容易踩的坑：

- **别用 `root.winfo_id()` + `GetParent()` 找窗口**。Tk 的顶层窗口外面还套了一层，`GetParent` 拿到的是 Tk 自己的 wrapper，它没有标题栏、`GetWindowRect` 返回的是客户区尺寸。带标题栏的那个窗口只能靠 `EnumWindows` + 标题匹配找。
- **`PostMessage(WM_LBUTTONDOWN/UP)` 点不动 Tk 控件**。消息能投递成功（返回 1），但 Tk 只处理前台窗口的鼠标消息，非前台时会被忽略。所以"点一下按钮看效果"这类验证要么把窗口切到前台（会打扰用户），要么**直接调方法**（推荐）。真要走点击路径时，只能像 `_verify_exe_i18n.py` 那样前台 + `SetCursorPos`，那就得接受鼠标会被抢走。

> 窗口坐标换算：`GetWindowRect` 是含边框的整窗，`ClientToScreen(hwnd, (0,0))` 减掉 `GetWindowRect` 左上角才是客户区偏移。本机 100% 缩放下是 `(8, 31)`，客户区 900×650 对应整窗 916×689。

> **为什么要有 `_enc_check.py` 的点击测试**：ttk 的 Combobox 是在 `ButtonRelease-1`
> 时才提交选择的（见 `ttk::combobox::Release`）。只拦截 `Button-1` 的话，按下被挡住了，
> 松开仍然会选中灰色项 —— 必须拦 `ButtonRelease-1`。

> `_verify_exe.py` 里有个坑：Pillow 的 `ImageGrab.grab(bbox=..., all_screens=True)`
> 的坐标是相对**主屏**而非虚拟屏，多显示器下会裁到别的屏幕去，采出来的颜色全是桌面内容。
> 正确做法是全屏抓一张再用 `SM_XVIRTUALSCREEN` 手动 crop。

> **截图验证 exe 时最大的坑：别的窗口会抢前台。** 给打包程序做自动化截图时，只要有一次点击
> 落在被测窗口之外，WorkBuddy 自己的窗口（`Chrome_WidgetWin_1`）就会抢到前台并**盖住被测窗口
> 的矩形区域** —— 之后每一张 `ImageGrab` 抓到的都是 WorkBuddy 的界面，而不是被测程序。
> 表现为「点着点着程序好像没了」，但进程其实活得好好的（`_exe_focus_diag.py` 就是用来确认
> 这一点的）。两条对策缺一不可：
> 1. 截图前 `SetWindowPos(hwnd, HWND_TOPMOST, ...)` 把被测窗口钉在最上层
> 2. 每次点击前 `SetForegroundWindow` 并**断言 `GetForegroundWindow() == hwnd`**，不成立就别点
>
> 另外验证脚本自己也要 `SetProcessDpiAwareness(2)`：被测程序是 DPI 感知的，用真实像素；
> 验证脚本若不感知，拿到的是被系统虚拟化过的坐标，150% 缩放的屏幕上每次点击都会偏。

> ⚠️ **让脚本真的去点按钮 = 抢用户的鼠标。** 这类"真实点击"验证会 `SetCursorPos` 挪走光标、
> 再把窗口钉成 topmost，用户正在用电脑时表现就是"鼠标自己飞走了"。所以：
> - 能用**直接调用方法**（`app._toggle_language()`）验证的，就不要用合成鼠标事件
> - 只有"点击路径本身"才是被测对象时才需要真的点（例如 Combobox 置灰项的点击拦截）
> - 验证窗口可以 `root.withdraw()` 后跑，完全不占屏幕：见 `_quiet_toggle_check.py`
> - 真的必须弹窗时，先问一句用户方不方便，别默默抢

> ⚠️ **PyInstaller onefile 的 `proc.terminate()` 杀不干净。** 用 `subprocess.Popen([EXE])`
> 启动 onefile 产物时，拿到的是**引导器父进程**，真正的程序是它 spawn 的子进程；
> 只 terminate 父进程有时会留下子进程继续运行。后果是文件被占用，下次 `cp` 覆盖直接
> `Device or resource busy`。收尾要么等久一点确认窗口真的消失，要么
> `MSYS2_ARG_CONV_EXCL='*' taskkill /F /T /IM av1_batch_converter.exe` 整棵树一起收。

> **别用"变化像素占总像素的比例"判断文字有没有变。** 界面文字是稀疏的：整块按钮横条
> 90% 以上是空的背景色，换一整个语言也只改动了 7% 的采样点，信号完全被背景淹没
> （实测三语两两之间的比例只有 0.05~0.08，和"没变"几乎分不开）。
> 改成**墨迹签名**：按列统计"偏离背景色的像素数"，归一化成分布，再算 L1/2 距离
> （0 = 完全相同，1 = 完全不重叠）。同一招实测能把换语言拉到 0.43~0.72，
> 而"点回原语言"仍然是 0.000 —— 阈值一下就有意义了。
> 同理，`log_box` 里写着编码参数的那几行**不随语言变**，测量时必须把它排除掉，
> 否则它会稀释信号。
