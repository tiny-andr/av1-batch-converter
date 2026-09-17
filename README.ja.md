# AV1 Batch Converter

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

動画をまとめて AV1 に変換する Windows 用の小さなツールです。

![AV1 Batch Converter ダークテーマ](docs/screenshot-dark-ja.png)

## 機能

- **バッチ キュー** —— フォルダ追加、ファイル追加、ドラッグ＆ドロップ、`list.txt` の読み込み
- **アクセラレーター自動検出** —— NVIDIA / AMD / Intel / CPU を起動時に実測
- **並列変換** —— 同時 1〜16 ファイル

## 動作環境

- Windows 10 または 11
- ffmpeg は exe に同梱済みなので、別途インストールは不要
  （exe の隣の `ffmpeg\` か `PATH` にあるものを優先して使います）
- ハードウェア アクセラレーションを使う場合は ffmpeg が扱える GPU
  （AV1 エンコードには新しいカードが必要: RTX 40 シリーズ、RX 7000 シリーズ、Arc 以降）

### 出力

各ファイルは元ファイルの隣に `<元の名前>.mp4`（AV1 / MP4 コンテナ）として出力され、
**元ファイルは削除されます**。変換は一時ファイル経由なので、途中で失敗しても元ファイルは残ります。

## ソースからビルド

`av1_batch_converter.pyw` がプログラム全体です —— Python + tkinter で、
`pywinstyles`（任意、タイトルバーのテーマ用）と `tkinterdnd2`（ドラッグ＆ドロップ用）
以外に実行時依存はありません。

```bat
python -m pip install pyinstaller tkinterdnd2 pywinstyles
python vendor\fetch_ffmpeg.py
pyinstaller av1_batch_converter.spec --noconfirm --distpath dist --workpath build
```

`build.bat` でも同じことができます（先に ffmpeg を自動ダウンロードして検証します）。
生成物は `dist\av1_batch_converter.exe` です。

## ライセンス

[MIT](LICENSE)。同梱の ffmpeg は **GPLv3**（© FFmpeg developers）で、exe と一緒に配布されます。
