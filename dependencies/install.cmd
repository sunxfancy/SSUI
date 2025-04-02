@echo off

rem 创建.build文件夹并将Python放入其中
if not exist ".venv" mkdir .venv

rem 检查Python是否已经存在
if not exist ".venv\python\python.exe" (
    rem 检查操作系统类型
    set OS_TYPE=%OS%
    set ARCHITECTURE=%PROCESSOR_ARCHITECTURE%
    set PYTHON_VERSION=3.12.8
    set RELEASE_DATE=20241219

    rem 检查系统是Windows
    if /I "%OS_TYPE%" neq "Windows_NT" (
        echo Unsupported OS!
        exit /b
    )

    rem 检查处理器架构
    if /I "%ARCHITECTURE%"=="x86" (
        set ARCH=i686-pc-windows-msvc
    ) else if /I "%ARCHITECTURE%"=="AMD64" (
        set ARCH=x86_64-pc-windows-msvc
    ) else (
        echo Unsupported architecture!
        exit /b
    )

    rem 设置下载链接
    set DOWNLOAD_URL=https://github.com/astral-sh/python-build-standalone/releases/download/%RELEASE_DATE%/cpython-%PYTHON_VERSION%+%RELEASE_DATE%-%ARCH%-install_only_stripped.tar.gz

    rem 下载并解压Python
    echo "Downloading Python from %DOWNLOAD_URL%..."
    curl -L %DOWNLOAD_URL% -o .venv\python.tar.gz

    powershell -Command "cd .venv; tar -xvzf python.tar.gz"
    powershell -Command "Remove-Item -Path '.venv\python.tar.gz' -Force"
)

rem 检查虚拟环境是否已经存在
if not exist ".venv\Scripts\python.exe" (
    rem 使用virtualenv创建虚拟环境
    echo "Creating virtual environment..."
    .venv\python\python.exe -m venv .venv
)

if not exist ".venv\Scripts\uv.exe" (
    echo "Install uv tool..."
    .venv\python\python.exe -m pip install uv
)
