@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ============================================
echo   HC-Note 待办事项 - 打包单文件 EXE
echo ============================================
echo.

rem 定位 Python 解释器
if exist "%ROOT%.build\venv\Scripts\python.exe" (
    set "PY=%ROOT%.build\venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if not %errorlevel%==0 (
        echo [错误] 未找到 Python 解释器，请先安装 Python 3.10+。
        pause
        exit /b 1
    )
    set "PY=python"
)

echo 使用解释器： %PY%
echo.

echo [1/3] 检查并安装打包依赖...
"%PY%" -m pip install --no-warn-script-location --retries 8 --timeout 60 pyinstaller
if %errorlevel% neq 0 (
    echo.
    echo [错误] PyInstaller 安装失败，请检查网络后重试。
    echo        如已安装，可忽略此提示继续观察后续输出。
    echo.
)

echo [2/3] 清理旧的构建产物...
if exist "%ROOT%build" rmdir /s /q "%ROOT%build"
if exist "%ROOT%dist" rmdir /s /q "%ROOT%dist"

echo [3/3] 开始打包...
echo.
"%PY%" -m PyInstaller --noconfirm --clean "%ROOT%HC-Note.spec"

if not exist "%ROOT%dist\HC-Note.exe" (
    echo.
    echo [错误] 打包失败，请查看上方日志。
    pause
    exit /b 1
)

echo.
echo ============================================
echo   打包完成
echo ============================================
echo   产物： %ROOT%dist\HC-Note.exe
echo.
echo   注意： 首次运行前请确认已安装 Edge WebView2 Runtime。
echo          将 dist 目录下的 HC-Note.exe 复制到任意位置即可便携使用，
echo          程序会在其同级目录自动创建 data 文件夹存放数据。
echo.
pause

endlocal
