@echo off
cd /d "%~dp0"
echo Checking the EXP reader against the saved test pictures. This takes a minute or two.
set FAILED=0
echo.
py -3.13 tests\test_exp.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_mobpics.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_server.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_update.py
if errorlevel 1 set FAILED=1
echo.
if "%FAILED%"=="0" (echo Everything passed.) else (echo Something failed - send Claude the text above.)
pause
