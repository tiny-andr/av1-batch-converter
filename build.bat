@echo off
chcp 65001 >nul
setlocal

rem Rebuild av1_batch_converter.exe with PyInstaller (dedicated venv)
set "VENV=C:\Users\Administrator\.workbuddy\binaries\python\envs\av1_converter_sys"
set "PYI=%VENV%\Scripts\pyinstaller.exe"

if not exist "%PYI%" (
  echo [ERROR] pyinstaller not found: %PYI%
  echo Install it first:  "%VENV%\Scripts\python.exe" -m pip install pyinstaller tkinterdnd2
  pause
  exit /b 1
)

pushd "%~dp0"
echo Building av1_batch_converter.exe ...
"%PYI%" av1_batch_converter.spec --noconfirm --distpath dist --workpath build

if errorlevel 1 (
  echo [ERROR] build failed
) else (
  echo [OK] output: %~dp0dist\av1_batch_converter.exe
)
popd
pause
