@echo off
cd /d "%~dp0"
echo Opening the live market in your browser. Keep this window open while you use it.
py -3.13 -m shopreader.market_server
pause
