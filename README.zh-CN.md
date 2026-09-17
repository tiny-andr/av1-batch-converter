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
- `PATH` 中有 [ffmpeg](https://ffmpeg.org/download.html)
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
pyinstaller av1_batch_converter.spec --noconfirm --distpath dist --workpath build
```

`build.bat` ，产物是 `dist\av1_batch_converter.exe`。

## 许可证

[MIT](LICENSE)
