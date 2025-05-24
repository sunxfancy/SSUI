@echo off
@setlocal enabledelayedexpansion

rem Create .build folder and put Python in it
if not exist ".venv" mkdir .venv

rem Check if Python already exists
if not exist ".venv\python\python.exe" (
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
        exit /b
    )

    rem Set download URLs
    set DOWNLOAD_URL=https://github.com/astral-sh/python-build-standalone/releases/download/!RELEASE_DATE!/cpython-!PYTHON_VERSION!+!RELEASE_DATE!-!ARCH!-install_only_stripped.tar.gz
    set CHINA_MIRROR=https://gitee.com/Swordtooth/ssui_assets/releases/download/v0.0.2/cpython-!PYTHON_VERSION!%!RELEASE_DATE!-!ARCH!-install_only_stripped.tar.gz

    rem Try to download Python from GitHub
    echo "Trying to download Python from GitHub..."
    curl -L !DOWNLOAD_URL! -o .venv\python.tar.gz
    if errorlevel 1 (
        echo "GitHub download failed, trying China mirror..."
        curl -L !CHINA_MIRROR! -o .venv\python.tar.gz
        if errorlevel 1 (
            echo "Both downloads failed. Please check your internet connection."
            exit /b 1
        )
    )

    powershell -Command "cd .venv; tar -xvzf python.tar.gz"
    powershell -Command "Remove-Item -Path '.venv\python.tar.gz' -Force"
)

rem Check if virtual environment already exists
if not exist ".venv\Scripts\python.exe" (
    rem Create virtual environment using venv
    echo "Creating virtual environment..."
    .venv\python\python.exe -m venv .venv
)

if not exist ".venv\Scripts\uv.exe" (
    echo "Install uv tool..."
    .venv\python\python.exe -m pip install uv==0.6.11
)
