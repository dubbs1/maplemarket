@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a screenshot file onto test.bat to test it.
) else (
  py -3.13 maple_shop_reader.py --image "%~1"
)
pause
