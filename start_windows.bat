@echo off
setlocal
cd /d "%~dp0"

rem This launcher uses ASCII text and Windows CRLF line endings for cmd.exe.
where py.exe >nul 2>&1
if errorlevel 1 goto use_python

py -3 main.py
set "GAME_EXIT=%errorlevel%"
goto finished

:use_python
where python.exe >nul 2>&1
if errorlevel 1 goto no_python

python main.py
set "GAME_EXIT=%errorlevel%"
goto finished

:no_python
echo Python was not found.
echo Install Python 3.10 or newer and select "Add Python to PATH".
set "GAME_EXIT=9009"

:finished
if "%GAME_EXIT%"=="0" goto normal_exit
echo.
echo The game stopped with error code %GAME_EXIT%.
echo Please send a screenshot of the error shown above.
echo You can also run: py -3 check_environment.py
goto hold_window

:normal_exit
echo.
echo The game window has closed normally.

:hold_window
echo Press any key to close this window.
pause >nul
exit /b %GAME_EXIT%
