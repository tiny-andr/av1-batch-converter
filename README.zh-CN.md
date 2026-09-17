# AV1 Batch Converter

[English](README.md) | **简体中文** | [日本語](README.ja.md)

一个用来把视频批量转成 AV1 的 Windows 小工具。

![AV1 Batch Converter 深色主题](docs/screenshot-dark-zh.png)

## 功能

- **批量队列** —— 添加文件夹、添加文件、拖放，或者载入 `list.txt`
- **自动检测加速设备** —— NVIDIA / AMD / Intel / CPU，启动时实测
- **并发转换** —— 一次 1 到 16 个文件

## 运行要求

- Windows 10 或 11
- ffmpeg 已内置在 exe 里，不用另外装
  （exe 旁边的 `ffmpeg\` 或 `PATH` 上的版本会优先使用）
- 想用硬件加速的话，需要一块 ffmpeg 能驱动的显卡
  （AV1 编码要求较新的卡：RTX 40 系、RX 7000 系、Arc 或更新）

### 输出

每个文件输出到源文件旁边，命名为 `<原名>.mp4`（AV1 封装进 MP4），并且**会删除原文件**。
转换走临时文件，所以中途失败不会动你的源文件。

## 从源码构建

`av1_batch_converter.pyw` 就是整个程序 —— Python + tkinter，除了 `pywinstyles`
（可选，用于标题栏主题）和 `tkinterdnd2`（拖放）之外没有别的运行时依赖。

```bat
python -m pip install pyinstaller tkinterdnd2 pywinstyles
python vendor\fetch_ffmpeg.py
pyinstaller av1_batch_converter.spec --noconfirm --distpath dist --workpath build
```

也可以直接跑 `build.bat`（会先自动下载并校验 ffmpeg），产物是 `dist\av1_batch_converter.exe`。

## 许可证

[MIT](LICENSE)。内置的 ffmpeg 是 **GPLv3**（© FFmpeg developers），随 exe 一起分发。
