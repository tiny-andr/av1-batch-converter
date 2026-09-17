@echo off
chcp 65001 >nul
setlocal

rem Rebuild av1_batch_converter.exe with PyInstaller (dedicated venv).
rem Fetches and hash-verifies the pinned ffmpeg build first, because the exe
rem carries ffmpeg inside it and the spec refuses to build without it.
set "VENV=C:\Users\Administrator\.workbuddy\binaries\python\envs\av1_converter_sys"
set "PYI=%VENV%\Scripts\pyinstaller.exe"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PYI%" (
  echo [ERROR] pyinstaller not found: %PYI%
  echo Install it first:  "%VENV%\Scripts\python.exe" -m pip install pyinstaller tkinterdnd2 pywinstyles
  pause
  exit /b 1
)

pushd "%~dp0"

echo [1/2] Checking for the bundled ffmpeg ...
"%PY%" "vendor\fetch_ffmpeg.py"
if errorlevel 1 (
  echo [ERROR] could not obtain vendor\ffmpeg\ffmpeg.exe
  popd
  pause
  exit /b 1
)

echo.
echo [2/2] Building av1_batch_converter.exe ...
"%PYI%" av1_batch_converter.spec --noconfirm --distpath dist --workpath build

if errorlevel 1 (
  echo [ERROR] build failed
) else (
  echo [OK] output: %~dp0dist\av1_batch_converter.exe
)
popd
pause
