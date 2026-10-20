@echo off
cd /d "%~dp0"
echo Checking the reader against the saved test pictures. This takes a few minutes.
set FAILED=0
echo.
py -3.13 tests\test_pictures.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_session.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_scroll.py
if errorlevel 1 set FAILED=1
echo.
py -3.13 tests\test_market.py
if errorlevel 1 set FAILED=1
echo.
if "%FAILED%"=="0" (echo Everything passed.) else (echo Something failed - send Claude the text above.)
pause
