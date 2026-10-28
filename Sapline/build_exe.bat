@echo off
cd /d "%~dp0"
echo Building Sapline.exe. This takes 2 to 5 minutes. Keep this window open.
echo.
echo Step 1 of 2: tools
py -3.13 -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
echo.
echo Step 2 of 2: building and putting Sapline.exe in this folder
py -3.13 build_app.py
if errorlevel 1 goto failed
echo.
pause
exit /b 0
:failed
echo.
echo The build did not finish. Copy the text above and send it to Claude.
pause
exit /b 1
