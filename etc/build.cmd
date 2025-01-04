@echo off
REM ----------------------------------------------
REM build.cmd
REM ----------------------------------------------
REM 功能: 将多个目录打包到同一个 ZIP 文件，但忽略部分子目录或文件
REM 注意: 需要 Windows 10 及以上版本，以使用 Compress-Archive。
REM ----------------------------------------------

::========= 配置部分 ==============
:: 1. 指定输出 ZIP 文件
set "ZIP_PATH=C:\temp\myarchive.zip"

:: 2. 列举需要压缩的根目录（用逗号或空格都可以，这里演示逗号）
set "SOURCE_DIRS=C:\temp\dir1,C:\temp\dir2,C:\temp\dir3"

:: 3. 需要忽略的子目录或文件，这里演示忽略 dir1\logs、dir2\temp
::   可以使用 -notmatch 'C:\\temp\\dir1\\logs' 这样的方式排除
::   或者单纯用目录名匹配（注意有无子字符串冲突），自行酌情处理
set "EXCLUDE_PATTERNS=($_.FullName -notmatch 'C:\\temp\\dir1\\logs') -and ($_.FullName -notmatch 'C:\\temp\\dir2\\temp')"

echo ----------------------------------------------
echo [ZIP 输出文件]:  %ZIP_PATH%
echo [要打包的目录]:  %SOURCE_DIRS%
echo [忽略条件]:      %EXCLUDE_PATTERNS%
echo ----------------------------------------------
echo.

::========= 如果已存在旧的压缩文件，则先删除 =========
if exist "%ZIP_PATH%" (
    echo 检测到已有旧的压缩文件，正在删除...
    del /f /q "%ZIP_PATH%"
    echo.
)

::========= 调用 PowerShell：先用 Get-ChildItem 收集文件，再用 Compress-Archive 压缩 =========
:: 说明:
::  1. Get-ChildItem -Path 支持同时指定多个目录，逗号分隔
::  2. -Recurse 递归子目录
::  3. -File 只获取文件（如果你需要打包空文件夹，可以去掉 -File）
::  4. Where-Object 里我们用 -notmatch 来过滤不想要的路径
::  5. Compress-Archive 最后打包到指定 ZIP
echo 正在执行压缩操作...
powershell -NoLogo -Command ^
    "Get-ChildItem -Path '%SOURCE_DIRS%' -Recurse -File | ^ 
     Where-Object { %EXCLUDE_PATTERNS% } | ^
     Compress-Archive -DestinationPath '%ZIP_PATH%'"

echo.
echo ----------------------------------------------
echo 压缩完成，打包文件位置:
echo   %ZIP_PATH%
echo ----------------------------------------------