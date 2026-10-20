@echo off
cd /d "%~dp0"
echo Building MapleReader.exe. This takes 2 to 5 minutes. Keep this window open.
echo.
echo Step 1 of 3: tools
py -3.13 -m pip install --upgrade pyinstaller mss pillow pytesseract
if errorlevel 1 goto failed
echo.
echo Step 2 of 3: building
py -3.13 -m PyInstaller --noconfirm --clean --windowed --name MapleReader --icon "%~dp0shopreader\icon.ico" --add-data "%~dp0shopreader\icon.png;shopreader" --add-data "%~dp0shopreader\icon.ico;shopreader" --add-data "%~dp0shopreader\market.html;shopreader" --workpath build_tmp --distpath build_tmp\dist --specpath build_tmp "%~dp0app.py"
if errorlevel 1 goto failed
echo.
echo Step 3 of 3: putting MapleReader.exe in this folder
if exist _internal rmdir /s /q _internal
xcopy /e /i /y /q build_tmp\dist\MapleReader . >nul
if errorlevel 1 goto failed
rmdir /s /q build_tmp
echo.
echo Done. Double-click MapleReader.exe to start. Keep the _internal folder next to it.
pause
exit /b 0
:failed
echo.
echo The build did not finish. Copy the text above and send it to Claude.
pause
exit /b 1
