@echo off
@setlocal enabledelayedexpansion
if not defined SSUI_VENV_PATH set "SSUI_VENV_PATH=%CD%\.venv"

rem Create .build folder and put Python in it
if not exist "%SSUI_VENV_PATH%" mkdir "%SSUI_VENV_PATH%"

rem Check if Python already exists
if not exist "%SSUI_VENV_PATH%\Scripts\python.exe" if not exist "%SSUI_VENV_PATH%\python\python.exe" (
    rem Check operating system type
    set PYTHON_VERSION=3.12.8
    set RELEASE_DATE=20241219

    rem Check processor architecture
    if /I "!PROCESSOR_ARCHITECTURE!"=="x86" (
        set ARCH=i686-pc-windows-msvc
    ) else if /I "!PROCESSOR_ARCHITECTURE!"=="AMD64" (
        set ARCH=x86_64-pc-windows-msvc
    ) else (
        echo Unsupported architecture!
        exit /b 1
    )

    rem Set download URLs
    set DOWNLOAD_URL=https://github.com/astral-sh/python-build-standalone/releases/download/!RELEASE_DATE!/cpython-!PYTHON_VERSION!+!RELEASE_DATE!-!ARCH!-install_only_stripped.tar.gz
    set CHINA_MIRROR=https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-!PYTHON_VERSION!%!RELEASE_DATE!-!ARCH!-install_only_stripped.tar.gz

    rem Try to download Python from GitHub
    echo "Trying to download Python from GitHub..."
    curl  --ssl-revoke-best-effort -L !DOWNLOAD_URL! -o "%SSUI_VENV_PATH%\python.tar.gz"
    if errorlevel 1 (
        echo "GitHub download failed, trying China mirror..."
        curl  --ssl-revoke-best-effort -L !CHINA_MIRROR! -o "%SSUI_VENV_PATH%\python.tar.gz"
        if errorlevel 1 (
            echo "Both downloads failed. Please check your internet connection."
            exit /b 1
        )
    )

    tar -xzf "%SSUI_VENV_PATH%\python.tar.gz" -C "%SSUI_VENV_PATH%"
    if errorlevel 1 exit /b 1
    del "%SSUI_VENV_PATH%\python.tar.gz"
)

rem Check if virtual environment already exists
if not exist "%SSUI_VENV_PATH%\Scripts\python.exe" (
    rem Create virtual environment using venv
    echo "Creating virtual environment..."
    "%SSUI_VENV_PATH%\python\python.exe" -m venv "%SSUI_VENV_PATH%"
    if errorlevel 1 exit /b 1
)

if not exist "%SSUI_VENV_PATH%\Scripts\uv.exe" (
    echo "Install uv tool..."
    "%SSUI_VENV_PATH%\Scripts\python.exe" -m pip install uv==0.6.11 packaging==24.1
)
