@echo off
chcp 65001 >nul
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo ============================================
echo   HC-Note 待办事项 - 源码运行
echo ============================================
echo.

rem 优先使用项目内置虚拟环境
if exist "%ROOT%.build\venv\Scripts\python.exe" (
    set "PY=%ROOT%.build\venv\Scripts\python.exe"
    goto :run
)

rem 回退到系统 Python
where python >nul 2>nul
if %errorlevel%==0 (
    set "PY=python"
    goto :check
)

echo [错误] 未找到 Python 解释器。
echo 请先安装 Python 3.10 或更高版本： https://www.python.org/downloads/
echo.
pause
exit /b 1

:check
echo [提示] 未检测到项目虚拟环境，将使用系统 Python。
echo        首次运行请先执行： pip install -r requirements.txt
echo.

:run
echo 使用解释器： %PY%
echo 启动中，请稍候...
echo.
"%PY%" "%ROOT%src\backend\app.py"

if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，退出码 %errorlevel%
    pause
)

endlocal
